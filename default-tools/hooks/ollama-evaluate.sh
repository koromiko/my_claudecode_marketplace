#!/bin/bash
# Evaluate a Claude Code tool use request using a local Ollama LLM.
# Called by auto-approve.sh for tool calls not handled by the fast path.
#
# Reads hook JSON from stdin. Outputs allow JSON to stdout, or exits
# silently (exit 0, no output) to fall through to the permission prompt.
#
# Configuration (environment variables):
#   OLLAMA_MODEL   — default: qwen3:0.6b
#   OLLAMA_HOST    — default: http://localhost:11434
#   OLLAMA_TIMEOUT — default: 4 (seconds)

set -u

MODEL="${OLLAMA_MODEL:-qwen3:0.6b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
TIMEOUT="${OLLAMA_TIMEOUT:-4}"

INPUT=$(cat)

# Detect project root for the system prompt
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || GIT_ROOT="$PWD"

SYSTEM_PROMPT="You are a security evaluator for a code editor's tool use requests.
Given a tool name and its parameters, decide if the operation should be auto-approved.

APPROVE if the operation is:
- Editing or writing files within the project directory: ${GIT_ROOT}
- Web search or documentation lookup
- Updating non-critical settings (editor config, formatting, linting)
- Creating or updating task/todo items
- Reading or searching any non-sensitive content

DENY if the operation is:
- Modifying files outside the project directory
- Touching sensitive paths (.ssh, .aws, .env, credentials, private keys)
- Running destructive or irreversible system commands
- Accessing or modifying authentication tokens/secrets
- Network operations that could exfiltrate data

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

if [[ "$DECISION" == "allow" ]]; then
  REASON=$(echo "$MODEL_OUTPUT" | jq -r '.reason // "LLM-approved"' 2>/dev/null)
  jq -n --arg reason "Ollama ($MODEL): $REASON" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: $reason
    }
  }'
fi

# If decision is not "allow" (deny, empty, or parse failure), exit silently → fall through
exit 0
