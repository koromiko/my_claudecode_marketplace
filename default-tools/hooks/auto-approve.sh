#!/bin/bash
# Auto-approve tools that need conditional logic beyond native permission rules.
# Used as a PreToolUse hook in Claude Code (matches ALL tools, no matcher filter).
#
# Native permission rules in settings.json handle unconditional allows:
#   WebSearch, ToolSearch, TaskOutput, read-only MCP tools
#
# This hook handles tools that need conditional approval:
#   - Read/Glob/Grep with sensitive-path guard
#   - WebFetch with credential-in-URL guard
#   - Bash with read-only command allowlist + metacharacter guard

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# --- Helper: check if a file path looks sensitive ---
is_sensitive_path() {
  local path="$1"
  [[ -z "$path" ]] && return 1

  # Normalize to lowercase for matching (portable across Bash 3.2+)
  local lpath
  lpath=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')

  # Sensitive directories
  if [[ "$lpath" == *"/.ssh/"* ]] || \
     [[ "$lpath" == *"/.aws/"* ]] || \
     [[ "$lpath" == *"/.gnupg/"* ]] || \
     [[ "$lpath" == *"/.kube/"* ]] || \
     [[ "$lpath" == *"/.docker/"* ]] || \
     [[ "$lpath" == *"/.npmrc"* ]] || \
     [[ "$lpath" == *"/.netrc"* ]] || \
     [[ "$lpath" == *"/.pypirc"* ]]; then
    return 0
  fi

  # Sensitive file patterns
  local basename="${lpath##*/}"
  if [[ "$basename" == ".env" ]] || \
     [[ "$basename" == .env.* ]] || \
     [[ "$basename" == *"secret"* ]] || \
     [[ "$basename" == *"credential"* ]] || \
     [[ "$basename" == *"password"* ]] || \
     [[ "$basename" == *"private_key"* ]] || \
     [[ "$basename" == *"private-key"* ]] || \
     [[ "$basename" == *"privatekey"* ]] || \
     [[ "$basename" == *"id_rsa"* ]] || \
     [[ "$basename" == *"id_ed25519"* ]] || \
     [[ "$basename" == *"id_ecdsa"* ]] || \
     [[ "$basename" == *"id_dsa"* ]] || \
     [[ "$basename" == *".pem" ]] || \
     [[ "$basename" == *".p12" ]] || \
     [[ "$basename" == *".pfx" ]] || \
     [[ "$basename" == *".keystore" ]] || \
     [[ "$basename" == *"token"* && "$basename" != *"tokenize"* && "$basename" != *"tokenizer"* ]]; then
    return 0
  fi

  return 1
}

# --- Helper: output an allow decision ---
allow() {
  local reason="${1:-Auto-approved}"
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# --- Helper: check if a Bash command is read-only ---
is_readonly_bash_command() {
  local cmd="$1"
  [[ -z "$cmd" ]] && return 1

  # Strip leading whitespace
  cmd="${cmd#"${cmd%%[![:space:]]*}"}"

  # Reject anything with shell meta-characters that could chain commands
  # (pipes, semicolons, &&, ||, backticks, $(), redirects)
  if [[ "$cmd" == *"|"* ]] || \
     [[ "$cmd" == *";"* ]] || \
     [[ "$cmd" == *"&&"* ]] || \
     [[ "$cmd" == *"||"* ]] || \
     [[ "$cmd" == *'`'* ]] || \
     [[ "$cmd" == *'$('* ]] || \
     [[ "$cmd" == *">"* ]] || \
     [[ "$cmd" == *"<"* ]]; then
    return 1
  fi

  # Read-only command prefixes — order matters (longest prefixes first where needed)
  local -a readonly_prefixes=(
    "git status"
    "git log"
    "git diff"
    "git show"
    "git branch"
    "git tag"
    "git remote"
    "git rev-parse"
    "git describe"
    "git ls-files"
    "git ls-tree"
    "git shortlog"
    "git stash list"
    "git config --get"
    "git config --list"
    "git config -l"
    "ls "
    "ls$"
    "pwd"
    "which "
    "type "
    "whoami"
    "hostname"
    "uname"
    "date"
    "env"
    "printenv"
    "echo "
    "wc "
    "du "
    "df "
    "file "
    "stat "
    "realpath "
    "dirname "
    "basename "
    "gh pr view"
    "gh pr list"
    "gh pr diff"
    "gh pr checks"
    "gh pr status"
    "gh issue view"
    "gh issue list"
    "gh issue status"
    "gh api "
    "gh repo view"
    "gh run list"
    "gh run view"
    "npm list"
    "npm ls"
    "npm view"
    "npm info"
    "npm outdated"
    "npm --version"
    "node --version"
    "node -v"
    "python --version"
    "python3 --version"
    "java -version"
    "java --version"
    "cargo --version"
    "go version"
    "rustc --version"
    "ruby --version"
  )

  for prefix in "${readonly_prefixes[@]}"; do
    if [[ "$prefix" == *'$' ]]; then
      # Exact match (with trailing $)
      local exact="${prefix%'$'}"
      [[ "$cmd" == "$exact" ]] && return 0
    else
      # Prefix match
      [[ "$cmd" == "$prefix"* ]] && return 0
    fi
  done

  return 1
}

# --- Tool-specific logic ---

case "$TOOL_NAME" in
  Read)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    if is_sensitive_path "$FILE_PATH"; then
      exit 0  # No decision — fall through to normal permission prompt
    fi
    allow "Auto-approved: reading non-sensitive file"
    ;;

  Glob)
    GLOB_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // ""')
    GLOB_PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""')
    if is_sensitive_path "$GLOB_PATH" || is_sensitive_path "$GLOB_PATTERN"; then
      exit 0
    fi
    allow "Auto-approved: glob search in non-sensitive location"
    ;;

  Grep)
    GREP_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // ""')
    if is_sensitive_path "$GREP_PATH"; then
      exit 0
    fi
    allow "Auto-approved: grep search in non-sensitive location"
    ;;

  WebFetch)
    URL=$(echo "$INPUT" | jq -r '.tool_input.url // ""')
    URL_LOWER=$(printf '%s' "$URL" | tr '[:upper:]' '[:lower:]')
    # Block fetching URLs that might contain credentials in query params
    if [[ "$URL_LOWER" == *"token="* ]] || \
       [[ "$URL_LOWER" == *"password="* ]] || \
       [[ "$URL_LOWER" == *"secret="* ]] || \
       [[ "$URL_LOWER" == *"api_key="* ]] || \
       [[ "$URL_LOWER" == *"apikey="* ]]; then
      exit 0
    fi
    allow "Auto-approved: web fetch from non-sensitive URL"
    ;;

  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    if is_readonly_bash_command "$COMMAND"; then
      allow "Auto-approved: read-only Bash command"
    fi
    exit 0
    ;;

  *)
    # All other tools handled by native permission rules or default prompts
    exit 0
    ;;
esac
