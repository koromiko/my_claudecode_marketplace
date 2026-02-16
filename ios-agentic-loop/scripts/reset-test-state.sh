#!/usr/bin/env bash
set -euo pipefail

# Reset app state on the simulator for clean test runs

usage() {
    echo "Usage: $0 <bundle_id> [--app-group <group_id>] [--keychain]"
    echo ""
    echo "Arguments:"
    echo "  bundle_id          App bundle identifier (required)"
    echo "  --app-group <id>   Also clear shared app group UserDefaults"
    echo "  --keychain         Also reset the simulator keychain"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

BUNDLE_ID="$1"
shift

APP_GROUP=""
RESET_KEYCHAIN=false

while [ $# -gt 0 ]; do
    case "$1" in
        --app-group)
            APP_GROUP="$2"
            shift 2
            ;;
        --keychain)
            RESET_KEYCHAIN=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

echo "=== Resetting test state for $BUNDLE_ID ==="

# Terminate app if running
xcrun simctl terminate booted "$BUNDLE_ID" 2>/dev/null || true
echo "  App terminated"

# Clear main app UserDefaults
xcrun simctl spawn booted defaults delete "$BUNDLE_ID" 2>/dev/null || true
echo "  UserDefaults cleared"

# Clear app group if specified
if [ -n "$APP_GROUP" ]; then
    xcrun simctl spawn booted defaults delete "$APP_GROUP" 2>/dev/null || true
    echo "  App group '$APP_GROUP' UserDefaults cleared"
fi

# Reset keychain if requested
if [ "$RESET_KEYCHAIN" = true ]; then
    xcrun simctl keychain booted reset 2>/dev/null || true
    echo "  Keychain reset"
fi

echo "=== Reset complete ==="
