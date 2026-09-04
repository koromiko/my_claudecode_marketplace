Research task (use WebSearch and WebFetch). Do NOT write any files — return your findings as markdown text in your final message.

Area to evaluate: **{{AREA_NAME}}**
Region / theme of the overall note: {{THEME}}
Criteria this area is being screened against: {{CRITERIA_LIST}}

## Already established — treat as given, do not re-derive

From the Google Maps Places/Routes API, not from search results:

- Focal point: {{MAPS_NAME}} — {{MAPS_LATLNG}} — {{MAPS_URL}}
- Nearest station: {{MAPS_STATION}}
- **Gate-to-start walking time: {{MAPS_WALK_MIN}} min / {{MAPS_WALK_KM}} km** (Routes API, walking mode)
- Venues found on the route, with per-weekday hours and 定休日 already attached: {{MAPS_NEARBY}}

Do not re-measure the walking time and do not re-look-up hours that are listed above. Your value is in what those numbers hide.

This area is a **candidate**, not a confirmed pick. Your job is to gather what's needed to rate it against each criterion — including the evidence that would disqualify it. A well-sourced "this fails criterion ③" is as valuable as a pass.

Find and return:

1. **Access — the qualitative half.** The gate-to-start minutes are given above. What the number does not say: which exit actually works, whether the walk is lit and populated, whether it crosses a highway or an industrial yard, whether there are steps/no lift. A 12-minute walk can fail a "convenient by train" criterion for reasons a routing engine cannot see. Also name the lines serving the station.

2. **Shops and restaurants actually along the walking route.** Start from the `{{MAPS_NEARBY}}` list above — those already carry per-weekday hours and 定休日. Your work on it:
   - **Confirm each is genuinely on the walking line**, not 300 m away across a river or a highway. Maps radius search cannot tell the difference; you can.
   - **Add anything missing** that the route obviously passes and Maps did not return.
   - **Check the plan-critical ones against their own site or official social account** — whichever venue the evening depends on. Maps hours go stale for small independent places, and a venue advertised as "open until 23:00" very often means 23:00 **on Fridays only**. Where the venue's own source contradicts the Maps hours above, report both and say which you trust and why.

3. **Seating** — are there benches, ledges, or steps to rest on along the route? Roughly how many and where (continuous along the promenade / only at one plaza / none)?

4. **Last train**, and **last bus** if any part of the route depends on a bus. Timetable sites often display the second-to-last departure prominently — state which one you're reporting and how you confirmed it.

5. **Time-limited walkways, bridges, decks, or parks** on the route: opening hours and any periodic closure (e.g. 第三個週一公休, seasonal hours). These are the most error-prone facts in this kind of note. **If you cannot find a current official page, say "no current official source found" — do not repeat a number from a blog as if it were confirmed.** Note the date of whatever source you did find.

6. **2–3 local-language blog/news articles** about walking this route specifically. WebFetch each to confirm it's really about this area. Add Traditional Chinese (繁體中文) coverage only if genuinely relevant — don't force it.

7. **Stale-information traps you noticed** — a shop that has closed but is still promoted in travel articles, a superseded price, a demolished landmark still listed as a view, an official notice whose "latest update" is years old. Flag each with the date evidence.

8. **Lighting and safety at night**, if the note is about evening/night walking: is the route lit, is it populated at that hour, are there stretches with neither?

Return as clean markdown, one section per numbered item above, then a final block:

`### 對照條件` — one line per criterion in {{CRITERIA_LIST}}, rated `◎優 / ○可 / △勉強 / ✗不合格`, each with the specific number or fact that produced the rating. If you couldn't establish a criterion, rate it `未確認` rather than guessing.
