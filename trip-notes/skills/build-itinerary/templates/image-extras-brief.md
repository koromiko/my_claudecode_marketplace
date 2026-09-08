Use WebFetch on the following blog/article URLs, all about the stop **{{STOP_NAME}}**. Do NOT write files — just report findings as markdown text in your final message.

URLs:
{{URL_LIST}}

Do three things: A) images, B) extra nearby spots, C) one Instagram post.

A) **Image extraction**: find **2–3 photo URLs** for {{STOP_NAME}} — real photos of the venue/place, not logos, ads, icons, or unrelated stock photos. Give **the direct image URL, the source page URL, the pixel dimensions, and any licence statement on the page — and nothing else. Do not describe what the image shows.** Captions in the final note are bare place names, so a content description is not needed and has repeatedly introduced errors (naming the wrong bridge, the wrong towers, the wrong time of day).

Two photos is the target, three is welcome, and they must be **genuinely different views** — different source pages, or clearly different subjects on the same page (exterior vs interior vs the signature dish). Several near-identical frames from one article's photo run count as **one** photo; sending them as two produces a note that looks padded rather than illustrated.

**One good photo beats two where the second is padding, and "no image found" beats one you had to stretch for.** The count is a target, not a quota — reporting a single image, or none, is a correct outcome and is expected on thinly covered stops. Never fabricate, guess, or pad a URL to reach two.

Reject and report as "no image found":
- Any photo where {{STOP_NAME}} isn't clearly identifiable — construction sites, distant haze, crowds, food close-ups with no venue context.
- Anything hosted on Flickr, Getty, Shutterstock, Alamy, PIXTA, or 写真AC, or any page stating "All rights reserved" — hotlinking these is a rights problem regardless of whether the URL loads. Prefer the venue's official site, a personal blog, or a municipal tourism page.

If no usable image exists, or the page only exposes relative/base64/placeholder images you can't resolve to a real absolute URL, say "no image found" — do not fabricate or guess a URL. "No image found" is an expected outcome, not a failure.

B) **Extra nearby spots**: read the article content and extract any OTHER nearby spots, restaurants, cafés, viewpoints, or attractions the article recommends visiting together with {{STOP_NAME}} (e.g. "周辺のおすすめスポット" style content, sister facilities, or other named locations in the same write-up). For each, give: name (local language), one-sentence description, and area if mentioned.

C) **Instagram account (the handle, never a post)**: run **one** WebSearch for `{{STOP_NAME}} instagram`, plus note any Instagram link the blog pages above already point at.

- Report the **handle only**, with where you saw it. **Never report a post or reel URL, and never build one out of a handle.** Post discovery is not your job — the orchestrator reads recent posts straight off the account page in a browser, which is the only thing that works for a small venue (Google does not index individual posts for an account with a few hundred of them). A handle you saw on a real page is exactly the evidence that step needs; a post code you inferred is worse than nothing.
- Say **where** you saw it — the stop's own site, one of the blogs above, or the search result listing. That is what separates the stop's own account from a same-name account somewhere else.
- Mark it as an adjacent account rather than the stop's own where that is the case — a parent company, the building, the floor it sits on. Still useful; the note just has to say so.
- Prefer the stop's own account. Skip aggregator and reposting accounts, and skip an account you cannot tie to this specific branch when the stop has siblings — "no Instagram found" beats the wrong branch.
- "No Instagram found" is an expected outcome, not a failure.

Return findings organized by URL, then a deduplicated consolidated list of extra spots found for this stop, then the Instagram line (`{{STOP_NAME}} — @<handle> — <where you saw it> — <own account|adjacent account>`, or "no Instagram found").
