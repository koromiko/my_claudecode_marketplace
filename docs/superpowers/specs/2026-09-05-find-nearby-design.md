# find-nearby — 設計

日期：2026-09-05
Plugin：`trip-notes`
狀態：設計已核可，待實作計畫

## 目的

在 `build-itinerary` 之外新增第二個 skill：給一個地點，找出周邊指定類型的店家（餐廳、咖啡廳、雜貨、服飾……），依**個人偏好**排序，產出一份與 `build-itinerary` 同等品質的 Obsidian 筆記，並在交付後透過回饋迴圈逐次改善偏好檔。

`build-itinerary` 回答的是「這趟行程怎麼走」；`find-nearby` 回答的是「這個點附近有什麼值得去、而且**符合我口味**」。兩者共用同一套 harness：`trip-maps`、subagent 扇出、curl 掃描、lint gate、browser 驗證、修正迴圈。

## 範圍

**做：** 單一地點的周邊搜尋、時間上限式的範圍定義、個人偏好排序、回饋迴圈、完整驗證的 Obsidian 筆記。

**不做：** 多點路線規劃（那是 `build-itinerary`）、訂位、即時擁擠度、跨城市比較。

## 輸入

| 輸入 | 必填 | 預設 / 說明 |
|---|---|---|
| 地點 | ✅ | 具體地名。沒有就問，不猜。 |
| 類型 | ❌ | 預設 `restaurant` + `cafe`。中文詞由 skill 內的對照表映射到 Places includedType。 |
| 範圍模式 | ❌ | **步行 15 分（預設）** / 開車 15 分 / 電車 15 分（含步行到站＋乘車） |
| 額外條件 | ❌ | 「泰式」「有陽台座位」「寵物友善」「晚上有開」等，見下方三層路由 |

模式與時間上限若未指定，直接採預設並在回覆中用一行說明假設，不停下來問。

### 中文類型 → Places includedType 對照

`nearby` 一次只接受一個 includedType，所以多類型 = 多次呼叫、多個 pool 檔。對照表寫在 SKILL.md 內，至少涵蓋：

| 中文 | includedType |
|---|---|
| 餐廳 | `restaurant` |
| 咖啡廳 | `cafe` |
| 麵包店 | `bakery` |
| 雜貨・生活用品 | `home_goods_store` |
| 禮品・選物 | `gift_shop` |
| 服飾 | `clothing_store` |
| 書店 | `book_store` |
| 藥妝 | `drugstore` |
| 超市 | `supermarket` |
| 便利商店 | `convenience_store` |
| **公園・綠地** | `park`（型別集合，見下） |
| **泛用**（自由描述） | 由 Step 0.2 解析，見下 |

表未涵蓋的詞：挑最接近的 type，並在回覆一行說明用了哪個；不要靜默替換。

**表中的每一個 type 字串都必須在實作時對真實 API 驗過。** Places API (New) 的 includedType 是封閉集合，打錯字或用了舊版 type 名稱會直接讓 `searchNearby` 回錯誤。實作的第一步是對每個 type 各發一次 `nearby` 確認它被接受；未通過的從表裡拿掉，不要留在 SKILL.md 裡等使用者踩到。

### 公園類型 = 一個型別集合，不是單一 type

「公園」在 Places 裡散在數個 type（`park` 之外還有國家公園、步道區、植物園等）。因此「公園・綠地」解析成一組 includedType，每個各發一次 `nearby`，結果**依 `place_id` 去重後合併成單一 pool**。集合的實際成員由上述 API 驗證決定；`park` 是確定成員，其餘視驗證結果納入。

去重與合併規則對所有多型別查詢通用（見下節），不是公園專屬。

### 泛用類型（Step 0.2）

使用者可以不給類型，而給一句描述 —— 「可以散步一小時的地方」「有名的景點或店家」「適合帶長輩去的」。這種輸入沒有對應的 includedType，所以先解析成兩樣東西：

1. **一組 includedType**（2–4 個），決定去抓什麼 pool
2. **一組額外篩選條件**，原文交給 Step 5 的 scoring agent，成為結論表的欄位

例：

| 描述 | 型別集合 | 額外條件 |
|---|---|---|
| 可以散步一小時的地方 | 公園集合 + `tourist_attraction` | 「腹地或路線足夠走約一小時」「有座椅」「不需門票或門票不高」 |
| 有名的景點或店家 | `tourist_attraction` + `restaurant` + `cafe` | 「知名度：評論數與在地報導」 |

解析結果**必須用一行回報**（「泛用類型『可以散步一小時的地方』→ 抓 park／tourist_attraction，額外篩選：腹地足夠、有座椅」），因為這一步是整個流程裡唯一由模型自由判讀輸入的環節，靜默進行等於使用者無從發現它會錯意。

**不提供「完全不加 type 過濾」作為預設。** `nearby` 允許省略 includedTypes，但在城市裡那樣抓回來的前 20 名會被車站、便利商店、大型商場佔滿（script 依評論數排序），對「有名的景點或店家」這種意圖幾乎無用。無過濾模式保留為明確的逃生口，使用者要求「這附近有什麼都好」時才用，並在回報中說明它會出現什麼。

### 額外條件的三層路由

「泰式餐廳」「有陽台座位的咖啡廳」「寵物友善的公園」表面上是同一類輸入，實際上分屬三個層次。每個條件必須被路由到**最便宜且真的能回答它**的那一層 —— 把「陽台座位」交給 scoring agent 去猜評論，而 Google 有一個布林欄位直接回答它，既浪費也比較不準。

| 層 | 條件形狀 | 解法 | 成本 |
|---|---|---|---|
| **1. 型別細分** | 料理、風格、主題（泰式、拉麵、古著、獨立書店） | Step 0.2 解析成細分 type 或 `searchText` 查詢字串 | 免費，確定性 |
| **2. 結構化布林欄位** | 陽台座位、寵物、素食、無障礙、兒童友善 | 加進 `nearby` 的 field mask，由 script 端過濾 | **升 SKU**，見下 |
| **3. 無結構化來源** | 有設計感、安靜、可久坐、氣氛好 | 交給 Step 5 scoring agent（評論）＋ 待確認問題 | 已含在既有流程 |

第 3 層與偏好檔走完全相同的機制 —— 兩者本來就是同一種東西，差別只在偏好是持久的、額外條件是本次的。

#### 第 2 層的兩條硬規則

**布林欄位只在需要時才加進 field mask。** Places API (New) 的 amenity 欄位（`outdoorSeating`、`allowsDogs`、`servesVegetarianFood`、`goodForChildren`、`restroom` 等 —— 實際欄位名與 SKU 分級待實測確認）屬於較高計費層，而請求是按其**最高階欄位**計費，跟 `reviews` 同樣的機制。使用者沒問陽台，就不要把 `outdoorSeating` 放進 mask。

**欄位是三態，不是布林。** 這些欄位對很多店是 `null`，而 `null` 的意思是「Google 沒資料」，不是「沒有」。所以：

| 值 | 處置 |
|---|---|
| `true` | 加分，可直接寫進筆記並標來源為 Google Places |
| `false` | 刷掉，理由寫進「已篩掉的候選」 |
| `null` / 缺欄 | **保留但降權**，並列入待確認問題交給 Step 6a |

用缺資料去刷掉候選，是這份設計反覆拒絕的同一種錯誤：被刷掉的東西不會出現在筆記裡，使用者不會知道它消失了，所以這種錯誤無法自我修正。一家真的有陽台但 Google 沒記的獨立咖啡廳，正是使用者最想要的那種店。

驗證狀態要記「N 家的 <欄位> 無資料，已列為待確認」。

### 兩條查詢管道：`nearby` 與 `searchText`

第 1 層的條件有兩種去處，因為 includedType 是封閉集合 —— `thai_restaurant` 在裡面，「有陳列館的咖啡廳」不在，而 Google 的文字索引本來就在處理後者。

| 條件形狀 | 管道 |
|---|---|
| 純型別，且細分 type 存在（咖啡廳、公園、泰式餐廳） | `nearby`（`trip-maps nearby`） |
| 帶料理／風格／主題詞，落不進任何 type（古著店、有陳列館的咖啡廳、深夜書店） | `searchText`（新增 `trip-maps search`） |
| 兩者都有（「泰式餐廳，要有陽台」） | **兩邊都發**，在 `reachable` 去重合併 |

**判斷不確定時的預設是「兩邊都發」，不是二選一。** 去重機制已經為多型別而存在，所以合併是免費的；代價只是一次多的 API 呼叫，遠比漏掉候選便宜。把 fallback 設成安全的那一邊，是因為「什麼時候用哪個」這種判斷規則很容易被模型略過 —— 略過時掉進的必須是完整的那條路。

`searchText` 的圓形範圍只能當 `locationBias`（偏好）不能當 `locationRestriction`（硬限制），所以它的結果會溢出範圍。這不致命：`reachable` 的時間過濾本來就是唯一的硬閘門，溢出的候選在那裡被剔除。代價是部分 pool 名額浪費在範圍外的店，所以 `search` 的 `--limit` 要比 `nearby` 給得寬一些。

### 多型別 pool 的合併

任何產生多個 pool 檔的查詢（公園集合、泛用類型、使用者同時要餐廳和咖啡廳、或 `nearby` + `searchText` 雙管道）：每個查詢各發一次 `--limit 20 --out`，然後**在 `trip-maps reachable` 這一步依 `place_id` 去重合併**。去重必須發生在 script 裡而非 orchestrator，理由與 Step 0.7 相同 —— pool 檔不進 orchestrator 的 context。

一家店可能同時符合多個 type，合併後保留第一次出現的記錄即可（欄位內容相同）。合併後的候選數會超過 20，這正是 `reachable` 的時間過濾與後續粗排存在的原因。

## 範圍語意：時間上限，不是直線半徑

`nearby` 只接受公尺半徑，而直線半徑在有河、鐵道、高速公路切斷的地方會嚴重騙人。所以分兩段：

1. **寬 pool**：以刻意寬鬆的半徑抓候選 — WALK 1500 m / DRIVE 10 km / TRANSIT 6 km。寬是故意的，過濾在下一步做。
2. **真實時間過濾**：`trip-maps reachable` 用 Routes API 的 `computeRouteMatrix`（1 origin × N destinations，**一次呼叫**）算出每個候選的實際分鐘數，超過上限的剔除，倖存者每筆帶 `travel_min`。

這麼做的結果是結論表可以寫「步行 12 分」這種可信數字，而不是直線距離。

**範圍是「過去要多久」，不是「到了要待多久」。** 這兩者在泛用類型下極易混淆：「可以散步一小時的地方」裡的一小時是**在目的地停留**的時間，跟預設的「步行 15 分可達」是兩個獨立的數字，同時成立沒有矛盾（走 12 分鐘到一個能逛一小時的公園）。停留時長屬於 Step 0.2 的額外篩選條件，永遠不會被拿去改寫範圍上限。若使用者真的要放寬範圍，那是明講的「開車 30 分內」這種輸入。

過濾必須留在 script 裡，不能由 orchestrator 做：`build-itinerary` Step 0.7 明令不准 `cat` pool 檔（13 KB JSON 進 context 就抵銷了整個機制），所以 pool × route 的 join 只能發生在 shell。

## 個人偏好檔

### 位置與格式

`~/.config/trip-notes/preferences.md` — 與既有的 `maps.env` 同目錄。天然不在任何 repo 內（不需要 `.gitignore`，也不可能被誤 commit），跨 vault 跨專案共用，純 markdown 使用者隨時可手改。

```markdown
# 個人偵店偏好
最後更新：2026-09-05（第 4 次回饋 · 正面 12 家 / 負面 9 家）

## 反感（唯一有刷掉權的區塊）
- 菸草可・分菸 — 4/4 次負面標記

## 強偏好（排序加重）
- 禁菸 — 4/4 次正面標記
- 獨立店・非連鎖 — 9/12

## 弱偏好（同分時的 tiebreak）
- 安靜、可久坐 — 5/12

## 未定（訊號不足，繼續觀察）
- 靠窗 — 只出現 1 次

## 證據紀錄
### 👍 想去
- Beasty Coffee（2026-08-12・清澄白河）— 禁菸／獨立／水泥設計
### 👎 不要
- <店名>（日期）— 推測排斥原因
```

### 維護規則（每一條都對應一個具體的失敗模式）

1. **一次證據只能進「未定」；累積到 2 次才升「強／弱偏好」。**
   單次的隨手一挑不該變成永久規則。偏好檔的價值來自它反映的是**重複出現**的傾向。

2. **只有「反感」區塊有刷掉權；偏好只影響順序。**
   一條學錯的偏好如果能刷掉候選，會讓整類店從結果中永久消失，而使用者不會知道它消失了 —— 沒有出現在筆記裡的東西不會觸發「這不對」的反應，所以這種錯誤無法自我修正。排序錯了看得見，篩掉錯了看不見。

3. **每區最多 8 條；滿了要合併相近條目或淘汰證據最弱的。**
   否則檔案無限膨脹，而它每次生成都要整份讀進 scoring agent 的 context。

4. **agent 只能用 `Edit` 針對性增修，禁止 `Write` 覆蓋整檔。**
   這是使用者的檔案，手動編輯的內容必須存活。整檔重寫會靜默吃掉它們。

5. **每次修改後在回報裡用一行說明改了什麼。**
   偏好檔在背景影響所有結果，靜默變更等於不可稽核。

### 冷啟動

檔案不存在時**不擋流程**：改用中性排序（`travel_min` + 評分 + 評論數），在筆記的「排序依據」註明「尚無偏好檔，本次為中性排序」，生成後照樣執行回饋階段並建檔。骨架取自 `templates/preferences-example.md`。

## 評論（reviews）如何參與，又不汙染事實

### 範圍與成本

`nearby` 不回傳評論，`trip-maps reviews` 一次一家，且 `reviews` 是 Enterprise + Atmosphere 欄位 —— 整個 request 按其最高階欄位計費。因此：

- 評論**只**拉在 `reachable` 過濾**之後**的倖存者身上，絕不對原始 pool 全拉。
- 倖存者先用免費欄位（`travel_min`、rating、userRatingCount、`businessStatus`、營業時間）粗排，**取前 12 家**各拉 5 則評論。
- 60 則評論寫入 `--out` 檔，只進 scoring subagent 的 context，不進 orchestrator。

粗排會偏袒評論數多的店，而評論數少的獨立小店往往正是使用者要的。緩解方式：粗排時把 `userRatingCount` 的權重壓低（只當作「是否有足夠評論可讀」的門檻，例如 ≥ 10 則），主要靠 `travel_min` 與 rating。

**最終筆記的 8–12 家全部來自這 12 家。** 未進前 12 的倖存者列入「已篩掉的候選」，理由寫「未進評論讀取名額」，並在驗證狀態記「有 N 家倖存候選未讀評論」。讓未讀評論的店混進正式清單，會讓「偏好符合」欄出現無依據的符號。

### 邊界：評論決定順序，不決定筆記正文的任何事實

`build-itinerary` Step 0.6 已經立下四條硬規則（review 是線索不是引用／不得貼入筆記／沉默不代表沒問題／永不覆蓋結構化欄位）。要讓「評論參與排序」與這四條同時成立，界線畫在這裡：

**scoring agent 從評論得到的任何具體特徵（禁菸、有插座、安靜）只能做兩件事：改變排序，以及變成一條「待確認問題」。它不能直接寫進筆記。**

待確認問題清單隨 Step 6a 交給首選店家的研究 agent（「這家是否禁菸？請從官網或網誌確認」）—— 這正是 Step 0.6 規則 1 的原文用法：把 review findings 當作 questions to chase。確認到了才寫進筆記並標來源；沒確認到就不寫。

結論表因此多一欄「偏好符合」，只放 ◎／○／△ 符號。符號的依據寫在驗證狀態的「排序依據」段落，並明確區分哪些特徵已確認、哪些只是評論推測。

評論是**不可信的使用者輸入**：餵進 scoring agent 時明文標記 data-never-instructions，沿用既有 Guardrails。`preferences.md` 是使用者自己的檔案，可信。

## Pipeline

```
0    解析輸入 → 類型映射、模式、時間上限、額外條件
0.2  類型與條件解析 → 型別集合、查詢管道、第 2 層布林欄位、第 3 層文字條件；
                        一行回報解析結果
0.5  讀 preferences.md（不存在 → 中性模式，一行告知）
1    trip-maps place <地點>                → origin place_id / latlng
2    每個查詢各發一次 --limit 20 --out：
     nearby（純型別，含所需的布林欄位 mask）／search（料理・風格・主題詞）
3    trip-maps reachable <pool 檔...>      → 依 place_id 去重合併，computeRouteMatrix
                                             一次算完，剔除超時，倖存者帶 travel_min
4    結構化粗排取前 12
     → trip-maps reviews --out <scratch>/reviews.json <place_id ×12>
5    scoring subagent (sonnet)             → 套用第 2 層布林三態規則、對照 preferences.md
                                             與第 3 層文字條件排序到 8–12 家；
                                             只有「反感」命中或布林欄位為 false 才刷掉；
                                             輸出排序理由 + 待確認問題清單
6    分層研究
     6a 首選 3–4 家 → research + image subagent (sonnet)，附待確認清單
     6b 其餘 5–8 家 → 只用 trip-maps 結構化欄位，不派 agent
7    Step 2.7 facts (sonnet)               → 營業時間決定成敗者 ＋ 首選的偏好宣稱
8    組檔
9    3.5 curl 掃描 → 3.9 lint → browser verify (opus，只驗 6a 的圖與網誌)
     → 修正迴圈，上限 2 輪
10   交付筆記
11   回饋階段 → 更新 preferences.md → 回報
```

### 模型分層

| 步驟 | 工作 | 模型 |
|---|---|---|
| 0–4 | 確定性 shell 呼叫，由 orchestrator 執行 | — |
| 5 | 偏好比對排序（判斷，不是機械過濾） | `sonnet` |
| 6a | 首選店家研究 + 實拍圖 | `sonnet` |
| 7 | 時間事實交叉比對 | `sonnet` |
| 9 | 瀏覽器驗證 | **`opus`** |

沿用 `build-itinerary` 的原則：預算放在唯一能阻止錯誤出貨的那道閘門。

## 回饋階段（Step 11）

筆記交付後，立刻用 `AskUserQuestion` 問兩題（`multiSelect: true`）：

1. 「哪幾家你會想去？」
2. 「哪幾家一看就不要？」

兩面都問，因為負面訊號不需要使用者真的去過就成立，而且直接對應「下次別再推這種」。

agent 接著從被標記店家的評論、結構化欄位、以及首選層的研究結果中抽出**共同特徵**，依前述維護規則增修 `preferences.md`，最後用一行回報改了什麼。

**這是意向回饋，不是體驗回饋** —— 使用者當下還沒去過，他挑的是對描述的反應。這仍然正是排序要預測的東西，但證據紀錄要如實記為當次日期與地區，不假裝是到訪心得。

使用者略過不答是合法結果：不更新偏好檔，不追問。

## 筆記形狀

```
---
date: <today>
tags: [travel, japan, nearby, <type>, ...]
---

# 🍽️ <地點>周邊<類型>（步行 15 分內）

> 一行摘要：範圍怎麼定義的 + 最重要的限制（例：本區多數店 21:00 打烊）

## 結論表
| 店名 | 類型 | 步行 | 營業時間 | 定休日 | 評分 | 偏好符合 | Maps |
依偏好排序，首選標 ★；「偏好符合」只放 ◎／○／△

## 首選（3–4 家，每家一段）
地址／各曜日時間／實拍圖 + **店名** caption／網誌連結／招牌與座位

## 其他候選
表格，僅結構化事實

## 已篩掉的候選
一行一個，附具體數字或命中的反感條目
（「步行 22 分，超過 15 分上限」／「命中反感：分菸」）

## 使用提醒
編號注意事項

## 驗證狀態
- 已用瀏覽器確認：<list>
- 無法確認、出發前請自行查證：<list>
- 排序依據：使用 preferences.md（最後更新 <date>）；
  命中條目 <list>；下列特徵僅來自評論推測、未經確認：<list>；
  有 N 家未讀評論
```

沿用 `build-itinerary` 的全部寫作規則：表格必須頂層靠左、圖片 caption 是**純店名**且必須是可見的 `**店名**` 行（不只 alt text）、絕不捏造連結／地址／時間、每次 `Write`／`Edit` 後跑 lint gate。

## 檔案與程式碼變動

```
trip-notes/skills/find-nearby/
├── SKILL.md
└── templates/
    ├── score-candidates-brief.md     # 偏好比對 + 排序 subagent
    ├── research-venue-brief.md       # 首選店家研究，吃待確認清單
    └── preferences-example.md        # 冷啟動建檔骨架
```

共用（相對路徑引用 `../build-itinerary/templates/`）：`verify-brief.md`、`verify-facts-brief.md`。

引用而非複製，是因為這兩份 brief 裡的規則是用真實事故換來的（`networkidle` 禁令來自一次約 50 分鐘的掛機；「verify agent 不得再開 subagent」來自一次回傳空結果的驗證）。存在第二份副本就等於允許其中一份漂移。同一個 plugin 內兩個 skill 一定同時安裝，所以相對路徑成立。

`score-candidates-brief.md` **取代**而非共用 `screen-pool-brief.md`：後者是「依明示條件篩選」，前者多了偏好比對與待確認清單產出，是不同的工作。

`scripts/maps` 兩處新增，`build-itinerary` 既有行為不變：

- **`reachable`** — 新子指令。讀入**一個或多個** pool 檔、依 `place_id` 去重合併，以 `computeRouteMatrix`（1 origin × N destinations 單次呼叫）取代 N 次 `computeRoutes`，剔除超過時間上限者、輸出帶 `travel_min` 的過濾結果。快取 TTL 沿用 `route`（WALK/TRANSIT 30 天、DRIVE 1 天）。
- **`search`** — 新子指令，包 Places `searchText`。接受自由文字查詢 + `locationBias` 圓形 + `--limit`，輸出格式與 `nearby` 完全相同（同樣的欄位、同樣的 `compact_hours`），好讓 `reachable` 能無差別合併兩種 pool 檔。
- **`nearby`** — 新增可選的 amenity 欄位旗標（例如 `--fields outdoorSeating,allowsDogs`），只在指定時才把這些欄位加進 field mask。預設行為與 SKU 不變，`build-itinerary` 不受影響。
- **`reviews`** — 改為接受多個 `place_id`，並遵守既有的全域 `--out` 旗標。

連帶更新：`trip-notes/.claude-plugin/plugin.json`（description、keywords）、`.claude-plugin/marketplace.json`（description）、`trip-notes/CLAUDE.md`、`trip-notes/AGENTS.md`。完成後執行 `./scripts/bump-plugin.sh trip-notes minor`。

## 已知取捨

- **粗排的評論數偏誤**：前 12 名的門檻無法完全避免偏袒熱門店。緩解是壓低權重並在驗證狀態揭露「有 N 家未讀評論」，而不是假裝沒有這個偏誤。
- **意向 ≠ 體驗**：偏好檔學到的是使用者對筆記描述的反應。若日後想加入到訪後的真實回饋，自然的接點是在 Step 0.5 讀檔時補問上次推薦的店 —— 但那需要維護一份待追蹤清單，本次不做。
- **跨 skill 的 template 耦合**：`find-nearby` 依賴 `build-itinerary` 的兩份 brief。改動那兩份時要同時考慮兩個呼叫端；此約束記入 `trip-notes/CLAUDE.md`。
- **amenity 欄位名與 SKU 分級未經實測**：`outdoorSeating`、`allowsDogs` 等欄位的確切名稱、是否存在於 `searchNearby` 的 field mask、以及各自的計費層級，都要在實作 `--fields` 之前用真實呼叫確認。與 includedType 字串同一批驗掉。
- **雙管道的路由規則可能被略過**：「什麼時候用 `nearby`、什麼時候用 `search`」是模型判斷。緩解不是把規則寫得更嚴，而是把 fallback 設成「兩邊都發」—— 略過判斷時掉進的是完整的那條路，代價只有一次多的呼叫。
- **泛用類型的解析是模型自由判讀**：Step 0.2 是整個流程裡唯一沒有確定性依據的環節，錯意的成本是整份筆記找錯東西。緩解只有一個 —— 強制一行回報解析結果，讓使用者在花掉時間之前看得到。不加確認提問，因為多數情況解析是對的，為少數錯誤讓每次都多一輪互動不划算。
- **多型別讓候選數超過矩陣上限的可能**：4 個 type × 20 筆 = 80 個 destination。`computeRouteMatrix` 有元素數上限（且 TRANSIT 的上限遠低於 DRIVE），實作時要確認並在超過時分批呼叫，而不是靜默截斷候選 —— 靜默截斷會讓「已篩掉的候選」漏記，那正是這份設計要求可稽核的東西。
- **`computeRouteMatrix` 對 TRANSIT 的支援未經實測**：實作 `reachable` 的第一步是用一次真實呼叫確認 TRANSIT 模式可用、以及 origins×destinations 的上限。若 TRANSIT 不支援矩陣，退路是電車模式改用逐筆 `computeRoutes`（20 次呼叫，可接受）或先用 WALK 矩陣粗篩再對前幾名算 TRANSIT。這條在寫程式前就要驗掉，不要等到整合階段才發現。
