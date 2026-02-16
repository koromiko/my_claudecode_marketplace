#!/usr/bin/env bash
set -euo pipefail

# Find the built .app bundle in DerivedData

usage() {
    echo "Usage: $0 [scheme-name] [--configuration Debug|Release]"
    echo ""
    echo "Finds the .app bundle for the given scheme in DerivedData."
    echo "If no scheme is given, searches for any .app in DerivedData."
    exit 1
}

SCHEME="${1:-}"
CONFIG="Debug"

shift || true
while [ $# -gt 0 ]; do
    case "$1" in
        --configuration)
            CONFIG="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            shift
            ;;
    esac
done

SDK_DIR="${CONFIG}-iphonesimulator"

# Method 1: Use xcodebuild -showBuildSettings (most reliable)
if [ -n "$SCHEME" ]; then
    PRODUCTS_DIR=$(xcodebuild -scheme "$SCHEME" -configuration "$CONFIG" \
        -showBuildSettings 2>/dev/null \
        | grep " BUILT_PRODUCTS_DIR" | awk '{print $3}' || true)

    if [ -n "$PRODUCTS_DIR" ] && [ -d "$PRODUCTS_DIR" ]; then
        APP_PATH=$(find "$PRODUCTS_DIR" -name "*.app" -maxdepth 1 | head -1)
        if [ -n "$APP_PATH" ]; then
            echo "$APP_PATH"
            exit 0
        fi
    fi
fi

# Method 2: Search DerivedData
SEARCH_PATTERN="$HOME/Library/Developer/Xcode/DerivedData"
if [ -n "$SCHEME" ]; then
    SEARCH_PATTERN="$SEARCH_PATTERN/${SCHEME}-*"
fi

APP_PATH=$(find $SEARCH_PATTERN/Build/Products/$SDK_DIR \
    -name "*.app" -maxdepth 1 2>/dev/null | head -1 || true)

if [ -n "$APP_PATH" ]; then
    echo "$APP_PATH"
    exit 0
fi

echo "Error: No .app bundle found" >&2
echo "  Searched: $SEARCH_PATTERN/Build/Products/$SDK_DIR/" >&2
echo "  Run your build command first." >&2
exit 1
