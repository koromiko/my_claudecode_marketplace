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
TIMEOUT="${OLLAMA_TIMEOUT:-4}"
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
