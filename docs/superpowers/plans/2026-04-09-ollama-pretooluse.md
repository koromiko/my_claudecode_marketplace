# Ollama-Powered PreToolUse Auto-Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local Ollama LLM fallback to the default-tools PreToolUse hook so that tool calls not handled by the existing fast path (Edit, Write, Agent, etc.) get an automated allow/deny decision instead of prompting the user.

**Architecture:** The existing `auto-approve.sh` keeps its fast path for Read/Glob/Grep/WebFetch/Bash. A new `ollama-evaluate.sh` script is called for unhandled tools. It sends the tool JSON to Ollama's `/api/generate` endpoint with a security-evaluator system prompt and structured JSON output. Hard guards (sensitive paths, outside-git-root) run deterministically before the LLM is ever consulted.

**Tech Stack:** Bash, curl, jq, Ollama API (REST), Qwen3:0.6b model

**Spec:** `docs/superpowers/specs/2026-04-09-ollama-pretooluse-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `default-tools/hooks/ollama-evaluate.sh` | Create | Standalone LLM evaluator script — receives hook JSON on stdin, calls Ollama, outputs allow decision or exits silently |
| `default-tools/hooks/auto-approve.sh` | Modify (lines 287-341) | Add Edit/Write cases with hard guards, change `*)` catch-all to delegate to `ollama-evaluate.sh` |
| `default-tools/CLAUDE.md` | Modify | Document new script, env vars, Ollama prerequisite |

---

### Task 1: Create `ollama-evaluate.sh`

**Files:**
- Create: `default-tools/hooks/ollama-evaluate.sh`

- [ ] **Step 1: Create the script with configuration and input parsing**

```bash
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

set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen3:0.6b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
TIMEOUT="${OLLAMA_TIMEOUT:-4}"

INPUT=$(cat)
```

- [ ] **Step 2: Add git root detection and system prompt construction**

Append to the script after the INPUT line:

```bash
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
```

- [ ] **Step 3: Add the Ollama API call and response parsing**

Append to the script:

```bash
# Build the full prompt: system prompt + tool JSON
FULL_PROMPT="${SYSTEM_PROMPT}

Evaluate this tool use request:
${INPUT}"

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
RESPONSE=$(curl -s --max-time "$TIMEOUT" \
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
```

- [ ] **Step 4: Make the script executable**

Run:
```bash
chmod +x default-tools/hooks/ollama-evaluate.sh
```

- [ ] **Step 5: Test `ollama-evaluate.sh` directly — allow case**

Run:
```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/sthuang/Project/my_claudecode_marketplace/default-tools/hooks/auto-approve.sh","old_string":"foo","new_string":"bar"}}' | bash default-tools/hooks/ollama-evaluate.sh
```

Expected: JSON output with `permissionDecision: "allow"` (file is inside the project).

- [ ] **Step 6: Test `ollama-evaluate.sh` directly — deny case**

Run:
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | bash default-tools/hooks/ollama-evaluate.sh
```

Expected: No output (model should deny, script exits silently).

- [ ] **Step 7: Test `ollama-evaluate.sh` — Ollama unavailable**

Run:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/foo.txt"}}' | OLLAMA_HOST=http://localhost:99999 bash default-tools/hooks/ollama-evaluate.sh
```

Expected: No output, exit code 0 (graceful fallthrough).

- [ ] **Step 8: Commit**

```bash
git add default-tools/hooks/ollama-evaluate.sh
git commit -m "feat(default-tools): add Ollama LLM evaluator script for PreToolUse hook"
```

---

### Task 2: Add Edit/Write cases and LLM fallback to `auto-approve.sh`

**Files:**
- Modify: `default-tools/hooks/auto-approve.sh:287-341`

- [ ] **Step 1: Add Edit and Write cases with hard guards before the `*)` catch-all**

Replace the tool-specific logic block (lines 287-341) in `auto-approve.sh` with:

```bash
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
    # Hard guard: files outside project scope never reach the LLM
    if [[ -n "$FILE_PATH" ]] && [[ "$FILE_PATH" != "$GIT_ROOT"* ]]; then
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
```

- [ ] **Step 2: Test Edit inside project scope (should allow via LLM)**

Run:
```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/sthuang/Project/my_claudecode_marketplace/default-tools/hooks/auto-approve.sh","old_string":"foo","new_string":"bar"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: JSON output with `permissionDecision: "allow"`.

- [ ] **Step 3: Test Edit on sensitive path (should fall through, no LLM call)**

Run:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/sthuang/.ssh/config","old_string":"foo","new_string":"bar"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: No output (hard guard blocks before LLM).

- [ ] **Step 4: Test Edit outside project scope (should fall through, no LLM call)**

Run:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/etc/hosts","old_string":"foo","new_string":"bar"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: No output (scope guard blocks before LLM).

- [ ] **Step 5: Test Write inside project scope (should allow via LLM)**

Run:
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/Users/sthuang/Project/my_claudecode_marketplace/default-tools/test-output.txt","content":"hello"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: JSON output with `permissionDecision: "allow"`.

- [ ] **Step 6: Test existing fast paths still work (Read, Bash)**

Run:
```bash
# Read — should still allow instantly (no LLM)
echo '{"tool_name":"Read","tool_input":{"file_path":"/some/file.txt"}}' | bash default-tools/hooks/auto-approve.sh

# Bash read-only — should still allow instantly (no LLM)
echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: Both produce JSON with `permissionDecision: "allow"`, and return in <100ms (no LLM latency).

- [ ] **Step 7: Test catch-all with unknown tool (should go to LLM)**

Run:
```bash
echo '{"tool_name":"Agent","tool_input":{"prompt":"search for files","description":"find stuff"}}' | bash default-tools/hooks/auto-approve.sh
```

Expected: JSON output with `permissionDecision: "allow"` (Agent tool with benign prompt).

- [ ] **Step 8: Commit**

```bash
git add default-tools/hooks/auto-approve.sh
git commit -m "feat(default-tools): route Edit/Write and catch-all tools to Ollama evaluator"
```

---

### Task 3: Update documentation

**Files:**
- Modify: `default-tools/CLAUDE.md`

- [ ] **Step 1: Update the Architecture section in CLAUDE.md**

After the existing "Auto-Approve Decision Logic" section (line 19), add a new subsection:

```markdown
### Ollama LLM Evaluator

`ollama-evaluate.sh` is a fallback for tool calls not handled by the fast path. It sends the tool JSON to a local Ollama model for a binary allow/deny decision.

**Tools routed to the LLM:**
- `Edit` / `Write` — after passing sensitive-path and project-scope hard guards
- `Bash` — non-readonly commands (after the allowlist check fails)
- `*` catch-all — any tool not explicitly handled (Agent, NotebookEdit, etc.)

**Configuration (environment variables):**
- `OLLAMA_MODEL` — default `qwen3:0.6b`
- `OLLAMA_HOST` — default `http://localhost:11434`
- `OLLAMA_TIMEOUT` — default `4` (seconds)

**Failure behavior:** If Ollama is unavailable, times out, or returns a deny/malformed response, the script exits silently and the tool falls through to the normal permission prompt.
```

- [ ] **Step 2: Update the Prerequisites section**

Replace the existing prerequisites line with:

```markdown
macOS with `jq`, `terminal-notifier` (`brew install terminal-notifier`), and iTerm2 for notifications. The `say` command is used for audio alerts. Ollama (`brew install ollama`) with Qwen3:0.6b (`ollama pull qwen3:0.6b`) for LLM-based tool evaluation.
```

- [ ] **Step 3: Add Ollama test examples to the Testing section**

Add after the existing test examples:

```bash
# Test LLM evaluation of an Edit (should allow — file is in project scope)
echo '{"tool_name":"Edit","tool_input":{"file_path":"'$(git rev-parse --show-toplevel)'/src/main.py","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# Test LLM evaluation with Ollama down (should fall through silently)
OLLAMA_HOST=http://localhost:99999 echo '{"tool_name":"Agent","tool_input":{"prompt":"do something"}}' | bash hooks/auto-approve.sh

# Test ollama-evaluate.sh directly
echo '{"tool_name":"Write","tool_input":{"file_path":"/project/README.md","content":"hello"}}' | bash hooks/ollama-evaluate.sh
```

- [ ] **Step 4: Commit**

```bash
git add default-tools/CLAUDE.md
git commit -m "docs(default-tools): document Ollama LLM evaluator and prerequisites"
```

---

### Task 4: Pull the model and end-to-end validation

- [ ] **Step 1: Ensure qwen3:0.6b is pulled**

Run:
```bash
ollama pull qwen3:0.6b
```

Expected: Model downloaded (or already present).

- [ ] **Step 2: Run the full test suite from the spec**

Run each command from the spec's Testing section and verify:

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace/default-tools

# 1. Edit inside project scope → allow
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/sthuang/Project/my_claudecode_marketplace/default-tools/hooks/auto-approve.sh","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# 2. Edit outside project scope → no output
echo '{"tool_name":"Edit","tool_input":{"file_path":"/etc/hosts","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# 3. Edit sensitive path → no output
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/sthuang/.aws/credentials","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# 4. Read (existing fast path) → allow, fast
echo '{"tool_name":"Read","tool_input":{"file_path":"/some/file.txt"}}' | bash hooks/auto-approve.sh

# 5. Bash read-only (existing fast path) → allow, fast
echo '{"tool_name":"Bash","tool_input":{"command":"git log --oneline -5"}}' | bash hooks/auto-approve.sh

# 6. Ollama down → no output, graceful
OLLAMA_HOST=http://localhost:99999 echo '{"tool_name":"Agent","tool_input":{"prompt":"do something"}}' | bash hooks/auto-approve.sh

# 7. Validate hooks.json still valid
jq . hooks/hooks.json
```

Expected:
- Test 1: JSON with `permissionDecision: "allow"` and reason mentioning Ollama
- Test 2: No output
- Test 3: No output
- Test 4: JSON with `permissionDecision: "allow"` reason "reading non-sensitive file"
- Test 5: JSON with `permissionDecision: "allow"` reason "read-only Bash command"
- Test 6: No output, exit 0
- Test 7: Valid JSON printed

- [ ] **Step 3: Bump the plugin version**

Run:
```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
./scripts/bump-plugin.sh default-tools 2>/dev/null || echo "No bump script or manual bump needed"
```

If no bump script exists, manually update the version in `default-tools/.claude-plugin/plugin.json`.
