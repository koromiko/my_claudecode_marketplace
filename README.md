# Claude Code Local Marketplace

A local marketplace for Claude Code plugins, providing custom tools, skills, and agents for enhanced development workflows.

## Structure

```
.
├── .claude-plugin/
│   └── marketplace.json    # Marketplace manifest
├── tmux-session-tools/     # Tmux integration plugin
│   ├── agents/             # Autonomous agents
│   ├── commands/           # Slash commands
│   ├── scripts/            # Helper scripts
│   └── skills/             # Knowledge skills
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

### tmux-session-tools

Tmux integration for Claude Code with session forking and comprehensive tmux knowledge.

- **Commands**: `/fork-session` - Fork current tmux session
- **Skills**: Tmux scripting and advanced usage knowledge
- **Keywords**: tmux, terminal, session, fork, multiplexer

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
