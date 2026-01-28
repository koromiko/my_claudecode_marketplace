---
description: Guides creation of custom tmux workflow commands. Use when user runs /create-workflow command.
allowed-tools: Bash(bash:*), Read, Write, AskUserQuestion
model: haiku
---

# Create Workflow Agent

Guide the user through creating a custom tmux workflow command for their project.

## Input

The prompt will contain:
- **Plugin root path**: Path to the plugin directory (required)
- **Current working directory**: The project path to analyze (required)
- **Workflow name**: Optional name for the workflow

## Workflow

### Phase 1: Project Analysis

#### Step 1.1: Detect project type

Run the detection script:

```bash
bash "PLUGIN_ROOT_PATH/scripts/detect-project.sh" "CWD"
```

Parse the output to extract:
- `PROJECT_TYPE`: frontend, backend, fullstack, monorepo, rust, go, python, docker, or unknown
- `PACKAGE_MANAGER`: npm, yarn, pnpm, bun, cargo, go, python, or none
- `HAS_DOCKER`: true or false
- `HAS_MONOREPO`: true or false
- `WORKSPACES`: comma-separated list of workspace patterns
- `FRAMEWORKS`: comma-separated list of detected frameworks

#### Step 1.2: List available scripts

Run the scripts listing tool:

```bash
bash "PLUGIN_ROOT_PATH/scripts/list-scripts.sh" "CWD"
```

Parse the output:
- `SCRIPTS`: comma-separated `name:command` pairs, or `none`

### Phase 2: Layout Suggestion

Based on detected project type, suggest a layout using these presets:

**Frontend (react, vue, angular, svelte, nextjs, nuxt):**
```
Suggested layout: 2 panes
┌────────────────┬────────────────┐
│                │      dev       │
│     main       │  npm run dev   │
│  (Claude Code) │                │
└────────────────┴────────────────┘

Panes:
1. dev: Development server (npm run dev or equivalent)
```

**Backend (express, fastify, nestjs, koa, hono):**
```
Suggested layout: 2 panes
┌────────────────┬────────────────┐
│                │     server     │
│     main       │  npm run dev   │
│  (Claude Code) │                │
└────────────────┴────────────────┘

Panes:
1. server: Backend server with watch mode
```

**Fullstack (frontend + backend detected):**
```
Suggested layout: 3 panes
┌────────────────┬────────────────┐
│                │    frontend    │
│     main       ├────────────────┤
│  (Claude Code) │    backend     │
└────────────────┴────────────────┘

Panes:
1. frontend: Frontend dev server
2. backend: Backend server (suggest watch: 30s)
```

**Monorepo:**
```
Suggested layout: Based on workspaces
Create one pane per main workspace with dev command
```

**Docker project:**
```
Suggested layout: 2 panes
┌────────────────┬────────────────┐
│                │     docker     │
│     main       │ docker compose │
│  (Claude Code) │      up        │
└────────────────┴────────────────┘

Panes:
1. docker: Docker compose services
```

**With Docker (any project with HAS_DOCKER=true):**
Add a docker pane option:
- docker: `docker-compose up` or `docker compose up`

**Rust:**
```
Panes:
1. dev: cargo watch -x run (or cargo run)
```

**Go:**
```
Panes:
1. dev: air (if .air.toml exists) or go run .
```

**Python:**
```
Panes:
1. dev: Framework-specific command from detection
```

**Unknown:**
```
Suggested layout: 2 panes
Generic layout - user will customize commands
```

### Phase 3: User Customization

Use AskUserQuestion for each decision.

#### Step 3.1: Present layout and get confirmation

Show the detected project info and suggested layout, then ask:

```
I detected a [PROJECT_TYPE] project.

[Present layout diagram and pane details]

Available commands from your project:
[List detected scripts]
```

Use AskUserQuestion with options:
1. "Use this layout" - Accept suggested layout
2. "Add a pane" - Add another pane
3. "Remove a pane" - Remove a pane from suggestion
4. "Start from scratch" - Manual configuration

#### Step 3.2: For each pane, confirm or customize

For each pane in the layout, use AskUserQuestion:

```
Pane: [PANE_NAME]
Command: [COMMAND]
Watch: [none or interval]
```

Options:
1. "Keep as-is" - Accept current configuration
2. "Change command" - Modify the command
3. "Toggle watch" - Add or remove watch interval
4. "Remove pane" - Remove this pane

If user chooses to change command, show available scripts and allow custom input.

If user chooses to toggle watch:
- If no watch, ask for interval (default 30 seconds)
- If has watch, remove it

#### Step 3.3: Adding panes

If user wants to add a pane, ask:

Options based on context:
1. "Docker logs" (if HAS_DOCKER and no docker pane)
2. "Test watcher" (if test script detected)
3. "Build watcher"
4. "Custom pane" - Enter name and command

For custom pane, ask:
1. Pane name (alphanumeric, no spaces)
2. Command to run
3. Watch interval (0 for none)

#### Step 3.4: Workflow naming

If no workflow name was provided in input:

```
What would you like to name this workflow?
You'll run it as: /workflow-[name]
```

Suggest names based on project type:
- "dev" - Generic development
- "fullstack" - For fullstack projects
- "docker-dev" - For Docker-based development
- Project name from package.json/Cargo.toml

Validate the name:
- Must be alphanumeric with hyphens only
- No spaces or special characters
- Check if `/commands/workflow-[name].md` already exists

If exists, ask:
1. "Overwrite existing" - Replace current workflow
2. "Choose different name" - Enter new name

### Phase 4: Generate Workflow Files

#### Step 4.1: Generate command file

Create the command file at `PLUGIN_ROOT_PATH/commands/workflow-[NAME].md`:

```markdown
---
description: [DESCRIPTION based on project type and panes]
argument-hint:
---

Use the Task tool to spawn the `workflow-[NAME]-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Session ID: `${CLAUDE_SESSION_ID}` (for watch functionality)

The agent will set up [N] tmux panes for [PROJECT_TYPE] development.
```

Use the Write tool to create this file.

#### Step 4.2: Generate agent file

Create the agent file at `PLUGIN_ROOT_PATH/agents/workflow-[NAME]-agent.md`:

```markdown
---
description: Sets up [NAME] workflow with [N] tmux panes. Use when user runs /workflow-[NAME] command.
allowed-tools: Bash(bash:*, tmux:*), Write
model: haiku
---

# Workflow: [NAME]

[DESCRIPTION]

## Layout

[ASCII_DIAGRAM]

## Pane Configuration

| Name | Command | Watch |
|------|---------|-------|
[TABLE_ROWS]

## Execution

### Step 1: Check tmux environment

```bash
if [ -z "$TMUX" ]; then
    echo "NOT_IN_TMUX"
else
    echo "IN_TMUX"
fi
```

If NOT_IN_TMUX:
- Inform user: "This command requires running inside a tmux session. Start tmux first."
- Stop execution.

### Step 2: Create panes

For each pane, execute in sequence:

[For each PANE in configuration:]

#### Pane: [PANE_NAME]

Create the pane:
```bash
NEW_PANE_ID=$(tmux split-window -h -P -F '#{pane_id}')
echo "Created: $NEW_PANE_ID"
```

Set the name:
```bash
bash "PLUGIN_ROOT_PATH/scripts/set-pane-name.sh" "$NEW_PANE_ID" "[PANE_NAME]"
```

Run the command:
```bash
tmux send-keys -t "$NEW_PANE_ID" "[COMMAND]" Enter
```

[If WATCH_INTERVAL > 0:]
### Step 3: Set up watch for [PANE_NAME]

Write watch config to `~/.claude/tmux-watch-SESSION_ID.json`:

```json
{
  "pane_name": "[PANE_NAME]",
  "interval": [WATCH_INTERVAL],
  "last_capture": 0
}
```

Use the Write tool to create this file.

### Step [N]: Report success

Tell the user:
- Workflow "[NAME]" started successfully
- Created [N] panes: [list pane names]
- [If watches:] Watching [PANE_NAME] every [INTERVAL]s
- Use `/list-panes` to see all panes
- Use `/capture-pane [name]` for one-time capture
- Use `/close-pane [name]` to close individual panes
```

Use the Write tool to create this file.

#### Step 4.3: Confirm and offer to run

Tell the user:
- Workflow created successfully!
- Command file: `PLUGIN_ROOT_PATH/commands/workflow-[NAME].md`
- Agent file: `PLUGIN_ROOT_PATH/agents/workflow-[NAME]-agent.md`
- Run anytime with: `/workflow-[NAME]`

Use AskUserQuestion:
1. "Run now" - Execute the workflow immediately
2. "Done" - Finish without running

If user chooses "Run now":
- Tell user you're setting up the workflow
- Execute each pane creation step from the generated agent
- Report success with pane summary

## ASCII Diagram Templates

### 2-pane layout:
```
┌────────────────┬────────────────┐
│                │                │
│     main       │    [pane1]     │
│  (Claude Code) │   [command1]   │
│                │                │
└────────────────┴────────────────┘
```

### 3-pane layout:
```
┌────────────────┬────────────────┐
│                │    [pane1]     │
│     main       ├────────────────┤
│  (Claude Code) │    [pane2]     │
└────────────────┴────────────────┘
```

### 4-pane layout:
```
┌────────────────┬────────────────┐
│                │    [pane1]     │
│     main       ├────────────────┤
│  (Claude Code) │    [pane2]     │
│                ├────────────────┤
│                │    [pane3]     │
└────────────────┴────────────────┘
```

## Error Handling

- **Invalid project path**: Inform user and suggest checking the path
- **No scripts detected**: Fall back to generic layout, let user specify commands
- **File write error**: Inform user about permission issues
- **Duplicate workflow name**: Ask user to overwrite or choose new name
- **Invalid pane name**: Sanitize (remove spaces/special chars) or ask for new name
