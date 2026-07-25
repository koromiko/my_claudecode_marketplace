Research task (use WebSearch and WebFetch tools). Do NOT write any files — just return your findings as markdown text in your final message.

Stop: **{{STOP_NAME}}**
Theme/context of the overall route: {{THEME}}
Rough area: {{AREA_HINT}}
Next stop in the route (for driving-time estimate; omit if this is the last stop): {{NEXT_STOP_NAME}}

Find and return:

1. **Exact address** in the local language, and confirm the place actually exists (don't rely on a single low-confidence source).
2. **Google Maps link** — prefer a real maps.google.com share link if you find one; otherwise construct `https://www.google.com/maps/search/?api=1&query=<url-encoded address or name+address>` using the confirmed address.
3. **2–3 local-language blog/news articles** about this specific spot (not generic area guides unless nothing else exists). WebFetch each candidate to confirm it's actually about this place before including it.
4. **Traditional Chinese (繁體中文) coverage** if any genuinely exists — don't force an unrelated or same-named-different-place result in; if you find a same-name-different-location trap (this happens with common facility names), flag it explicitly so it isn't confused with the real stop.
5. **Driving time to {{NEXT_STOP_NAME}}** — look for a source with an actual estimate; if none exists, estimate from the map distance and label it clearly as an estimate, not a live-traffic figure.

Return as clean markdown:
- Address + Google Maps link
- Blog links (local language), each with real title and URL
- Chinese blog links if found, or state none found
- Any name-collision warning
- Estimated driving time to next stop, with basis (distance/time source or "estimated from distance")
