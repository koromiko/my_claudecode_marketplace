# AGENTS.md

This file provides guidance to coding agents (Codex, Claude Code, etc.) when working with code in this repository.

## What This Is

A local marketplace of Claude Code plugins. Each plugin is a self-contained directory providing commands, skills, agents, hooks, and/or MCP servers to extend the agent. The central registry is `.claude-plugin/marketplace.json`.

## Architecture

```
marketplace.json (registry)
  ├── session-manager/      → Terminal session forking (tmux/iTerm), pane tracking
  ├── claude-usage-analyzer/ → Python pipeline analyzing ~/.claude/ session data
  ├── default-tools/        → Hook-only plugin: auto-approve, macOS notifications
  ├── agent-orchestration/  → Reusable subagent dispatch/retry/fallback protocol
  └── swift-project-tools/  → (symlink) Swift project setup skills
```

Each plugin follows this structure:
```
plugin-name/
├── .claude-plugin/plugin.json   # Required: name, version, description
├── CLAUDE.md / AGENTS.md        # Implementation guide for the agent
├── commands/                    # Slash commands (Markdown files)
├── skills/                      # Knowledge skills (SKILL.md + references/)
├── agents/                      # Agent definitions (Markdown files)
├── hooks/                       # hooks.json + handler scripts
└── scripts/                     # Helper scripts (Bash/Python)
```

Symlinked plugin (`swift-project-tools`) lives in an external repo and is gitignored.

## Commands

### claude-usage-analyzer (Python 3.8+, stdlib only)
```bash
python3 claude-usage-analyzer/scripts/generate_report.py --period weekly
python3 claude-usage-analyzer/scripts/generate_report.py --session <uuid>
```

### Bump plugin version + clear cache
```bash
./scripts/bump-plugin.sh <plugin>          # patch bump (default) + clear cache
./scripts/bump-plugin.sh <plugin> minor    # minor bump + clear cache
./scripts/bump-plugin.sh <plugin> major    # major bump + clear cache
./scripts/bump-plugin.sh <plugin> none     # clear cache only, no version change
```

### Validate Hook JSON
```bash
jq . <plugin>/hooks/hooks.json
```

## Key Conventions

- **Registering a plugin**: Add entry to `.claude-plugin/marketplace.json` with name, version, source path, and category.
- **Hook types**: PreToolUse (auto-approve decisions), PostToolUse (file watchers), Notification (permission prompts), Stop (session end). Handler scripts read JSON from stdin and write JSON to stdout.
- **No external Python deps**: `claude-usage-analyzer` uses only Python 3.8+ stdlib. No pip install needed.
- **Per-plugin guide**: Each plugin has its own CLAUDE.md/AGENTS.md with detailed implementation guidance. Read the relevant one when working on a specific plugin.
- **Skill creation/improvement**: Always use the `skill-creator:skill-creator` skill, not `plugin-dev:skill-development`.
- **Agent teams + MCP tools**: Background agents cannot handle MCP permission prompts. If a team task requires MCP tools (Chrome DevTools, Slack, etc.), the coordinator must run those calls directly or spawn the agent in the foreground.
- **Bump plugin version when finishing an implementation**: After completing a change to a plugin (feature, fix, or notable refactor), run `./scripts/bump-plugin.sh <plugin> [patch|minor|major]` (default: `patch`) to bump the `version` in that plugin's `.claude-plugin/plugin.json` and clear its cache. Use semver: patch for fixes, minor for features, major for breaking changes. Do this before committing.
