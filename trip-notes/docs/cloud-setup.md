# Running trip-notes in a Claude Code cloud session

How to make `build-itinerary` and `find-nearby` run on claude.ai/code (or `claude --cloud`) from the ObsidianVault repo. The skills themselves branch on `CLAUDE_CODE_REMOTE=true`; see "Execution environment" in each SKILL.md.

This repo is **public**. Nothing personal — preferences, sightings, keys, the R2 account ID — goes in it.

## What moves where

| Thing | Mac | Cloud VM |
|---|---|---|
| The plugin | directory marketplace | cloned from GitHub by the setup script |
| `trip-maps` on PATH | `~/.local/bin` symlink | `/usr/local/bin` symlink, setup script |
| `agent-browser` CLI + skill | Homebrew, `~/.claude/skills/agent-browser` | npm + Chrome + skill stub, setup script |
| Google Maps key | `~/.config/trip-notes/maps.env` | API credential, attached by the proxy |
| `preferences.md`, `sightings.jsonl` | `~/.config/trip-notes/` | pulled from / pushed to R2 by `find-nearby/scripts/config-sync` |
| The finished note | vault | vault, `publish-private: true`, pushed on the session branch and opened as a PR into `main` (a session can push only to its own branch); merging it publishes the page to the private site |

## 1. R2 bucket (once, on the Mac)

1. Cloudflare dashboard → R2 → create bucket `trip-notes-config`. Keep it private: no r2.dev URL, no custom domain.
2. R2 → Manage API tokens → create **two** tokens, both *Object Read & Write*, both restricted to `trip-notes-config` — one for the Mac, one for the cloud environment, so either can be revoked alone.
3. rclone remote for the Mac token:
   ```ini
   [r2-trip-notes]
   type = s3
   provider = Cloudflare
   access_key_id = <mac token id>
   secret_access_key = <mac token secret>
   endpoint = https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   acl = private
   no_check_bucket = true
   ```
4. First upload, then check it came back:
   ```bash
   skills/find-nearby/scripts/config-sync push
   rclone ls r2-trip-notes:trip-notes-config     # preferences.md + sightings.jsonl, no maps.env
   ```

## 2. Cloud environment (claude.ai/code → environment settings)

**Network access: Full.** Both skills research the open web (blogs, official sites, Instagram), and WebFetch obeys the allowlist too.

**Environment variables** (readable by everyone who uses the environment — keep it a personal one):
```
TRIP_NOTES_R2_ACCESS_KEY_ID=<cloud token id>
TRIP_NOTES_R2_SECRET_ACCESS_KEY=<cloud token secret>
TRIP_NOTES_R2_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
TRIP_NOTES_SITE_URL=https://<your private Quartz site>   # optional: lets the report give the page URL
```
The names are namespaced so they cannot collide with another project's `AWS_*` in the same environment. R2 goes through env vars rather than an API credential because the SigV4 credential type cannot sign a non-AWS host (every request 502s).

**API credential** for Google Maps (only addable when *editing* an existing environment):
- Type: Bearer
- Header name: `X-Goog-Api-Key`, prefix: empty
- Hosts: `places.googleapis.com`, `routes.googleapis.com`

Leave `GOOGLE_MAPS_API_KEY` unset in the environment; `trip-maps` then sends no key header and the proxy attaches it.

**Setup script:**
```bash
#!/bin/bash
set -euo pipefail

# trip-notes plugin
rm -rf /opt/cc-marketplace
git clone --depth 1 https://github.com/koromiko/my_claudecode_marketplace /opt/cc-marketplace
if ! { claude plugin marketplace add /opt/cc-marketplace \
       && claude plugin install trip-notes@cc-local-marketplace; }; then
  # fallback: plain user skills (named build-itinerary / find-nearby, no prefix)
  mkdir -p ~/.claude/skills
  ln -sfn /opt/cc-marketplace/trip-notes/skills/build-itinerary ~/.claude/skills/build-itinerary
  ln -sfn /opt/cc-marketplace/trip-notes/skills/find-nearby     ~/.claude/skills/find-nearby
fi
ln -sf /opt/cc-marketplace/trip-notes/skills/build-itinerary/scripts/maps /usr/local/bin/trip-maps

# agent-browser: CLI, Chrome with its Linux deps, and the discovery skill
npm install -g agent-browser
agent-browser install --with-deps
mkdir -p ~/.claude/skills/agent-browser
curl -fsSL https://raw.githubusercontent.com/vercel-labs/agent-browser/main/skills/agent-browser/SKILL.md \
  -o ~/.claude/skills/agent-browser/SKILL.md

# config-sync backend + JSON tooling
command -v jq >/dev/null || { apt-get update && apt-get install -y jq; }
pip install awscli
```

## 3. Verify in stages

1. **Local**: `tests/*.sh` pass; `config-sync push` from the Mac round-trips.
2. **Cloud checklist session** (no real work) — have it report, never values:
   - `/skills` lists `trip-notes:build-itinerary` and `trip-notes:find-nearby` (or the unprefixed fallback) and `agent-browser`
   - `echo $CLAUDE_CODE_REMOTE`, `command -v trip-maps agent-browser aws jq`
   - `trip-maps place "東京駅"` returns a place_id (proves the proxy key)
   - `config-sync pull` updates both files; `wc -l ~/.config/trip-notes/sightings.jsonl` matches the Mac
   - `agent-browser open https://example.com --load domcontentloaded --timeout 20000` works
3. **Full cloud trial**: one small `find-nearby` run. Afterwards, on the Mac, `config-sync pull` must bring the new sightings in, and the note must arrive on the pushed branch.

## Known limits

- Instagram from a datacenter IP, logged out, may get a login wall more often than at home. The skills already treat "could not read" as distinct from "nothing there", so the cost is a missing embed, not a wrong one.
- If the environment caches its setup, a newer plugin version on GitHub reaches the VM only when the setup script runs again.
