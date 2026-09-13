# Plan: notification batching

1. Add `BatchAccumulator` in notification-service, flush every 30s or 50 items.
2. New kafka topic `notif.batched.v1`, 12 partitions, keyed by userId.
3. Backfill the last 7 days from `notif_events` into the new topic.
4. Cut over readers behind proctor `notifbatch`, delete the old path after 2 releases.

Assumes: ordering per user is preserved by the userId key; the backfill can
replay without duplicating already-delivered notifications.
