#!/usr/bin/env bash
set -euo pipefail

# Boot an iOS Simulator by name and optional runtime

usage() {
    echo "Usage: $0 <device-name> [--runtime <ios-version>]"
    echo ""
    echo "Examples:"
    echo "  $0 'iPhone 16 Pro'"
    echo "  $0 'iPhone 15' --runtime 'iOS 17.0'"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

DEVICE_NAME="$1"
shift

RUNTIME=""
while [ $# -gt 0 ]; do
    case "$1" in
        --runtime)
            RUNTIME="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Check if already booted
BOOTED_UDID=$(xcrun simctl list devices booted -j 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in data.get('devices', {}).items():
    for d in devices:
        if d.get('state') == 'Booted' and d.get('name') == '$DEVICE_NAME':
            if '$RUNTIME' == '' or '$RUNTIME' in runtime:
                print(d['udid'])
                sys.exit(0)
" 2>/dev/null || true)

if [ -n "$BOOTED_UDID" ]; then
    echo "Simulator '$DEVICE_NAME' already booted: $BOOTED_UDID"
    echo "$BOOTED_UDID"
    exit 0
fi

# Find the simulator UDID
UDID=$(xcrun simctl list devices available -j 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in data.get('devices', {}).items():
    for d in devices:
        if d.get('name') == '$DEVICE_NAME' and d.get('isAvailable', False):
            if '$RUNTIME' == '' or '$RUNTIME' in runtime:
                print(d['udid'])
                sys.exit(0)
print('')
" 2>/dev/null || true)

if [ -z "$UDID" ]; then
    echo "Error: Simulator '$DEVICE_NAME' not found" >&2
    if [ -n "$RUNTIME" ]; then
        echo "  Runtime filter: $RUNTIME" >&2
    fi
    echo "  Available devices:" >&2
    xcrun simctl list devices available | grep -i "iphone\|ipad" >&2
    exit 1
fi

echo "Booting simulator '$DEVICE_NAME' ($UDID)..."
xcrun simctl boot "$UDID"

# Wait for boot to complete
for i in {1..30}; do
    STATE=$(xcrun simctl list devices -j | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in data.get('devices', {}).items():
    for d in devices:
        if d.get('udid') == '$UDID':
            print(d.get('state', ''))
            sys.exit(0)
" 2>/dev/null || true)

    if [ "$STATE" = "Booted" ]; then
        echo "Simulator booted: $UDID"
        echo "$UDID"
        exit 0
    fi
    sleep 1
done

echo "Error: Simulator did not boot within 30 seconds" >&2
exit 1
