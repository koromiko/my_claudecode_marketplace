#!/bin/bash
# Test harness for default-tools/hooks/ollama-evaluate.sh
# Reads fixture cases from fixtures/ollama-test-cases.json,
# pipes each to ollama-evaluate.sh, grades allow/deny decisions,
# writes timestamped JSON results, and prints a human-readable summary.
#
# Exit codes:
#   0 — all cases passed, or Ollama unavailable (all skipped)
#   1 — one or more cases failed (expected ≠ actual)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE_FILE="$SCRIPT_DIR/fixtures/ollama-test-cases.json"
RESULTS_DIR="$SCRIPT_DIR/results"
EVALUATOR="$SCRIPT_DIR/../hooks/ollama-evaluate.sh"

MODEL="${OLLAMA_MODEL:-qwen3:0.6b}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S)
RESULTS_FILE="$RESULTS_DIR/run-${TIMESTAMP}.json"

mkdir -p "$RESULTS_DIR"

# Millisecond timestamp (macOS-compatible via python3)
ms_now() { python3 -c "import time; print(int(time.time()*1000))"; }

# --- Phase 1: Health check ---
OLLAMA_AVAILABLE=false
if curl -s --fail --max-time 2 "${HOST}/api/tags" > /dev/null 2>&1; then
  OLLAMA_AVAILABLE=true
fi

TOTAL=$(jq 'length' "$FIXTURE_FILE")

echo "=== Ollama Evaluator Test Run — $TIMESTAMP ==="
echo "Model: $MODEL  Available: $([ "$OLLAMA_AVAILABLE" = "true" ] && echo YES || echo NO)"
echo ""

# Temp file to accumulate per-case result objects (one JSON object per line)
TEMP_RESULTS=$(mktemp)
trap 'rm -f "$TEMP_RESULTS"' EXIT

# --- If Ollama is down, skip all and write results ---
if [ "$OLLAMA_AVAILABLE" = "false" ]; then
  jq -c '.[]' "$FIXTURE_FILE" | while IFS= read -r test_case; do
    id=$(echo "$test_case" | jq -r '.id')
    category=$(echo "$test_case" | jq -r '.category')
    description=$(echo "$test_case" | jq -r '.description')
    expected=$(echo "$test_case" | jq -r '.expected')
    jq -n \
      --arg id "$id" --arg cat "$category" --arg desc "$description" \
      --arg exp "$expected" \
      '{id:$id,category:$cat,description:$desc,expected:$exp,actual:"",status:"skip",latency_ms:0,reason:"Ollama unavailable",error:null}' \
      >> "$TEMP_RESULTS"
    printf "  SKIP  %-22s  %s\n" "$id" "$description"
  done

  jq -n \
    --arg run_id "$TIMESTAMP" \
    --arg model "$MODEL" \
    --argjson total "$TOTAL" \
    --slurpfile cases "$TEMP_RESULTS" \
    '{run_id:$run_id,ollama_available:false,ollama_model:$model,
      summary:{total:$total,passed:0,failed:0,skipped:$total},
      cases:$cases}' > "$RESULTS_FILE"

  echo ""
  echo "Summary: 0 passed / 0 failed / $TOTAL skipped  (Ollama unavailable)"
  echo "Results written to: $RESULTS_FILE"
  exit 0
fi

# --- Phase 2: Execute each test case ---
CURRENT_CATEGORY=""

while IFS= read -r test_case; do
  id=$(echo "$test_case" | jq -r '.id')
  category=$(echo "$test_case" | jq -r '.category')
  description=$(echo "$test_case" | jq -r '.description')
  expected=$(echo "$test_case" | jq -r '.expected')
  input_json=$(echo "$test_case" | jq -c '.input')

  # Print category header when it changes
  if [ "$category" != "$CURRENT_CATEGORY" ]; then
    CURRENT_CATEGORY="$category"
    echo "[$category]"
  fi

  # Run evaluator, capture output and latency
  START_MS=$(ms_now)
  STDOUT=$(echo "$input_json" | bash "$EVALUATOR" 2>/dev/null) || true
  END_MS=$(ms_now)
  LATENCY_MS=$(( END_MS - START_MS ))

  # Parse decision: allow, deny, or error (empty = Ollama unavailable mid-run)
  if [ -z "$STDOUT" ]; then
    actual="error"
  elif echo "$STDOUT" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' > /dev/null 2>&1; then
    actual="allow"
  else
    actual="deny"
  fi

  # Grade: error means Ollama didn't respond — treat as skip (not a fail)
  if [ "$actual" = "error" ]; then
    status="skip"
  elif [ "$actual" = "$expected" ]; then
    status="pass"
  else
    status="fail"
  fi

  # Extract reason from evaluator output (empty string if not present)
  reason=$(echo "$STDOUT" | jq -r '.hookSpecificOutput.permissionDecisionReason // ""' 2>/dev/null || true)

  # Append result object to temp file
  jq -n \
    --arg id "$id" --arg cat "$category" --arg desc "$description" \
    --arg exp "$expected" --arg actual "$actual" --arg status "$status" \
    --argjson latency "$LATENCY_MS" --arg reason "$reason" \
    '{id:$id,category:$cat,description:$desc,expected:$exp,actual:$actual,
      status:$status,latency_ms:$latency,reason:$reason,error:null}' \
    >> "$TEMP_RESULTS"

  # Print result line
  printf "  %-4s  %-22s  %-44s  %s → %s  (%dms)\n" \
    "$(echo "$status" | tr '[:lower:]' '[:upper:]')" \
    "$id" "$description" "$expected" "$actual" "$LATENCY_MS"

done < <(jq -c '.[]' "$FIXTURE_FILE")

# --- Phase 3: Write results JSON ---
PASSED=$(jq -s '[.[] | select(.status == "pass")] | length' "$TEMP_RESULTS" 2>/dev/null || echo 0)
FAILED=$(jq -s '[.[] | select(.status == "fail")] | length' "$TEMP_RESULTS" 2>/dev/null || echo 0)
SKIPPED=$(jq -s '[.[] | select(.status == "skip")] | length' "$TEMP_RESULTS" 2>/dev/null || echo 0)

if [ $(( PASSED + FAILED )) -gt 0 ]; then
  ACCURACY=$(( (PASSED * 100) / (PASSED + FAILED) ))
else
  ACCURACY=0
fi

jq -n \
  --arg run_id "$TIMESTAMP" \
  --arg model "$MODEL" \
  --argjson total "$TOTAL" \
  --argjson passed "$PASSED" \
  --argjson failed "$FAILED" \
  --argjson skipped "$SKIPPED" \
  --slurpfile cases "$TEMP_RESULTS" \
  '{run_id:$run_id,ollama_available:true,ollama_model:$model,
    summary:{total:$total,passed:$passed,failed:$failed,skipped:$skipped},
    cases:$cases}' > "$RESULTS_FILE"

# --- Phase 4: Stdout summary ---
echo ""
echo "Summary: $PASSED passed / $FAILED failed / $SKIPPED skipped  (accuracy: ${ACCURACY}%)"
echo "Results written to: $RESULTS_FILE"

# Exit 1 if any failures
[ "$FAILED" -eq 0 ]
