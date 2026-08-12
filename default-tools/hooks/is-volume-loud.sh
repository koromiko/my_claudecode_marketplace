#!/bin/bash
# Checks system output volume against a threshold.
# Exit 0 = volume is at/above threshold (suppress spoken announcements).
# Exit 1 = volume is below threshold, or it could not be read.
#
# Threshold percent: CLAUDE_HOOK_SAY_MAX_VOLUME (default 50).
# Some output devices (aggregate, certain Bluetooth) report "missing value";
# that case exits 1 so the announcement still happens.

threshold="${CLAUDE_HOOK_SAY_MAX_VOLUME:-50}"

volume=$(osascript -e 'output volume of (get volume settings)' 2>/dev/null) || exit 1
[[ "$volume" =~ ^[0-9]+$ ]] || exit 1

if (( volume >= threshold )); then
  exit 0
fi

exit 1
