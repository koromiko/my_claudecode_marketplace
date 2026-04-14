#!/bin/bash
set -e

CONFIG_DIR="$HOME/.claude/obsidian-vault"
CONFIG_FILE="$CONFIG_DIR/config.json"

case "${1:-}" in
  read)
    if [ -f "$CONFIG_FILE" ]; then
      cat "$CONFIG_FILE"
    else
      echo "NOT_CONFIGURED" >&2
      exit 1
    fi
    ;;
  validate)
    if [ ! -f "$CONFIG_FILE" ]; then
      echo "NOT_CONFIGURED"
      exit 1
    fi
    VAULT_PATH=$(python3 -c "import json,sys; print(json.load(open('$CONFIG_FILE'))['vault_path'])" 2>/dev/null)
    if [ -z "$VAULT_PATH" ]; then
      echo "INVALID_CONFIG"
      exit 1
    fi
    if [ ! -d "$VAULT_PATH" ]; then
      echo "PATH_NOT_FOUND"
      exit 1
    fi
    if [ -d "$VAULT_PATH/.obsidian" ]; then
      echo "VALID"
    else
      echo "NOT_OBSIDIAN_VAULT"
      exit 1
    fi
    ;;
  init)
    mkdir -p "$CONFIG_DIR"
    echo "CONFIG_DIR_READY"
    ;;
  *)
    echo "Usage: vault-config.sh {read|validate|init}" >&2
    exit 1
    ;;
esac
