# tmux-session-tools

A Claude Code plugin for tmux integration with session forking, pane management, output capture, and context injection.

## Features

- **`/fork-session`**: Fork your current Claude Code session into a new tmux window
- **`/split-run`**: Split current pane and run a command with an auto-assigned name
- **`/list-panes`**: List all panes with their Claude names
- **`/capture-pane`**: Capture output from a named pane (one-time)
- **`/watch-pane`**: Auto-inject pane output as context periodically
- **`/unwatch-pane`**: Stop watching a pane
- **`/close-pane`**: Close a pane by name or ID
- **tmux skill**: Comprehensive tmux knowledge for windows, panes, scripting, and more

## Requirements

- [tmux](https://github.com/tmux/tmux) installed on your system
- Claude Code running inside a tmux session

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

### Split & Run (Create Named Panes)

Create a new pane, run a command, and name it for future reference:

```
/split-run server npm run dev
/split-run logs tail -f /var/log/app.log
/split-run build npm run build:watch
```

### List Panes

See all panes with their names:

```
/list-panes
```

### Capture Pane Output

Get a one-time capture of pane output:

```
/capture-pane server
/capture-pane server 500   # Last 500 lines
```

### Watch Pane (Context Injection)

Automatically inject pane output as context on every prompt:

```
/watch-pane server 30      # Capture every 30 seconds
/unwatch-pane              # Stop watching
```

### Close Panes

Close a pane by name:

```
/close-pane server
/close-pane                # Interactive selection
```

### Fork Session

Create a parallel Claude session with full conversation history:

```
/fork-session
/fork-session my-experiment
```

## Pane Naming

Panes created with `/split-run` are automatically named using tmux's user-defined options. Names persist across detach/reattach and can be referenced in other commands:

```
/split-run logs tail -f app.log    # Creates pane named "logs"
/capture-pane logs                  # Capture output from "logs" pane
/close-pane logs                    # Close the "logs" pane
```

## Plugin Structure

```
tmux-session-tools/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── fork-session.md
│   ├── split-run.md
│   ├── list-panes.md
│   ├── capture-pane.md
│   ├── watch-pane.md
│   ├── unwatch-pane.md
│   └── close-pane.md
├── agents/
│   ├── fork-session-agent.md
│   ├── split-run-agent.md
│   ├── list-panes-agent.md
│   ├── capture-pane-agent.md
│   ├── watch-pane-agent.md
│   ├── unwatch-pane-agent.md
│   └── close-pane-agent.md
├── hooks/
│   └── hooks.json
├── scripts/
│   ├── list-sessions.sh
│   ├── resolve-pane.sh
│   ├── list-named-panes.sh
│   ├── set-pane-name.sh
│   └── check-watch.sh
├── skills/
│   └── tmux/
│       ├── SKILL.md
│       └── references/
│           └── advanced-scripting.md
└── README.md
```

## License

MIT
