# Extract trip-notes into its own repository — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `trip-notes` plugin out of `koromiko/my_claudecode_marketplace` into a new **private** repo `koromiko/trip-notes`, with its full history, installable on the Mac and in Claude Code cloud sessions, and with the generalization proposal recorded as a roadmap.

**Architecture:** `git filter-repo` on a fresh clone keeps only the plugin's two historical directories (`travel-drive-itinerary/` before commit `09cc4a7`, `trip-notes/` after) plus its five design docs, and moves the plugin to the repo root. The new repo is its own single-plugin marketplace (`.claude-plugin/marketplace.json` next to `plugin.json`, plugin source `./`), so the install id becomes `trip-notes@trip-notes`. The old marketplace drops the entry entirely rather than redirecting to it, so there is only ever one install of the skills.

**Tech Stack:** git, git-filter-repo (`/opt/homebrew/bin/git-filter-repo`), gh CLI, bash test scripts, GitHub Actions (ubuntu-latest), Claude Code plugin CLI.

**Spec:** this conversation's decisions, restated under Global Constraints. The roadmap content comes from the generalization proposal and is reproduced verbatim in Task 5.

## Global Constraints

- New repo: `koromiko/trip-notes`, **private** (for now), no LICENSE file, default branch `main`, local path `/Users/neo/Projects/trip-notes`.
- Marketplace name `trip-notes`; plugin name `trip-notes`; install id `trip-notes@trip-notes`. Plugin version stays `2.1.0` (no behavior change).
- The repo is written as if public (it may be opened later) and contains no personal data: no R2 account ID, no private-site domain, no preferences or sightings content. `/Users/neo/...` paths inside historical plan docs are acceptable (already public in the old repo).
- Only `main` is extracted; `feat/trip-notes-photos-ig-prerank` is already merged into it.
- Every task ends with all five suites passing: `tests/test-maps.sh`, `tests/test-skill-integrity.sh`, `tests/test-note-provenance.sh`, `tests/test-sightings.sh`, `tests/test-config-sync.sh`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Use `git -C <absolute path>`, never `cd … && git …`.

## Review Focus

1. **The suites on Linux.** The cloud VM is Linux and the scripts were only ever run on macOS. `tests/test-config-sync.sh`'s `mtime()` tries `stat -f %m` first; GNU `stat -f` means *file-system status* and prints junk instead of failing. Expected: CI on ubuntu-latest passes. Pinned by Task 4 (fix + CI).
2. **Two installs of the same skills.** If the old marketplace entry survives while `trip-notes@trip-notes` is installed, both `build-itinerary` copies load. Expected: exactly one. Pinned by Task 7's `claude plugin list` check and Task 8's removal.
3. **The `trip-maps` symlink after the move.** `~/.local/bin/trip-maps` points into the old repo; after Task 8 deletes that directory it would dangle and every Maps call would fail. Expected: it points into the new repo before the old copy is deleted. Pinned by Task 7.
4. **History that stops at the rename.** Filtering only `trip-notes/` drops everything before `09cc4a7`. Expected: `git log` in the new repo reaches `Add travel-drive-itinerary plugin`. Pinned by Task 2.
5. **Marketplace source `./`.** The docs show relative sources like `./plugins/x` but no example of `./`. Expected: `claude plugin validate .` passes and install succeeds; if not, Task 3's fallback applies. Pinned by Task 3.

---

### Task 1: Land the pending cloud-support work in the old repo

The cloud-session changes (config-sync, maps key via proxy, PR delivery, docs/cloud-setup.md, v2.1.0) are uncommitted. They must be in history before extraction.

**Files:**
- Commit: `.claude-plugin/marketplace.json`, `trip-notes/**`, this plan file

- [ ] **Step 1: Run the suites**

```bash
M=/Users/neo/Projects/claude_local_marketplace
for t in $M/trip-notes/tests/*.sh; do bash "$t" 2>&1 | tail -1; done
```
Expected: five summary lines, none with a nonzero failure count.

- [ ] **Step 2: Commit and push**

```bash
M=/Users/neo/Projects/claude_local_marketplace
git -C $M add .claude-plugin/marketplace.json trip-notes docs/superpowers/plans/2026-09-29-extract-trip-notes-repo.md
git -C $M status --short   # expect nothing left under trip-notes/ except ignored *-workspace
git -C $M commit -m "feat(trip-notes): 2.1.0 — run in Claude Code cloud sessions

- maps: no key header when CLAUDE_CODE_REMOTE=true and no key (proxy injects it)
- find-nearby: config-sync pulls/pushes preferences + sightings via private R2
- both skills: cloud delivery as publish-private note + PR into main
- docs/cloud-setup.md; plan for extracting the plugin into its own repo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C $M push origin main
```

---

### Task 2: Extract the history into a new local repo

**Files:**
- Create: `/Users/neo/Projects/trip-notes/` (whole repo)

- [ ] **Step 1: Fresh clone (filter-repo refuses to run on a non-fresh clone)**

```bash
test ! -e /Users/neo/Projects/trip-notes || { echo "target exists — stop"; exit 1; }
git clone --no-local --single-branch --branch main \
  /Users/neo/Projects/claude_local_marketplace /Users/neo/Projects/trip-notes
```

- [ ] **Step 2: Filter**

```bash
T=/Users/neo/Projects/trip-notes
git -C $T filter-repo --force \
  --path travel-drive-itinerary/ \
  --path trip-notes/ \
  --path docs/superpowers/specs/2026-09-05-find-nearby-design.md \
  --path docs/superpowers/specs/2026-09-06-trip-itinerary-site-design.md \
  --path docs/superpowers/specs/2026-09-16-find-nearby-preference-learning-design.md \
  --path docs/superpowers/plans/2026-09-05-find-nearby.md \
  --path docs/superpowers/plans/2026-09-16-find-nearby-preference-learning.md \
  --path docs/superpowers/plans/2026-09-29-extract-trip-notes-repo.md \
  --path-rename travel-drive-itinerary/: \
  --path-rename trip-notes/:
git -C $T remote -v   # expect nothing: filter-repo drops origin
```

- [ ] **Step 3: Verify shape and history**

```bash
T=/Users/neo/Projects/trip-notes
ls -a $T          # expect: .claude-plugin AGENTS.md CLAUDE.md docs skills tests (no trip-notes/, no other plugins)
git -C $T log --oneline | tail -1           # expect: "Add travel-drive-itinerary plugin (build-drive-itinerary skill)"
M=/Users/neo/Projects/claude_local_marketplace
want=$(git -C $M log --oneline main -- travel-drive-itinerary trip-notes docs/superpowers/specs/2026-09-05-find-nearby-design.md docs/superpowers/specs/2026-09-06-trip-itinerary-site-design.md docs/superpowers/specs/2026-09-16-find-nearby-preference-learning-design.md docs/superpowers/plans/2026-09-05-find-nearby.md docs/superpowers/plans/2026-09-16-find-nearby-preference-learning.md docs/superpowers/plans/2026-09-29-extract-trip-notes-repo.md | wc -l)
got=$(git -C $T log --oneline | wc -l)
echo "want=$want got=$got"                   # expect equal (filter-repo keeps exactly the commits touching the kept paths)
git -C $T log --oneline -1                  # expect: Task 1's commit
for t in $T/tests/*.sh; do bash "$t" 2>&1 | tail -1; done   # all pass
```

---

### Task 3: Make the repo a standalone marketplace

**Files:**
- Create: `.claude-plugin/marketplace.json`, `.gitignore`, `README.md`
- Modify: `CLAUDE.md` (test paths), `docs/cloud-setup.md` (clone URL, install id), `tests/test-skill-integrity.sh` (version check)

- [ ] **Step 1: Write the failing test — marketplace and plugin versions must agree**

Append before the summary block of `tests/test-skill-integrity.sh`:

```bash
# The marketplace entry and plugin.json must carry the same name and version;
# a mismatch makes `claude plugin update` see a version that is not the plugin's.
ROOT="$SCRIPT_DIR/.."
if [[ -f "$ROOT/.claude-plugin/marketplace.json" ]]; then
  pv=$(jq -r '.version' "$ROOT/.claude-plugin/plugin.json")
  mv=$(jq -r '.plugins[] | select(.name=="trip-notes") | .version' "$ROOT/.claude-plugin/marketplace.json")
  if [[ "$pv" == "$mv" ]]; then assert_pass "marketplace and plugin.json versions agree ($pv)"
  else assert_fail "marketplace and plugin.json versions agree" "plugin.json=$pv marketplace=$mv"; fi
else
  assert_fail "marketplace.json exists at the repo root" "missing"
fi
```

The file already defines `SCRIPT_DIR`, `assert_pass` and `assert_fail` (lines 10–15).

- [ ] **Step 2: Run it — expect FAIL "marketplace.json exists at the repo root"**

```bash
bash /Users/neo/Projects/trip-notes/tests/test-skill-integrity.sh | tail -3
```

- [ ] **Step 3: Create `.claude-plugin/marketplace.json`**

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "trip-notes",
  "description": "Verified travel notes as markdown: drive/train itineraries and a nearby-places finder ranked against your own preferences",
  "owner": { "name": "Neo" },
  "plugins": [
    {
      "name": "trip-notes",
      "description": "Verified travel notes as Obsidian markdown — drive/train itineraries, plus a nearby-places finder ranked against your own saved preferences",
      "version": "2.1.0",
      "source": "./",
      "category": "travel"
    }
  ]
}
```

- [ ] **Step 4: Validate the `./` source**

```bash
claude plugin validate /Users/neo/Projects/trip-notes
```
Expected: `✔ Validation passed`. **Fallback if `./` is rejected:** `git -C $T mv` the plugin files (`.claude-plugin/plugin.json`, `skills`, `AGENTS.md`, `CLAUDE.md`) under `plugins/trip-notes/`, set `"source": "./plugins/trip-notes"`, and point every path in later tasks there.

- [ ] **Step 5: `.gitignore`**

```gitignore
.DS_Store
# Skill eval workspaces (generated)
skills/*-workspace/
```

- [ ] **Step 6: Fix repo-relative paths**

- `CLAUDE.md` "Tests" block: `trip-notes/tests/` → `tests/` (five lines).
- `docs/cloud-setup.md` setup script, replace the plugin block with:

```bash
rm -rf /opt/trip-notes
# private repo: TRIP_NOTES_GH_TOKEN is a fine-grained token, read-only Contents on
# koromiko/trip-notes only, set as an environment variable. Try the plain URL
# first in case the GitHub proxy already authenticates setup-script clones.
git clone --depth 1 https://github.com/koromiko/trip-notes /opt/trip-notes 2>/dev/null \
  || git clone --depth 1 "https://x-access-token:${TRIP_NOTES_GH_TOKEN}@github.com/koromiko/trip-notes" /opt/trip-notes
git -C /opt/trip-notes remote set-url origin https://github.com/koromiko/trip-notes   # drop the token from .git/config
if ! { claude plugin marketplace add /opt/trip-notes \
       && claude plugin install trip-notes@trip-notes; }; then
  mkdir -p ~/.claude/skills
  ln -sfn /opt/trip-notes/skills/build-itinerary ~/.claude/skills/build-itinerary
  ln -sfn /opt/trip-notes/skills/find-nearby     ~/.claude/skills/find-nearby
fi
ln -sf /opt/trip-notes/skills/build-itinerary/scripts/maps /usr/local/bin/trip-maps
```
  and in its first table `| The plugin | directory marketplace | cloned from GitHub by the setup script |` stays true.
- Grep for leftovers: `grep -rn 'claude_local_marketplace\|cc-local-marketplace\|trip-notes/tests\|trip-notes/skills' --include='*.md' --include='*.sh' --include='*.json' /Users/neo/Projects/trip-notes | grep -v '^.*docs/superpowers/'` → expect no output (historical plan docs keep their old paths on purpose).

- [ ] **Step 7: `README.md`** — public front page:

```markdown
# trip-notes

A Claude Code plugin that turns a travel request into a **verified** markdown note.

- `build-itinerary` — self-drive routes or train/walk plans: Google Maps links, real driving/walking times, opening hours checked against official sources, blog references, photos.
- `find-nearby` — restaurants, cafés, shops or parks within a real travel-time budget of a place, ranked against your own saved preferences.

Every link, image and time in the note is checked by a browser subagent before delivery; anything that could not be verified is listed, not hidden.

## Install

    claude plugin marketplace add koromiko/trip-notes
    claude plugin install trip-notes@trip-notes

Requirements: `jq`, `curl`, the [`agent-browser`](https://github.com/vercel-labs/agent-browser) CLI, and a Google Maps Platform key (Places API (New) + Routes API) in `~/.config/trip-notes/maps.env`:

    export GOOGLE_MAPS_API_KEY=...

Put `skills/build-itinerary/scripts/maps` on your PATH as `trip-maps`.

Cloud sessions (claude.ai/code): see [docs/cloud-setup.md](docs/cloud-setup.md).

## Status

Output is currently Traditional Chinese, Obsidian-flavoured markdown, tuned for Japan. Making locale, output format and delivery configurable is planned: [docs/roadmap/generalization.md](docs/roadmap/generalization.md).

## Tests

    for t in tests/*.sh; do bash "$t"; done
```

- [ ] **Step 8: Run all suites — expect all pass, including the new version check**

```bash
for t in /Users/neo/Projects/trip-notes/tests/*.sh; do bash "$t" 2>&1 | tail -1; done
```

- [ ] **Step 9: Commit**

```bash
T=/Users/neo/Projects/trip-notes
git -C $T add .claude-plugin/marketplace.json .gitignore README.md CLAUDE.md docs/cloud-setup.md tests/test-skill-integrity.sh
git -C $T commit -m "chore: stand alone as the trip-notes marketplace

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Linux portability + CI

**Files:**
- Modify: `tests/test-config-sync.sh:40`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Fix `mtime()` — GNU form first**

GNU `stat -f` is file-system status and does not fail on `%m`, so the BSD form must not be tried first. BSD `stat -c` does fail (illegal option), so the reverse order is safe on both:

```bash
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"; }
```

- [ ] **Step 2: Run on macOS — expect `-- 12 passed, 0 failed --`**

```bash
bash /Users/neo/Projects/trip-notes/tests/test-config-sync.sh | tail -1
```

- [ ] **Step 3: CI workflow `.github/workflows/test.yml`**

```yaml
name: test
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y jq
      - name: Run suites
        run: |
          rc=0
          for t in tests/*.sh; do
            echo "::group::$t"
            bash "$t" || rc=1
            echo "::endgroup::"
          done
          exit $rc
```

- [ ] **Step 4: Commit** (CI runs in Task 6 once the remote exists)

```bash
T=/Users/neo/Projects/trip-notes
git -C $T add tests/test-config-sync.sh .github/workflows/test.yml
git -C $T commit -m "ci: run the suites on Linux, where cloud sessions run

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Record the generalization roadmap

**Files:**
- Create: `docs/roadmap/generalization.md`

- [ ] **Step 1: Write the file**

````markdown
# Roadmap: from a personal tool to a general trip planner

Status: proposal, not started. Recorded 2026-09-29.

## What is personal today

| Layer | Now | Difficulty |
|---|---|---|
| Locale | `maps` defaults to `ja`/`JP`; `sightings` matches opening hours on 「月曜日…日曜日」 labels (its own comment: under `MAPS_LANG=en` none match) | medium |
| Output language | zh-TW with native place names; section headings (結論表, 景點總覽, 驗證狀態, …) are written into SKILL.md | **high** — see below |
| Output format | Obsidian callouts (`> [!tip]`), `[[wikilinks]]`, Instagram iframes, "add a callout to the overview note if one exists" | medium |
| Delivery & memory | vault path, `publish-private`, PR delivery, R2 sync, preference-file path | low — already env-driven |

**Language is coupled to the gates.** The lint gate counts `<iframe>` against the literal `[在 Instagram 開啟]`; the provenance gate looks for 「無資料」. Translating headings alone would make both gates pass silently while checking nothing. Output language must switch the strings the gates look for, not just the prose.

## Proposed architecture: engine / profile / shapes

**1. Engine (stays in the plugin, not configurable).** Maps resolution, parallel research, fact checks, browser verification, provenance, the capped fix loop. These rules were paid for with real incidents; they are a quality floor, not a preference.

**2. Profile (outside the plugin)** — `~/.config/trip-notes/profile.yaml`:

```yaml
locale:
  maps_language: ja
  region: JP
  blog_languages: [ja, zh-TW]
output:
  language: zh-TW          # selects the shape set
  format: obsidian         # obsidian | markdown
  dir: vault/Travel
  frontmatter:             # written verbatim into every note
    publish-private: true
delivery:
  local: write
  cloud: pr                # pr | push-branch
  site_url_env: TRIP_NOTES_SITE_URL
memory:
  sync: r2                 # none | r2
features:
  instagram: true
```

- Precedence: environment variables → profile → built-in defaults.
- No profile: ask 3–4 questions on first run and write it after confirmation (distinct from `preferences.md`, which the skill never writes).
- The owner's profile joins `config-sync`'s file list so cloud sessions get it.

**3. Shapes (shipped in the plugin, extensible).** Move the note shapes out of SKILL.md into `templates/shapes/<format>-<language>/{drive,train,nearby}.md`, each set with a `labels` file listing the strings the gates look for. The gates read labels instead of literals.

## Order of work (each step ships on its own)

1. **`sightings` weekday by position, not label** — use the index into `weekdayDescriptions` instead of matching 「月曜日」. Smallest step, and a latent bug on its own.
2. **Profile loading** — locale, output dir, frontmatter, delivery first; these are plain value substitutions.
3. **Shapes + gate labels** — move today's zh-TW + Obsidian output verbatim into `obsidian-zh-TW`, keep every existing test green, then add `markdown-en`.
4. **Obsidian-only syntax behind `format: obsidian`** — callouts, wikilinks, cross-link callouts; the markdown format uses blockquotes and relative links.

Step 3 is the largest and riskiest: prove the gates still reject bad notes under the new structure before adding a second shape set.
````

- [ ] **Step 2: Commit**

```bash
T=/Users/neo/Projects/trip-notes
git -C $T add docs/roadmap/generalization.md
git -C $T commit -m "docs: roadmap for making locale, output and delivery configurable

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Publish the repo

- [ ] **Step 1: Pre-publish scan — expect no output**

```bash
T=/Users/neo/Projects/trip-notes
git -C $T grep -n -e '844f53' -e 'huangshihting' -e 'koromiko1104' -e 'GOOGLE_MAPS_API_KEY=[A-Za-z0-9]' || true
git -C $T log --all -p | grep -n -e '844f53' -e 'huangshihting' -e 'AIza[0-9A-Za-z_-]\{20,\}' | head
```
Any hit: stop and report before creating the remote.

- [ ] **Step 2: Create and push**

```bash
T=/Users/neo/Projects/trip-notes
gh repo create koromiko/trip-notes --private \
  --description "Claude Code plugin: verified travel itineraries and nearby-place notes" \
  --source $T --remote origin --push
```

- [ ] **Step 3: CI must pass**

```bash
gh run watch --repo koromiko/trip-notes --exit-status "$(gh run list --repo koromiko/trip-notes --limit 1 --json databaseId -q '.[0].databaseId')"
```
Expected: success. A Linux-only failure is a real cloud bug — fix it here, in a new commit, before Task 7.

---

### Task 7: Switch the Mac to the new repo

Order matters: re-point `trip-maps` and install the new plugin **before** Task 8 deletes the old copy.

- [ ] **Step 1: Register the local clone as a directory marketplace (edits stay live, as today)**

```bash
claude plugin marketplace add /Users/neo/Projects/trip-notes
claude plugin uninstall trip-notes@cc-local-marketplace
claude plugin install trip-notes@trip-notes
```

- [ ] **Step 2: Re-point `trip-maps`**

```bash
ln -sfn /Users/neo/Projects/trip-notes/skills/build-itinerary/scripts/maps /Users/neo/.local/bin/trip-maps
readlink /Users/neo/.local/bin/trip-maps   # expect the new path
trip-maps cache stats                      # expect a summary, not "No such file"
```

- [ ] **Step 3: Exactly one install**

```bash
claude plugin list 2>&1 | grep -i trip-notes     # expect only trip-notes@trip-notes, enabled
claude -p "Do not use tools. List every skill name containing itinerary or nearby." 
```
Expected: `trip-notes:build-itinerary` and `trip-notes:find-nearby`, each once.

---

### Task 8: Remove the plugin from the old marketplace

**Files (old repo):**
- Delete: `trip-notes/`, the five docs moved in Task 2 plus this plan
- Modify: `.claude-plugin/marketplace.json` (drop the entry), `README.md` (pointer)

- [ ] **Step 1: Remove**

```bash
M=/Users/neo/Projects/claude_local_marketplace
git -C $M rm -r -q trip-notes \
  docs/superpowers/specs/2026-09-05-find-nearby-design.md \
  docs/superpowers/specs/2026-09-06-trip-itinerary-site-design.md \
  docs/superpowers/specs/2026-09-16-find-nearby-preference-learning-design.md \
  docs/superpowers/plans/2026-09-05-find-nearby.md \
  docs/superpowers/plans/2026-09-16-find-nearby-preference-learning.md \
  docs/superpowers/plans/2026-09-29-extract-trip-notes-repo.md
rm -rf $M/trip-notes   # the ignored *-workspace dir is left behind by git rm
jq '.plugins |= map(select(.name != "trip-notes"))' $M/.claude-plugin/marketplace.json > /tmp/mkt.json \
  && mv /tmp/mkt.json $M/.claude-plugin/marketplace.json
```

- [ ] **Step 2: Pointer in the old README** — add under the plugin list:

```markdown
> `trip-notes` moved to its own repository: https://github.com/koromiko/trip-notes
```

- [ ] **Step 3: Verify**

```bash
M=/Users/neo/Projects/claude_local_marketplace
claude plugin validate $M                                    # ✔ Validation passed
grep -rn 'trip-notes' $M --include='*.json' --include='*.md' | grep -v 'moved to its own repository'   # expect none
claude plugin list 2>&1 | grep -i trip-notes                 # still only trip-notes@trip-notes
```

- [ ] **Step 4: Commit and push**

```bash
M=/Users/neo/Projects/claude_local_marketplace
git -C $M add -A .claude-plugin/marketplace.json README.md
git -C $M commit -m "chore: trip-notes moved to koromiko/trip-notes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C $M push origin main
```

---

### Task 9: Point the cloud environment at the new repo

Done by the user in claude.ai/code → environment settings; nothing to commit.

- [ ] **Step 0:** The repo is private. First try the setup script without a token; if the clone fails, create a fine-grained GitHub token (repository access: only `koromiko/trip-notes`; permission: Contents read-only) and add it as `TRIP_NOTES_GH_TOKEN` in the environment variables.
- [ ] **Step 1:** Replace the plugin block of the setup script with the one in the new repo's `docs/cloud-setup.md` (clone `koromiko/trip-notes` to `/opt/trip-notes`, install `trip-notes@trip-notes`).
- [ ] **Step 2:** Checklist session from the ObsidianVault repo: `/skills` shows `trip-notes:build-itinerary` and `trip-notes:find-nearby` once each; `readlink /usr/local/bin/trip-maps` → `/opt/trip-notes/...`; `trip-maps place "東京駅"` returns a place_id.

The vault note `vault/LLM/Running Local Claude Code Skills in Cloud Sessions.md` needs no change: it describes the method, not this plugin's location.
