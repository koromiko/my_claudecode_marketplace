#!/bin/bash

# Fork Claude Code session into a new tmux pane or iTerm tab
# Auto-detects session ID from Claude's session files
# Returns a managed ID for tracking via session-manager.sh

# Check if running on macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "Error: This script only works on macOS."
    exit 1
fi

# Get the working directory (passed as argument or use current)
WORKING_DIR="${1:-$(pwd)}"

# Detect the user's default shell
# Priority: $SHELL env var -> dscl lookup -> fallback to /bin/zsh
if [ -n "$SHELL" ]; then
    DEFAULT_SHELL="$SHELL"
elif command -v dscl &>/dev/null; then
    # macOS: lookup from directory services
    DEFAULT_SHELL=$(dscl . -read /Users/"$(whoami)" UserShell | awk '{print $2}')
fi
# Fallback to zsh if detection failed
DEFAULT_SHELL="${DEFAULT_SHELL:-/bin/zsh}"

# Registry setup (shared with session-manager.sh)
REGISTRY_DIR="$HOME/.claude/session-manager"
REGISTRY_FILE="$REGISTRY_DIR/registry.json"
mkdir -p "$REGISTRY_DIR"

# Initialize registry if it doesn't exist
init_registry() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        cat > "$REGISTRY_FILE" << 'EOF'
{
  "panes": {},
  "version": "1.0.0"
}
EOF
    fi
}

# Generate a unique managed ID
generate_id() {
    echo "sm-$(head -c 6 /dev/urandom | base64 | tr -dc 'a-z0-9' | head -c 6)"
}

# Get current timestamp in ISO format
get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Add a pane to the registry
registry_add() {
    local id="$1"
    local type="$2"
    local pane_id="$3"
    local working_dir="$4"
    local initial_cmd="$5"
    local timestamp="$6"

    python3 - "$REGISTRY_FILE" "$id" "$type" "$pane_id" "$working_dir" "$initial_cmd" "$timestamp" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
managed_id = sys.argv[2]
terminal_type = sys.argv[3]
pane_id = sys.argv[4]
working_dir = sys.argv[5]
initial_cmd = sys.argv[6]
timestamp = sys.argv[7]

try:
    with open(registry_file, 'r') as f:
        registry = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    registry = {'panes': {}, 'version': '1.0.0'}

registry['panes'][managed_id] = {
    'id': managed_id,
    'type': terminal_type,
    'pane_id': pane_id,
    'created_at': timestamp,
    'working_directory': working_dir,
    'initial_command': initial_cmd,
    'status': 'active'
}

with open(registry_file, 'w') as f:
    json.dump(registry, f, indent=2)
PYEOF
}

# Initialize registry
init_registry

# Detect session ID via debug symlink (primary method)
detect_session_id_symlink() {
    local debug_latest="$HOME/.claude/debug/latest"

    if [ ! -L "$debug_latest" ]; then
        return 1
    fi

    local session_id
    session_id=$(basename "$(readlink "$debug_latest")" .txt)

    if [ -z "$session_id" ]; then
        return 1
    fi

    echo "$session_id"
}

# Detect session ID via project files (fallback method)
detect_session_id_project_files() {
    local working_dir="$1"

    # Encode the path for Claude's directory structure
    local encoded_path
    encoded_path=$(echo "$working_dir" | sed 's|/|-|g' | sed 's|_|-|g')

    local sessions_dir="$HOME/.claude/projects/$encoded_path"

    if [ ! -d "$sessions_dir" ]; then
        return 1
    fi

    # Find most recently modified .jsonl file
    local session_file
    session_file=$(ls -t "$sessions_dir"/*.jsonl 2>/dev/null | head -1)

    if [ -z "$session_file" ]; then
        return 1
    fi

    local session_id
    session_id=$(basename "$session_file" .jsonl)

    if [ -z "$session_id" ]; then
        return 1
    fi

    echo "$session_id"
}

# Main detection function using dual-track approach
detect_session_id() {
    local working_dir="$1"

    # Try both methods
    local symlink_id=""
    local project_id=""

    symlink_id=$(detect_session_id_symlink 2>/dev/null) || true
    project_id=$(detect_session_id_project_files "$working_dir" 2>/dev/null) || true

    # Decision logic
    if [ -n "$symlink_id" ] && [ -n "$project_id" ]; then
        if [ "$symlink_id" = "$project_id" ]; then
            echo "Session ID confirmed by both methods: $symlink_id" >&2
            echo "$symlink_id"
        else
            echo "Session IDs differ - symlink: $symlink_id, project: $project_id" >&2
            echo "Using symlink ID (more reliable for current session)" >&2
            echo "$symlink_id"
        fi
    elif [ -n "$symlink_id" ]; then
        echo "Session ID from debug symlink: $symlink_id" >&2
        echo "$symlink_id"
    elif [ -n "$project_id" ]; then
        echo "Session ID from project files: $project_id" >&2
        echo "$project_id"
    else
        echo "Error: Could not detect session ID using any method."
        echo "Tried:"
        echo "  - ~/.claude/debug/latest symlink (not found or invalid)"
        echo "  - Project files in ~/.claude/projects/ (not found)"
        exit 1
    fi
}

# Check if running inside tmux
if [ -n "$TMUX" ]; then
    SESSION_ID=$(detect_session_id "$WORKING_DIR")

    # Check if detect_session_id returned an error (starts with "Error:")
    if [[ "$SESSION_ID" == Error:* ]]; then
        echo "$SESSION_ID" >&2
        exit 1
    fi

    echo "Detected session: $SESSION_ID" >&2

    # Generate managed ID and timestamp
    managed_id=$(generate_id)
    timestamp=$(get_timestamp)
    fork_cmd="claude -r $SESSION_ID --fork-session"

    # Fork session in new tmux pane (horizontal split) and capture pane ID
    # Use the user's default shell for the new session
    pane_id=$(tmux split-window -h -P -F '#{pane_id}' "$DEFAULT_SHELL -c 'cd \"$WORKING_DIR\" && $fork_cmd'")

    if [ $? -eq 0 ] && [ -n "$pane_id" ]; then
        # Register the forked session
        registry_add "$managed_id" "tmux" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
        echo "Session forked successfully into new tmux pane." >&2
        # Output only the managed ID on stdout for easy parsing
        echo "$managed_id"
    else
        echo "Error: Failed to create new tmux pane." >&2
        exit 1
    fi
    exit 0
fi

# Not in tmux - check for iTerm

# Check if iTerm is installed
if [ ! -d "/Applications/iTerm.app" ]; then
    echo "Error: iTerm2 is not installed and not running in tmux."
    echo "Please either:"
    echo "  - Run this command inside a tmux session, or"
    echo "  - Install iTerm2 from https://iterm2.com/ or via:"
    echo "    brew install --cask iterm2"
    exit 1
fi

# Check if iTerm is running (using osascript since pgrep doesn't reliably detect iTerm2 on macOS)
if ! osascript -e 'tell application "System Events" to (name of processes) contains "iTerm2"' 2>/dev/null | grep -q "true"; then
    echo "Error: iTerm2 is not running and not running in tmux."
    echo "Please either:"
    echo "  - Run this command inside a tmux session, or"
    echo "  - Start iTerm2 and run this command again."
    exit 1
fi

# Detect session ID using shared function
SESSION_ID=$(detect_session_id "$WORKING_DIR")

# Check if detect_session_id returned an error (starts with "Error:")
if [[ "$SESSION_ID" == Error:* ]]; then
    echo "$SESSION_ID" >&2
    exit 1
fi

echo "Detected session: $SESSION_ID" >&2

# Generate managed ID and timestamp
managed_id=$(generate_id)
timestamp=$(get_timestamp)
fork_cmd="claude -r $SESSION_ID --fork-session"
# Generate a unique pane identifier for iTerm (since we can't get actual tab ID)
pane_id="iterm-$(date +%s)"

# Fork session in new iTerm tab using AppleScript
# Use the user's default shell for the new session
osascript <<EOF
tell application "iTerm"
    tell current window
        create tab with default profile
        tell current session
            write text "$DEFAULT_SHELL -c 'cd \"$WORKING_DIR\" && $fork_cmd'"
        end tell
    end tell
end tell
EOF

if [ $? -eq 0 ]; then
    # Register the forked session
    registry_add "$managed_id" "iterm" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
    echo "Session forked successfully into new iTerm tab." >&2
    # Output only the managed ID on stdout for easy parsing
    echo "$managed_id"
else
    echo "Error: Failed to create new iTerm tab." >&2
    exit 1
fi
