# Claude Code Local Marketplace

A local marketplace for Claude Code plugins, providing custom tools, skills, and agents for enhanced development workflows.

## Structure

```
.
├── .claude-plugin/
│   └── marketplace.json    # Marketplace manifest
├── session-manager/        # Terminal session management plugin
│   ├── commands/           # Slash commands
│   ├── scripts/            # Helper scripts
│   └── skills/             # Knowledge skills
├── claude-usage-analyzer/  # Usage analytics plugin
│   ├── commands/           # Slash commands
│   ├── scripts/            # Python analysis pipeline
│   └── reference/          # Reference data
├── default-tools/          # Auto-approve hooks plugin
│   └── hooks/              # Event handlers
├── stackey-backend/        # Stackey API integration plugin
│   ├── agents/             # Code generation agents
│   └── skills/             # API, auth, database knowledge
├── stackey-experts/        # Stackey expert agents (symlink → /Users/neo/Projects/Stackey)
│   ├── agents/             # Domain expert agents
│   └── commands/           # Orchestration commands
├── swift-project-tools/    # Swift Project Tools (symlink)
└── local_plugins/          # Additional local plugins
    └── tokenz-checkout-skills/
```

## Available Plugins

### session-manager

Terminal session management - fork sessions, run commands in panes/tabs, capture output.

- **Commands**: `/fork` - Fork current Claude Code session, `/run-in-pane` - Run command in new pane/tab, `/list-sessions` - List managed sessions
- **Skills**: Pane context capture and interaction
- **Keywords**: tmux, iterm, terminal, session, fork, pane

### claude-usage-analyzer

Analyze Claude Code session usage data and generate comprehensive reports with quantitative and qualitative insights.

- **Commands**: `/analyze-usage` - Run full analysis pipeline
- **Scripts**: Python analysis pipeline (generate_report.py, analyze_sessions.py, etc.)
- **Keywords**: usage, analytics, sessions, reports, statistics

### default-tools

Auto-approve safe tools with sensitive-path guards, macOS permission and stop notifications.

- **Hooks**: Auto-approve (PreToolUse), permission notification, stop notification
- **Keywords**: auto-approve, notifications, hooks, permissions

### stackey-backend

Skills for working with StackeyBackend Supabase API - blocks, media, favorites, and authentication.

- **Skills**: API endpoints, authentication patterns, database schema
- **Agents**: TypeScript/Swift code generation for API integration
- **Keywords**: stackey, supabase, api, blocks, media, authentication

### stackey-experts

Expert agents for the Stackey ecosystem with specialized knowledge for each component.

- **Agents**:
  - `stackey-app-expert` - iOS/Swift, XcodeGen, SwiftUI, keyboard extension
  - `stackey-backend-expert` - Supabase Edge Functions, PostgreSQL, authentication
  - `contract-manager` - OpenAPI specs, Swift type generation, contract testing
- **Commands**: `/generate-orchestration` - Generate agent orchestration instructions for CLAUDE.md
- **Keywords**: stackey, ios, swift, supabase, openapi, api-contract, agents

### tokenz-specs (local)

Cross-references web checkout specifications for iOS SDK development.

## Installation

Add this marketplace to your Claude Code configuration:

```json
{
  "marketplace": {
    "sources": [
      "git@github.com:koromiko/my_claudecode_marketplace.git"
    ]
  }
}
```

## Adding New Plugins

1. Create a new directory for your plugin
2. Add a `plugin.json` manifest with name, version, and description
3. Add components (commands, skills, agents, hooks) in their respective directories
4. Register the plugin in `.claude-plugin/marketplace.json`

## License

Private repository for personal use.
