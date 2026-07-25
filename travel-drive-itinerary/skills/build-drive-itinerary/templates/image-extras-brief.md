Use WebFetch on the following blog/article URLs, all about the stop **{{STOP_NAME}}**. Do NOT write files — just report findings as markdown text in your final message.

URLs:
{{URL_LIST}}

For EACH URL, do two things:

A) **Image extraction**: find a representative/hero image URL for {{STOP_NAME}} — a real photo of the venue/place, not a logo, ad, icon, or unrelated stock photo. Give the direct image URL. If no usable image exists or the page only exposes relative/base64/placeholder images you can't resolve to a real absolute URL, say "no image found" — do not fabricate or guess a URL.

B) **Extra nearby spots**: read the article content and extract any OTHER nearby spots, restaurants, cafés, viewpoints, or attractions the article recommends visiting together with {{STOP_NAME}} (e.g. "周辺のおすすめスポット" style content, sister facilities, or other named locations in the same write-up). For each, give: name (local language), one-sentence description, and area if mentioned.

Return findings organized by URL, then a deduplicated consolidated list of extra spots found for this stop.
