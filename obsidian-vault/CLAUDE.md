# CLAUDE.md

This file provides guidance to Claude Code when working with the obsidian-vault plugin.

## Overview

Plugin for capturing knowledge from Claude Code conversations and storing them as notes in an Obsidian vault. Respects vault-specific formatting conventions by reading CLAUDE.md/agent.md/rules files in the target vault before writing.

## Plugin Structure

```
.claude-plugin/plugin.json       # Plugin manifest
CLAUDE.md                        # This file
skills/
  setup-vault/SKILL.md           # Interactive vault configuration
  save-to-vault/SKILL.md         # Knowledge capture and note writing
scripts/
  vault-config.sh                # Config read/validate/init helper
```

## Configuration

Stored at `~/.claude/obsidian-vault/config.json`:

```json
{
  "vault_path": "/absolute/path/to/vault",
  "default_folder": "claude-notes",
  "default_tags": ["claude"],
  "created_at": "2026-04-14T10:00:00Z",
  "updated_at": "2026-04-14T10:00:00Z"
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `vault_path` | Yes | — | Absolute path to Obsidian vault root (must contain `.obsidian/`) |
| `default_folder` | No | `""` | Relative path within vault for new notes |
| `default_tags` | No | `["claude"]` | Tags added to every note's YAML frontmatter |

## Skills

### setup-vault
Interactive setup that guides the user through providing their vault path and preferences. Validates the vault exists and has `.obsidian/`. Writes the config file. Scans the vault for formatting convention files and reports what was found.

Invoked via: `/obsidian-vault:setup-vault` or natural language ("setup my obsidian vault", "configure vault path").

### save-to-vault
Captures knowledge from the current conversation and writes it as a note. Before writing, discovers vault formatting conventions by reading CLAUDE.md, agent.md, templates, and sampling existing notes. Supports creating new notes and updating existing ones.

Invoked via: `/obsidian-vault:save-to-vault` or natural language ("save to obsidian", "capture lessons learned in my vault").

## Vault Rules Discovery

The save skill reads formatting conventions from the target vault in this priority order:

1. `{vault_path}/CLAUDE.md` — Claude-specific formatting instructions (highest priority)
2. `{vault_path}/.claude/CLAUDE.md` — alternative location
3. `{vault_path}/agent.md` or `AGENTS.md` — general agent instructions
4. `{vault_path}/templates/` or `_templates/` — note templates
5. Existing notes in `default_folder` — sampled for frontmatter/tag/link conventions
6. Sensible defaults — YAML frontmatter, wikilinks, kebab-case filenames

## Helper Script

`scripts/vault-config.sh` provides three subcommands:

```bash
vault-config.sh read      # Output config JSON (exits 1 if not configured)
vault-config.sh validate  # Check vault path: VALID, PATH_NOT_FOUND, NOT_OBSIDIAN_VAULT, NOT_CONFIGURED
vault-config.sh init      # Create ~/.claude/obsidian-vault/ directory
```

## Testing

```bash
# Validate plugin manifest
jq . obsidian-vault/.claude-plugin/plugin.json

# Test config script (before setup)
bash obsidian-vault/scripts/vault-config.sh read       # Should error: NOT_CONFIGURED
bash obsidian-vault/scripts/vault-config.sh validate   # Should error: NOT_CONFIGURED

# Test setup flow
# Say: "setup my obsidian vault"
# Provide a vault path, verify config.json is created

# Test save flow
# Have a conversation, then say: "save lessons learned to obsidian"
# Verify a .md note is created in the vault

# Test convention discovery
# Add a CLAUDE.md to the vault with custom rules
# Run save — verify the note follows those rules
```

## No External Dependencies

Uses only bash and python3 stdlib. No pip install needed.
