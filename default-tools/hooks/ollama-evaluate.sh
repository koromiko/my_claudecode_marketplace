#!/bin/bash
# Evaluate a Claude Code tool use request using a local Ollama LLM.
# Called by auto-approve.sh for tool calls not handled by the fast path.
#
# Reads hook JSON from stdin. Outputs allow JSON to stdout, or exits
# silently (exit 0, no output) to fall through to the permission prompt.
#
# Configuration (environment variables):
#   OLLAMA_MODEL   — default: gemma4:latest
#   OLLAMA_HOST    — default: http://localhost:11434
#   OLLAMA_TIMEOUT — default: 15 (seconds)

set -u

MODEL="${OLLAMA_MODEL:-gemma4:latest}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
TIMEOUT="${OLLAMA_TIMEOUT:-15}"

INPUT=$(cat)

# Detect project root for the system prompt
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || GIT_ROOT="$PWD"

SYSTEM_PROMPT="You are a security evaluator for a code editor's tool use requests.
Given a tool name and its parameters, decide if the operation should be auto-approved.

IMPORTANT: DENY rules always take precedence over APPROVE rules. Check DENY rules first.

DENY immediately if the operation matches ANY of:
- File path is outside the project directory: ${GIT_ROOT} (e.g. /etc/, /usr/, ~/.ssh/, ~/Documents/)
- File path contains any of: .env, secrets/, credentials, api-keys, private_key, .pem, .p12, .pfx
- File path is inside: .ssh/, .aws/, .gnupg/, .kube/, .docker/
- Bash command writes (> or >>) into a sensitive filename (.env, secrets, credentials)
- Bash command is destructive: rm -rf, git reset --hard, git clean -fd on source directories
- curl/wget sends file contents (-d @filename, --data @filename) to an external host

APPROVE if (and no DENY rule matched):
- Editing or writing non-sensitive files within the project: ${GIT_ROOT}
- Web search or documentation lookup
- Updating non-critical settings (editor config, formatting, linting)
- Creating or updating task/todo items
- Reading or searching any non-sensitive content
- HTTP requests (curl/wget) to known developer APIs using environment variable tokens
  (e.g. \$SG_DEEPSEARCH_API_KEY, \$GITHUB_TOKEN), even with Authorization headers —
  these use pre-configured credentials, not raw secrets
- Standard git workflow: rebase, merge, push, pull, fetch, stash, cherry-pick
- Reading from system temp directories (/tmp, /var/tmp) — ephemeral, not sensitive
- Workflow meta-tools (ExitPlanMode, EnterPlanMode, ToolSearch, Skill, TaskCreate,
  TaskUpdate) — these control the editor, not the filesystem; always safe

Respond with ONLY valid JSON: {\"decision\": \"allow\" or \"deny\", \"reason\": \"brief explanation\"}"

# Extract structured fields to mitigate prompt injection via raw tool input
TOOL_NAME_PARSED=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_PARAMS=$(echo "$INPUT" | jq -r '.tool_input | to_entries | map("\(.key): \(.value | tostring | .[0:200])") | join(", ")' 2>/dev/null) || TOOL_PARAMS="(unable to parse)"

FULL_PROMPT="${SYSTEM_PROMPT}

Tool: ${TOOL_NAME_PARSED}
Parameters: ${TOOL_PARAMS}"

# Build the request body with structured output format
REQUEST_BODY=$(jq -n \
  --arg model "$MODEL" \
  --arg prompt "$FULL_PROMPT" \
  '{
    model: $model,
    prompt: $prompt,
    stream: false,
    think: false,
    format: {
      type: "object",
      properties: {
        decision: { type: "string", enum: ["allow", "deny"] },
        reason: { type: "string" }
      },
      required: ["decision", "reason"]
    }
  }')

# Call Ollama — any failure (connection refused, timeout, bad JSON) falls through
RESPONSE=$(curl -s --fail --max-time "$TIMEOUT" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY" \
  "${HOST}/api/generate" 2>/dev/null) || exit 0

# Extract the model's response text and parse the decision
MODEL_OUTPUT=$(echo "$RESPONSE" | jq -r '.response // ""' 2>/dev/null) || exit 0
DECISION=$(echo "$MODEL_OUTPUT" | jq -r '.decision // ""' 2>/dev/null) || exit 0

REASON=$(echo "$MODEL_OUTPUT" | jq -r '.reason // ""' 2>/dev/null)

if [[ "$DECISION" == "allow" ]]; then
  jq -n --arg reason "Ollama ($MODEL): ${REASON:-LLM-approved}" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: $reason
    }
  }'
elif [[ "${OLLAMA_TEST_MODE:-}" == "1" ]]; then
  # In test mode, emit a deny JSON so the test runner can distinguish a correct
  # deny from a timeout/parse error.  Production callers never set this variable.
  jq -n --arg reason "Ollama ($MODEL): ${REASON:-LLM-denied}" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
fi

# If decision is not "allow" (deny, empty, or parse failure), exit silently → fall through
exit 0
