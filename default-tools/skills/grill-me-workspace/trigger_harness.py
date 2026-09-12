#!/usr/bin/env python3
"""Measure whether a real installed skill triggers on a set of queries.

Written because skill-creator's run_eval.py scores a run as "not triggered" the
moment the model calls any tool other than Skill/Read (run_eval.py:137-141), and
exposes the skill as a slash command rather than a skill. Both make it unusable
for a skill whose trigger surface is "user references a plan document".

This harness loads the plugin with `claude --plugin-dir` (session-scoped, so no
plugin-cache mutation), scans the entire stream, and counts a trigger only on a
real Skill tool_use naming the target skill.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run_one(query, run_idx, args):
    """Return (triggered: bool, tools: list[str], raw_path: Path)."""
    cmd = [
        "claude", "-p", query,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--plugin-dir", args.plugin_dir,
    ]
    if args.model:
        cmd += ["--model", args.model]

    # CLAUDECODE is set inside a Claude Code session and blocks nesting; the
    # guard exists for interactive terminal conflicts, not subprocess use.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    raw_dir = Path(args.out) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{abs(hash(query)) % 10**8}-run{run_idx}.jsonl"

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=args.cwd, env=env,
    )
    triggered, tools = False, []
    start = time.time()
    with open(raw_path, "w", encoding="utf-8") as raw:
        try:
            for line in proc.stdout:
                text = line.decode("utf-8", errors="replace")
                raw.write(text)
                if time.time() - start > args.timeout:
                    break
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    continue

                # Completed assistant messages carry the authoritative tool_use
                # blocks; partial stream_events are only used to exit early.
                if event.get("type") == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") != "tool_use":
                            continue
                        name = block.get("name", "")
                        tools.append(name)
                        if name == "Skill":
                            skill = str(block.get("input", {}).get("skill", ""))
                            if args.skill_name in skill:
                                triggered = True
                elif event.get("type") == "stream_event":
                    se = event.get("event", {})
                    if se.get("type") == "content_block_start":
                        cb = se.get("content_block", {})
                        if cb.get("type") == "tool_use" and cb.get("name") == "Skill":
                            pass  # input arrives in deltas; assistant event confirms

                if triggered:
                    break  # detection is terminal; stop paying for the rest
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
    return triggered, tools, raw_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--eval-set", required=True)
    p.add_argument("--plugin-dir", required=True)
    p.add_argument("--skill-name", required=True, help="substring matched against Skill input.skill")
    p.add_argument("--cwd", required=True, help="working dir for claude -p runs")
    p.add_argument("--out", required=True)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--model", default=None)
    args = p.parse_args()

    evals = json.load(open(args.eval_set, encoding="utf-8"))
    jobs = [(e, i) for e in evals for i in range(args.runs)]
    results = {}

    def work(job):
        e, i = job
        trig, tools, raw = run_one(e["query"], i, args)
        print(f"  {'TRIG' if trig else '----'} run{i} [{','.join(tools[:4]) or 'no-tools'}] {e['query'][:60]}",
              file=sys.stderr, flush=True)
        return e["query"], e["should_trigger"], trig, tools

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for query, should, trig, tools in pool.map(work, jobs):
            r = results.setdefault(query, {"should_trigger": should, "triggers": 0,
                                           "runs": 0, "tools": []})
            r["triggers"] += int(trig)
            r["runs"] += 1
            r["tools"] += tools

    rows = []
    for query, r in results.items():
        rate = r["triggers"] / r["runs"] if r["runs"] else 0.0
        rows.append({
            "query": query,
            "should_trigger": r["should_trigger"],
            "trigger_rate": round(rate, 3),
            "triggers": r["triggers"],
            "runs": r["runs"],
            # >=0.5 of runs triggering counts as "triggers" for pass/fail
            "pass": (rate >= 0.5) == r["should_trigger"],
            "tools_seen": sorted(set(r["tools"])),
        })
    rows.sort(key=lambda x: (not x["should_trigger"], -x["trigger_rate"]))
    pos = [r for r in rows if r["should_trigger"]]
    neg = [r for r in rows if not r["should_trigger"]]
    out = {
        "skill_name": args.skill_name,
        "model": args.model,
        "runs_per_query": args.runs,
        "results": rows,
        "summary": {
            "passed": sum(r["pass"] for r in rows),
            "total": len(rows),
            "recall_positives": round(sum(r["pass"] for r in pos) / len(pos), 3) if pos else None,
            "specificity_negatives": round(sum(r["pass"] for r in neg) / len(neg), 3) if neg else None,
            "mean_rate_positives": round(sum(r["trigger_rate"] for r in pos) / len(pos), 3) if pos else None,
            "mean_rate_negatives": round(sum(r["trigger_rate"] for r in neg) / len(neg), 3) if neg else None,
        },
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
