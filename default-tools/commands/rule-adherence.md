---
description: Measure whether CLAUDE.md rules are actually followed, by grading past session transcripts per rule
allowed-tools:
  - Bash(python3:*)
  - Read
argument-hint: "[--since YYYY-MM-DD] [--until YYYY-MM-DD] [--project <name>] [--examples N]"
---

# Rule Adherence

Grade `~/.claude/projects/*/*.jsonl` against the rules in CLAUDE.md and report, per rule: trigger
count, followed, violated, adherence rate, and unresolved cases. Answers the only question that
matters about a rule — when its trigger appeared, did the behavior follow?

Defaults to the **last 30 days, all projects**.

## Arguments

`$ARGUMENTS` is forwarded to the script verbatim.

- `--since YYYY-MM-DD` — sessions starting on or after this date
- `--until YYYY-MM-DD` — exclusive upper bound; pair with `--since` for before/after comparisons
- `--project <substr>` — substring match on the project directory name
- `--examples N` — print N offending excerpts per rule, each with its session id
- `--json <path>` — write the full report, including up to 25 examples per rule
- `--candidates <path>` — write unresolved cases as JSONL for a follow-up LLM pass
- `--selftest` — assert every detector fires on a synthetic violation, then exit

## Instructions

Run the self-test first. A detector whose regex has rotted reports 100% adherence forever, so a
green self-test is what makes the numbers meaningful.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rule-adherence.py" --selftest
```

If any detector fails, report which one and stop — do not present adherence numbers from a run with
a broken detector.

Then run the report:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rule-adherence.py" $ARGUMENTS
```

Summarize in this order:

1. **Worst adherence at meaningful volume** — a rule that is stated and ignored. Recommend
   converting it to a hook; prose is losing to context pressure.
2. **DEAD rules** (zero triggers) — prune candidates, or the trigger is written too narrowly to
   match real work. Say which of the two you think it is.
3. **Unresolved-dominated rules** — the detector found triggers but cannot judge compliance. Report
   the count, not a rate, and offer to grade the `--candidates` dump with a subagent.

Do not present a violation count as fact without a spot check. Pull one example with `--examples`
and confirm it is a real violation against ground truth — for rules about landed artifacts, that
means `git log`, not the transcript, because PreToolUse hooks rewrite tool input before it is
recorded.

## Reading the numbers

- Adherence is `followed / (followed + violated)`. Unresolved cases are excluded.
- Session dates come from the first record timestamp, not file mtime — a resumed session carries an
  mtime days after its content, so mtime windows over-include.
- A window returning 0 sessions means the transcripts are gone (rotated or deleted), not that
  behavior was perfect. Baselines older than the retention window are unrecoverable.

## Adding a rule

Append a detector to `RULES` in `scripts/rule-adherence.py`. It takes the ordered event list and
yields `(status, excerpt)` with status `followed`, `violated`, or `suspect`. **Add a `selftest()`
case in the same change.**

Events are `assistant_text`, `thinking`, `tool_use`, `tool_result`, and `user_prompt`, each carrying
`ts`, `branch`, `cwd`, and `sidechain`. Use `sidechain` to exclude subagent output from rules about
user-facing prose.
