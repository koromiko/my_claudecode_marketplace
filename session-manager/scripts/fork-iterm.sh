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

# How long (seconds) to wait for the forked Claude session to come up.
FORK_VERIFY_TIMEOUT="${FORK_VERIFY_TIMEOUT:-10}"

# Failure markers that indicate the fork command was sent but Claude did not start.
FORK_FAIL_RE='command not found|no such file or directory|no conversation found|could not (find|resume)|failed to (load|resume)|invalid session|permission denied'
# Positive markers that the Claude Code TUI is up (used as a fallback / iTerm signal).
FORK_OK_RE='Claude Code|/help for help|esc to interrupt|shortcuts'

# Verify a forked session inside a tmux pane.
# Echoes one of: verified | failed
# Primary signal: the pane's foreground process is no longer the login shell
# (claude has taken over). Failure markers in the pane buffer short-circuit to failed.
verify_fork_tmux() {
    local pane_id="$1"
    local i=0 content cur
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        # Pane vanished => the shell (and any fork) exited.
        if ! tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane_id}$"; then
            echo failed
            return
        fi

        content=$(tmux capture-pane -t "$pane_id" -p -S -200 2>/dev/null)
        if printf '%s' "$content" | grep -qiE "$FORK_FAIL_RE"; then
            echo failed
            return
        fi

        cur=$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null)
        case "$cur" in
            zsh | -zsh | bash | -bash | sh | -sh | fish | login | "")
                # Still sitting at the login shell — keep waiting.
                ;;
            *)
                # Some process (node/claude) is in the foreground — fork took.
                echo verified
                return
                ;;
        esac
    done

    # Timed out still at the shell prompt: last-chance content check, else failed.
    content=$(tmux capture-pane -t "$pane_id" -p -S -200 2>/dev/null)
    if printf '%s' "$content" | grep -qiE "$FORK_OK_RE"; then
        echo verified
    else
        echo failed
    fi
}

# Verify a forked session inside an iTerm tab (best effort).
# Echoes one of: verified | failed | unverified
# iTerm has no reliable per-tab foreground-process introspection, so we scan the
# current session's visible contents for failure / success markers.
verify_fork_iterm() {
    local i=0 content
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        content=$(osascript 2>/dev/null <<'OSA'
tell application "iTerm" to tell current window to tell current session to contents
OSA
)
        if printf '%s' "$content" | grep -qiE "$FORK_FAIL_RE"; then
            echo failed
            return
        fi
        if printf '%s' "$content" | grep -qiE "$FORK_OK_RE"; then
            echo verified
            return
        fi
    done

    # Could not positively confirm and saw no failure marker.
    echo unverified
}

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
            echo "Using project ID (actual conversation session file)" >&2
            echo "$project_id"
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
    # Open an interactive shell first, then send the fork command via send-keys.
    # This ensures: (1) .zshrc is sourced so `claude` is in PATH,
    # (2) the pane stays open if the command exits unexpectedly.
    pane_id=$(tmux split-window -h -P -F '#{pane_id}' -c "$WORKING_DIR" "$DEFAULT_SHELL")

    if [ $? -eq 0 ] && [ -n "$pane_id" ]; then
        # Brief delay to ensure shell is ready, then send the fork command
        sleep 0.3
        tmux send-keys -t "$pane_id" "$fork_cmd" Enter

        # Verify the forked Claude session actually started before reporting success.
        echo "Verifying forked session started (up to ${FORK_VERIFY_TIMEOUT}s)..." >&2
        fork_status=$(verify_fork_tmux "$pane_id")

        if [ "$fork_status" = "verified" ]; then
            # Register the forked session only after it is confirmed up.
            registry_add "$managed_id" "tmux" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
            echo "Session forked successfully into new tmux pane (verified)." >&2
            # Output only the managed ID on stdout for easy parsing
            echo "$managed_id"
            exit 0
        else
            echo "Error: Fork command was sent but the Claude session did not start in the new tmux pane." >&2
            echo "----- pane output (last 50 lines) -----" >&2
            tmux capture-pane -t "$pane_id" -p -S -50 2>/dev/null >&2
            echo "---------------------------------------" >&2
            echo "The pane was left open for inspection; it was NOT registered as a managed session." >&2
            exit 1
        fi
    else
        echo "Error: Failed to create new tmux pane." >&2
        exit 1
    fi
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

if [ $? -ne 0 ]; then
    echo "Error: Failed to create new iTerm tab." >&2
    exit 1
fi

# Verify the forked Claude session actually started before reporting success.
echo "Verifying forked session started (up to ${FORK_VERIFY_TIMEOUT}s)..." >&2
fork_status=$(verify_fork_iterm)

case "$fork_status" in
    verified)
        registry_add "$managed_id" "iterm" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
        echo "Session forked successfully into new iTerm tab (verified)." >&2
        # Output only the managed ID on stdout for easy parsing
        echo "$managed_id"
        ;;
    unverified)
        # iTerm tab introspection is best-effort; the tab opened and the command
        # was sent, but we could not positively confirm the Claude TUI came up.
        registry_add "$managed_id" "iterm" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
        echo "Warning: iTerm tab created and fork command sent, but the Claude session could not be positively confirmed (iTerm tab introspection is best-effort). Please verify the new tab manually." >&2
        # Still emit the managed ID so the (likely-running) session can be managed.
        echo "$managed_id"
        ;;
    *)
        echo "Error: Fork command was sent but the Claude session did not start in the new iTerm tab." >&2
        echo "The tab was left open for inspection; it was NOT registered as a managed session." >&2
        exit 1
        ;;
esac
