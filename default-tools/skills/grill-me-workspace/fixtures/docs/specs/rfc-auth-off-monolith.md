# RFC: move auth off the monolith

Extract session validation and token issuance into `auth-svc`.

1. Stand up `auth-svc` with the existing JWT signing keys, read-only at first.
2. Dual-write sessions to the monolith and `auth-svc` for one release.
3. Flip readers behind proctor `authsvc`, monolith becomes a proxy.
4. Delete the monolith auth package once the proxy sees zero direct callers.

Assumes: key rotation can be coordinated across both services without a
flag day, and the monolith's session table is the only writer today.
