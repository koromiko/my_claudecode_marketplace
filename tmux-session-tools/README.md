# tmux-session-tools

A Claude Code plugin for tmux integration with session forking capabilities and comprehensive tmux knowledge.

## Features

- **`/fork-session` command**: Fork your current Claude Code session into a new tmux window, allowing parallel conversations
- **tmux skill**: Comprehensive tmux knowledge including windows, panes, sessions, keybindings, copy mode, scripting, and plugins

## Requirements

- [tmux](https://github.com/tmux/tmux) installed on your system
- Claude Code running inside a tmux session (for the fork-session command)

## Installation

### Option 1: Local Installation

Copy the plugin to your Claude Code plugins directory:

```bash
cp -r tmux-session-tools ~/.claude/plugins/
```

### Option 2: Development Testing

Run Claude Code with the plugin directory:

```bash
claude --plugin-dir /path/to/tmux-session-tools
```

## Usage

### Fork Session Command

While running Claude Code inside tmux, use the fork-session command to create a parallel conversation:

```
/fork-session
```

Or with a custom window name:

```
/fork-session my-experiment
```

This will:
1. Create a new tmux window
2. Launch a forked Claude Code session with the full conversation history
3. Switch focus to the new window

Both sessions can then proceed independently.

### Tmux Skill

The tmux skill activates automatically when you ask questions about tmux:

- "How do I split panes in tmux?"
- "What are the tmux keybindings for window management?"
- "How do I create a tmux session script?"
- "Help me configure tmux"

## Plugin Structure

```
tmux-session-tools/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── fork-session.md
├── skills/
│   └── tmux/
│       ├── SKILL.md
│       └── references/
│           ├── advanced-scripting.md
│           └── plugins.md
└── README.md
```

## License

MIT
