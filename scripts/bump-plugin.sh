#!/bin/bash

# bump-plugin.sh - Clear plugin cache and optionally bump version
#
# Usage: ./scripts/bump-plugin.sh <plugin-name> [bump-strategy]
#
# Arguments:
#   plugin-name    Name of the plugin to update (required)
#   bump-strategy  Version bump type: major, minor, patch, none (default: patch)
#
# Examples:
#   ./scripts/bump-plugin.sh session-manager           # Clear cache + bump 1.0.0 → 1.0.1
#   ./scripts/bump-plugin.sh session-manager patch     # Clear cache + bump 1.0.0 → 1.0.1
#   ./scripts/bump-plugin.sh session-manager minor     # Clear cache + bump 1.0.0 → 1.1.0
#   ./scripts/bump-plugin.sh session-manager major     # Clear cache + bump 1.0.0 → 2.0.0
#   ./scripts/bump-plugin.sh session-manager none      # Clear cache only

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"

# Arguments
PLUGIN_NAME="${1:-}"
BUMP_STRATEGY="${2:-patch}"

# Validate bump strategy
validate_strategy() {
    if [[ ! "$BUMP_STRATEGY" =~ ^(major|minor|patch|none)$ ]]; then
        echo -e "${RED}Error: Invalid bump strategy '$BUMP_STRATEGY'${NC}"
        echo "Valid options: major, minor, patch, none"
        exit 1
    fi
}

# Resolve marketplace name for cache path
resolve_marketplace_name() {
    if ! command -v jq &>/dev/null; then
        echo -e "${RED}Error: jq is required but not installed. Install with: brew install jq${NC}" >&2
        exit 1
    fi
    if [[ ! -f "$MARKETPLACE_JSON" ]]; then
        echo -e "${RED}Error: marketplace.json not found at $MARKETPLACE_JSON${NC}" >&2
        exit 1
    fi
    jq -r '.name' "$MARKETPLACE_JSON"
}

# Bump a single plugin by name
bump_plugin() {
    local plugin_name="$1"
    local marketplace_name="$2"
    local plugin_json="$REPO_ROOT/$plugin_name/.claude-plugin/plugin.json"
    local cache_dir="$HOME/.claude/plugins/cache/$marketplace_name/$plugin_name"

    echo -e "${YELLOW}--- $plugin_name ---${NC}"

    # Clear plugin cache
    echo -e "${YELLOW}Clearing cache for plugin '$plugin_name'...${NC}"
    if [[ -d "$cache_dir" ]]; then
        rm -rf "$cache_dir"
        echo -e "${GREEN}✓ Cache cleared: $cache_dir${NC}"
    else
        echo -e "${YELLOW}  (No cache directory found at $cache_dir)${NC}"
    fi

    # Bump version if strategy is not 'none'
    if [[ "$BUMP_STRATEGY" != "none" ]]; then
        echo -e "${YELLOW}Bumping $BUMP_STRATEGY version...${NC}"

        # Use Python for JSON manipulation
        python3 << EOF
import json
import sys

plugin_json_path = "$plugin_json"
bump_strategy = "$BUMP_STRATEGY"

# Read current plugin.json
with open(plugin_json_path, 'r') as f:
    data = json.load(f)

# Get current version
old_version = data.get('version', '0.0.0')
parts = old_version.split('.')

# Ensure we have 3 parts
while len(parts) < 3:
    parts.append('0')

major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

# Bump appropriate component
if bump_strategy == 'major':
    major += 1
    minor = 0
    patch = 0
elif bump_strategy == 'minor':
    minor += 1
    patch = 0
elif bump_strategy == 'patch':
    patch += 1

new_version = f"{major}.{minor}.{patch}"
data['version'] = new_version

# Write updated plugin.json
with open(plugin_json_path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

print(f"OLD_VERSION={old_version}")
print(f"NEW_VERSION={new_version}")
EOF

        # Capture the output to display version change
        VERSION_INFO=$(python3 << EOF
import json

with open("$plugin_json", 'r') as f:
    data = json.load(f)
print(data.get('version', '0.0.0'))
EOF
)

        echo -e "${GREEN}✓ Version bumped to $VERSION_INFO${NC}"
    fi

    echo ""
}

# --- Main ---

# Validate plugin name is provided
if [[ -z "$PLUGIN_NAME" ]]; then
    echo -e "${RED}Error: Plugin name is required${NC}"
    echo "Usage: $0 <plugin-name> [bump-strategy]"
    echo "  bump-strategy: major, minor, patch, none (default: patch)"
    exit 1
fi

validate_strategy

# Validate plugin exists
PLUGIN_JSON="$REPO_ROOT/$PLUGIN_NAME/.claude-plugin/plugin.json"
if [[ ! -f "$PLUGIN_JSON" ]]; then
    echo -e "${RED}Error: Plugin '$PLUGIN_NAME' not found${NC}"
    echo "Expected: $PLUGIN_JSON"
    echo ""
    echo "Available plugins:"
    for dir in "$REPO_ROOT"/*/.claude-plugin/plugin.json; do
        if [[ -f "$dir" ]]; then
            name=$(basename "$(dirname "$(dirname "$dir")")")
            echo "  - $name"
        fi
    done
    exit 1
fi

MARKETPLACE_NAME=$(resolve_marketplace_name)

bump_plugin "$PLUGIN_NAME" "$MARKETPLACE_NAME"
echo -e "${GREEN}Done!${NC}"
