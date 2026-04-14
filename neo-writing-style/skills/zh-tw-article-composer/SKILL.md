---
name: zh-tw-article-composer
description: This skill should be used when the user asks to "write a zh-tw article", "compose an article in Traditional Chinese", "draft a blog post in Chinese", "write like me", "write in my style", "write a technical tutorial in Chinese", or when composing any long-form zh-tw content including technical tutorials, opinion pieces, or educational articles. Also trigger when asked to "write for AppCoda" or produce content matching Neo's writing voice.
---

# Neo's zh-tw Article Composition Guide

This skill encodes Neo (Huang ShihTing)'s writing style as demonstrated across 10 published articles on AppCoda.com.tw. Apply these patterns when composing zh-tw articles to match Neo's distinctive voice and tone.

## Core Voice: Conversational-Professional

Write in a warm, approachable tone — like a knowledgeable friend explaining over coffee, not a textbook or corporate blog.

### Key Traits

- **Casual but credible** — colloquial phrasing with technical accuracy
- **Self-aware humor** — light self-deprecation, playful parenthetical asides, sparse emoji
- **Direct and natural** — speak to the reader conversationally, not formally
- **Honest about trade-offs** — openly discuss pros and cons, no hype

### Signature Humor Patterns

- Parenthetical asides that acknowledge reader behavior: "(不用真的回去)"
- Dramatizing developer pain: "你知道接手的人正在你後面嗎？他非常火！"
- Quantifying absurdity: referencing "七部電影" worth of wasted time, "200行code的距離"
- Deflating jargon: "更有名的是它是選擇了用 100 分的複雜名詞去解釋 10 分的簡單概念"
- Playful emphasis markers: "(認真)"

### Reader Consideration

- Offer skip-ahead options for different reader interests: "如果你只想試 X 部分，可直接跳過"
- Acknowledge that readers have context: don't over-explain what's obvious to the target audience

## Language & Terminology Rules

- **Primary language**: Traditional Chinese (zh-tw), full-width punctuation (，、。！？）
- **Technical terms**: Keep industry-standard English terms untranslated — "data race", "protocol", "cache", "mutation", "actor", "closure", "API", "server", "app"
- **Do NOT force-translate** well-known tech terms. "Actor" stays "Actor", never "演員"
- **Loan words** like "app", "API", "server", "model" remain in English
- Keep "alert" and "flag" untranslated per user preference
- Half-width punctuation inside code and around English terms

## Explanation Micro-Pattern

When introducing any concept, follow this sequence:

1. **Name it** — one clear sentence stating what it is
2. **Compare it** — analogy to something the reader already knows (e.g., "堆積木一樣", USB 接頭, 掃地機器人)
3. **Show it** — concrete example (code, diagram, or scenario)
4. **Narrate it** — walk through the example explaining key decisions
5. **Connect it** — relate back to the bigger picture or problem

Analogies are a signature element — always prefer concrete, everyday comparisons over abstract descriptions.

## Transition Style

Use natural bridging phrases, not mechanical connectors:

- "那我們要怎樣做到..." (So how do we achieve...)
- "現在我們要來製作..." (Now let's build...)
- "接下來" (Next up)
- "不過跟 X 不太一樣的地方是..." (But unlike X...)
- Rhetorical questions to bridge sections

## Article Structure Rhythm

Neo's articles follow a characteristic "dive and resurface" depth progression:

1. **Hook** — relatable problem, historical context, or provocative observation (never a dry definition)
2. **Problem deep-dive** — establish WHY the topic matters before offering solutions
3. **Concept introduction** — analogy first, then incremental revelation
4. **Hands-on walkthrough** — step-by-step with progressive build-up
5. **Advanced considerations** — edge cases, trade-offs, alternatives
6. **Honest conclusion** — summarize takeaways, acknowledge limitations, suggest next steps

### Title Formula

Titles combine **[Topic/Action] + [Benefit/Promise]**:

- Question + Solution: "Table View 太複雜？利用 MVVM 和 Protocol 就可以為它重構瘦身！"
- Topic + Benefit: "Compositional Layout 詳解　讓你簡單操作 CollectionView！"
- Verb-first action: "利用 Core ML 3.0 的 API　一步步製作個人化的塗鴉 app"
- Subtitle style: "給 Swift 工程師的後端指南：用 Kitura 來架設自己的 API 後台"

## Additional Resources

### Reference Files

For categorized examples of openings, transitions, humor, analogies, and conclusions extracted from all 10 published articles:

- **`references/style-examples.md`** — Detailed style patterns with direct quotes and categorized examples
