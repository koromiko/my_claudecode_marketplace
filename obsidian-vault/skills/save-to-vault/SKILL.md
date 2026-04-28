---
name: obsidian-vault-save
description: Use this skill when the user asks to save, capture, record, or write knowledge, notes, lessons learned, decisions, or summaries to their Obsidian vault. Triggers on phrases like "save to obsidian", "write a note", "capture this in my vault", "record this decision", "save lessons learned", "update my vault", "add to obsidian", "note this down in obsidian", "write to my knowledge base", "save to my second brain", "document this in obsidian".
---

# Save to Obsidian Vault

Capture knowledge from the current conversation and write it as a note in the user's Obsidian vault.

## Step 1: Read Configuration

Read the config file at `~/.claude/obsidian-vault/config.json`.

If the file does not exist, tell the user:
> "No Obsidian vault is configured yet. Run `/obsidian-vault:setup-vault` or say 'setup my obsidian vault' to get started."

Then **stop** — do not proceed without configuration.

Parse these fields from the config:
- `vault_path` — absolute path to vault root
- `default_folder` — subfolder for notes (may be empty string = vault root)
- `default_tags` — array of default tags

## Step 2: Validate Vault Path

Verify the vault is accessible:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/vault-config.sh validate
```

- If `VALID` — proceed
- If `PATH_NOT_FOUND` — tell user the vault path no longer exists and suggest re-running setup
- If `NOT_OBSIDIAN_VAULT` — warn that `.obsidian/` is missing, ask if they want to proceed anyway
- If `NOT_CONFIGURED` — direct to setup (same as Step 1)

## Step 3: Discover Vault Conventions

Before writing any note, learn how this vault formats its content. Read whichever of these files exist (in priority order):

### 3a: Rules Files
1. `{vault_path}/CLAUDE.md` — highest priority, Claude-specific formatting instructions
2. `{vault_path}/.claude/CLAUDE.md` — alternative location for Claude instructions
3. `{vault_path}/agent.md` or `{vault_path}/AGENTS.md` — general agent instructions

Read each file that exists. These may specify:
- Required YAML frontmatter fields and their format
- Folder placement rules (e.g., "put AI notes in `AI/`")
- Tag conventions (e.g., "use nested tags like `#source/claude`")
- Heading structure or template requirements
- Wikilink vs. standard link preference
- Naming conventions for files

### 3b: Templates
Check for template directories:
- `{vault_path}/templates/`
- `{vault_path}/_templates/`

If found, list the template files. If there's a template that matches the note type (e.g., `note.md`, `decision.md`, `lesson.md`), read it to understand the expected structure.

### 3c: Sample Existing Notes
If `default_folder` is set and contains `.md` files, read 1-2 existing notes to learn:
- What YAML frontmatter fields are used (e.g., `date`, `tags`, `aliases`, `cssclass`)
- Whether notes use `[[wikilinks]]` or standard `[links](path)`
- Tag format: inline `#tag` vs. frontmatter `tags:` array vs. both
- Heading hierarchy and section structure

### 3d: Folder Structure
Run `ls {vault_path}/` to understand the top-level organization. This helps determine where the note belongs if the user hasn't specified a folder.

### Convention Priority
When conventions conflict: **Rules files > Templates > Sampled notes > Defaults**

### Defaults (when no conventions are discovered)
- YAML frontmatter: `date`, `tags`, `source: claude-code`
- Standard markdown headings (H1 for title, H2 for sections)
- `[[wikilinks]]` for cross-references
- Tags in frontmatter array
- Filename: kebab-case with `.md` extension

## Step 4: Determine Note Intent

Based on the user's request, decide:

### New Note vs. Update
- **New note**: User says "save", "capture", "write a note about", "document"
- **Update existing**: User says "update", "add to", "append to", or references a specific existing note
- If updating, use Grep to search the vault for notes matching the topic. If multiple matches, ask the user which one. If no match, create a new note and inform the user.

### Title
- Derive from the user's prompt and conversation topic
- Examples: "Lessons Learned: Auth Migration", "Decision: Use PostgreSQL for User Data", "Session Summary: 2026-04-14"

### Target Folder
- Use `default_folder` from config if set
- Override with vault rules if they specify a different location for this note type
- If neither applies, use the vault root

### Filename
- Convert title to the vault's naming convention (discovered in Step 3)
- Default: kebab-case (e.g., `lessons-learned-auth-migration.md`)
- If a file with this name already exists and intent is "new note", append a date suffix (e.g., `lessons-learned-auth-migration-2026-04-14.md`)

## Step 5: Synthesize Content

Analyze the current conversation and extract the knowledge the user wants captured. The content style depends on the user's request:

### Conversation Summary
- Key topics discussed
- Decisions made and their rationale
- Action items or next steps
- Important code changes or findings

### Lessons Learned
- What was attempted and what happened
- What worked well and what didn't
- Takeaways for future reference

### Decision Record
- Context and problem statement
- Options considered
- Decision and rationale
- Consequences and trade-offs

### Code Knowledge
- What the code does and why
- Key patterns or techniques used
- Gotchas or edge cases discovered
- Relevant file paths and references

### General Knowledge
- Core concepts or facts
- How-to steps or procedures
- Links to resources mentioned

Format the content using the conventions discovered in Step 3. Always include:
- **YAML frontmatter** with at minimum: `date` (today), `tags` (merge `default_tags` with topic-specific tags), `source: claude-code`
- **AI-generated disclaimer tag — REQUIRED.** Every note saved by this skill must carry an `ai-generated` tag in the frontmatter `tags:` array so readers can distinguish AI-authored notes from hand-written ones. If the vault rules file (Step 3a) specifies a different disclaimer tag (e.g., `ai/claude-code`, `source/claude`), use that — but never omit the disclaimer entirely. If the vault uses inline tags, also place `#ai-generated` (or the vault's equivalent) near the top of the body.
- **AI-generated callout — REQUIRED.** Immediately after the H1 title (or after the frontmatter if there is no H1), insert a short Obsidian callout disclaiming AI authorship. Default form:
  ```markdown
  > [!info] AI-generated
  > This note was generated by Claude Code from a conversation on {date}. Review for accuracy before relying on it.
  ```
  If the vault rules specify a different disclaimer format, follow them, but the note must still visibly disclose AI authorship in the body.
- **Title** as H1 heading (unless vault convention says otherwise)
- **Obsidian-compatible markdown**: `[[wikilinks]]` for cross-references to other vault notes, fenced code blocks with language tags, `#tags` if the vault uses inline tags

## Step 6: Write or Update the Note

### Creating a New Note
Use the **Write** tool to create the file at:
```
{vault_path}/{target_folder}/{filename}.md
```

### Updating an Existing Note
1. Use **Read** to get the current note content
2. Determine update strategy:
   - **Append**: Add a horizontal rule and new timestamped section at the bottom
   - **Merge**: Integrate new information into existing sections (use **Edit** tool)
3. Update the `updated` or `modified` frontmatter field if present
4. **Disclaimer maintenance — REQUIRED.** Ensure the AI-generated disclaimer is still present after the update:
   - If the existing note's frontmatter `tags:` array does not include `ai-generated` (or the vault's configured disclaimer tag), add it.
   - If the existing note has no AI-generated callout/disclaimer in the body, add one (see Step 5). For appended sections, mark the appended block itself as AI-generated (e.g., `## Update: YYYY-MM-DD (AI-generated)`).

### Append Format
```markdown

---

## Update: YYYY-MM-DD (AI-generated)

[New content here]
```

## Step 7: Confirm to User

Report what was done:
- Whether a new note was created or an existing one was updated
- The full file path (so the user can open it in Obsidian)
- A brief summary of what was captured
- Any wikilinks created that reference other vault notes
- Suggest: "You can open this note in Obsidian to review and refine it."
