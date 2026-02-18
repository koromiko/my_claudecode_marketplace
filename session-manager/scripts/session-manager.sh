#!/bin/bash

# Session Manager - Unified script for managing tmux panes and iTerm tabs
# Subcommands: run, capture, send, list, status, cleanup

set -e

REGISTRY_DIR="$HOME/.claude/session-manager"
REGISTRY_FILE="$REGISTRY_DIR/registry.json"

# Ensure registry directory exists
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

# Detect terminal type: "tmux" or "iterm"
detect_terminal() {
    if [ -n "$TMUX" ]; then
        echo "tmux"
    elif [ -d "/Applications/iTerm.app" ]; then
        # Check if iTerm is running
        if osascript -e 'tell application "System Events" to (name of processes) contains "iTerm2"' 2>/dev/null | grep -q "true"; then
            echo "iterm"
        else
            echo "none"
        fi
    else
        echo "none"
    fi
}

# Detect the user's default shell
# Priority: $SHELL env var -> dscl lookup -> fallback to /bin/zsh
detect_default_shell() {
    if [ -n "$SHELL" ]; then
        echo "$SHELL"
    elif command -v dscl &>/dev/null; then
        # macOS: lookup from directory services
        dscl . -read /Users/"$(whoami)" UserShell | awk '{print $2}'
    else
        echo "/bin/zsh"
    fi
}

DEFAULT_SHELL=$(detect_default_shell)

# Python helper for JSON manipulation (avoids jq dependency)
python_json() {
    python3 "$@"
}

# Add a pane to the registry
registry_add() {
    local id="$1"
    local type="$2"
    local pane_id="$3"
    local working_dir="$4"
    local initial_cmd="$5"
    local timestamp="$6"

    python_json - "$REGISTRY_FILE" "$id" "$type" "$pane_id" "$working_dir" "$initial_cmd" "$timestamp" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
managed_id = sys.argv[2]
terminal_type = sys.argv[3]
pane_id = sys.argv[4]
working_dir = sys.argv[5]
initial_cmd = sys.argv[6]
timestamp = sys.argv[7]

with open(registry_file, 'r') as f:
    registry = json.load(f)

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

# Get pane info from registry
registry_get() {
    local id="$1"
    python_json - "$REGISTRY_FILE" "$id" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
managed_id = sys.argv[2]

with open(registry_file, 'r') as f:
    registry = json.load(f)

if managed_id in registry['panes']:
    pane = registry['panes'][managed_id]
    print(json.dumps(pane))
else:
    print('null')
PYEOF
}

# Remove pane from registry
registry_remove() {
    local id="$1"
    python_json - "$REGISTRY_FILE" "$id" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
managed_id = sys.argv[2]

with open(registry_file, 'r') as f:
    registry = json.load(f)

if managed_id in registry['panes']:
    del registry['panes'][managed_id]

with open(registry_file, 'w') as f:
    json.dump(registry, f, indent=2)
PYEOF
}

# List all panes from registry
registry_list() {
    python_json - "$REGISTRY_FILE" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]

with open(registry_file, 'r') as f:
    registry = json.load(f)

for managed_id, pane in registry['panes'].items():
    print(f"{pane['id']}\t{pane['type']}\t{pane['pane_id']}\t{pane['status']}\t{pane.get('initial_command', 'N/A')[:50]}")
PYEOF
}

# Check if a tmux pane exists
tmux_pane_exists() {
    local pane_id="$1"
    tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane_id}$"
}

# Get list of all actual tmux panes
get_actual_tmux_panes() {
    if [ -n "$TMUX" ] || command -v tmux &>/dev/null; then
        tmux list-panes -a -F '#{pane_id}' 2>/dev/null || true
    fi
}

# Sync registry with actual pane state
# Returns list of stale IDs (one per line, prefixed with "stale:")
# Args: [auto_remove] - if "true", removes stale entries
sync_registry() {
    local auto_remove="${1:-false}"
    local actual_panes=$(get_actual_tmux_panes)

    python_json - "$REGISTRY_FILE" "$auto_remove" "$actual_panes" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
auto_remove = sys.argv[2] == 'true'
actual_panes_str = sys.argv[3] if len(sys.argv) > 3 else ""
actual_panes = set(actual_panes_str.strip().split('\n')) if actual_panes_str.strip() else set()

try:
    with open(registry_file, 'r') as f:
        registry = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    registry = {'panes': {}, 'version': '1.0.0'}

stale_ids = []
for managed_id, pane in list(registry['panes'].items()):
    if pane['type'] == 'tmux':
        if pane['pane_id'] not in actual_panes:
            stale_ids.append(managed_id)
            if auto_remove:
                del registry['panes'][managed_id]
    # For iTerm entries, we can't reliably check - skip sync for now

if auto_remove and stale_ids:
    with open(registry_file, 'w') as f:
        json.dump(registry, f, indent=2)

for sid in stale_ids:
    print(f"stale:{sid}")
PYEOF
}

# Check if an iTerm session exists (best effort)
iterm_session_exists() {
    local session_id="$1"
    # iTerm sessions are harder to track - we do best effort
    # For now, return true if iTerm is running
    osascript -e 'tell application "System Events" to (name of processes) contains "iTerm2"' 2>/dev/null | grep -q "true"
}

# =============================================================================
# SUBCOMMAND: run
# =============================================================================
cmd_run() {
    local cmd=""
    local working_dir="$(pwd)"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --working-dir)
                working_dir="$2"
                shift 2
                ;;
            *)
                if [ -z "$cmd" ]; then
                    cmd="$1"
                else
                    cmd="$cmd $1"
                fi
                shift
                ;;
        esac
    done

    if [ -z "$cmd" ]; then
        echo "Error: No command specified"
        echo "Usage: session-manager.sh run <command> [--working-dir <path>]"
        exit 1
    fi

    local terminal_type=$(detect_terminal)
    if [ "$terminal_type" = "none" ]; then
        echo "Error: No supported terminal detected (tmux or iTerm)"
        exit 1
    fi

    local managed_id=$(generate_id)
    local timestamp=$(get_timestamp)
    local pane_id=""

    if [ "$terminal_type" = "tmux" ]; then
        # Create new tmux pane with user's shell directly
        pane_id=$(tmux split-window -h -P -F '#{pane_id}' -c "$working_dir" "$DEFAULT_SHELL")

        if [ $? -ne 0 ]; then
            echo "Error: Failed to create tmux pane"
            exit 1
        fi

        # Send the command to the new pane (shell is already the user's shell)
        sleep 0.1  # Brief delay to ensure shell is ready
        tmux send-keys -t "$pane_id" "$cmd" Enter
    else
        # iTerm: Create new tab
        # Generate a unique marker for this session
        pane_id="iterm-$(date +%s)"

        # iTerm uses the user's default shell from their macOS profile
        osascript << EOF
tell application "iTerm"
    tell current window
        create tab with default profile
        tell current session
            write text "cd '$working_dir' && $cmd"
        end tell
    end tell
end tell
EOF
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create iTerm tab"
            exit 1
        fi
    fi

    # Add to registry
    registry_add "$managed_id" "$terminal_type" "$pane_id" "$working_dir" "$cmd" "$timestamp"

    # Output the managed ID
    echo "$managed_id"
}

# =============================================================================
# SUBCOMMAND: capture
# =============================================================================
cmd_capture() {
    local managed_id=""
    local lines=100
    local no_sync=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --lines)
                lines="$2"
                shift 2
                ;;
            --no-sync)
                no_sync=true
                shift
                ;;
            *)
                managed_id="$1"
                shift
                ;;
        esac
    done

    if [ -z "$managed_id" ]; then
        echo "Error: No pane ID specified"
        echo "Usage: session-manager.sh capture <id> [--lines N] [--no-sync]"
        exit 1
    fi

    local pane_info=$(registry_get "$managed_id")
    if [ "$pane_info" = "null" ]; then
        echo "Error: Pane '$managed_id' not found in registry"
        exit 1
    fi

    local terminal_type=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['type'])")
    local pane_id=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['pane_id'])")

    # Sync check for tmux panes
    if [ "$terminal_type" = "tmux" ] && [ "$no_sync" = false ]; then
        local stale_ids=$(sync_registry false)
        if echo "$stale_ids" | grep -q "stale:$managed_id"; then
            echo "Error: Pane '$managed_id' no longer exists (tmux pane closed)"
            echo "Run 'session-manager.sh cleanup' to remove stale entries"
            exit 1
        fi
    fi

    if [ "$terminal_type" = "tmux" ]; then
        # Capture tmux pane content
        if ! tmux_pane_exists "$pane_id"; then
            echo "Error: tmux pane '$pane_id' no longer exists"
            echo "Run 'session-manager.sh cleanup' to remove stale entries"
            exit 1
        fi
        tmux capture-pane -t "$pane_id" -p -S -"$lines"
    else
        # iTerm: Capture is more limited
        echo "Note: iTerm output capture is limited. Showing recent history."
        osascript << EOF
tell application "iTerm"
    tell current window
        tell current session
            contents
        end tell
    end tell
end tell
EOF
    fi
}

# =============================================================================
# SUBCOMMAND: send
# =============================================================================
cmd_send() {
    local managed_id=""
    local cmd=""
    local no_sync=false

    # Check for --no-sync flag first
    local args=()
    for arg in "$@"; do
        if [ "$arg" = "--no-sync" ]; then
            no_sync=true
        else
            args+=("$arg")
        fi
    done

    # First arg is ID, rest is command
    if [ ${#args[@]} -lt 2 ]; then
        echo "Error: Missing arguments"
        echo "Usage: session-manager.sh send <id> <command> [--no-sync]"
        exit 1
    fi

    managed_id="${args[0]}"
    cmd="${args[@]:1}"

    local pane_info=$(registry_get "$managed_id")
    if [ "$pane_info" = "null" ]; then
        echo "Error: Pane '$managed_id' not found in registry"
        exit 1
    fi

    local terminal_type=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['type'])")
    local pane_id=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['pane_id'])")

    # Sync check for tmux panes
    if [ "$terminal_type" = "tmux" ] && [ "$no_sync" = false ]; then
        local stale_ids=$(sync_registry false)
        if echo "$stale_ids" | grep -q "stale:$managed_id"; then
            echo "Error: Pane '$managed_id' no longer exists (tmux pane closed)"
            echo "Run 'session-manager.sh cleanup' to remove stale entries"
            exit 1
        fi
    fi

    if [ "$terminal_type" = "tmux" ]; then
        if ! tmux_pane_exists "$pane_id"; then
            echo "Error: tmux pane '$pane_id' no longer exists"
            echo "Run 'session-manager.sh cleanup' to remove stale entries"
            exit 1
        fi
        tmux send-keys -t "$pane_id" "$cmd" Enter
        echo "Command sent to tmux pane $managed_id"
    else
        osascript << EOF
tell application "iTerm"
    tell current window
        tell current session
            write text "$cmd"
        end tell
    end tell
end tell
EOF
        echo "Command sent to iTerm tab $managed_id"
    fi
}

# =============================================================================
# SUBCOMMAND: list
# =============================================================================
cmd_list() {
    local auto_cleanup=false
    local no_sync=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --auto-cleanup)
                auto_cleanup=true
                shift
                ;;
            --no-sync)
                no_sync=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    # Get stale IDs from sync (optionally auto-remove)
    local stale_ids=""
    if [ "$no_sync" = false ]; then
        stale_ids=$(sync_registry "$auto_cleanup")
    fi

    # Convert stale IDs to a lookup string
    local stale_lookup=""
    if [ -n "$stale_ids" ]; then
        stale_lookup=$(echo "$stale_ids" | sed 's/^stale://' | tr '\n' '|')
    fi

    echo "ID              TYPE    PANE_ID         STATUS  COMMAND"
    echo "--------------------------------------------------------------------------"

    # List with real-time status
    python_json - "$REGISTRY_FILE" "$stale_lookup" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]
stale_lookup = sys.argv[2] if len(sys.argv) > 2 else ""
stale_ids = set(stale_lookup.strip('|').split('|')) if stale_lookup else set()

try:
    with open(registry_file, 'r') as f:
        registry = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    registry = {'panes': {}, 'version': '1.0.0'}

for managed_id, pane in registry['panes'].items():
    # Determine real-time status for tmux panes
    if pane['type'] == 'tmux':
        status = 'stale' if managed_id in stale_ids else 'active'
    else:
        status = pane.get('status', 'unknown')

    cmd = pane.get('initial_command', 'N/A')[:50]
    print(f"{pane['id']}\t{pane['type']}\t{pane['pane_id']}\t{status}\t{cmd}")
PYEOF
}

# =============================================================================
# SUBCOMMAND: status
# =============================================================================
cmd_status() {
    local managed_id="$1"

    if [ -z "$managed_id" ]; then
        echo "Error: No pane ID specified"
        echo "Usage: session-manager.sh status <id>"
        exit 1
    fi

    local pane_info=$(registry_get "$managed_id")
    if [ "$pane_info" = "null" ]; then
        echo "Error: Pane '$managed_id' not found in registry"
        exit 1
    fi

    local terminal_type=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['type'])")
    local pane_id=$(echo "$pane_info" | python3 -c "import json,sys; print(json.load(sys.stdin)['pane_id'])")

    if [ "$terminal_type" = "tmux" ]; then
        if tmux_pane_exists "$pane_id"; then
            echo "active"
        else
            echo "stale"
        fi
    else
        if iterm_session_exists "$pane_id"; then
            echo "active"
        else
            echo "stale"
        fi
    fi
}

# =============================================================================
# SUBCOMMAND: cleanup
# =============================================================================
cmd_cleanup() {
    local removed=0

    # Get list of all managed IDs
    local ids=$(python_json - "$REGISTRY_FILE" << 'PYEOF'
import json
import sys

registry_file = sys.argv[1]

with open(registry_file, 'r') as f:
    registry = json.load(f)

for managed_id in registry['panes'].keys():
    print(managed_id)
PYEOF
)

    for managed_id in $ids; do
        local status=$(cmd_status "$managed_id" 2>/dev/null || echo "stale")
        if [ "$status" = "stale" ]; then
            registry_remove "$managed_id"
            echo "Removed stale pane: $managed_id"
            ((removed++)) || true
        fi
    done

    if [ $removed -eq 0 ]; then
        echo "No stale panes found"
    else
        echo "Cleaned up $removed stale pane(s)"
    fi
}

# =============================================================================
# MAIN
# =============================================================================

# Initialize registry
init_registry

# =============================================================================
# SUBCOMMAND: sync
# =============================================================================
cmd_sync() {
    local auto_remove=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --auto-remove)
                auto_remove=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    local stale_ids=$(sync_registry "$auto_remove")

    if [ -z "$stale_ids" ]; then
        echo "Registry is in sync - no stale entries found"
    else
        local count=$(echo "$stale_ids" | wc -l | tr -d ' ')
        if [ "$auto_remove" = true ]; then
            echo "Removed $count stale entries:"
        else
            echo "Found $count stale entries:"
        fi
        echo "$stale_ids" | sed 's/^stale:/  - /'
        if [ "$auto_remove" = false ]; then
            echo ""
            echo "Run with --auto-remove to clean them up"
        fi
    fi
}

# Check for subcommand
if [ $# -eq 0 ]; then
    echo "Session Manager - Manage tmux panes and iTerm tabs"
    echo ""
    echo "Usage: session-manager.sh <subcommand> [options]"
    echo ""
    echo "Subcommands:"
    echo "  run <cmd> [--working-dir <path>]  Run command in new pane/tab, return managed ID"
    echo "  capture <id> [--lines N]          Capture output from pane (default 100 lines)"
    echo "  send <id> <cmd>                   Send command to existing pane"
    echo "  list [--auto-cleanup] [--no-sync] List all managed panes with real-time status"
    echo "  status <id>                       Check if pane is active/stale"
    echo "  sync [--auto-remove]              Validate registry against actual panes"
    echo "  cleanup                           Remove stale registry entries"
    exit 0
fi

subcommand="$1"
shift

case "$subcommand" in
    run)
        cmd_run "$@"
        ;;
    capture)
        cmd_capture "$@"
        ;;
    send)
        cmd_send "$@"
        ;;
    list)
        cmd_list "$@"
        ;;
    status)
        cmd_status "$@"
        ;;
    sync)
        cmd_sync "$@"
        ;;
    cleanup)
        cmd_cleanup "$@"
        ;;
    *)
        echo "Error: Unknown subcommand '$subcommand'"
        echo "Run 'session-manager.sh' without arguments for usage"
        exit 1
        ;;
esac
