Use WebSearch and WebFetch. Do NOT write files — just report findings as markdown text in your final message.

I need photo URLs for each of these "延伸推薦" (extra nearby) spots, surfaced from blogs about the main itinerary stops. Area/region context: {{AREA_HINT}}.

For EACH spot below, search for it, find a real blog/news/official-site page about it, and WebFetch that page to extract real photo URLs (direct image URLs ending in .jpg/.png/.webp, or CDN URLs that serve an image — real photos of the place, not logos/icons/ads). If a spot turns out to share its name with an unrelated place elsewhere, flag that so the image isn't misattributed.

**Aim for 2 photos per spot; 1 is a perfectly good result and "no image found" is a normal one.** These spots are mentioned in passing inside someone else's article, so the coverage is thin by nature and a large share of them will yield one photo or none — that is the expected shape of this pass, not a shortfall. Stop after 1–2 tries per spot. **Never fabricate, guess, or pad a URL to reach two**; a second photo that is another frame from the same photo run is padding, not a second photo, and should not be reported.

**Return the image URLs, the source page URL, the pixel dimensions, and any licence statement — and nothing else. Do not describe what the images show.**

Reject and report as "no image found":
- Any photo where the spot isn't clearly identifiable — construction sites, distant haze, crowds, food close-ups with no venue context.
- Anything on Flickr, Getty, Shutterstock, Alamy, PIXTA, or 写真AC, or a page stating "All rights reserved" — hotlinking these is a rights problem regardless of whether the URL loads.

Spots:
{{SPOT_LIST}}

Return a markdown list, one line per spot: `**{spot name}**: {image URL 1} | {image URL 2 if found} (source: {page URL})`, or `**{spot name}**: no image found`.
