#!/bin/bash
# List recent Claude Code sessions for the current project
# Output format:
#   Line 1: STATUS:OK|NOT_IN_TMUX|NO_SESSIONS
#   Line 2: SESSION_COUNT:N
#   Lines 3+: SESSION:uuid|timestamp|first_message_preview

# Check if running in tmux
if [ -z "$TMUX" ]; then
    echo "STATUS:NOT_IN_TMUX"
    exit 0
fi

# Convert current path to Claude Code project directory name
# Slashes become hyphens, underscores become hyphens
PROJECT_DIR=$(echo "$PWD" | sed 's|/|-|g' | sed 's|_|-|g')
SESSIONS_PATH="$HOME/.claude/projects/${PROJECT_DIR}"

# Check if project directory exists and has sessions
if [ ! -d "$SESSIONS_PATH" ]; then
    echo "STATUS:NO_SESSIONS"
    echo "DEBUG:Directory not found: $SESSIONS_PATH"
    exit 0
fi

# Get the 5 most recent session files
SESSION_FILES=$(ls -t "$SESSIONS_PATH"/*.jsonl 2>/dev/null | head -5)

if [ -z "$SESSION_FILES" ]; then
    echo "STATUS:NO_SESSIONS"
    echo "DEBUG:No .jsonl files in $SESSIONS_PATH"
    exit 0
fi

# Count sessions
SESSION_COUNT=$(echo "$SESSION_FILES" | wc -l | tr -d ' ')

echo "STATUS:OK"
echo "SESSION_COUNT:$SESSION_COUNT"

# Process each session file
while IFS= read -r file; do
    # Extract session ID from filename
    SESSION_ID=$(basename "$file" .jsonl)

    # Get last modified timestamp
    if [[ "$OSTYPE" == "darwin"* ]]; then
        TIMESTAMP=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file")
    else
        TIMESTAMP=$(stat -c "%y" "$file" | cut -d'.' -f1)
    fi

    # Extract first user message (not meta, not command)
    # Look for type:user without isMeta:true and without command-name
    FIRST_MSG=$(grep -m1 '"type":"user"' "$file" | \
        grep -v '"isMeta":true' | \
        grep -v 'command-name' | \
        head -1)

    # If no regular user message, try to get any user message
    if [ -z "$FIRST_MSG" ]; then
        FIRST_MSG=$(grep -m1 '"type":"user"' "$file" | head -1)
    fi

    # Extract message content - look for the content field
    MSG_PREVIEW=""
    if [ -n "$FIRST_MSG" ]; then
        # Try to extract content from the message
        MSG_PREVIEW=$(echo "$FIRST_MSG" | \
            sed 's/.*"content":"\([^"]*\)".*/\1/' | \
            head -c 60 | \
            tr '\n' ' ' | \
            sed 's/\\n/ /g')
    fi

    # If still empty, mark as unknown
    if [ -z "$MSG_PREVIEW" ] || [ "$MSG_PREVIEW" = "$FIRST_MSG" ]; then
        MSG_PREVIEW="(session start)"
    fi

    # Output session info (use | as delimiter since it's unlikely in messages)
    echo "SESSION:${SESSION_ID}|${TIMESTAMP}|${MSG_PREVIEW}"
done <<< "$SESSION_FILES"
