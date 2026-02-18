---
description: Analyze the current session, find improvement opportunities, and suggest CLAUDE.md changes to build institutional memory
allowed-tools:
  - Read(*)
  - Glob(*)
  - Grep(*)
---

# Session Retrospective

Analyze the current conversation to build institutional memory. Identify what went well, what could be improved, and suggest specific CLAUDE.md additions for future sessions.

## Process

### Phase 1: Session Summary

Summarize the current conversation:

1. **Tasks completed**: What was accomplished (code written, docs generated, bugs fixed, designs created)
2. **Tools and patterns used**: Which tools, frameworks, or patterns were applied
3. **User corrections**: Identify every moment where the user redirected your approach, corrected an assumption, or asked you to redo something — these are the highest-signal inputs for CLAUDE.md improvements

Present this as a concise 3-5 sentence summary.

### Phase 2: Improvement Analysis

Review the work done during this session. Look for:

- **Convention deviations**: Did you use patterns inconsistent with the rest of the codebase?
- **Over-engineering**: Did you add unnecessary abstraction, error handling, or complexity?
- **Missing context**: Were there project-specific facts you didn't know that caused rework?
- **Repeated mistakes**: Did the same type of correction happen more than once?
- **Quality gaps**: Missing tests, docs, edge cases, or accessibility considerations?

Focus on issues that are **systemic** (would recur in future sessions) rather than one-off mistakes.

Present each finding as a numbered list with a brief explanation of why it matters.

### Phase 3: CLAUDE.md Suggestions

Before suggesting changes:

1. Find and read the project-root CLAUDE.md using Glob and Read
2. Understand its current structure and what it already covers
3. **Do not suggest anything already covered** by existing CLAUDE.md content

Generate specific, minimal CLAUDE.md additions. Each suggestion must:

- Be tied to something that actually happened in this session (include rationale)
- Be 1-3 lines that fit into an existing or new section of CLAUDE.md
- Be a **convention** (do X), **constraint** (don't do Y), or **context** (this project uses Z)
- Be specific enough to change behavior, not vague guidance

**YAGNI filter**: Only suggest things motivated by this session. Do not speculate about hypothetical improvements.

## Output Format

Present the retrospective in this structure:

```
## Session Retrospective

### Summary
[3-5 sentence summary of what was accomplished and how the session went]

### Key Corrections
[List moments where the user corrected your approach — these drive the suggestions below]

1. [What you did] → [What the user asked for instead]

### Improvement Opportunities
[Systemic findings that would recur in future sessions]

1. **[Finding title]** — [Why it matters and how it manifested in this session]

### Suggested CLAUDE.md Changes

#### 1. [Category: Convention/Constraint/Context] — [Brief title]

**Rationale**: During this session, [specific thing that happened that motivated this suggestion].

**Suggested addition** (to [section name] section):
\```
[Exact text to add to CLAUDE.md]
\```

#### 2. ...
```

## Guidelines

- If no meaningful improvements were identified, say so honestly rather than inventing suggestions
- Prioritize suggestions by impact: things that would save the most rework in future sessions come first
- Keep the total number of suggestions to 3-5 maximum — focus on the highest-value changes
- Frame suggestions positively when possible ("prefer X" over "don't do Y")
- If the session went smoothly with no corrections, focus Phase 2 on quality improvements rather than mistakes
