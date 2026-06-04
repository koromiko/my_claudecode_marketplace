# grill-me Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `grill-me` capability to the `default-tools` plugin: an auto-triggering skill that interrogates a plan/design one question at a time through a separate read-only grill agent, with the main agent answering autonomously and escalating only costly-to-reverse decisions to the human.

**Architecture:** Two net-new prose artifacts — `skills/grill-me/SKILL.md` (the trigger + relay-loop conductor) and `agents/grill.md` (the read-only interrogator persona, the first agent in this marketplace) — plus doc/manifest updates to reflect the plugin's expanded scope. The skill directs the main agent to spawn the grill agent once, answer each returned question, and continue the same agent via SendMessage until a `DONE` sentinel or a 15-round safety cap.

**Tech Stack:** Markdown (skill + agent definitions), YAML frontmatter, `jq` for JSON manifest edits, bash for structural validation. No build system; these are prompt artifacts loaded by Claude Code's plugin loader.

**Spec:** `docs/superpowers/specs/2026-06-05-grill-me-design.md`

---

## Testing approach (read first)

These artifacts are **prompt prose**, not executable code, so "tests" are **structural assertions** run with bash/jq (file exists, required frontmatter present, tool list is read-only-only, loop steps documented). Each task writes the assertion first, watches it fail, creates the artifact, then watches it pass — TDD adapted to prose.

**Behavioral end-to-end testing (actually dispatching the grill agent) is NOT possible inside this worktree** — Claude Code loads the plugin from the marketplace source path (the main checkout), not from this worktree, so the new agent/skill go live only after merge + cache clear. End-to-end behavioral verification is therefore a **post-merge** step, documented in the Finishing section, not a task here.

## File Structure

| File | Responsibility |
|---|---|
| `default-tools/agents/grill.md` (create) | The grill agent persona: read-only interrogator that walks the design tree one question at a time and emits `DONE`. First agent in the marketplace. |
| `default-tools/skills/grill-me/SKILL.md` (create) | The trigger (description) + the relay-loop conductor the main agent follows: spawn → answer → SendMessage → DONE/cap, escalation rule, decision log, plan revision. |
| `default-tools/CLAUDE.md` (modify line 11 + add section) | Remove "There are no skills or agents"; document the skill, agent, and loop. |
| `default-tools/.claude-plugin/plugin.json` (modify `description`) | Mention the grill-me skill. |
| `.claude-plugin/marketplace.json` (modify default-tools `version`) | Keep registry version in sync with plugin.json after the bump. |
| `default-tools/README.md` (add section) | User-facing grill-me docs. |

All paths below are relative to the repo root (the worktree checkout root).

---

### Task 1: Grill agent definition (`agents/grill.md`)

**Files:**
- Create: `default-tools/agents/grill.md`
- Test: inline bash assertion (no test file)

- [ ] **Step 1: Write the failing assertion**

Run this exact check:

```bash
F=default-tools/agents/grill.md
{ test -f "$F" \
  && grep -q '^name: grill$' "$F" \
  && grep -q '^description:' "$F" \
  && grep -q '^tools:' "$F" \
  && grep -q '^model:' "$F" \
  && ! grep -E '^tools:.*(Edit|Write|Bash|NotebookEdit|mcp__|Agent)' "$F" \
  && grep -q 'DONE' "$F" \
  && grep -q 'EXACTLY ONE' "$F" ; } \
  && echo "PASS" || echo "FAIL"
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `FAIL` (file does not exist yet).

- [ ] **Step 3: Create the agent definition**

Write `default-tools/agents/grill.md` with EXACTLY this content:

```markdown
---
name: grill
description: Relentless plan/design interrogator. Walks every branch of a design tree one question at a time, resolving dependencies, until shared understanding is reached. Read-only — explores the codebase to ground its questions but never edits. Dispatched by the grill-me skill and continued across rounds via SendMessage.
tools: Read, Grep, Glob
model: inherit
---

# Grill Agent

You are a relentless but constructive design interrogator. Your job is to stress-test a plan or design BEFORE it is implemented by walking every meaningful branch of its decision tree, one question at a time, until you and the requester reach shared understanding.

You are dispatched by the `grill-me` skill. The main agent relays your questions and answers them — usually from the codebase. It continues you across multiple rounds via SendMessage, so you retain everything asked and answered so far. Treat each incoming message as the answer to your previous question.

## Your inputs (first message)

The main agent gives you:
- The plan/design under review, verbatim.
- Pointers to the relevant code/files.

## How you operate

1. Build a mental model of the design tree: the decisions the plan makes (explicit and implicit) and the dependencies between them (decision B only matters given a particular answer to decision A).
2. Each turn, ask EXACTLY ONE question — the single most important unresolved one given everything answered so far. Pick the question that, once answered, unblocks the most of the remaining tree.
3. With each question include:
   - **WHY** — one line: what breaks or changes depending on the answer.
   - **RECOMMENDED** — your best-guess answer plus brief reasoning, grounded in the plan and codebase.
4. Ground questions in the actual codebase. Use Read/Grep/Glob to check before asking something the code already answers — never ask what you can verify yourself.
5. Walk dependencies in order: resolve a parent decision before drilling into the branches it gates.
6. Never batch questions. One per turn. The next message you receive is the answer; only then ask the next question.

## Output format (every turn)

Return ONLY this block and nothing else:

```
QUESTION <n>: <the single question>
WHY: <one line>
RECOMMENDED: <your recommended answer + reasoning>
```

## When you are done

When the design tree is exhausted and dependencies are resolved — i.e., further questions would be nitpicks, not material to the design — emit exactly:

```
DONE
SUMMARY: <2-4 sentences: what was clarified, the key decisions reached, anything still genuinely open>
```

Emit DONE as soon as continued questioning would not change the design. Do not pad to hit a number. If the main agent sends "CAP REACHED — summarize unresolved threads and emit DONE", immediately emit the DONE block with the unresolved threads named in the summary.

## Constraints

- You are READ-ONLY. You never edit files or run mutating commands. You interrogate and explore; the main agent and the human make changes.
- Stay material. Every question must be able to change the design or the plan. No process boilerplate ("have you considered tests?") unless testing is a genuine design fork.
- Be direct and specific. Reference concrete parts of the plan and concrete files.
```

- [ ] **Step 4: Run the assertion to verify it passes**

Re-run the Step 1 check. Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
git add default-tools/agents/grill.md
git commit -m "feat(default-tools): add read-only grill agent persona

First agent in the marketplace. Walks a design tree one question at a
time, read-only (Read/Grep/Glob), emits DONE when shared understanding
is reached. Dispatched and continued by the grill-me skill.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: grill-me skill (`skills/grill-me/SKILL.md`)

**Files:**
- Create: `default-tools/skills/grill-me/SKILL.md`
- Test: inline bash assertion

- [ ] **Step 1: Write the failing assertion**

```bash
F=default-tools/skills/grill-me/SKILL.md
{ test -f "$F" \
  && grep -q '^name: grill-me$' "$F" \
  && grep -q '^description:' "$F" \
  && grep -q 'grill me' "$F" \
  && grep -q 'SendMessage' "$F" \
  && grep -q 'AskUserQuestion' "$F" \
  && grep -q 'subagent_type' "$F" \
  && grep -q '15' "$F" \
  && grep -q 'DONE' "$F" ; } \
  && echo "PASS" || echo "FAIL"
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `FAIL` (file does not exist yet).

- [ ] **Step 3: Create the skill**

Write `default-tools/skills/grill-me/SKILL.md` with EXACTLY this content:

```markdown
---
name: grill-me
description: Use when the user wants a plan or design stress-tested before building it. Triggers on "grill me", "grill this plan", "stress-test this plan", "poke holes in this design", "interrogate this design/plan", AND on pre-implementation moments where a concrete plan or design is on the table and about to be implemented. Dispatches a separate read-only grill agent that interrogates the plan one question at a time; the main agent answers each question from the codebase and escalates only costly-to-reverse decisions (schema/contract, public API, data migration, security boundary) to the human.
---

# grill-me

Stress-test a plan or design before implementation by running a relentless, one-question-at-a-time interrogation through a separate **grill agent**. The grill agent asks; YOU (the main agent) answer — usually from the codebase; the human is pulled in only for costly-to-reverse decisions.

## When this applies

- **Explicit:** "grill me", "grill this plan", "stress-test this plan", "poke holes in this design", "interrogate this design".
- **Implicit:** a concrete plan or design is on the table and about to be built, and it should be vetted first.

If there is no concrete plan/design yet, say so and offer to brainstorm one first — there is nothing to grill.

## The relay loop

This loop is the whole skill. Run it.

1. **Spawn the grill agent once.** Use the Agent tool with:
   - `subagent_type: "grill"`
   - `name: "grill"` — fixed, because you will continue THIS agent every round.
   - prompt: the plan/design under review verbatim, plus pointers to the relevant files/dirs, ending with "Ask your first question."
   - Leave permission mode at default — the grill agent is read-only and needs no edit permissions.

2. **Receive one question** — a `QUESTION / WHY / RECOMMENDED` block — or `DONE`.

3. **Answer it yourself.** Derive the answer from the codebase, project conventions, git history, or sound engineering defaults; Read/grep as needed.
   - **Escalate to the human ONLY** when the question concerns a costly-to-reverse decision: a schema/contract change, a public API shape, a data migration, or a security boundary. For those, use `AskUserQuestion`.
   - For everything else, answer autonomously — regardless of your confidence.

4. **Log the round.** Append one row to a running decision log you keep visible in the conversation:

   | # | Question | Answer | Source |
   |---|----------|--------|--------|

   `Source` is one of: `codebase`, `convention`, `git`, `default`, `HUMAN`.

5. **Continue the grill agent** with the answer:
   - `SendMessage({ to: "grill", message: "ANSWER <n>: <your answer>" })`
   - It returns the next question, or `DONE`.

6. **Stop when** the grill agent emits `DONE`, OR you reach the safety cap of **15 rounds** (use a different number only if the user named one). At the cap, send `SendMessage({ to: "grill", message: "CAP REACHED — summarize unresolved threads and emit DONE" })` and use its summary. The user can say "keep going" to extend the cap.

## On completion

1. Print the final decision log (the fully populated table above).
2. **Revise the plan/design on the table** to fold in every resolved decision, so the user leaves with an updated plan — not just a transcript. Show the revised plan or a diff of what changed.
3. List any open items explicitly: anything the human deferred, or threads the cap cut short.

## Guardrails

- The grill agent is **read-only** — it cannot change files. All edits happen in this main session.
- One question per round. Do not let the loop batch questions or skip the answer step.
- Keep answers grounded: name the file or convention you used in the `Source` column.
```

- [ ] **Step 4: Run the assertion to verify it passes**

Re-run the Step 1 check. Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
git add default-tools/skills/grill-me/SKILL.md
git commit -m "feat(default-tools): add grill-me skill (relay-loop conductor)

Auto-triggers on grill/stress-test intent and pre-implementation
contexts. Spawns the grill agent, answers each question from the
codebase, escalates only costly-to-reverse decisions via
AskUserQuestion, continues the agent via SendMessage to a 15-round cap,
then revises the plan with the resolved decisions.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Documentation + manifest scope updates

**Files:**
- Modify: `default-tools/CLAUDE.md:11` (+ new section)
- Modify: `default-tools/.claude-plugin/plugin.json` (`description`)
- Modify: `default-tools/README.md` (new section)

- [ ] **Step 1: Write the failing assertion**

```bash
{ ! grep -q 'There are no skills or agents' default-tools/CLAUDE.md \
  && grep -q 'grill-me' default-tools/CLAUDE.md \
  && grep -q 'grill-me' default-tools/README.md \
  && jq -e '.description | test("grill")' default-tools/.claude-plugin/plugin.json >/dev/null \
  && jq -e . default-tools/.claude-plugin/plugin.json >/dev/null ; } \
  && echo "PASS" || echo "FAIL"
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `FAIL`.

- [ ] **Step 3a: Edit `default-tools/CLAUDE.md`**

Replace this exact sentence on line 11:

```
Logic lives primarily in `hooks/`. There are no skills or agents. The plugin also ships a `scripts/` directory with the auto-approve usage reports (terminal + HTML) and a `commands/` directory with the `/auto-approve-report` slash command that wraps the HTML report script.
```

with:

```
Logic lives primarily in `hooks/`. The plugin also ships one skill (`skills/grill-me/`) and one agent (`agents/grill.md`) — see **grill-me Skill** below — a `scripts/` directory with the auto-approve usage reports (terminal + HTML), and a `commands/` directory with the `/auto-approve-report` slash command that wraps the HTML report script.
```

Then append this section to the end of `default-tools/CLAUDE.md`:

```markdown
## grill-me Skill

`skills/grill-me/SKILL.md` is an auto-triggering skill that stress-tests a plan
or design before implementation. It triggers on explicit grill intent ("grill
me", "stress-test this plan", "poke holes in this design") and on
pre-implementation contexts where a concrete plan is about to be built.

The skill conducts a **relay loop** with a separate read-only **grill agent**
(`agents/grill.md` — the first agent in this marketplace):

1. The main agent spawns the grill agent once (`subagent_type: "grill"`,
   `name: "grill"`), passing the plan and code pointers.
2. The grill agent returns ONE question per turn (`QUESTION / WHY / RECOMMENDED`).
3. The main agent answers it autonomously from the codebase/conventions, and
   escalates to the human via `AskUserQuestion` only for costly-to-reverse
   decisions (schema/contract, public API, data migration, security boundary).
4. The answer is fed back via `SendMessage(to: "grill", ...)`; repeat until the
   grill agent emits `DONE` or a 15-round safety cap is hit.
5. On completion the main agent prints the decision log and revises the plan to
   fold in the resolved decisions.

The grill agent's `tools` are restricted to `Read, Grep, Glob` so it is
strictly read-only and never trips a permission prompt mid-loop (background
agents cannot handle permission prompts — see the marketplace CLAUDE.md).

This relay-loop use of `SendMessage` (continuing one named agent across rounds)
is intentional and unique in this repo; elsewhere `SendMessage` is used only for
TeamCreate swarm coordination.
```

- [ ] **Step 3b: Edit `default-tools/.claude-plugin/plugin.json`**

```bash
TMP=$(mktemp)
jq '.description = "Default tool auto-approval with sensitive-path guards, Ollama LLM fallback evaluator, macOS notification hooks, and a grill-me skill that interrogates plans before implementation"' \
  default-tools/.claude-plugin/plugin.json > "$TMP" && mv -f "$TMP" default-tools/.claude-plugin/plugin.json
```

- [ ] **Step 3c: Edit `default-tools/README.md`**

Insert this section immediately before the `## Hooks` line (i.e., after the
intro paragraph, line 3):

```markdown
## grill-me Skill

`skills/grill-me/` auto-triggers when you want a plan or design stress-tested
before building it — say "grill me", "stress-test this plan", or "poke holes in
this design", or it fires when a concrete plan is on the table pre-implementation.

It spawns a separate **read-only grill agent** (`agents/grill.md`) that
interrogates the plan one question at a time. The main agent answers each
question from the codebase and only escalates costly-to-reverse decisions
(schema/contract, public API, data migration, security boundary) to you. The
loop runs via `SendMessage` until the agent is satisfied or a 15-round safety
cap is reached, then the plan is revised with the resolved decisions.

```

- [ ] **Step 4: Run the assertion to verify it passes**

Re-run the Step 1 check. Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
git add default-tools/CLAUDE.md default-tools/README.md default-tools/.claude-plugin/plugin.json
git commit -m "docs(default-tools): document grill-me skill and grill agent

Remove the now-stale 'no skills or agents' note and describe the
relay-loop architecture in CLAUDE.md, README, and the plugin description.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Version bump + final validation

**Files:**
- Modify: `default-tools/.claude-plugin/plugin.json` (`version`, via script)
- Modify: `.claude-plugin/marketplace.json` (default-tools `version`, sync)

- [ ] **Step 1: Bump the plugin version (minor — new feature)**

```bash
./scripts/bump-plugin.sh default-tools minor
```

Expected: prints the new version `1.5.0` and clears the plugin cache.

- [ ] **Step 2: Sync the marketplace registry version**

```bash
NEW=$(jq -r '.version' default-tools/.claude-plugin/plugin.json)
TMP=$(mktemp)
jq --arg v "$NEW" '(.plugins[] | select(.name=="default-tools") | .version) = $v' \
  .claude-plugin/marketplace.json > "$TMP" && mv -f "$TMP" .claude-plugin/marketplace.json
```

- [ ] **Step 3: Final validation — run all assertions together**

```bash
echo "== plugin.json valid + version synced =="
jq -e . default-tools/.claude-plugin/plugin.json >/dev/null && echo "json ok"
test "$(jq -r '.version' default-tools/.claude-plugin/plugin.json)" \
   = "$(jq -r '.plugins[]|select(.name=="default-tools")|.version' .claude-plugin/marketplace.json)" \
   && echo "versions in sync" || echo "VERSION MISMATCH"

echo "== marketplace.json valid =="
jq -e . .claude-plugin/marketplace.json >/dev/null && echo "json ok"

echo "== agent read-only =="
grep -E '^tools:' default-tools/agents/grill.md | grep -Eqv 'Edit|Write|Bash|NotebookEdit|mcp__|Agent' \
  && echo "agent read-only ok"

echo "== skill + agent discoverable =="
test -f default-tools/skills/grill-me/SKILL.md && test -f default-tools/agents/grill.md && echo "files present"

echo "== docs updated =="
! grep -q 'There are no skills or agents' default-tools/CLAUDE.md && echo "claude.md updated"
```

Expected: every line prints its OK message; no `VERSION MISMATCH`.

- [ ] **Step 4: Commit**

```bash
git add default-tools/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(default-tools): bump to 1.5.0 for grill-me skill

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Finishing (post-merge — outside the worktree)

These steps require the plugin to be live (loaded from the marketplace source
path with a cleared cache), which only happens after the worktree is merged back
and the cache is cleared. Do them after merge:

1. **Reload / verify discovery:** confirm `grill-me` appears in the skill list
   and `grill` resolves as a `subagent_type`.
2. **Behavioral smoke test:** give Claude a tiny throwaway plan (e.g. "I'm going
   to add a `--json` flag to the usage report script") and say "grill this
   plan". Verify:
   - the grill agent is spawned and returns exactly ONE `QUESTION/WHY/RECOMMENDED`
     block;
   - the main agent answers from the codebase and logs a decision row;
   - the loop continues via SendMessage and terminates on `DONE` (or the cap);
   - a costly-to-reverse question (introduce one, e.g. "should the JSON schema be
     stable/public?") routes to `AskUserQuestion`;
   - on completion the plan is revised and the decision log is printed.
3. If any behavior is off, iterate on `SKILL.md` / `grill.md` wording (prose
   tuning only — no structural change).

## Self-Review (completed by plan author)

- **Spec coverage:** skill form ✓ (Task 2), auto-trigger description ✓ (Task 2
  frontmatter), separate grill agent ✓ (Task 1), interactive relay loop via
  SendMessage ✓ (Task 2 step 3 loop), main-agent-answers + costly-to-reverse
  escalation ✓ (Task 2 step 3 + escalation rule), grill-agent DONE + 15-round cap
  ✓ (Tasks 1 & 2), decision log + plan revision output ✓ (Task 2 completion),
  read-only agent guardrail ✓ (Task 1 tools), doc/scope updates ✓ (Task 3),
  version bump ✓ (Task 4).
- **Placeholder scan:** none — all artifact bodies are given in full.
- **Type/name consistency:** `subagent_type: "grill"` and `name: "grill"` match
  the agent frontmatter `name: grill` across Tasks 1–3; skill `name: grill-me`
  matches the path `skills/grill-me/` and the assertions; cap value `15`
  consistent across SKILL.md, CLAUDE.md, README; `DONE` sentinel consistent
  across agent + skill.
