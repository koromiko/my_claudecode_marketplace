# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A local marketplace of Claude Code plugins. Each plugin is a self-contained directory providing commands, skills, agents, hooks, and/or MCP servers to extend Claude Code. The central registry is `.claude-plugin/marketplace.json`.

## Architecture

```
marketplace.json (registry)
  ├── session-manager/      → Terminal session forking (tmux/iTerm), pane tracking
  ├── claude-usage-analyzer/ → Python pipeline analyzing ~/.claude/ session data
  ├── default-tools/        → Hook-only plugin: auto-approve, macOS notifications
  ├── ios-agentic-loop/     → iOS testing via idb + Maestro, includes TypeScript MCP server
  ├── stackey-backend/      → Supabase API skills and code-gen agents
  ├── stackey-experts/      → (symlink) Domain expert agents for Stackey ecosystem
  ├── agent-orchestration/  → Reusable subagent dispatch/retry/fallback protocol
  └── swift-project-tools/  → (symlink) Swift project setup skills
```

Each plugin follows this structure:
```
plugin-name/
├── .claude-plugin/plugin.json   # Required: name, version, description
├── CLAUDE.md                    # Implementation guide for Claude
├── commands/                    # Slash commands (Markdown files)
├── skills/                      # Knowledge skills (SKILL.md + references/)
├── agents/                      # Agent definitions (Markdown files)
├── hooks/                       # hooks.json + handler scripts
├── scripts/                     # Helper scripts (Bash/Python)
└── mcp-server/                  # MCP server (only ios-agentic-loop)
```

Symlinked plugins (`stackey-experts`, `swift-project-tools`) live in external repos and are gitignored.

## Commands

### ios-agentic-loop MCP Server (TypeScript)
```bash
cd ios-agentic-loop/mcp-server
npm install && npm run build    # Compile TypeScript
npm test                        # Run vitest tests
```

### claude-usage-analyzer (Python 3.8+, stdlib only)
```bash
python3 claude-usage-analyzer/scripts/generate_report.py --period weekly
python3 claude-usage-analyzer/scripts/generate_report.py --session <uuid>
```

### Plugin Cache
```bash
./scripts/clear-cache.sh            # Clear all plugin caches
./scripts/clear-cache.sh --dry-run  # Preview
```

### Validate Hook JSON
```bash
jq . <plugin>/hooks/hooks.json
```

## Key Conventions

- **Registering a plugin**: Add entry to `.claude-plugin/marketplace.json` with name, version, source path, and category.
- **Hook types**: PreToolUse (auto-approve decisions), PostToolUse (file watchers), Notification (permission prompts), Stop (session end). Handler scripts read JSON from stdin and write JSON to stdout.
- **MCP config**: Only `ios-agentic-loop` has an MCP server. Config is in `.mcp.json` using `${CLAUDE_PLUGIN_ROOT}` for portable paths.
- **No external Python deps**: `claude-usage-analyzer` uses only Python 3.8+ stdlib. No pip install needed.
- **Per-plugin CLAUDE.md**: Each plugin has its own CLAUDE.md with detailed implementation guidance. Read the relevant one when working on a specific plugin.
