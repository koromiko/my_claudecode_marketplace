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
