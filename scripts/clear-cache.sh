#!/bin/bash
#
# Clear Claude Code plugin cache for plugins in this marketplace
#
# Usage: ./scripts/clear-cache.sh [--dry-run]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(dirname "$SCRIPT_DIR")"
MARKETPLACE_JSON="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"
CACHE_DIR="$HOME/.claude/plugins/cache"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}Dry run mode - no files will be deleted${NC}\n"
fi

# Check if marketplace.json exists
if [[ ! -f "$MARKETPLACE_JSON" ]]; then
    echo -e "${RED}Error: marketplace.json not found at $MARKETPLACE_JSON${NC}"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required but not installed. Install with: brew install jq${NC}"
    exit 1
fi

# Get marketplace name
MARKETPLACE_NAME=$(jq -r '.name' "$MARKETPLACE_JSON")
MARKETPLACE_CACHE="$CACHE_DIR/$MARKETPLACE_NAME"

echo "Marketplace: $MARKETPLACE_NAME"
echo "Cache location: $MARKETPLACE_CACHE"
echo ""

# Check if cache directory exists
if [[ ! -d "$MARKETPLACE_CACHE" ]]; then
    echo -e "${YELLOW}Cache directory does not exist. Nothing to clear.${NC}"
    exit 0
fi

# Get plugin names from marketplace.json
PLUGINS=$(jq -r '.plugins[].name' "$MARKETPLACE_JSON")

cleared=0
not_found=0

echo "Clearing plugin caches:"
echo "----------------------"

for plugin in $PLUGINS; do
    PLUGIN_CACHE="$MARKETPLACE_CACHE/$plugin"

    if [[ -d "$PLUGIN_CACHE" ]]; then
        if $DRY_RUN; then
            echo -e "  ${YELLOW}[DRY-RUN]${NC} Would delete: $plugin"
        else
            rm -rf "$PLUGIN_CACHE"
            echo -e "  ${GREEN}✓${NC} Cleared: $plugin"
        fi
        ((cleared++))
    else
        echo -e "  ${YELLOW}-${NC} Not cached: $plugin"
        ((not_found++))
    fi
done

echo ""
echo "----------------------"
if $DRY_RUN; then
    echo -e "Would clear ${GREEN}$cleared${NC} plugin cache(s), $not_found not in cache"
else
    echo -e "Cleared ${GREEN}$cleared${NC} plugin cache(s), $not_found not in cache"
fi

# Option to clear entire marketplace cache
echo ""
if [[ -d "$MARKETPLACE_CACHE" ]]; then
    remaining=$(ls -1 "$MARKETPLACE_CACHE" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$remaining" -gt 0 ]]; then
        echo -e "${YELLOW}Note:${NC} $remaining item(s) remain in cache (may be unlisted plugins)"
        echo "To clear entire marketplace cache: rm -rf \"$MARKETPLACE_CACHE\""
    fi
fi
