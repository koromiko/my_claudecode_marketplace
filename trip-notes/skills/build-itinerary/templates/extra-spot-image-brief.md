Use WebSearch and WebFetch. Do NOT write files — just report findings as markdown text in your final message.

I need a representative photo URL for each of these "延伸推薦" (extra nearby) spots, surfaced from blogs about the main itinerary stops. Area/region context: {{AREA_HINT}}.

For EACH spot below, search for it, find a real blog/news/official-site page about it, and WebFetch that page to extract a real photo URL (a direct image URL ending in .jpg/.png/.webp, or a CDN URL that serves an image — a real photo of the place, not a logo/icon/ad). If you can't find a usable image after 1–2 tries, say "no image found" for that spot — do not fabricate or guess a URL. If a spot turns out to share its name with an unrelated place elsewhere, flag that so the image isn't misattributed.

**Return the image URL, the source page URL, the pixel dimensions, and any licence statement — and nothing else. Do not describe what the image shows.**

Reject and report as "no image found":
- Any photo where the spot isn't clearly identifiable — construction sites, distant haze, crowds, food close-ups with no venue context.
- Anything on Flickr, Getty, Shutterstock, Alamy, PIXTA, or 写真AC, or a page stating "All rights reserved" — hotlinking these is a rights problem regardless of whether the URL loads.

Spots:
{{SPOT_LIST}}

Return a markdown list, one line per spot: `**{spot name}**: {image URL or "no image found"} (source: {page URL})`.
