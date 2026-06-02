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

# True if NAME is a login/interactive shell (i.e. NOT a forked child process).
# A leading "-" (login shell) and any directory prefix are stripped before matching.
is_shell_name() {
    local n="${1##*/}"
    n="${n#-}"
    case "$n" in
        zsh | bash | sh | fish | dash | ksh | tcsh | csh | login | "") return 0 ;;
        *) return 1 ;;
    esac
}

# True if the given tty has a non-shell process in the FOREGROUND process group
# (the "+" flag in ps stat). This is the content-independent signal that `claude`
# (a node process) took over the terminal — we deliberately do NOT scan rendered
# output, because a forked session displays the prior conversation verbatim and that
# text can contain arbitrary "command not found" / "Claude Code" substrings.
tty_has_nonshell_foreground() {
    local tty="${1#/dev/}" stat comm
    [ -n "$tty" ] || return 1
    while read -r stat comm; do
        case "$stat" in
            *+*) ;;        # foreground process group
            *) continue ;;
        esac
        if ! is_shell_name "$comm"; then
            return 0
        fi
    done < <(ps -t "$tty" -o stat=,comm= 2>/dev/null)
    return 1
}

# Verify a forked session inside a tmux pane. Echoes: verified | failed
# Signal: the pane's foreground process is no longer the login shell (claude/node
# took over). Pane disappearing => the shell and fork exited => failed.
verify_fork_tmux() {
    local pane_id="$1"
    local i=0 cur
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        # Pane vanished => the shell (and any fork) exited.
        if ! tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane_id}$"; then
            echo failed
            return
        fi

        cur=$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null)
        if ! is_shell_name "$cur"; then
            # Some process (node/claude) is in the foreground — fork took.
            echo verified
            return
        fi
    done

    # Timed out still sitting at the login shell — claude never took over.
    echo failed
}

# Verify a forked session inside an iTerm tab. Echoes: verified | failed
# Signal: read the *specific* session's tty (by its iTerm session id, so focus is
# irrelevant) and check whether a non-shell process holds the foreground — the same
# content-independent signal used for tmux. Session id gone => fork exited => failed.
verify_fork_iterm() {
    local session_id="$1"
    local i=0 tty
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        tty=$(osascript 2>/dev/null <<OSA
tell application "iTerm"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (id of s) is "$session_id" then return (tty of s)
            end repeat
        end repeat
    end repeat
    return "__SESSION_NOT_FOUND__"
end tell
OSA
)
        if [ "$tty" = "__SESSION_NOT_FOUND__" ] || [ -z "$tty" ]; then
            # The forked tab/session no longer exists — the command exited.
            echo failed
            return
        fi
        if tty_has_nonshell_foreground "$tty"; then
            echo verified
            return
        fi
    done

    # Timed out: the tab is alive but only a shell is in the foreground.
    echo failed
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

# Fork session in new iTerm tab using AppleScript, capturing the real iTerm session
# id so the tab can be tracked and verified precisely (independent of focus).
pane_id=$(osascript 2>/dev/null <<EOF
tell application "iTerm"
    tell current window
        create tab with default profile
        tell current session
            write text "$DEFAULT_SHELL -c 'cd \"$WORKING_DIR\" && $fork_cmd'"
            return id of it
        end tell
    end tell
end tell
EOF
)

if [ $? -ne 0 ] || [ -z "$pane_id" ]; then
    echo "Error: Failed to create new iTerm tab." >&2
    exit 1
fi

# Verify the forked Claude session actually started before reporting success.
echo "Verifying forked session started (up to ${FORK_VERIFY_TIMEOUT}s)..." >&2
fork_status=$(verify_fork_iterm "$pane_id")

if [ "$fork_status" = "verified" ]; then
    registry_add "$managed_id" "iterm" "$pane_id" "$WORKING_DIR" "$fork_cmd" "$timestamp"
    echo "Session forked successfully into new iTerm tab (verified)." >&2
    # Output only the managed ID on stdout for easy parsing
    echo "$managed_id"
else
    echo "Error: Fork command was sent but the Claude session did not start in the new iTerm tab." >&2
    echo "The tab was left open for inspection; it was NOT registered as a managed session." >&2
    exit 1
fi
