#!/bin/bash
#
# local_release.sh - Bump plugin versions and clear caches
#
# Usage: scripts/local_release.sh [options] [plugin-name] [bump-strategy]
#
# Modes:
#   local_release.sh session-manager patch     Bump version + clear cache
#   local_release.sh session-manager           Clear cache only (no bump)
#   local_release.sh --modified                Clear caches for all git-modified plugins
#   local_release.sh --dry-run session-manager patch   Preview bump + cache clear
#   local_release.sh --dry-run --modified      Preview which modified caches would clear
#
# Options:
#   --dry-run   Preview actions without making changes
#   --modified  Detect plugins with uncommitted git changes and clear their caches
#
# Bump strategies: major, minor, patch

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"
CACHE_BASE="$HOME/.claude/plugins/cache"

# --- Parse arguments ---
DRY_RUN=false
MODIFIED=false
PLUGIN_NAME=""
BUMP_STRATEGY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=true; shift ;;
        --modified) MODIFIED=true; shift ;;
        -*)
            echo -e "${RED}Error: Unknown option '$1'${NC}" >&2
            echo "Usage: $0 [--dry-run] [--modified] [plugin-name] [bump-strategy]" >&2
            exit 1
            ;;
        *)
            if [[ -z "$PLUGIN_NAME" ]]; then
                PLUGIN_NAME="$1"
            elif [[ -z "$BUMP_STRATEGY" ]]; then
                BUMP_STRATEGY="$1"
            else
                echo -e "${RED}Error: Unexpected argument '$1'${NC}" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# --- Validate environment ---
if ! command -v jq &>/dev/null; then
    echo -e "${RED}Error: jq is required but not installed. Install with: brew install jq${NC}" >&2
    exit 1
fi

if [[ ! -f "$MARKETPLACE_JSON" ]]; then
    echo -e "${RED}Error: marketplace.json not found at $MARKETPLACE_JSON${NC}" >&2
    exit 1
fi

if [[ -z "$PLUGIN_NAME" && "$MODIFIED" == false ]]; then
    echo -e "${RED}Error: Provide a plugin name or use --modified${NC}" >&2
    echo "Usage: $0 [--dry-run] [--modified] [plugin-name] [bump-strategy]" >&2
    exit 1
fi

if [[ -n "$BUMP_STRATEGY" && ! "$BUMP_STRATEGY" =~ ^(major|minor|patch)$ ]]; then
    echo -e "${RED}Error: Invalid bump strategy '$BUMP_STRATEGY'${NC}" >&2
    echo "Valid options: major, minor, patch" >&2
    exit 1
fi

if [[ "$MODIFIED" == true && -n "$BUMP_STRATEGY" ]]; then
    echo -e "${RED}Error: --modified cannot be combined with a bump strategy${NC}" >&2
    exit 1
fi

# --- Read marketplace metadata ---
MARKETPLACE_NAME=$(jq -r '.name' "$MARKETPLACE_JSON")
MARKETPLACE_CACHE="$CACHE_BASE/$MARKETPLACE_NAME"

if $DRY_RUN; then
    echo -e "${YELLOW}[DRY-RUN] Preview only — no changes will be made${NC}"
    echo ""
fi

# --- Helper: clear cache for a single plugin ---
clear_plugin_cache() {
    local plugin="$1"
    local cache_dir="$MARKETPLACE_CACHE/$plugin"

    if [[ -d "$cache_dir" ]]; then
        if $DRY_RUN; then
            echo -e "  ${YELLOW}[DRY-RUN]${NC} Would clear cache: $cache_dir"
        else
            rm -rf "$cache_dir"
            echo -e "  ${GREEN}✓${NC} Cache cleared: $plugin"
        fi
        return 0
    else
        echo -e "  ${YELLOW}-${NC} No cache found: $plugin"
        return 0
    fi
}

# --- Helper: bump version for a single plugin ---
bump_plugin_version() {
    local plugin="$1"
    local strategy="$2"
    local source_path
    source_path=$(jq -r --arg name "$plugin" '.plugins[] | select(.name == $name) | .source' "$MARKETPLACE_JSON")
    local plugin_json="$REPO_ROOT/${source_path#./}/.claude-plugin/plugin.json"

    if [[ ! -f "$plugin_json" ]]; then
        echo -e "  ${RED}Error: plugin.json not found at $plugin_json${NC}" >&2
        return 1
    fi

    python3 - "$plugin_json" "$MARKETPLACE_JSON" "$plugin" "$strategy" "$DRY_RUN" << 'PYEOF'
import json, sys

plugin_json_path = sys.argv[1]
marketplace_path = sys.argv[2]
plugin_name      = sys.argv[3]
strategy         = sys.argv[4]
dry_run          = sys.argv[5] == "true"

# Read plugin.json
with open(plugin_json_path, "r") as f:
    plugin_data = json.load(f)

old_version = plugin_data.get("version", "0.0.0")
parts = old_version.split(".")
while len(parts) < 3:
    parts.append("0")
major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

if strategy == "major":
    major += 1; minor = 0; patch = 0
elif strategy == "minor":
    minor += 1; patch = 0
elif strategy == "patch":
    patch += 1

new_version = f"{major}.{minor}.{patch}"

if dry_run:
    print(f"  [DRY-RUN] Would bump {plugin_name}: {old_version} → {new_version}")
else:
    # Update plugin.json
    plugin_data["version"] = new_version
    with open(plugin_json_path, "w") as f:
        json.dump(plugin_data, f, indent=2)
        f.write("\n")

    # Update marketplace.json
    with open(marketplace_path, "r") as f:
        mp_data = json.load(f)
    for p in mp_data.get("plugins", []):
        if p.get("name") == plugin_name:
            p["version"] = new_version
            break
    with open(marketplace_path, "w") as f:
        json.dump(mp_data, f, indent=2)
        f.write("\n")

    print(f"  ✓ Version bumped: {old_version} → {new_version}")
PYEOF
}

# --- Mode: --modified ---
if [[ "$MODIFIED" == true ]]; then
    echo "Detecting modified plugins..."
    echo ""

    # Get all changed files (staged + unstaged + untracked)
    changed_files=$(cd "$REPO_ROOT" && {
        git diff --name-only HEAD 2>/dev/null || true
        git diff --name-only --cached 2>/dev/null || true
        git ls-files --others --exclude-standard 2>/dev/null || true
    } | sort -u)

    # Get plugin names from marketplace
    plugin_names=$(jq -r '.plugins[].name' "$MARKETPLACE_JSON")

    matched=0
    for plugin in $plugin_names; do
        # Check if any changed file starts with the plugin directory
        if echo "$changed_files" | grep -q "^${plugin}/"; then
            ((matched++))
            echo -e "${GREEN}Modified:${NC} $plugin"
            clear_plugin_cache "$plugin"
        fi
    done

    echo ""
    if [[ $matched -eq 0 ]]; then
        echo -e "${YELLOW}No modified plugins detected.${NC}"
    else
        echo -e "Processed ${GREEN}$matched${NC} modified plugin(s)."
    fi
    exit 0
fi

# --- Mode: single plugin ---
echo "Plugin: $PLUGIN_NAME"
echo "Marketplace: $MARKETPLACE_NAME"
echo ""

# Validate plugin exists in marketplace
if ! jq -e --arg name "$PLUGIN_NAME" '.plugins[] | select(.name == $name)' "$MARKETPLACE_JSON" &>/dev/null; then
    echo -e "${RED}Error: Plugin '$PLUGIN_NAME' not found in marketplace.json${NC}" >&2
    echo ""
    echo "Available plugins:"
    jq -r '.plugins[].name' "$MARKETPLACE_JSON" | while read -r name; do
        echo "  - $name"
    done
    exit 1
fi

# Bump version if strategy given
if [[ -n "$BUMP_STRATEGY" ]]; then
    echo "Bumping version ($BUMP_STRATEGY):"
    bump_plugin_version "$PLUGIN_NAME" "$BUMP_STRATEGY"
    echo ""
fi

# Clear cache
echo "Cache:"
clear_plugin_cache "$PLUGIN_NAME"

echo ""
echo -e "${GREEN}Done.${NC}"
