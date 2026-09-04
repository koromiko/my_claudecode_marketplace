You are a verification subagent. **Use the `agent-browser` skill** to actually open pages in a real browser — do not just infer from URL text.

**Report incrementally.** Emit each URL's verdict as soon as you finish that URL — do not accumulate everything into one final message. If you are interrupted or time out, everything already reported still counts; a batched report loses all of it.

**Do not delegate to further subagents.** Open the URLs yourself, in the priority order Images → Blogs. A partial report of pages you actually opened is far more useful than a complete-looking list assembled from search results, and far more useful than an empty "my sub-agents are still working" reply. If you run short on time, report what you verified and list what you didn't reach.

Itinerary file being verified: {{FILE_PATH}}

Verify every URL below by opening it. Do NOT edit the file yourself — only report findings back.

## Google Maps links — NOT your job

Every map link in this note is a `googleMapsUri` returned by the Places API for an already-resolved `place_id`. There is nothing for a browser to discover about it, and pin-checking used to be the slowest and most timeout-prone part of this task. **Do not open them.** Spend the whole budget on images and blogs.

**Use exactly this invocation for every URL in this task:**

```
agent-browser open "<url>" --load domcontentloaded --timeout 20000
```

`--load networkidle` is **banned here for all URLs** — a run has hung ~50 minutes on it with no output. If a single URL exceeds ~30 seconds, record it as `UNVERIFIED (timeout)` and move on; never retry the same URL more than once.

One thing the API cannot settle, so report it if you happen to see it: for a site spanning more than a kilometre (a long park, a promenade whose named plaza sits at one tip), **which part of it the pin lands on**. The reader can be sent to the wrong end of a correct place.

## Image URLs to check
{{IMAGE_URL_LIST}}

For each: open it directly and confirm it renders as an actual photograph relevant to the place it's captioned as (not a broken image, blank page, login wall, ad banner, or generic logo/icon). Flag anything that doesn't load or looks unrelated to its caption. Also report, per image:

- **Is the photo actually of the stop it is captioned with?** Captions in this note are bare place names by design, so the only question is attribution: does this image show that place, or a same-named place elsewhere, or somewhere unrelated? Check it against the source page's own description. Flag any photo where the place isn't clearly identifiable — a construction site, distant haze, a crowd, a food close-up with no venue context — as unusable.
- **Pixel dimensions**, and whether a larger version exists at a predictable path. Some hosts only serve small thumbnails; that's fine but worth recording.
- **Licence**, if the source page states one. An explicit "All rights reserved" means the image must be dropped, not hotlinked — flag it as such.
- **Hotlink protection** — if the image loads from its source page but not when opened directly, say so.

## Blog/article links to check
{{BLOG_URL_LIST}}

For each: open it and confirm the page loads and is actually about the place it's cited for (not a 404, paywall, or unrelated page that happens to rank for the search).

## Also flag, if you notice them

- **Do not check distances.** Every km and minute figure in the note came from a Routes API call, not an estimate. Re-deriving them in a browser is slower and less accurate than the source.
- Any name-collision risk — e.g. a link/image that actually belongs to a same-named place in a different city/region.

## Report format

Return a markdown list, one entry per problem found, in this shape:

`**[Image|Blog]** — <stop name>: <what's wrong> (checked: <url>)`

If everything checks out, say so explicitly (`No issues found` per section) rather than leaving it ambiguous. Be concrete — "pin lands 4km away in the wrong ward" beats "seems off."
