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
#   - Bash with read-only command/pipeline allowlist + metacharacter guard

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

# --- Helper: check a single command (no pipes) against the read-only allowlist ---
is_readonly_single_command() {
  local cmd="$1"
  [[ -z "$cmd" ]] && return 1

  # Strip leading and trailing whitespace
  cmd="${cmd#"${cmd%%[![:space:]]*}"}"
  cmd="${cmd%"${cmd##*[![:space:]]}"}"

  [[ -z "$cmd" ]] && return 1

  # Shell comment lines are harmless — skip them
  [[ "$cmd" == "#"* ]] && return 0

  # Reject mutating variants of otherwise read-only commands
  [[ "$cmd" == "sed -i"* ]] && return 1

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
    "strings "
    "strings$"
    "stat "
    "realpath "
    "dirname "
    "basename "
    "find "
    "grep "
    "grep$"
    "egrep "
    "egrep$"
    "fgrep "
    "fgrep$"
    "rg "
    "rg$"
    "head "
    "head$"
    "tail "
    "tail$"
    "sort "
    "sort$"
    "uniq "
    "uniq$"
    "cut "
    "cut$"
    "cat "
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
    "cd "
    "sed "
    "sed$"
    "glab mr view"
    "glab mr list"
    "glab mr diff"
    "glab mr status"
    "glab ci view"
    "glab ci list"
    "glab ci status"
    "glab repo view"
    "xcrun simctl list"
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

  # Check against extra allowed prefixes from project config
  local extra_prefix
  while IFS= read -r extra_prefix; do
    [[ -n "$extra_prefix" ]] && [[ "$cmd" == "$extra_prefix"* ]] && return 0
  done < <(load_extra_prefixes)

  return 1
}

# --- Helper: load extra allowed prefixes from .claude/settings.json ---
load_extra_prefixes() {
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || root="$PWD"

  # Check settings.local.json first (user-specific), then settings.json (shared)
  local f
  for f in "${root}/.claude/settings.local.json" "${root}/.claude/settings.json"; do
    if [[ -f "$f" ]]; then
      jq -r '.autoApproveCommands[]? // empty' "$f" 2>/dev/null
    fi
  done
}

# --- Helper: check if a Bash command (possibly a pipeline/compound) is read-only ---
is_readonly_bash_command() {
  local cmd="$1"
  [[ -z "$cmd" ]] && return 1

  # Strip leading whitespace
  cmd="${cmd#"${cmd%%[![:space:]]*}"}"

  # Strip harmless stderr suppression/redirection before checking for dangerous chars
  local cmd_check
  cmd_check="${cmd//2>\/dev\/null/}"
  cmd_check="${cmd_check//2>\&1/}"

  # Reject dangerous metacharacters that can't be safely split
  if [[ "$cmd_check" == *'`'* ]] || \
     [[ "$cmd_check" == *'$('* ]] || \
     [[ "$cmd_check" == *">"* ]] || \
     [[ "$cmd_check" == *"<"* ]]; then
    return 1
  fi

  # Split on unquoted &&, ||, ;, and | into simple commands.
  # Respects single/double quotes so operators inside quoted strings
  # (e.g., grep -E "(a|b)") are not treated as separators.
  local -a commands
  while IFS= read -r line; do
    [[ -n "$line" ]] && commands+=("$line")
  done < <(printf '%s' "$cmd" | awk '
  BEGIN { FS=""; sq = sprintf("%c", 39) }
  {
    in_sq=0; in_dq=0; esc=0
    for (i=1; i<=length($0); i++) {
      c = substr($0, i, 1)
      if (esc) { esc=0; printf "%s", c; continue }
      if (c == "\\") { esc=1; printf "%s", c; continue }
      if (c == sq && !in_dq) { in_sq = !in_sq; printf "%s", c; continue }
      if (c == "\"" && !in_sq) { in_dq = !in_dq; printf "%s", c; continue }
      if (!in_sq && !in_dq) {
        two = substr($0, i, 2)
        if (two == "&&" || two == "||") { printf "\n"; i++; continue }
        if (c == ";" || c == "|") { printf "\n"; continue }
      }
      printf "%s", c
    }
    printf "\n"
  }')

  for segment in "${commands[@]}"; do
    if ! is_readonly_single_command "$segment"; then
      return 1
    fi
  done

  return 0
}

# --- Tool-specific logic ---

# Resolve git root once for scope checks
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || GIT_ROOT="$PWD"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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
    # Non-readonly bash: delegate to LLM
    echo "$INPUT" | "$SCRIPT_DIR/ollama-evaluate.sh"
    exit 0
    ;;

  Edit|Write)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    # Hard guard: sensitive paths never reach the LLM
    if is_sensitive_path "$FILE_PATH"; then
      exit 0
    fi
    # Hard guard: empty path or files outside project scope never reach the LLM
    if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != "$GIT_ROOT/"* ]]; then
      exit 0
    fi
    # In-scope, non-sensitive: delegate to LLM
    echo "$INPUT" | "$SCRIPT_DIR/ollama-evaluate.sh"
    exit 0
    ;;

  *)
    # All other tools: delegate to LLM for evaluation
    echo "$INPUT" | "$SCRIPT_DIR/ollama-evaluate.sh"
    exit 0
    ;;
esac
