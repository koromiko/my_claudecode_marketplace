---
name: obsidian-vault-setup
description: Use this skill when the user wants to set up, configure, or reconfigure their Obsidian vault connection, change their vault path, or when running initial setup for the obsidian-vault plugin. Triggers on phrases like "setup obsidian", "configure vault", "set vault path", "connect obsidian", "obsidian vault setup", "change vault path", "reconfigure obsidian".
---

# Obsidian Vault Setup

Interactive setup to configure which Obsidian vault to use for knowledge capture.

## Step 1: Check for Existing Configuration

Read the config file at `~/.claude/obsidian-vault/config.json`.

- If it exists, show the user their current settings (vault path, default folder, default tags) and ask if they want to reconfigure.
- If it does not exist, proceed to Step 2.

## Step 2: Gather Vault Path

Ask the user for the absolute path to their Obsidian vault. Provide hints:
- Common locations: `~/Documents/MyVault`, `~/Obsidian`, `~/vaults/...`
- The path should be the root directory of the vault — the one containing the `.obsidian/` folder

Validate the provided path:
1. Check the directory exists: `ls <path>`
2. Check `.obsidian/` subdirectory exists: `ls <path>/.obsidian`
3. If validation fails, explain exactly what went wrong and ask again
4. If the directory exists but has no `.obsidian/`, warn the user it does not appear to be an Obsidian vault and ask if they want to proceed anyway

## Step 3: Gather Optional Preferences

Ask the user (they can skip any of these):

1. **Default folder**: A subfolder within the vault where notes should be saved by default (e.g., `claude-notes/`, `inbox/`, `AI/`). If the folder does not exist, offer to create it.
2. **Default tags**: Comma-separated tags to add to every note's YAML frontmatter (e.g., `claude, ai-generated`). Suggest `["claude"]` as a sensible default.

## Step 4: Write Configuration

Initialize the config directory and write the config file:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/vault-config.sh init
```

Then use the Write tool to create `~/.claude/obsidian-vault/config.json` with this schema:

```json
{
  "vault_path": "/absolute/path/to/vault",
  "default_folder": "claude-notes",
  "default_tags": ["claude"],
  "created_at": "ISO-8601-timestamp",
  "updated_at": "ISO-8601-timestamp"
}
```

- `vault_path` (required): Absolute path to the vault root
- `default_folder` (optional, default `""`): Relative path within the vault for new notes
- `default_tags` (optional, default `["claude"]`): Tags array for YAML frontmatter
- `created_at` / `updated_at`: Set both to current ISO 8601 timestamp

If `default_folder` was specified and does not exist in the vault, create it:
```bash
mkdir -p <vault_path>/<default_folder>
```

## Step 5: Scan Vault for Conventions

Read whatever convention/rules files exist in the vault and report what was found:

1. Check for `{vault_path}/CLAUDE.md` — read and summarize if present
2. Check for `{vault_path}/.claude/CLAUDE.md` — read and summarize if present
3. Check for `{vault_path}/agent.md` or `{vault_path}/AGENTS.md` — read and summarize if present
4. Check for template directories: `{vault_path}/templates/` or `{vault_path}/_templates/`
5. List top-level vault folders to identify organizational pattern (Zettelkasten, PARA, topic-based, etc.)

Report findings to the user, e.g.: "Found a CLAUDE.md with formatting instructions. Your vault uses a PARA structure with Projects/, Areas/, Resources/, Archives/ folders. Notes will follow these conventions."

If no convention files are found, inform the user: "No formatting rules found. Notes will use sensible defaults (YAML frontmatter with date/tags, standard markdown headings). You can add a CLAUDE.md to your vault root to customize formatting."

## Step 6: Confirm Setup

Report the final configuration and show example usage:

- "Your Obsidian vault is configured. You can now use these phrases in any conversation:"
  - "Save this to obsidian"
  - "Capture lessons learned in my vault"
  - "Write a note about what we discussed"
  - "Update my vault with this decision"
- "To reconfigure, say 'reconfigure my obsidian vault' or run `/obsidian-vault:setup-vault`"
