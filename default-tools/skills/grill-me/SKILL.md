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
   - prompt: the plan/design under review verbatim, plus pointers to the relevant files/dirs, ending with "Ask your first question."
   - Leave permission mode at default — the grill agent is read-only and needs no edit permissions.
   - **Capture the `agentId` from the spawn result** (format `a…`; the result reads "use SendMessage with to: '<agentId>'"). You address the grill agent by this `agentId` for every subsequent round — a fresh `Agent` call would start over with no memory.

2. **Receive one question** — a `QUESTION / WHY / RECOMMENDED` block — or `DONE`. **If the response is `DONE`, skip straight to "On completion" below** — do not log it as a round and do not send another answer.

3. **Answer it yourself.** Derive the answer from the codebase, project conventions, git history, or sound engineering defaults; Read/grep as needed.
   - **Escalate to the human ONLY** when the question concerns a costly-to-reverse decision: a schema/contract change, a public API shape, a data migration, or a security boundary. For those, use `AskUserQuestion`.
   - For everything else, answer autonomously — regardless of your confidence.

4. **Log the round.** Append one row to a running decision log you keep visible in the conversation:

   | # | Question | Answer | Source |
   |---|----------|--------|--------|

   `Source` is one of: `codebase`, `convention`, `git`, `default`, `HUMAN`.

5. **Continue the grill agent** with the answer, addressing it by the captured `agentId`:
   - `SendMessage({ to: "<agentId>", message: "ANSWER <n>: <your answer>" })`
   - `<n>` is the round number from the `QUESTION <n>` you just received.
   - It returns the next question, or `DONE`.

6. **Stop when** the grill agent emits `DONE` (handled at step 2). Independently, if you reach the safety cap of **15 rounds** (use a different number only if the user named one), pause and tell the user the cap was reached. If they say "keep going", raise the cap by another 15 and continue the loop — the grill agent is still active and needs no re-spawn. Otherwise, send `SendMessage({ to: "<agentId>", message: "CAP REACHED — summarize unresolved threads and emit DONE" })` and use its summary.

## On completion

1. Print the final decision log (the fully populated table above).
2. **Revise the plan/design on the table** to fold in every resolved decision, so the user leaves with an updated plan — not just a transcript. Show the revised plan or a diff of what changed.
3. List any open items explicitly: anything the human deferred, or threads the cap cut short.

## Guardrails

- The grill agent is **read-only** — it cannot change files. All edits happen in this main session.
- One question per round. Do not let the loop batch questions or skip the answer step.
- Keep answers grounded: name the file or convention you used in the `Source` column.
