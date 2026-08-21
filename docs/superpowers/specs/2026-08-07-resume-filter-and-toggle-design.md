# Filter autonomous sessions + per-project toggle in `tmux-cc-attach` — design

Date: 2026-08-07
Status: approved for planning

## Problem

`tmux-cc-attach` resumes recently-ended sessions on by default, but two rough
edges remain:

1. **Autonomous sessions pollute the resume list.** Background teammate/agent
   sessions fire the same `SessionStart`/`SessionEnd` hooks as human ones and
   land in the resume store. On this machine 14 of 36 resume records are such
   sessions — noise a human never wants to hand-resume.
2. **Resume is all-or-nothing.** The only interaction is a single
   `Proceed? [y/N]`; the user cannot pick which projects to bring back.

## Goals

- Exclude autonomous (teammate/agent) sessions from the resume list.
- Let the user toggle which project groups to attach/resume after seeing the
  report, preserving the one-keystroke "take everything" flow.

## Non-goals

- No per-session toggle (project-group is the unit).
- No opt-in flag to re-include autonomous sessions (YAGNI; add later if asked).
- No change to live-session classification — the autonomous filter applies only
  to resume-store entries.

## Autonomous detection

A session transcript that contains a `"type":"agent-setting"` record is an
autonomous teammate/agent session; human sessions have none. Verified as a 100%
clean split across the current resume store (14 autonomous, 22 human): the
`agent-setting` record and the corroborating `<teammate-message>` opening user
message agree on every record. `agent-setting` is a first-class Claude Code
transcript record type, not a string heuristic.

## Components

### a. `resume_is_autonomous <id> <root>` (new helper)

Locates the transcript with the same `"$root"/*/"$id".jsonl` glob as
`resume_is_resumable`, then `grep -q '"type":"agent-setting"'`. Returns 0 when
the session is autonomous. Early-exit grep; cheap.

Placed with the other resume helpers, above the `TMUX_CC_LIB_ONLY` guard so it
is unit-testable.

### b. Read-time filter (resume-build loop)

In the resume-build loop the check order becomes:

```
age-prune → transcript-exists → autonomous-skip → live-dedup → project-glob
```

Autonomous entries are **skipped from the list, not unlinked** — they are valid
resumable transcripts, merely unwanted; the existing 14-day age-prune clears the
files eventually. The check runs after `resume_is_resumable`, so the transcript
is known to exist. Unconditional: no flag.

### c. Per-project-group toggle

The grouped report numbers its group headers (`[1] <project>`, `[2] …`) so no
second menu is printed. The `Proceed? [y/N]` prompt is replaced by:

```
Select projects [Enter=all, e.g. '1 3', 'n'=none]:
```

Input handling:

- empty / Enter → all groups (preserves today's one-keystroke flow)
- `n` / `none` → abort, exit 0
- space- or comma-separated numbers → those groups only
- out-of-range or non-numeric → re-prompt

A deselected group skips **both** its live-attach and resume entries. The attach
loop gains a `contains_exact "$group" "${SELECTED_GROUPS[@]}"` gate.

Flag interactions:
- `-y` / `--yes` → skip the prompt, take all groups (unchanged behavior).
- `-n` / `--dry-run` → no prompt, preview all groups (unchanged).
- `-p` / `--project` → pre-filters groups; the prompt then numbers only the
  surviving groups.

Parsing is extracted as a pure `parse_group_selection <input> <count>` that
prints the selected 1-based indices (or all, on empty) and signals error on bad
tokens, so the interactive read loop stays thin and the parser is unit-testable.

## Data flow

```
read_resume_records ─▶ age-prune ─▶ transcript-exists ─▶ autonomous-skip
                     ─▶ live-dedup ─▶ project-glob ─▶ RESUME_* arrays
report (numbered groups) ─▶ prompt ─▶ parse_group_selection ─▶ SELECTED_GROUPS
attach loop (gated on SELECTED_GROUPS)
```

## Error handling

- Missing transcript: already handled upstream by `resume_is_resumable`; the
  autonomous check never runs on a missing transcript.
- Missing `grep`: not a concern (POSIX baseline); a failed grep returns
  non-autonomous, so the entry is kept rather than silently dropped.
- Bad selection input: re-prompt rather than abort; `n`/empty are the explicit
  exits.

## Testing (`tests/test-tmux-cc-attach.sh`)

- Unit `resume_is_autonomous`: fixture transcript containing an `agent-setting`
  record → autonomous; a transcript without one → not autonomous.
- Unit `parse_group_selection`: empty→all, `n`→none, `1 3`→{1,3}, `2,4`→{2,4},
  out-of-range→error, non-numeric→error.
- Integration: extend the existing `--resume-only -n` fixture set with one
  autonomous transcript and assert its id is absent from the dry-run output.

## Migration

No data migration. Existing autonomous records in the store simply stop
appearing in the list on the next run and age out normally. Bump the plugin
2.9.0 → 2.10.0 (minor: two user-facing features). Update
`session-manager/CLAUDE.md` and `README` for the new hygiene step and the
toggle.

## Dependencies / risks

- Relies on `agent-setting` remaining the marker Claude Code writes for
  teammate/agent sessions; if that record type is renamed the filter silently
  stops matching (fails open — autonomous sessions reappear, nothing breaks).
- The toggle changes the default interactive path; `-y` preserves the
  non-interactive contract for any scripted callers.
