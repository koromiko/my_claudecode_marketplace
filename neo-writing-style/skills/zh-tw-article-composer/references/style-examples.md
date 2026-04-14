# Neo's Writing Style — Extracted Examples

This reference file contains categorized examples from Neo's 10 published AppCoda.com.tw articles. Use these as pattern templates when composing new articles.

## Published Articles (Source Material)

1. Swift 5.5 的新語法和機制 讓我們用最直觀的方式撰寫非同步程式
2. 利用 Core ML 3.0 的 API 一步步製作個人化的塗鴉 app
3. 利用 EarlGrey 做 UI Test 強化你的 UI 測試流程
4. GraphQL 教學：為你迭代快速的專案 提供最適合的解決方案！
5. Compositional Layout 詳解 讓你簡單操作 CollectionView！
6. 給 Swift 工程師的後端指南：用 Kitura 來架設自己的 API 後台
7. 利用 Protocol Extension 減少重覆的 Code 大大增強 Code 的維護性
8. 深入了解 Swift String 字串型別 讓你的程式跑得更快更好
9. 生產力再提升：利用 Swift Package Manager 製作自動化開發者工具
10. Table View 太複雜？利用 MVVM 和 Protocol 就可以為它重構瘦身！

---

## Title Patterns

Neo's titles follow a consistent formula: **[Topic/Action] + [Benefit/Promise]**, separated by a full-width space or punctuation.

Examples:
- "Compositional Layout 詳解　讓你簡單操作 CollectionView！"
- "生產力再提升：利用 Swift Package Manager 製作自動化開發者工具"
- "Table View 太複雜？利用 MVVM 和 Protocol 就可以為它重構瘦身！"
- "利用 Protocol Extension 減少重覆的 Code　大大增強 Code 的維護性"

Pattern variants:
- **Question + Solution**: "Table View 太複雜？利用 MVVM 和 Protocol 就可以為它重構瘦身！"
- **Topic + Benefit**: "Compositional Layout 詳解　讓你簡單操作 CollectionView！"
- **Verb-first action**: "利用 Core ML 3.0 的 API　一步步製作個人化的塗鴉 app"
- **Subtitle style**: "給 Swift 工程師的後端指南：用 Kitura 來架設自己的 API 後台"

---

## Opening Patterns

### Pain Point Opener (Most Common)

From Table View MVVM article:
> UITableView 與 UICollectionView 是 iOS 開發的核心元件。隨著介面複雜度提升，單一檔案往往累積數千行程式碼。一開始新增一個 cell 類型可能只需要半天，隨著 tableView 越來越肥大，新增一個 cell 類型可能需要一週。

From Protocol Extension article:
> 軟體開發中「減少重覆 code，把權責明確分開」的重要性。當相同功能的代碼分散在各處時，會增加維護成本與困難度。

### Historical Context Opener

From Compositional Layout article:
> Contrasts the 2008 AppStore's simplicity with modern app interfaces' complexity, establishing the problem through narrative before introducing the solution.

### Quantification Opener

From Swift Package Manager article:
> 計算「每年花費超過1,200分鐘進行手動同步」來強調自動化的必要性。

---

## Analogy & Metaphor Examples

These analogies are a signature style element — always use concrete, relatable comparisons:

- **Actor model**: "有排隊機制的獨立環境" (an isolated environment with a queuing mechanism)
- **Layout composition**: "堆積木一樣" (like stacking building blocks)
- **Protocol interfaces**: USB 接頭 (USB connectors) — different devices, same interface
- **Automation value**: 掃地機器人 (robot vacuum) — automate repetitive cleaning
- **k-NN classifier**: 圖形分群的二維平面 (2D plane of point clusters)
- **SPM vs CocoaPods**: 去中心化 vs 中央集中式 (decentralized vs centralized)

---

## Humor & Personality Examples

### Self-Deprecating / Playful

- "認真" (seriously) — used as a parenthetical when making a point that sounds exaggerated but isn't
- "沒有要等人的意思" (not waiting for anyone) — casual aside
- "你知道接手的人正在你後面嗎？他非常火！" (You know the person taking over is right behind you? They're furious!) — dramatizing the cost of bad code
- "Protocol-Oriented Programming 的中心原則之一也是 DIP，更有名的是它是選擇了用 100 分的複雜名詞去解釋 10 分的簡單概念" (POP's core principle DIP is more famous for using 100-point complex terminology to explain a 10-point simple concept)
- "200行code的距離" (200 lines of code away) — measuring progress playfully
- References to "看Netflix" and "七部電影" when quantifying wasted time

### Considerate Reader Asides

- "(不用真的回去)" — telling the reader they don't literally need to scroll back
- "如果你只想試手機部分，可直接跳過" — letting readers skip ahead based on interest
- Emoji used sparingly for warmth, not as decoration

---

## Transition Phrases

Natural bridging between sections (not mechanical):

- "那我們要怎樣做到..." (So how do we achieve...)
- "現在我們要來製作..." (Now let's build...)
- "接下來" (Next up)
- "不過跟 X 不太一樣的地方是..." (But unlike X...)
- "一個 actor 其實跟一個 class 一樣..." (An actor is actually like a class...) — comparison-based transition
- "任何 conform 這個 protocol 的型別，都是可以安全地在不同 concurrency domain 傳遞的" — definition-as-transition

---

## Conclusion Patterns

### Honest Summary + Limitations

From Protocol Extension article:
> 總結三大要點，同時強調軟體設計無唯一解，鼓勵讀者根據具體情況做出最佳決策。

From Table View MVVM article:
> 該方案符合 SOLID 原則，但認可仍存在記憶體負擔與 view controller transition 等未解決問題，邀請讀者持續迭代改進。

From GraphQL article:
> 強調 GraphQL 的「強大彈性」特別適合複雜專案，但也指出學習曲線、schema 設計複雜性等缺點。

### Common Closing Moves

1. Summarize 3-4 concrete takeaways
2. Acknowledge what the approach does NOT solve
3. Encourage the reader to evaluate for their own context
4. Provide GitHub source code link
5. List reference resources (WWDC videos, official docs, related blog posts)

---

## Pedagogical Micro-Pattern

When explaining any concept, Neo follows this sequence consistently:

1. **Name it**: State the concept in one clear sentence
2. **Compare it**: Analogy to something the reader already knows
3. **Show it**: Complete code example
4. **Narrate it**: Walk through the code explaining key decisions
5. **Connect it**: Relate back to the bigger architecture or problem

Example from Actor article:
1. "一個 actor 其實跟一個 class 一樣，它是一個 reference type"
2. "不過跟 class 不太一樣的地方是，一個 actor 不能繼承另外一個 actor"
3. [BalanceStore code example]
4. Line-by-line explanation of isolation mechanism
5. Connects to solving the data race problem introduced in the opening

---

## Section Depth Pattern

Neo's articles have a characteristic depth progression:

1. **Opening** (shallow, wide): Relatable problem, broad context
2. **Problem** (medium): Specific pain points with code
3. **Theory** (deeper): Concepts and how they work
4. **Implementation** (deepest, longest): Full step-by-step build
5. **Advanced** (selective depth): Specific edge cases
6. **Conclusion** (back to shallow): Summary and next steps

This creates a "dive and resurface" rhythm that keeps readers oriented.

---

## Formatting Conventions

- Use full-width punctuation for Chinese text (，、。！？）
- Use half-width punctuation inside code and for English terms
- Section headers are descriptive and often include the benefit (not just the topic)
- Code blocks are always language-tagged (swift, python, etc.)
- Bold for key terms on first introduction
- Numbered lists for sequential steps, bullet points for non-sequential items
