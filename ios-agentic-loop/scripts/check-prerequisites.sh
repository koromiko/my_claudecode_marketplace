#!/usr/bin/env bash
set -euo pipefail

# Check prerequisites for agentic iOS testing

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    local install_msg="$3"

    if eval "$cmd" > /dev/null 2>&1; then
        echo "  [PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name"
        echo "         Install: $install_msg"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Agentic iOS Testing Prerequisites ==="
echo ""

check "Xcode" \
    "xcode-select -p" \
    "Install Xcode from the App Store, then run: xcode-select --install"

check "Xcode Command Line Tools" \
    "xcode-select -p && test -d \$(xcode-select -p)" \
    "xcode-select --install"

check "idb (iOS Development Bridge)" \
    "which idb" \
    "pip3 install fb-idb  (or: pipx install fb-idb)"

check "idb_companion" \
    "which idb_companion" \
    "brew tap facebook/fb && brew install idb-companion"

check "Maestro" \
    "which maestro" \
    "curl -Ls 'https://get.maestro.mobile.dev' | bash"

check "Booted simulator" \
    "xcrun simctl list devices booted 2>/dev/null | grep -q Booted" \
    "xcrun simctl boot 'iPhone 16 Pro'"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Fix the failed checks above before proceeding."
    exit 1
else
    echo ""
    echo "All prerequisites met. Ready for agentic testing."
    exit 0
fi
