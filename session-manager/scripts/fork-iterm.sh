#!/bin/bash

# Fork Claude Code session into a new tmux pane or iTerm tab
# Auto-detects session ID from Claude's session files
# Returns a managed ID for tracking via session-manager.sh

# Check if running on macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "Error: This script only works on macOS."
    exit 1
fi

# --- Arguments ------------------------------------------------------------
# Usage: fork-iterm.sh [current_dir] [--fork-dir <dir>] [--relocate] [--resolve]
#   current_dir   The directory the caller is in (default: pwd). Used only to
#                 detect drift from the session's own directory and as the
#                 --relocate target default.
#   --fork-dir D  Launch the fork from D instead of the session's own cwd.
#   --relocate    Copy the session record into the fork dir's project before
#                 forking, so `claude -r` resolves there (Approach B). Without
#                 this, the fork dir must already own the session.
#   --resolve     Print resolution info (SESSION_ID, OWNER_CWD, CURRENT_DIR,
#                 MATCH) and exit 0, without forking. Lets the /fork command
#                 decide whether to prompt the user for A vs B.
CURRENT_DIR=""
FORK_DIR_OPT=""
RELOCATE=0
RESOLVE_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --fork-dir) FORK_DIR_OPT="$2"; shift 2 ;;
        --relocate) RELOCATE=1; shift ;;
        --resolve)  RESOLVE_ONLY=1; shift ;;
        --) shift; break ;;
        -*) echo "Error: unknown option: $1" >&2; exit 2 ;;
        *)  [ -z "$CURRENT_DIR" ] && CURRENT_DIR="$1"; shift ;;
    esac
done
CURRENT_DIR="${CURRENT_DIR:-$(pwd)}"

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

# --- Session resolution / resume pre-flight helpers -----------------------
# `claude -r <id>` resolves a session ONLY from the directory that owns it: it
# looks up ~/.claude/projects/<cwd-encoded>/<id>.jsonl for the *current* cwd
# (verified empirically — resuming from any other directory fails with "No
# conversation found", even though the record exists elsewhere). The working
# directory can also drift during a session. So we don't trust the caller's pwd:
# we resolve the session by id, find the project that actually owns its record,
# and launch the fork from that record's real cwd (Approach A). Optionally we can
# copy the record into another directory's project and fork there (--relocate,
# Approach B) — at the cost of the conversation's historical paths no longer
# matching the new cwd.
#
# (Why not verify success by watching for a new transcript file? Empirically, an
# interactive fork loads the conversation into the TUI but does NOT write its new
# session .jsonl until the first prompt is submitted — only `--print` mode flushes
# it immediately — so there is no startup file to watch. And a *failed* resume
# keeps node/claude in the foreground showing an error rather than exiting, so
# "a process took over the terminal" cannot distinguish success from failure.
# Hence: validate resumability up front, then confirm the process launched and
# stayed up.)

# Map a working directory to Claude's encoded project session directory.
# Mirrors detect_session_id_project_files' encoding.
project_sessions_dir() {
    local working_dir="$1"
    local encoded_path
    encoded_path=$(echo "$working_dir" | sed 's|/|-|g' | sed 's|_|-|g')
    echo "$HOME/.claude/projects/$encoded_path"
}

# True if SESSION_ID has a resumable transcript under the given dir's project dir.
session_resumable_in() {
    local session_id="$1" working_dir="$2"
    local dir
    dir=$(project_sessions_dir "$working_dir")
    [ -f "$dir/$session_id.jsonl" ]
}

# Echo the transcript file that owns SESSION_ID, searching ALL projects. The
# encoded project-dir name is lossy (both / and _ map to -), so we find the
# record by id rather than by re-encoding a path. Empty output => not found.
find_session_owner_file() {
    local session_id="$1"
    ls "$HOME/.claude/projects"/*/"$session_id.jsonl" 2>/dev/null | head -1
}

# Echo the real launch cwd recorded inside a transcript (its "cwd" field). This
# is the canonical directory the session is resumable from. Empty if not present.
session_launch_cwd() {
    local owner_file="$1"
    [ -n "$owner_file" ] && [ -f "$owner_file" ] || return 0
    grep -m1 -o '"cwd":"[^"]*"' "$owner_file" | sed 's/.*"cwd":"//; s/"$//'
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
FORK_VERIFY_TIMEOUT="${FORK_VERIFY_TIMEOUT:-20}"
# Consecutive 1s checks the forked process must hold the foreground before we call
# it verified. This stabilization window rejects a command that briefly launches
# then exits/crashes (e.g. `claude` not on PATH, or an immediate launch error,
# which fall back to the shell prompt).
FORK_STABILIZE_CHECKS="${FORK_STABILIZE_CHECKS:-3}"

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
# Signal: claude/node replaces the login shell in the pane foreground AND holds it
# for FORK_STABILIZE_CHECKS consecutive checks. A command that fails to launch
# (claude not on PATH, immediate crash) falls back to the shell prompt — the streak
# never accrues, so it is reported failed. Pane disappearing => the process exited
# => failed. (Resume *validity* is pre-checked via session_resumable_in.)
verify_fork_tmux() {
    local pane_id="$1"
    local i=0 cur streak=0
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        # Pane vanished => the shell (and any fork) exited.
        if ! tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane_id}$"; then
            echo failed
            return
        fi

        cur=$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null)
        if is_shell_name "$cur"; then
            streak=0   # still (or back) at the login shell — claude not up / exited
        else
            streak=$((streak + 1))
            if [ "$streak" -ge "$FORK_STABILIZE_CHECKS" ]; then
                echo verified
                return
            fi
        fi
    done

    # Timed out: claude never held the foreground long enough.
    echo failed
}

# Echo the tty path of the iTerm session with the given id, or "__SESSION_NOT_FOUND__".
# Looks the session up by its iTerm session id, so the result is focus-independent.
iterm_session_tty() {
    local session_id="$1"
    osascript 2>/dev/null <<OSA
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
}

# Verify a forked session inside an iTerm tab. Echoes: verified | failed
# Same contract as verify_fork_tmux: the tab's tty must hold a non-shell (claude)
# foreground process for FORK_STABILIZE_CHECKS consecutive checks. The tab is
# located by its iTerm session id (focus-independent). Session id gone => the
# command exited => failed. (Resume *validity* is pre-checked via session_resumable_in.)
verify_fork_iterm() {
    local session_id="$1"
    local i=0 tty streak=0
    while [ "$i" -lt "$FORK_VERIFY_TIMEOUT" ]; do
        sleep 1
        i=$((i + 1))

        tty=$(iterm_session_tty "$session_id")
        if [ "$tty" = "__SESSION_NOT_FOUND__" ] || [ -z "$tty" ]; then
            # The forked tab/session no longer exists — the command exited.
            echo failed
            return
        fi

        if tty_has_nonshell_foreground "$tty"; then
            streak=$((streak + 1))
            if [ "$streak" -ge "$FORK_STABILIZE_CHECKS" ]; then
                echo verified
                return
            fi
        else
            streak=0   # still (or back) at the login shell — claude not up / exited
        fi
    done

    # Timed out: claude never held the foreground long enough.
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

# Allow tests to source this file for its helper/verify functions without running
# the fork flow: `FORK_LIB_ONLY=1 source fork-iterm.sh`.
if [ "${FORK_LIB_ONLY:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Resolve the session and the directory to fork from -------------------
# The authoritative current session id is in the environment when run inside
# Claude; fall back to the project/symlink heuristics for older CLIs or
# out-of-session use.
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(detect_session_id "$CURRENT_DIR")
    if [[ "$SESSION_ID" == Error:* ]]; then
        echo "$SESSION_ID" >&2
        exit 1
    fi
fi

# Find the project that actually owns the record, and its real launch cwd.
OWNER_FILE=$(find_session_owner_file "$SESSION_ID")
if [ -z "$OWNER_FILE" ]; then
    echo "Error: no transcript found for session $SESSION_ID in any project." >&2
    echo "  (searched ~/.claude/projects/*/$SESSION_ID.jsonl)" >&2
    exit 1
fi
OWNER_CWD=$(session_launch_cwd "$OWNER_FILE")
[ -n "$OWNER_CWD" ] || OWNER_CWD="$CURRENT_DIR"

# Where to fork from: explicit --fork-dir wins, else the session's own cwd.
FORK_DIR="${FORK_DIR_OPT:-$OWNER_CWD}"

# --resolve: report and exit (lets /fork decide whether to prompt for A vs B).
if [ "$RESOLVE_ONLY" = "1" ]; then
    if [ "$OWNER_CWD" = "$CURRENT_DIR" ]; then match=yes; else match=no; fi
    echo "SESSION_ID=$SESSION_ID"
    echo "OWNER_CWD=$OWNER_CWD"
    echo "CURRENT_DIR=$CURRENT_DIR"
    echo "MATCH=$match"
    exit 0
fi

# Approach B: copy the record into the fork dir's project so `claude -r` resolves
# there. Copy (never move) — the source session is live when forking it.
if [ "$RELOCATE" = "1" ] && [ "$FORK_DIR" != "$OWNER_CWD" ]; then
    relocate_dst=$(project_sessions_dir "$FORK_DIR")
    mkdir -p "$relocate_dst"
    if ! cp "$OWNER_FILE" "$relocate_dst/$SESSION_ID.jsonl"; then
        echo "Error: failed to copy session record into $relocate_dst for relocate." >&2
        exit 1
    fi
    echo "Relocated: copied session $SESSION_ID record into $FORK_DIR's project." >&2
    echo "Note: the conversation's historical paths still refer to $OWNER_CWD." >&2
fi

# The fork directory must exist and must own the record by now.
if [ ! -d "$FORK_DIR" ]; then
    echo "Error: fork directory does not exist: $FORK_DIR" >&2
    [ "$FORK_DIR" = "$OWNER_CWD" ] && echo "  (the session's original directory may have been moved or deleted.)" >&2
    exit 1
fi
if ! session_resumable_in "$SESSION_ID" "$FORK_DIR"; then
    echo "Error: session $SESSION_ID is not resumable from $FORK_DIR" >&2
    echo "  (no transcript at $(project_sessions_dir "$FORK_DIR")/$SESSION_ID.jsonl)" >&2
    if [ -n "$FORK_DIR_OPT" ] && [ "$RELOCATE" != "1" ]; then
        echo "  re-run with --relocate to copy the session record there first." >&2
    fi
    exit 1
fi

echo "Forking session $SESSION_ID from $FORK_DIR" >&2

# Common managed id / timestamp / fork command (used by both tmux and iTerm paths).
managed_id=$(generate_id)
timestamp=$(get_timestamp)
fork_cmd="claude -r $SESSION_ID --fork-session"

# Check if running inside tmux
if [ -n "$TMUX" ]; then
    # Fork session in new tmux pane (horizontal split) and capture pane ID
    # Open an interactive shell first, then send the fork command via send-keys.
    # This ensures: (1) .zshrc is sourced so `claude` is in PATH,
    # (2) the pane stays open if the command exits unexpectedly.
    pane_id=$(tmux split-window -h -P -F '#{pane_id}' -c "$FORK_DIR" "$DEFAULT_SHELL")

    if [ $? -eq 0 ] && [ -n "$pane_id" ]; then
        # Brief delay to ensure shell is ready, then send the fork command
        sleep 0.3
        tmux send-keys -t "$pane_id" "$fork_cmd" Enter

        # Verify the forked Claude session actually started before reporting success.
        echo "Verifying forked session started (up to ${FORK_VERIFY_TIMEOUT}s)..." >&2
        fork_status=$(verify_fork_tmux "$pane_id")

        if [ "$fork_status" = "verified" ]; then
            # Register the forked session only after it is confirmed up.
            registry_add "$managed_id" "tmux" "$pane_id" "$FORK_DIR" "$fork_cmd" "$timestamp"
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

# Fork session in new iTerm tab using AppleScript, capturing the real iTerm session
# id so the tab can be tracked and verified precisely (independent of focus).
pane_id=$(osascript 2>/dev/null <<EOF
tell application "iTerm"
    tell current window
        create tab with default profile
        tell current session
            write text "$DEFAULT_SHELL -c 'cd \"$FORK_DIR\" && $fork_cmd'"
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
    registry_add "$managed_id" "iterm" "$pane_id" "$FORK_DIR" "$fork_cmd" "$timestamp"
    echo "Session forked successfully into new iTerm tab (verified)." >&2
    # Output only the managed ID on stdout for easy parsing
    echo "$managed_id"
else
    echo "Error: Fork command was sent but the Claude session did not start in the new iTerm tab." >&2
    echo "The tab was left open for inspection; it was NOT registered as a managed session." >&2
    exit 1
fi
