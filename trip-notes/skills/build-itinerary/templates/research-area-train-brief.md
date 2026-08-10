Research task (use WebSearch and WebFetch). Do NOT write any files — return your findings as markdown text in your final message.

Area to evaluate: **{{AREA_NAME}}**
Region / theme of the overall note: {{THEME}}
Criteria this area is being screened against: {{CRITERIA_LIST}}

This area is a **candidate**, not a confirmed pick. Your job is to gather what's needed to rate it against each criterion — including the evidence that would disqualify it. A well-sourced "this fails criterion ③" is as valuable as a pass.

Find and return:

1. **Access** — nearest station(s), which lines serve them, and **walking minutes from the ticket gate to the start of the walking route**. Not "near X station" — the actual gate-to-start figure, with the source. If it's over ~15 minutes, say so plainly; that usually fails a "convenient by train" criterion regardless of how good the destination is.

2. **Shops and restaurants actually along the walking route** (not merely in the same district). For each: name, genre, and **closing time broken down by day of week**, plus 定休日 (regular closing days).
   - The weekday breakdown is mandatory. A venue advertised as "open until 23:00" very often means 23:00 **on Fridays only** and 22:00 the rest of the week. Report the per-day figures, not the maximum.
   - Prefer the venue's own site or its official social account over aggregator listings, which go stale.

3. **Seating** — are there benches, ledges, or steps to rest on along the route? Roughly how many and where (continuous along the promenade / only at one plaza / none)?

4. **Last train**, and **last bus** if any part of the route depends on a bus. Timetable sites often display the second-to-last departure prominently — state which one you're reporting and how you confirmed it.

5. **Time-limited walkways, bridges, decks, or parks** on the route: opening hours and any periodic closure (e.g. 第三個週一公休, seasonal hours). These are the most error-prone facts in this kind of note. **If you cannot find a current official page, say "no current official source found" — do not repeat a number from a blog as if it were confirmed.** Note the date of whatever source you did find.

6. **2–3 local-language blog/news articles** about walking this route specifically. WebFetch each to confirm it's really about this area. Add Traditional Chinese (繁體中文) coverage only if genuinely relevant — don't force it.

7. **Stale-information traps you noticed** — a shop that has closed but is still promoted in travel articles, a superseded price, a demolished landmark still listed as a view, an official notice whose "latest update" is years old. Flag each with the date evidence.

8. **Lighting and safety at night**, if the note is about evening/night walking: is the route lit, is it populated at that hour, are there stretches with neither?

Return as clean markdown, one section per numbered item above, then a final block:

`### 對照條件` — one line per criterion in {{CRITERIA_LIST}}, rated `◎優 / ○可 / △勉強 / ✗不合格`, each with the specific number or fact that produced the rating. If you couldn't establish a criterion, rate it `未確認` rather than guessing.
