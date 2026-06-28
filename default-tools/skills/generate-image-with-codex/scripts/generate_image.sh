#!/usr/bin/env bash
# Generate image(s) from a text description using the Codex CLI's built-in
# image_generation tool, then print the absolute path of every PNG produced.
#
# Usage: generate_image.sh "<image description>"
#
# Codex writes generated images to ~/.codex/generated_images/<thread-id>/.
# We capture the thread id from the JSONL event stream so we can locate
# exactly the images this run produced (rather than guessing by mtime).

set -euo pipefail

prompt="${1:-}"
if [[ -z "$prompt" ]]; then
  echo "ERROR: no image description supplied" >&2
  echo "Usage: generate_image.sh \"<image description>\"" >&2
  exit 2
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: the 'codex' CLI is not installed or not on PATH." >&2
  echo "Install the Codex CLI and authenticate it, then retry." >&2
  exit 3
fi

images_root="${HOME}/.codex/generated_images"

# Wrap the description in an explicit instruction so Codex reliably reaches
# for its image_generation tool instead of just replying with text.
full_prompt="Generate an image using your image generation tool. Do not ask
for confirmation. Image description: ${prompt}"

# Run Codex non-interactively. --json emits a JSONL event stream on stdout;
# stdin is closed so Codex does not block waiting for additional input.
json_out="$(codex exec --skip-git-repo-check --json "$full_prompt" </dev/null 2>/dev/null)" || {
  status=$?
  echo "ERROR: 'codex exec' failed (exit ${status})." >&2
  echo "Run 'codex exec \"hello\"' yourself to check Codex is authenticated." >&2
  exit 4
}

# The thread.started event carries the thread id, which names the output dir.
thread_id="$(printf '%s\n' "$json_out" \
  | grep -m1 '"type":"thread.started"' \
  | sed -E 's/.*"thread_id":"([^"]+)".*/\1/')"

if [[ -z "$thread_id" ]]; then
  echo "ERROR: could not determine the Codex thread id from its output." >&2
  printf '%s\n' "$json_out" >&2
  exit 5
fi

dir="${images_root}/${thread_id}"
shopt -s nullglob
images=("$dir"/*.png "$dir"/*.jpg "$dir"/*.jpeg "$dir"/*.webp)
shopt -u nullglob

if [[ ${#images[@]} -eq 0 ]]; then
  echo "ERROR: Codex finished but produced no image (thread ${thread_id})." >&2
  echo "It may have declined the request or hit a content limit." >&2
  exit 6
fi

# Newest first, one absolute path per line.
ls -t "${images[@]}"
