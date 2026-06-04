# grill-me — Design

**Date:** 2026-06-05
**Plugin:** `default-tools`
**Status:** Approved (brainstorming) → ready for implementation plan

## Summary

Add a `grill-me` capability to the `default-tools` plugin that mimics
[mattpocock/skills/grill-me](https://www.skills.sh/mattpocock/skills/grill-me):
a relentless, one-question-at-a-time interrogation of a plan or design before
implementation. The capability is delivered as an **auto-triggering skill** that
conducts the interrogation through a **separate grill agent**. The main agent
answers the grill agent's questions autonomously from the codebase, escalating
to the human only for costly-to-reverse decisions.

This is the first skill and the first agent in the `default-tools` plugin (and
the first `agents/` directory in the marketplace).

## Goals

- Faithfully reproduce grill-me's substance: walk every branch of the design
  tree, resolve dependencies between decisions one-by-one, ask one probing
  question at a time until shared understanding is reached.
- Delegate the interrogation to a dedicated agent persona (separate from the
  main session).
- Have the **main agent** answer the grill agent's questions autonomously
  wherever the answer is derivable, pulling in the human only when a decision is
  expensive to reverse.
- Leave the user with an **updated plan**, not just a transcript.

## Non-Goals

- Not a slash command (explicitly chose the skill form).
- Not a one-shot written report — the interrogation is an interactive relay
  loop, not a single autonomous pass.
- The grill agent does not modify files or run mutating commands.
- No changes to `marketplace.json` / `plugin.json` registration beyond
  description text (components are auto-discovered by directory convention).

## Components

### 1. `default-tools/skills/grill-me/SKILL.md`

The trigger and the loop conductor. First skill in `default-tools`.

- **Frontmatter:** `name`, `description` only — matches the dominant convention
  across the marketplace's 5 existing SKILL.md files (no `tools`/`model`/
  `triggers` keys; those don't appear in any existing skill).
- **Trigger scope (the `description`):** fires on **both**
  1. explicit grill intent — "grill me", "grill this plan", "stress-test this
     plan", "poke holes in this design", "interrogate this design"; and
  2. pre-implementation / design-review contexts — a plan or design is on the
     table and about to be built.
- **Body:** instructs the main agent to run the relay loop (below), defines the
  escalation rule, the decision log format, the safety cap, and the DONE
  handling. The loop is written out step-by-step so this novel-for-this-repo
  pattern is explicit and grep-able in place.
- Optional `references/` subdir if the prompt grows long (follows
  `agent-orchestration` / `neo-writing-style` precedent).

### 2. `default-tools/agents/grill.md`

The interrogator persona. First agent in the marketplace — frontmatter schema
defined deliberately since there is no local precedent to pattern-match:

- **Frontmatter:** `name`, `description`, `tools`, `model`.
  - `tools`: **read-only only** — `Read`, `Grep`, `Glob`, plus the search tools.
    No `Edit`/`Write`, no mutating `Bash`, no MCP tools. This keeps the agent
    safe and sidesteps the marketplace CLAUDE.md constraint that background
    agents cannot handle permission prompts mid-run.
  - `model`: inherit from the session.
- **Body (the grill-me prompt):**
  - Walk every meaningful branch of the design tree; resolve dependencies
    between decisions one-by-one.
  - Ask **exactly one** question per turn, then stop and return it.
  - Provide a recommended answer with each question (mirrors the original).
  - Explore the codebase (read-only) to ground questions where it can.
  - Emit a `DONE` sentinel when shared understanding is reached, with a brief
    summary; on a forced stop (cap), return a summary of unresolved threads.

## Control Flow — SendMessage relay loop

The SKILL.md directs the **main agent** to:

1. **Spawn** the grill agent **once** via the Agent tool with a fixed name
   (`grill`), handing it the plan/design under review plus pointers to relevant
   code. Request its first question.
2. **Receive one question.**
3. **Answer autonomously** from the codebase, conventions, git history, or sound
   engineering defaults.
   - **Escalate to the human only** when the question concerns a
     costly-to-reverse decision: schema/contract change, public API shape, data
     migration, or a security boundary. (Use `AskUserQuestion` for these.)
4. **Append** `{question, answer, source}` to a running **decision log** shown
   inline in the conversation.
5. **Continue** the grill agent via `SendMessage(to: "grill", ...)` with the
   answer — context is preserved, so it walks to the next branch. It returns the
   next question, or `DONE`.
6. **Loop** until `DONE` **or** the safety cap (default **15** rounds,
   configurable inline by the user — e.g. "keep going" extends it). At the cap,
   the grill agent returns unresolved threads.

```
main agent ──spawn(plan, code pointers)──▶ grill agent
            ◀──── question #1 ────────────
   answer (codebase) │ escalate if costly-to-reverse → human
            ──SendMessage(answer)────────▶ grill agent
            ◀──── question #2 / DONE ─────
            … repeat until DONE or cap(15) …
```

### Escalation rule (when the human is pulled in)

| Question concerns… | Who answers |
|---|---|
| Anything derivable from code, convention, git history, defaults | Main agent (autonomous) |
| Schema / contract change | Human |
| Public API shape | Human |
| Data migration | Human |
| Security boundary | Human |

Confidence level does not trigger escalation — only the costly-to-reverse
nature of the decision does.

## Output

On `DONE` (or cap):

1. Print the final **decision log** (every question, the main agent's answer,
   the source, and human-escalated decisions).
2. **Revise the plan/design on the table** to fold in everything resolved, so
   the user leaves with an updated plan rather than only a transcript.

## Documentation & Scope Changes

The plugin currently self-describes as hooks-only. Adding a skill + agent
requires:

- `default-tools/CLAUDE.md` — replace "There are no skills or agents" with a
  section documenting the grill-me skill, the grill agent, and the relay loop.
- `default-tools/.claude-plugin/plugin.json` — extend `description` to mention
  the interrogation skill.
- `default-tools/README.md` — add a grill-me section.
- Version bump: `./scripts/bump-plugin.sh default-tools minor` (new feature)
  before commit.

## Testing

- **Skill trigger check:** confirm the `description` triggers on the explicit
  phrases and on pre-implementation contexts, and does not over-fire on
  unrelated plans/questions (manual eval against a few sample prompts).
- **Agent contract:** dispatch the grill agent in isolation with a sample plan;
  confirm it returns exactly one question + recommended answer and emits `DONE`
  appropriately.
- **Loop dry-run:** walk a small sample plan end-to-end; confirm the decision
  log accumulates, escalation fires only on costly-to-reverse questions, and the
  cap terminates the loop with an unresolved-threads summary.
- **Read-only guarantee:** confirm the agent's `tools` list contains no
  mutating tools.
- JSON validity for any touched config (`jq . default-tools/.claude-plugin/plugin.json`).

## Risks & Precedent Notes

- **Relay loop is novel in this repo.** `SendMessage` is otherwise used only for
  TeamCreate swarm coordination, not multi-round single-agent dialogue.
  Mitigation: the SKILL.md spells the loop out step-by-step so the pattern is
  documented in place.
- **First agent definition in the marketplace.** Frontmatter schema is defined
  deliberately (`name`, `description`, `tools`, `model`) since there is no local
  precedent; this becomes the pattern others copy.
- **Permission-prompt constraint.** Addressed by restricting the grill agent to
  read-only tools so it never needs an interactive approval mid-loop.
- **Runaway token burn.** Bounded by the safety cap (default 15 rounds).
