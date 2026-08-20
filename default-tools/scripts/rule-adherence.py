#!/usr/bin/env python3
"""Per-rule adherence counts for CLAUDE.md rules, measured over Claude Code transcripts.

Answers, for each rule: how often did its trigger appear, and when it did, was the
rule followed? Rules with zero triggers are dead weight; rules with a high violation
rate need to become hooks.

Shipped as the default-tools plugin command /default-tools:rule-adherence.

Usage:
  rule-adherence.py                          # last 30 days, all projects
  rule-adherence.py --selftest                # assert every detector still fires
  rule-adherence.py --since 2026-06-01
  rule-adherence.py --project jsma            # substring match on the project dir
  rule-adherence.py --examples 3              # show offending excerpts per rule
  rule-adherence.py --since A --until B       # closed window, for before/after
  rule-adherence.py --json report.json
  rule-adherence.py --candidates cand.jsonl   # dump ambiguous cases for an LLM grader
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict

TRANSCRIPT_ROOT = os.path.expanduser("~/.claude/projects")

FOLLOWED, VIOLATED, SUSPECT = "followed", "violated", "suspect"

# ---------------------------------------------------------------------------
# event extraction
# ---------------------------------------------------------------------------


class Event:
    __slots__ = ("i", "kind", "name", "input", "text", "is_error", "tool_use_id",
                 "ts", "branch", "cwd", "sidechain")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def cmd(self):
        return (self.input or {}).get("command", "") or ""


def load_events(path):
    """Flatten one transcript into an ordered event list."""
    events = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rtype = rec.get("type")
            if rtype not in ("assistant", "user"):
                continue
            common = dict(
                ts=rec.get("timestamp"),
                branch=rec.get("gitBranch"),
                cwd=rec.get("cwd"),
                sidechain=bool(rec.get("isSidechain")),
            )
            content = (rec.get("message") or {}).get("content")
            if rtype == "user" and isinstance(content, str):
                events.append(Event(i=len(events), kind="user_prompt", text=content, **common))
                continue
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    kind = "assistant_text" if rtype == "assistant" else "user_prompt"
                    events.append(Event(i=len(events), kind=kind, text=block.get("text") or "", **common))
                elif btype == "thinking":
                    events.append(Event(i=len(events), kind="thinking", text=block.get("thinking") or "", **common))
                elif btype == "tool_use":
                    events.append(Event(i=len(events), kind="tool_use", name=block.get("name"),
                                        input=block.get("input") or {}, tool_use_id=block.get("id"), **common))
                elif btype == "tool_result":
                    raw = block.get("content")
                    if isinstance(raw, list):
                        raw = " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in raw)
                    events.append(Event(i=len(events), kind="tool_result", text=str(raw or ""),
                                        is_error=block.get("is_error"), tool_use_id=block.get("tool_use_id"), **common))
    return events


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

INTERNAL_MCP = re.compile(r"^mcp__(glean|slack|dataplat|indeed-google-workspace|experimentation-platform-mcp"
                          r"|indeed-assistant-mcp|mcp-marvin|design-system-mcp|sre-astrolabe|herbie-mcp|figma)__")
INTERNAL_CLI = re.compile(r"(?:^|[\s;|&(])(acli|glab|src|mcpc|jsma)\b")
ERROR_TEXT = re.compile(r"(?i)\b(401|403|unauthorized|forbidden|permission denied|not found|timed? ?out|timeout"
                        r"|econnrefused|5\d\d server error|authentication (failed|required)|token (expired|invalid))\b")

TOOL_ALIASES = {"Task": "Agent"}

# An agent that moves into a plugin gains its namespace. Transcripts predating the move
# carry the bare name, so both must resolve or every historical session scores SUSPECT.
AGENT_ALIASES = {"convention-audit:convention-checker": "convention-checker"}


def tool_name(ev):
    return TOOL_ALIASES.get(ev.name, ev.name)


def agent_type(ev):
    t = (ev.input or {}).get("subagent_type")
    return AGENT_ALIASES.get(t, t)


# Harness-level errors, not backend failures: the rule is about sources of truth
# going dark, not about output limits or tool-call mistakes.
HARNESS_ERROR = re.compile(r"(?i)(exceeds maximum allowed tokens|output has been saved to"
                           r"|has not been read yet|string to replace not found|no changes to make"
                           r"|permission (?:for this action was )?denied|user (?:rejected|doesn't want)"
                           r"|InputValidationError|interrupted by user|file has been (?:modified|unexpectedly)"
                           r"|parameter extraction failed|failed to unmarshal|unknown field|invalid_?request_?error"
                           r"|is not a valid|required (?:parameter|argument)|unrecognized (?:option|argument))")
# A named resource coming back absent is a real answer as often as it is an outage.
SOFT_MISS = re.compile(r"(?i)\b(not found (?:for|in)|no (?:results?|matches|definition|records?) (?:found|for)"
                       r"|does not exist|0 results)\b")


def is_failure(ev):
    """tool_result that represents a genuine backend failure (empty result sets are not)."""
    if ev.kind != "tool_result":
        return False
    head = (ev.text or "")[:600]
    if HARNESS_ERROR.search(head):
        return False
    if ev.is_error is True:
        return True
    return head.startswith("Error") or "<tool_use_error>" in head


def forward(events, i, n=6, kinds=("tool_use", "assistant_text", "user_prompt")):
    out = []
    for ev in events[i + 1:]:
        if ev.kind in kinds:
            out.append(ev)
            if len(out) >= n:
                break
    return out


def added_lines(ev):
    """Lines a Write/Edit introduces."""
    inp = ev.input or {}
    if "content" in inp:
        return (inp["content"] or "").splitlines()
    new = (inp.get("new_string") or "")
    old = set((inp.get("old_string") or "").splitlines())
    return [ln for ln in new.splitlines() if ln not in old]


COMMENT_RE = re.compile(r"^\s*(//+|#+|/\*+|\*(?!/)|--)\s*(.+?)\s*(\*/)?$")
CODE_EXT = re.compile(r"\.(swift|kt|java|ts|tsx|js|jsx|py|rb|go|rs|c|cc|cpp|h|hpp|m|mm|sh|gradle|graphql)$")


def comment_body(line):
    m = COMMENT_RE.match(line)
    if not m:
        return None
    body = m.group(2).strip()
    return body or None


def tokens(s):
    parts = re.split(r"[^A-Za-z0-9]+", s)
    out = []
    for p in parts:
        if not p:
            continue
        for piece in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", p):
            if len(piece) > 2:
                out.append(piece.lower())
    return out


# ---------------------------------------------------------------------------
# detectors: each yields (status, excerpt)
# ---------------------------------------------------------------------------

def d_tool_failure(events):
    """Stop and Confirm on Critical Tool Failures."""
    by_id = {e.tool_use_id: e for e in events if e.kind == "tool_use"}
    for ev in events:
        if not is_failure(ev):
            continue
        call = by_id.get(ev.tool_use_id)
        if not call:
            continue
        name = tool_name(call) or ""
        critical = bool(INTERNAL_MCP.match(name)) or (name == "Bash" and INTERNAL_CLI.search(call.cmd()))
        if not critical:
            continue
        nxt = forward(events, ev.i, 4)
        excerpt = f"{name}: {(ev.text or '')[:110]}"
        soft = bool(SOFT_MISS.search((ev.text or "")[:600]))
        if not nxt:                                            # turn ended -> it stopped
            yield FOLLOWED, excerpt
            continue
        if any(n.kind == "tool_use" and tool_name(n) == "AskUserQuestion" for n in nxt):
            yield FOLLOWED, excerpt
            continue
        if nxt[0].kind == "user_prompt":                       # handed back to the user
            yield FOLLOWED, excerpt
            continue
        if soft:                                               # absent resource: answer or outage, unclear
            yield SUSPECT, excerpt
            continue
        retried = any(n.kind == "tool_use" and tool_name(n) == name for n in nxt[:2])
        swapped = any(n.kind == "tool_use" and tool_name(n) in ("Grep", "Glob", "WebSearch", "WebFetch")
                      for n in nxt[:3])
        yield (VIOLATED if (retried or swapped) else SUSPECT), excerpt


def d_glean_chat_first(events):
    """Primary sources before Glean synthesis."""
    seen_primary = False
    for ev in events:
        if ev.kind != "tool_use":
            continue
        name = tool_name(ev) or ""
        if name == "mcp__glean__chat":
            yield (FOLLOWED if seen_primary else VIOLATED), "glean chat with no prior primary source"
            seen_primary = True
            continue
        if (INTERNAL_MCP.match(name) and name != "mcp__glean__chat") or \
           (name == "Bash" and re.search(r"\bacli\b", ev.cmd())):
            seen_primary = True


def d_convention_check(events):
    """Check convention before proposing a code shape."""
    PROPOSE = re.compile(r"(?i)\b(I propose|here'?s the design|here is the design|I'?ll implement|I will implement"
                         r"|approach A or B|I recommend (?:using|adding|creating|introducing)|my recommendation is)\b")
    checked = False
    for ev in events:
        if ev.kind == "tool_use" and tool_name(ev) == "Agent" and \
           agent_type(ev) == "convention-checker":
            checked = True
        if ev.kind == "assistant_text" and not ev.sidechain and PROPOSE.search(ev.text or ""):
            m = PROPOSE.search(ev.text)
            excerpt = (ev.text[max(0, m.start() - 20):m.start() + 90]).replace("\n", " ")
            yield (FOLLOWED if checked else SUSPECT), excerpt


def d_coauthor(events):
    for ev in events:
        if ev.kind == "tool_use" and tool_name(ev) == "Bash" and "git commit" in ev.cmd():
            bad = "co-authored-by" in ev.cmd().lower()
            yield (VIOLATED if bad else FOLLOWED), ev.cmd()[:120].replace("\n", " ")


def d_worktree(events):
    """Offer worktree isolation before substantial changes on the default branch."""
    mentioned = False
    fired = False
    for ev in events:
        if ev.kind in ("assistant_text", "thinking") and "worktree" in (ev.text or "").lower():
            mentioned = True
        if ev.kind == "tool_use" and tool_name(ev) in ("EnterWorktree",):
            mentioned = True
        if fired or ev.sidechain:
            continue
        if ev.kind == "tool_use" and tool_name(ev) in ("Edit", "Write", "MultiEdit"):
            path = (ev.input or {}).get("file_path") or ""
            if not CODE_EXT.search(path):
                continue
            if (ev.branch or "") not in ("main", "master"):
                continue
            fired = True
            yield (FOLLOWED if mentioned else VIOLATED), f"{ev.branch}: {os.path.basename(path)}"


def d_md_link_backticks(events):
    RE = re.compile(r"\[[^\]\n]*`[^\]\n]*\]\(")
    LINK = re.compile(r"\[[^\]\n]+\]\(")
    for ev in events:
        if ev.kind != "assistant_text" or ev.sidechain or not LINK.search(ev.text or ""):
            continue
        m = RE.search(ev.text)
        yield (VIOLATED, m.group(0)[:80]) if m else (FOLLOWED, "")


def d_verification_narrative(events):
    RE = re.compile(r"(?i)\b(?:I(?:'ve| have)\s+(?:now\s+|also\s+)?(?:verified|confirmed|double-checked|validated)"
                    r"|I can confirm that|I've checked)\b")
    for ev in events:
        if ev.kind != "assistant_text" or ev.sidechain or len(ev.text or "") < 40:
            continue
        m = RE.search(ev.text)
        yield (VIOLATED, ev.text[max(0, m.start() - 10):m.start() + 80].replace("\n", " ")) if m else (FOLLOWED, "")


def d_comment_discipline(events):
    """No comments restating the code or recording same-conversation design flips."""
    # unambiguous records of a change: only meaningful to someone who watched it happen
    FLIP = re.compile(r"(?i)\b(we used to|used to be|previously|simplified from|no longer|switched from"
                      r"|changed from|as discussed|per (?:the )?(?:above|earlier) discussion|for now)\b")
    # a contrast that may be a legitimate warning, or may be a discarded alternative
    FLIP_WEAK = re.compile(r"(?i)\b(instead of|rather than|not using)\b")
    for ev in events:
        if ev.kind != "tool_use" or tool_name(ev) not in ("Edit", "Write", "MultiEdit"):
            continue
        path = (ev.input or {}).get("file_path") or ""
        if not CODE_EXT.search(path):
            continue
        lines = added_lines(ev)
        for idx, line in enumerate(lines):
            body = comment_body(line)
            if not body or len(body) < 8:
                continue
            if FLIP.search(body):
                yield VIOLATED, f"{os.path.basename(path)}: {body[:90]}"
                continue
            if FLIP_WEAK.search(body):
                yield SUSPECT, f"{os.path.basename(path)}: {body[:90]}"
                continue
            nxt = next((l for l in lines[idx + 1:idx + 3] if l.strip() and not comment_body(l)), "")
            if nxt and len(body.split()) <= 9:
                shared = set(tokens(body)) & set(tokens(nxt))
                if len(shared) >= 2:
                    yield SUSPECT, f"{os.path.basename(path)}: {body[:60]} || {nxt.strip()[:50]}"
                    continue
            yield FOLLOWED, ""


def d_guessed_email(events):
    RE = re.compile(r"\b[a-z][a-z0-9._-]{2,}@indeed\.com\b")
    corpus = []
    for ev in events:
        if ev.kind in ("tool_result", "user_prompt"):
            corpus.append(ev.text or "")
        if ev.kind != "assistant_text" or ev.sidechain:
            continue
        found = set(RE.findall(ev.text or ""))
        if not found:
            continue
        haystack = "\n".join(corpus)
        for addr in found:
            yield (FOLLOWED, "") if addr in haystack else (VIOLATED, addr)


def d_sourcegraph_links(events):
    validated = False
    for ev in events:
        if ev.kind == "tool_use":
            name = tool_name(ev)
            if name == "Bash" and re.search(r"src (search|api)|sourcegraph", ev.cmd()):
                validated = True
            if name == "WebFetch" and "sourcegraph" in str((ev.input or {}).get("url", "")):
                validated = True
        if ev.kind == "assistant_text" and not ev.sidechain and "indeed.sourcegraph.com" in (ev.text or ""):
            m = re.search(r"https://indeed\.sourcegraph\.com/\S+", ev.text)
            yield (FOLLOWED if validated else SUSPECT), (m.group(0)[:100] if m else "")


def d_idle_agents(events):
    dispatched = [e for e in events if e.kind == "tool_use" and tool_name(e) == "Agent" and not e.sidechain]
    if not dispatched:
        return
    names = {tool_name(e) for e in events if e.kind == "tool_use"}
    excerpt = f"{len(dispatched)} agent dispatch(es)"
    yield (FOLLOWED if ("TaskStop" in names or "ListAgents" in names) else VIOLATED), excerpt


def d_explore_vs_grep(events):
    for ev in events:
        if ev.kind != "tool_use" or tool_name(ev) != "Agent":
            continue
        if agent_type(ev) != "Explore":
            continue
        prompt = str((ev.input or {}).get("prompt", ""))
        targeted = bool(re.search(r"`[A-Za-z_][A-Za-z0-9_]{3,}`|\b(definition of|where .* calls|find the file)\b", prompt))
        yield (SUSPECT if targeted else FOLLOWED), prompt[:100].replace("\n", " ")


def d_adf_description(events):
    for ev in events:
        if ev.kind != "tool_use" or tool_name(ev) != "Bash":
            continue
        cmd = ev.cmd()
        if "acli" in cmd and "--description-file" in cmd:
            m = re.search(r"--description-file[= ]+(\S+)", cmd)
            f = (m.group(1).strip("\"'") if m else "")
            yield (VIOLATED if f.endswith((".md", ".txt")) else FOLLOWED), f[:90]


def d_ci_before_local(events):
    """Existing CI artifacts before alternative test rigs."""
    saw_ci = False
    for ev in events:
        if ev.kind != "tool_use" or tool_name(ev) != "Bash":
            continue
        cmd = ev.cmd()
        if re.search(r"glab ci (status|list|view)", cmd):
            saw_ci = True
        if re.search(r"\bjsma (ios|android) build\b|hoboRun|\bpod install\b", cmd):
            yield (FOLLOWED if saw_ci else SUSPECT), cmd[:90]
            saw_ci = True   # count once per session


RULES = [
    ("tool-failure-stop", "Stop and confirm on critical tool failures", "user", d_tool_failure),
    ("convention-check", "convention-checker before a code-shape proposal", "user", d_convention_check),
    ("comment-discipline", "No restating / design-flip code comments", "user", d_comment_discipline),
    ("md-link-backticks", "No backticks in markdown links", "user", d_md_link_backticks),
    ("no-verify-narrative", "Conclusions, not verification narrative", "user", d_verification_narrative),
    ("worktree-offer", "Offer worktree before edits on default branch", "user", d_worktree),
    ("no-coauthor-trailer", "No Co-Authored-By trailer", "user", d_coauthor),
    ("stop-idle-agents", "Stop idle agents before ending a phase", "user", d_idle_agents),
    ("grep-over-explore", "Grep+Read for targeted lookups", "user", d_explore_vs_grep),
    ("primary-before-glean", "Primary sources before Glean chat", "indeed", d_glean_chat_first),
    ("sourcegraph-verified", "Validate Sourcegraph links before citing", "indeed", d_sourcegraph_links),
    ("jira-adf", "Jira descriptions are ADF JSON", "indeed", d_adf_description),
    ("ci-before-local", "CI artifacts before local test rigs", "indeed", d_ci_before_local),
    ("no-guessed-email", "No constructed @indeed.com addresses", "indeed", d_guessed_email),
]


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def session_start(events, path):
    """Session start from the earliest record timestamp. File mtime is only an upper
    bound — resumed sessions carry an mtime days after the content was written."""
    for ev in events:
        if not ev.ts:
            continue
        try:
            return time.mktime(time.strptime(str(ev.ts)[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def transcripts(since_epoch, project_filter):
    for proj in sorted(os.listdir(TRANSCRIPT_ROOT)):
        pdir = os.path.join(TRANSCRIPT_ROOT, proj)
        if not os.path.isdir(pdir):
            continue
        if project_filter and project_filter not in proj:
            continue
        for fn in os.listdir(pdir):
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(pdir, fn)
            try:
                if os.path.getmtime(path) < since_epoch:
                    continue
            except OSError:
                continue
            yield proj, path


def _ev(kind, **kw):
    kw.setdefault("sidechain", False)
    return Event(i=0, kind=kind, **kw)


def selftest():
    """Every detector must fire on a synthetic violation. A detector whose regex is
    broken otherwise reports a perfect adherence rate forever."""
    cases = [
        ("tool-failure-stop", [
            _ev("tool_use", name="mcp__glean__search", input={"query": "x"}, tool_use_id="t1"),
            _ev("tool_result", text="Error: 401 unauthorized", is_error=True, tool_use_id="t1"),
            _ev("tool_use", name="Grep", input={"pattern": "x"}),
        ]),
        ("convention-check", [_ev("assistant_text", text="I propose a free-standing Factory enum here.")]),
        ("comment-discipline", [
            _ev("tool_use", name="Write", input={"file_path": "/a/B.swift",
                                                 "content": "// we used to gate on the proctor\nlet x = 1"})]),
        ("md-link-backticks", [_ev("assistant_text", text="see [`Foo.swift`](https://x/y) now")]),
        ("no-verify-narrative", [_ev("assistant_text", text="I've verified the bundle loads correctly on both "
                                                            "platforms and the proctor resolves as expected.")]),
        ("worktree-offer", [_ev("tool_use", name="Edit", input={"file_path": "/a/B.swift"}, branch="main")]),
        ("no-coauthor-trailer", [_ev("tool_use", name="Bash",
                                     input={"command": "git commit -m 'x\n\nCo-Authored-By: Claude <x@y>'"})]),
        ("stop-idle-agents", [_ev("tool_use", name="Agent", input={"prompt": "go"})]),
        ("grep-over-explore", [_ev("tool_use", name="Agent",
                                   input={"subagent_type": "Explore", "prompt": "find the definition of `MobileGroupsManager`"})]),
        ("primary-before-glean", [_ev("tool_use", name="mcp__glean__chat", input={"q": "how do I deactivate"})]),
        ("sourcegraph-verified", [_ev("assistant_text", text="see https://indeed.sourcegraph.com/x/-/blob/y?L1-2")]),
        ("jira-adf", [_ev("tool_use", name="Bash",
                          input={"command": "acli jira workitem create --description-file d.md"})]),
        ("ci-before-local", [_ev("tool_use", name="Bash", input={"command": "jsma ios build"})]),
        ("no-guessed-email", [_ev("assistant_text", text="ping sthuang@indeed.com about it")]),
    ]
    # A detector that stops recognising compliance still fires on the violation case,
    # so "must fire" alone cannot catch it -- an agent rename went undetected that way.
    negatives = [
        ("convention-check", [
            _ev("tool_use", name="Agent", input={"subagent_type": name, "prompt": "verify"}),
            _ev("assistant_text", text="I propose a free-standing Factory enum here."),
        ], f"a proposal preceded by {name} is compliant")
        for name in ("convention-checker", "convention-audit:convention-checker")
    ]

    dets = {rid: det for rid, _, _, det in RULES}
    failed = []
    for rid, events in cases:
        for n, ev in enumerate(events):
            ev.i = n
        got = [s for s, _ in dets[rid](events)]
        if VIOLATED not in got and SUSPECT not in got:
            failed.append((rid, got))
    for rid, got in failed:
        print(f"FAIL {rid}: expected a violation/suspect, got {got or 'nothing'}")
    fire_failures = len(failed)
    for rid, events, reason in negatives:
        for n, ev in enumerate(events):
            ev.i = n
        got = [s for s, _ in dets[rid](events)]
        if VIOLATED in got or SUSPECT in got:
            print(f"FAIL {rid}: {reason}, got {got}")
            failed.append((rid, got))
    quiet_failures = len(failed) - fire_failures
    covered = {rid for rid, _ in cases}
    for rid, *_ in RULES:
        if rid not in covered:
            print(f"FAIL {rid}: no self-test case")
            failed.append((rid, []))
    print(f"\nselftest: {len(cases) - fire_failures}/{len(RULES)} detectors fire on a synthetic violation, "
          f"{len(negatives) - quiet_failures}/{len(negatives)} stay quiet on a compliant one")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="assert every detector fires, then exit")
    ap.add_argument("--since", help="YYYY-MM-DD (default: 30 days ago)")
    ap.add_argument("--until", help="YYYY-MM-DD, exclusive — for before/after comparisons")
    ap.add_argument("--project", help="substring of the project dir name")
    ap.add_argument("--examples", type=int, default=0, help="print N offending excerpts per rule")
    ap.add_argument("--json", dest="json_out", help="write the full report here")
    ap.add_argument("--candidates", help="write ambiguous cases as JSONL for an LLM grader")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if args.since:
        since = time.mktime(time.strptime(args.since, "%Y-%m-%d"))
    else:
        since = time.time() - 30 * 86400
    until = time.mktime(time.strptime(args.until, "%Y-%m-%d")) if args.until else None

    counts = {rid: defaultdict(int) for rid, *_ in RULES}
    examples = defaultdict(list)
    candidates = []
    files = sessions = 0

    for proj, path in transcripts(since, args.project):
        files += 1
        try:
            events = load_events(path)
        except (OSError, MemoryError) as exc:
            print(f"skip {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        if not events:
            continue
        start = session_start(events, path)
        if start < since or (until and start >= until):
            continue
        sessions += 1
        sid = os.path.basename(path)[:-6]
        for rid, title, scope, det in RULES:
            try:
                for status, excerpt in det(events):
                    counts[rid][status] += 1
                    if status in (VIOLATED, SUSPECT):
                        examples[rid].append({"session": sid, "project": proj,
                                              "status": status, "excerpt": excerpt})
                        if args.candidates and status == SUSPECT:
                            candidates.append({"rule": rid, "title": title, "session": sid,
                                               "project": proj, "excerpt": excerpt})
            except Exception as exc:                      # a broken detector must not kill the run
                print(f"detector {rid} failed on {sid}: {exc}", file=sys.stderr)

    # ---- report ----
    print(f"\nRule adherence — {sessions} sessions, {files} transcripts, since "
          f"{time.strftime('%Y-%m-%d', time.localtime(since))}"
          f"{' until ' + args.until if args.until else ''}\n")
    hdr = f"{'rule':24} {'scope':7} {'trig':>6} {'ok':>6} {'viol':>6} {'adherence':>10} {'unresolved':>11}"
    print(hdr)
    print("-" * len(hdr))
    dead, report = [], {}
    for rid, title, scope, _ in RULES:
        c = counts[rid]
        ok, vi, su = c[FOLLOWED], c[VIOLATED], c[SUSPECT]
        trig = ok + vi + su
        decided = ok + vi
        report[rid] = {"title": title, "scope": scope, "triggers": trig,
                       "followed": ok, "violated": vi, "unresolved": su,
                       "adherence": (round(100.0 * ok / decided, 1) if decided else None)}
        if trig == 0:
            dead.append((rid, title))
            continue
        rate = f"{100.0 * ok / decided:5.1f}%" if decided else "n/a"
        print(f"{rid:24} {scope:7} {trig:6d} {ok:6d} {vi:6d} {rate:>10} {su:11d}")
    print("\nadherence = followed / (followed + violated); unresolved cases need an LLM pass "
          "(--candidates) and are excluded from the rate.")

    if dead:
        print("\nDEAD — trigger never appeared in this window (prune candidates):")
        for rid, title in dead:
            print(f"  {rid:24} {title}")

    if args.examples:
        print("\nExamples:")
        for rid, title, _, _ in RULES:
            rows = examples.get(rid) or []
            if not rows:
                continue
            print(f"\n  {rid} — {title}")
            for row in rows[:args.examples]:
                print(f"    [{row['status']:8}] {row['excerpt'][:140]}")
                print(f"               {row['project']}/{row['session']}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"since": time.strftime("%Y-%m-%d", time.localtime(since)),
                       "sessions": sessions, "rules": report,
                       "examples": {k: v[:25] for k, v in examples.items()}}, fh, indent=2)
        print(f"\nwrote {args.json_out}")

    if args.candidates:
        with open(args.candidates, "w", encoding="utf-8") as fh:
            for row in candidates:
                fh.write(json.dumps(row) + "\n")
        print(f"wrote {len(candidates)} candidates to {args.candidates}")


if __name__ == "__main__":
    main()
