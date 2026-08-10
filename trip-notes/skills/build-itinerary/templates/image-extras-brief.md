Use WebFetch on the following blog/article URLs, all about the stop **{{STOP_NAME}}**. Do NOT write files — just report findings as markdown text in your final message.

URLs:
{{URL_LIST}}

For EACH URL, do two things:

A) **Image extraction**: find a representative/hero image URL for {{STOP_NAME}} — a real photo of the venue/place, not a logo, ad, icon, or unrelated stock photo. Give **the direct image URL, the source page URL, the pixel dimensions, and any licence statement on the page — and nothing else. Do not describe what the image shows.** Captions in the final note are bare place names, so a content description is not needed and has repeatedly introduced errors (naming the wrong bridge, the wrong towers, the wrong time of day).

Reject and report as "no image found":
- Any photo where {{STOP_NAME}} isn't clearly identifiable — construction sites, distant haze, crowds, food close-ups with no venue context.
- Anything hosted on Flickr, Getty, Shutterstock, Alamy, PIXTA, or 写真AC, or any page stating "All rights reserved" — hotlinking these is a rights problem regardless of whether the URL loads. Prefer the venue's official site, a personal blog, or a municipal tourism page.

If no usable image exists, or the page only exposes relative/base64/placeholder images you can't resolve to a real absolute URL, say "no image found" — do not fabricate or guess a URL. "No image found" is an expected outcome, not a failure.

B) **Extra nearby spots**: read the article content and extract any OTHER nearby spots, restaurants, cafés, viewpoints, or attractions the article recommends visiting together with {{STOP_NAME}} (e.g. "周辺のおすすめスポット" style content, sister facilities, or other named locations in the same write-up). For each, give: name (local language), one-sentence description, and area if mentioned.

Return findings organized by URL, then a deduplicated consolidated list of extra spots found for this stop.
