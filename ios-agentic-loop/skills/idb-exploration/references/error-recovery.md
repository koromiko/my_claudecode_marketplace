# Error Recovery Reference

## Crash Detection and Recovery

```
describe-all returns empty/error
    |
    idb list-apps --running
    |
    +-- App not running --> App crashed
    |       |
    |       idb launch <bundle_id>
    |       Wait 3 seconds
    |       Re-observe
    |       Log crash event
    |
    +-- App running --> UI may be loading
            |
            Wait 2 seconds
            Re-try describe-all
            |
            +-- Still empty --> Force terminate and restart
            +-- Has elements --> Continue
```

## Error Types

| Error Type | Detection | Recovery |
|-----------|-----------|----------|
| Unexpected alert | Alert-type elements in a11y tree | Tap "OK" / "Dismiss" / "Cancel" |
| App crash | describe-all empty + app not in `list-apps --running` | `idb launch` to restart |
| Login required | Login screen elements detected | Execute login flow with test credentials |
| Loading stuck | Screenshot unchanged after 5s | Swipe to refresh or navigate back |
| Keyboard blocking UI | Keyboard visible, target element hidden behind it | `idb ui key 1 escape` or tap outside text area |
| Network error | Error banner or "Retry" button visible | Retry action after 2s delay |
| Permission dialog | System alert with "Allow" / "Don't Allow" | Tap "Allow" (or "Don't Allow" per test needs) |

## Timeout Escalation

| Level | Wait Time | Situation |
|-------|-----------|-----------|
| 1 | 400ms | Normal action delay, wait for UI update |
| 2 | 2s | Extended wait for network responses, animations |
| 3 | 5s | describe-all timeout, possible hung state |
| 4 | 10s | Screenshot diff check -- is anything changing? |
| 5 | 30s | Force terminate and restart app |

## Stuck State Detection

Compare consecutive screenshots to detect if the app is stuck:

1. Take screenshot after action
2. Compare with previous screenshot
3. If **different**: UI is responding, continue
4. If **identical** after action:
   - Retry action with slightly adjusted coordinates (+/- 10px)
   - If still identical: try alternative action (back button, swipe)
   - If still stuck after 3 attempts: force restart

For robust comparison, use perceptual hashing rather than exact pixel comparison (clock changes, blinking cursors cause false negatives).

## Retry Limits

| Operation | Max Retries | Backoff Strategy |
|-----------|------------|------------------|
| Single tap | 3 | +100ms delay between retries |
| Text input | 2 | Clear field before retry |
| Swipe | 3 | Adjust coordinates by 10px |
| App launch | 3 | 2s between attempts |
| describe-all | 5 | 1s between attempts |
| Full goal | 1 | Report failure, move to next goal |

## Error Reporting

Each run produces a summary:

```json
{
  "run_id": "run_20260216_143022",
  "scenario": "form_submission",
  "status": "completed_with_errors",
  "total_steps": 18,
  "successful_actions": 15,
  "failed_actions": 3,
  "retries": 5,
  "crashes_recovered": 0,
  "duration_seconds": 47,
  "errors": [
    {
      "step": 7,
      "action": "tap",
      "target": "Submit button",
      "error": "Element not found in describe-all, used vision fallback",
      "resolved": true
    }
  ],
  "goals_achieved": ["form_filled", "form_submitted"],
  "goals_missed": ["success_verified"]
}
```

## Vision-Based Fallback

When `describe-all` fails to report an element that's visually present:

1. Use the screenshot to **identify the element visually**
2. Estimate coordinates from visual position (less precise)
3. Attempt the tap at estimated coordinates
4. Verify success via post-action screenshot

This ensures the agent can still interact with elements even when accessibility data is incomplete.
