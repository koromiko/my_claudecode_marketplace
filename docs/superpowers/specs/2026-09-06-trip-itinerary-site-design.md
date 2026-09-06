# 行程發佈站（trip-itineraries）— 設計

日期：2026-09-06
Plugin：`trip-notes`（`build-itinerary`）
新 repo：`trip-itineraries`
狀態：設計待核可

## 目的

把 `build-itinerary` 的產出從「一份只存在於 vault 的 Obsidian 筆記」變成「一個可以分享給別人閱讀的網頁」，頁面上有嵌入式 Google 地圖，各站以編號 pin 標出，列表與地圖雙向連動。

現況的結構性問題是：**note 是 prose，而網頁需要結構。** 表格、callout、驗證狀態的資訊密度很高，但機器難以解析；而 `trip-maps` 的 cache 雖然是結構化的，卻用 request hash 當 key，跟「哪份行程用到這個地點」毫無關聯。兩者之間沒有中間層。

本設計的核心決定就是補上那一層：**結構化資料升格為唯一產物，note 與網頁都是它的 render。**

## 範圍

**做：** 一日以內的單一路線、資料模型、靜態網站產生、嵌入地圖與列表連動、skill 改為輸出 YAML。

**不做：** 多日行程、別人自己產生行程、帳號系統、訂位、即時擁擠度。

## 已確定的範圍決定

| 決定 | 值 | 理由 |
|---|---|---|
| 誰產生行程 | 只有 Neo。別人唯讀。 | 砍掉排隊、計費、濫用防護、金鑰外流風險。 |
| 網頁住哪 | 獨立站、獨立 repo | 分享情境乾淨；發佈節奏與 vault 解耦；日後要開放比較好長。 |
| 事後怎麼修改 | 重跑 skill 重生，不手改 | 資料檔是唯一產物，人不碰中間格式。 |
| 資料新鮮度 | build 時拉取 | 每日重建**已砍掉**（見「擱置的問題」）。 |
| YAML 放哪 | `trip-itineraries` repo | 隱私邊界：對外網站的 build 不該 checkout 整個 vault（內含 `Credential/` 與私人筆記）。 |
| 行程長度 | 一日以內 | 多日的正確模型是「一天一條路線 + 串接物」，現在猜會猜錯。 |

---

## 法規限制（決定了技術選型）

Google Maps Platform 條款有兩條直接打到這個設計。**以下依記憶陳述，實作前須自行核對原文。**

1. **不得與非 Google 地圖並用。** Places API 取得的座標與名稱不能畫在 MapLibre / OSM / Leaflet 上。因此「用免費 tile 自己畫」這條路實際上是關的，地圖必須是 Google。
2. **快取上限 30 天。** `place_id` 可無限期保存；座標、地址、營業時間屬受限內容。

第 2 點反而指向更好的設計：**資料檔只存 `place_id` 與人工編輯內容，其餘 Google 欄位一律 build 時現拉。** 這同時解決合規與資料腐壞。人工編輯內容（中文譯名、停車費警告、時間辨析、驗證狀態）全是原創，不受限。

---

## 資料模型

一個檔案 = 一條路線 = 一頁 = 一日。多路線的 note 在驗收時就是最麻煩的那一份；分享一條路線給別人，對方不該先選一次。

```yaml
slug: zushi-hayama-yokosuka
title: 逗子・葉山・橫須賀 海景溫泉自駕路線
summary: 沿相模灣海岸線南下，終點泡東京灣海景露天溫泉的半日行程。
mode: drive                          # drive | train
region: 神奈川
tags: [海景, 溫泉, 半日]
status: published                    # draft | published
source_note: Travel/20260705/逗子葉山橫須賀海景溫泉自駕路線.md
start_time: "11:00"

provenance:
  generated: 2026-09-06
  verification: browser-local        # browser-local | browser-ci | fetch-only | none

stops:
  - place_id: ChIJofSSE04UGGARmr-MepKsDy4
    label: 馬里布農場 逗子瑪麗娜
    role: lunch                      # lunch | shop | view | onsen | drive | station
    stay: 90                         # 分鐘
    notes_md: |
      平日 11:30 才開，週六日 8:00 開門，適合安排成早午餐。
    parking:
      fee: 第 1 小時 ¥800，之後每小時 ¥400
      capacity: 170
      note: 過午後車位常接近滿場，建議排在中午前段。
    photos:
      - url: https://someblog.jp/photo.jpg
        credit: someblog.jp
        source_url: https://someblog.jp/post/123

  - query: 神奈川県三浦郡葉山町 国道134号
    label: 國道134號（海景公路）
    role: drive
    via: [葉山公園前, 秋谷]
    notes_md: |
      這段是全程風景最好的地方，別走內陸捷徑。

extras:
  - place_id: ChIJ...
    label: 觀音崎公園
    notes_md: 時間有多的話值得繞。

references:
  - url: https://someblog.jp/post/123
    title: 葉山ドライブで寄りたいカフェ5選
    lang: ja

cautions_md: |
  逗子瑪麗娜停車費是本路線最大的變動成本。

unconfirmed:
  - 逗子瑪麗娜停車場的開放時間未能從官方來源確認
  - SUNSHINE+CLOUD 停車場的車位數與費用未能確認
```

### 模型決定與理由

**沒有 `legs` 陣列。** 路線就是 stops 的順序，`via` 掛在「要走去的那一站」上。這消滅了一整類 bug——leg 指到不存在的 stop、順序改了 leg 沒跟上。代價是不能表達非線性路線，而那本來就不是需求。

**`query` 是 `place_id` 的合法替代。** 國道134號這種路段在 Places 裡沒有乾淨的 place，硬塞會拿到奇怪的 pin。`query` 是自己寫的字串，不是 Google 的受限內容。**query stop 不上 pin**——路段不是點；它的作用是讓路線折線經過該處，靠 `via`。

**沒有 `confirmed: true/false` 旗標，欄位缺席即代表不知道。** 兩套表達「不確定」的機制一定會互相矛盾。要讓讀者看到的不確定寫進 `unconfirmed`，它會渲染成頁面上一個明確區塊。這是現有 note 最好的特質之一。

**兩件事改成推導，不寫進檔案：**

- **公休矩陣**（「週一少一站、週三少一站」）由各站營業時間於 build 時算出。寫死只會腐壞，算出來永遠對。
- **時間軸**由 `start_time` + 各站 `stay` + Routes 回傳的路段時間算出。手寫的時間軸在任何一段路程變動後就是錯的。

**`provenance.verification` 區分 `browser-local` 與 `browser-ci`。** 兩者可信度不同，不該混成同一個值（理由見「第三階段」）。沒有這個欄位，半年後看著兩份行程分不出哪份被真的驗過。

---

## 建置流程

```
itineraries/*.yaml
      │
      ├─ 1. 驗證 schema ──────────── 失敗 → 整個 build 失敗
      │
      ├─ 2. 每個 stop 取 Google 資料
      │      place_id → Place Details
      │      query    → 不取、不上 pin
      │      via      → 暫時 geocode，只餵給 Routes，不落地
      │
      ├─ 3. 相鄰 stop 之間算 leg
      │      Routes API → 距離、時間、polyline
      │      mode: drive → DRIVE；mode: train → TRANSIT + WALK
      │
      ├─ 4. 推導公休矩陣與時間軸
      │
      └─ 5. 渲染 HTML（每份行程一頁 + 索引頁）
```

**建置腳本直接呼叫現有的 `trip-maps`，不重寫一套。** 它已處理好 cache、TTL、field mask、錯誤碼，而且 CI 本來就要 checkout plugin repo（skill 從那裡來）。兩份實作一定會漂移，一份不會。

### 失敗處理：全有全無

任何一份行程出問題，**整個 build 失敗，Cloudflare 繼續服務上一次成功的版本。** 沒有半成品上線，不需要為此寫任何機制——這是靜態站的預設行為。

但不是所有壞消息都該擋 build：

| 情況 | 處理 |
|---|---|
| schema 不合法、`place_id` 查無此地、金鑰失效、配額用盡 | **build 失敗**，站台維持舊版 |
| `CLOSED_PERMANENTLY` / `CLOSED_TEMPORARILY` | **照常出頁**，該站與頁首標紅，列進 build report |
| 某站沒有營業時間資料 | 照常出頁，該欄顯示「未提供」 |

歇業不擋 build，因為那是**真實世界的事實**，讀者比作者更需要立刻看到；而 `place_id` 查不到是**資料錯了**，讀者只會看到破頁。

---

## 頁面結構

```
手機                          桌機
┌──────────────┐             ┌─────────────┬──────────────┐
│              │             │ 逗子・葉山… │              │
│     地圖     │ ← sticky    │ ─────────── │              │
│  ①②③④⑤⑥    │   40vh      │ ① 馬里布農場│     地圖     │ ← sticky
├──────────────┤             │ ② Ron Herman│  ①②③④⑤⑥   │
│ ⚠ 週一/週三  │             │ ③ SUNSHINE… │              │
│   各少一站   │             │ ④ 国道134号 │              │
├──────────────┤             │ ⑤ 馬堀海岸  │              │
│ ① 馬里布農場 │  ← 捲動     │ ⑥ 湯樂之里  │              │
│   マリブ…    │             │ 注意事項    │              │
│   11:30–20:00│             │ 未能確認    │              │
└──────────────┘             └─────────────┴──────────────┘
```

- **地圖固定、列表捲動，雙向連動。** 點列表第 ③ 站地圖飛過去；點地圖 ③ 捲到那張卡。這個連動是選擇 Maps JS API 而非 Embed iframe 的**全部理由**，版型必須讓它隨時可用——地圖捲出畫面的設計會毀掉它。
- **每張站點卡上中文名與日文名都要在。** 不是排版偏好：人在現場要把日文名給店員看、貼進 Google Maps 搜尋。
- **沒有 JS 也要能讀。** 列表是 build 出來的靜態 HTML，地圖是加分項。分享出去的連結不該依賴一支腳本載入成功。
- **頁尾標上資料取得時間。** 既然不做每日重建，這行字更重要。
- **畫路線折線。** 順序是這種行程的核心資訊。
- **延伸景點用不同顏色小 pin，預設關閉，一個開關打開。** 埼玉那份有 13 個延伸點，全上會淹掉主路線。
- **第一版不做 OG 預覽圖。** 先確認整條路走得通。

### 地圖金鑰

互動地圖需要一把瀏覽器端金鑰（資料由 build 時取得，不需要金鑰；**地圖本身需要**）。限制為「僅 Maps JS API」+「僅本站 domain」。Essentials 每月一萬次地圖載入免費，以此量級不會觸及。

---

## Skill 改動

| 步驟 | 現在 | 改成 |
|---|---|---|
| Step 0.5–0.8 | 地點解析、評論、篩選、cache | **完全不動**（新架構更依賴它們） |
| Step 3 組檔案 | LLM 手寫 markdown（3A/3B 版型） | **寫 YAML**；版型移出 skill，成為 renderer 模板 |
| Step 3.5 機械掃描 | 檢查連結格式、座標、表格欄數 | **大部分刪掉** |
| Step 3.9 lint gate | LLM 自行判斷 note 合格與否 | **換成 schema 驗證腳本** |
| Step 4 瀏覽器驗證 | 驗所有連結、圖片、事實 | **範圍縮小**：只驗網誌 URL、圖片、prose 主張 |
| research-*-brief 模板 | 回報格式為自由文字 | 回報格式對齊 YAML 欄位 |

**Step 3.5 幾乎整個消失，這是最大的收穫。** 它現在檢查的東西——連結格式、座標、表格欄數——在新架構下**結構上不可能出錯**，因為連結是 build 時從 `place_id` 生成的，不是 LLM 打出來的。一整類錯誤不是被檢查掉，是被消滅掉。

Step 4 縮小同理：地點資料不再需要驗證，它直接來自 API。剩下要驗的是**只有人能判斷的東西**——網誌連結還活著嗎、這張圖能不能用、這句話是不是真的。

### 產物落點

- YAML → `trip-itineraries` repo
- 渲染後的 note → vault（由 renderer 產生，非 skill 直接寫）

renderer 與 build script 同住 `trip-itineraries` repo。代價是一次生成會動到兩個 repo。接受，理由見「隱私邊界」。

**note 渲染是本機限定的步驟。** CI 沒有、也不該有 vault 的 checkout（隱私邊界），因此第三階段由網頁觸發的生成**只會產出 YAML 與網站，不會產出 note**。要補 note 就在本機重跑 renderer。這是刻意的取捨，不是缺陷。

### 第一階段順手要做的小改動

`trip-maps` 目前只讀 `~/.config/trip-notes/maps.env`。改成**有 `GOOGLE_MAPS_API_KEY` 環境變數就用，沒有才讀檔**。十行以內，同時讓 CI 與本地測試都更方便。

---

## 分期

| 階段 | 內容 | 為什麼這樣切 |
|---|---|---|
| **一** | 定 YAML schema；skill 改為輸出 YAML；`trip-maps` 吃環境變數 | 用兩三份真實行程確認 schema 扛得住。schema 設計錯了只是改幾個檔，不是改一個已經長出來的網站。 |
| **二** | `trip-itineraries` repo、build script、renderer、網站、部署 | |
| **三** | 網頁觸發生成 | 不擋前兩階段，可延後決定。 |

---

## 第三階段：網頁觸發（GitHub Actions）

**這一段先只寫到「不擋路」的程度，不是完整設計。**

### 為什麼選 GitHub Actions 而非自架 Agent SDK

官方文件寫明：**GitHub Action 就是 Agent SDK 加一層托管。** 所以這不是兩種技術的對比，而是「用別人打包好的，還是自己組」。

| | GitHub Actions | Agent SDK 自架 |
|---|---|---|
| 運算與維運 | GitHub runner，零基礎設施 | 自己的容器，要顧部署、重啟、日誌 |
| 進度回報 | queued／running／done，log 事後看 | **可串流**，SDK 唯一的決定性優勢 |
| 認證計費 | `CLAUDE_CODE_OAUTH_TOKEN`，走訂閱、**不另計費** | `ANTHROPIC_API_KEY`，**按量計費** |
| 沿用現有 skill | `plugins` + `/trip-notes:build-itinerary`，幾乎零移植 | 自己接 plugin 與 skill 載入 |
| 產物落地 | job 本來就在 checkout 裡 | 自己 clone／push |
| 每次執行的隔離 | 全新 VM，用完即丟 | 長駐行程，狀態會累積 |
| 除錯 | 永久 log ＋ re-run 按鈕 | 自己建 |

計費那一格有官方依據：Agent SDK overview 明寫「Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK. Use the API key authentication methods instead.」且 SDK 受 Commercial Terms 規範。

**但這個成本優勢有期限。** `CLAUDE_CODE_OAUTH_TOKEN` 綁的是個人訂閱。一旦開放給別人按，別人的用量走個人訂閱已離開個人使用的語意，GHA 也該換成 API key——**兩個方案的計費就此收斂**。因此 GHA 的優勢只存在於「只有你按」的階段，而那正是第三階段第一版。

**曾經誇大、已修正的一點：** 早先認為 checkout/push 是 SDK 的主要遷移成本，這是錯的。容器完全可以 clone 與 push。真正的差別只有憑證生命週期（GHA 每次鑄一把短期 token）與「保證乾淨的工作目錄」（容器裡只要每個 job clone 到臨時目錄跑完刪掉即等價）。**並行 push 衝突兩者都有**，GHA 並未代為解決。

### 觸發鏈

```
瀏覽器
  │  POST /api/generate   { place, mode, notes }
  ▼
Cloudflare Worker  ← 既有，加一個路由
  │  ① 驗身分（沿用既有的 Basic Auth）
  │  ② 產一個 job_id
  │  ③ 打 GitHub API，帶 Worker secret 裡的 token
  ▼
POST /repos/koromiko/trip-itineraries/actions/workflows/build.yml/dispatches
  │
  ▼
workflow → claude-code-action → 產 YAML → commit → 網站重建
```

**GitHub token 絕對不能進瀏覽器**，所以必須有伺服器端中介——但 Cloudflare Worker 已經存在，加一個路由即可。

用 `workflow_dispatch` 而非 `repository_dispatch`：輸入有型別、有描述，而且**可以直接在 GitHub 網頁按按鈕測試**，前端還沒寫就能驗證整條鏈。它的執行者是 token 擁有者（人），因此不會撞到 Action 的 bot 檢查；用 GitHub App 才需要 `allowed_bots`。

**已知坑：dispatch API 回 `204 No Content`，不給 run id。** 解法是把 `job_id` 塞進 workflow 的 `run-name`，查詢時用它比對。土，但不需要任何額外儲存或回呼。需要細緻進度時再讓 workflow 回打 Worker 寫進 KV。

Token 用 **fine-grained PAT**，只授權該 repo、最小權限、設到期日、存為 Worker secret。不建議一開始上 GitHub App——更正確但零件更多，且會推回 bot 檢查那個坑。

身分驗證沿用 `cf-worker/private-auth.ts` 那套 Basic Auth：已在跑、已 fail-closed、已知能動。

### 保持可遷移的四條規則（現在就要遵守）

這四條是零成本的設計約束，事後補是補不回來的：

1. **skill 不碰 git，也不讀任何 `GITHUB_*` 環境變數。** 只吃參數、把 YAML 寫到指定路徑，對執行環境完全無知。
2. **commit 與 push 寫成獨立腳本，不是 workflow 裡的 inline 指令。** 換 SDK 時原封不動呼叫同一支腳本。四條裡最值錢的一條。
3. **workflow YAML 保持薄。** 超過「checkout → 裝 plugin → 跑 claude → 呼叫 push 腳本」就代表邏輯正在洩漏到不會搬家的地方。
4. **Worker 裡把觸發與查詢狀態隔離成 `startJob(inputs) → job_id` 與 `getStatus(job_id)` 兩個函式。** 換後端只換這一個檔案的實作。

### CI 環境的瀏覽器限制

**瀏覽器本身沒問題。** GitHub ubuntu runner 預裝 Chrome / Chromium / Firefox / Edge。不存在的是 **claude-in-chrome 這個特定管道**（靠 Chrome 擴充功能接本機已登入的瀏覽器）。替代方案是 **Playwright MCP**，經 `claude_args` 的 `--mcp-config` 傳入。因此驗證模板**不能綁死工具名稱**。

真正的限制在別處：

- **IP 信譽。** runner 是 Azure 資料中心位址，遇到 Cloudflare 挑戰、CAPTCHA、429、403 的機率遠高於家用網路。日本的個人網誌、觀光協會官網、店家官網擋得很兇——而那正是本 skill 最需要讀的來源。**不是沒有瀏覽器，是不被當成人。**
- **沒有登入狀態。** 需要 cookie 的內容讀不到。
- **失敗長得像成功。** 被擋時拿到的是一個「頁面」而非錯誤，驗證 subagent 可能對著挑戰頁下結論說「連結有效」。這比單純失敗危險。**驗證模板必須把「被擋掉」與「連結壞掉」分開回報**，遇到挑戰頁標為「無法驗證」，不下任何結論。

**可能兩全的選項：** GHA 支援 self-hosted runner。控制平面、secrets、log、re-run 照用，執行落在自己的機器上，IP 信譽問題隨之解決。代價是機器要開著。

### 成本

Worker 在免費額度內。Actions 分鐘數：private repo 每月 2,000 分鐘免費，一次生成抓十分鐘約 200 次，遠超實際用量。不夠就把 repo 設為 public（行程資料本來就要公開），分鐘數無限。

---

## 擱置的問題（明確已知，非遺漏）

| 問題 | 狀態 |
|---|---|
| **30 天快取上限的合規性** | 已決定最後再處理。砍掉每日重建後，已部署的頁面會長期持有受限內容。 |
| **營業時間腐壞** | 同上。不重建 = 讀者看到的營業時間停留在最後一次部署時。頁尾的日期是目前唯一的緩解。 |
| **每日重建的成本** | 曾估算十份行程 × 八站 × 每日 ≈ 每月 2,400 次 Place Details，會超出免費額度。SKU 分層與免費額度的確切數字係憑記憶，不足以作為決策依據——要恢復每日重建前，應先在 Google Cloud Console 觀察一個月實際用量。 |
| **CI 中的瀏覽器驗證品質** | 未知數。瀏覽器驗證是本 skill 品質的來源；CI 中會被擋多兇只能實測。第三階段處理。 |

---

## 決策紀錄（為什麼沒選另一條路）

| 曾考慮 | 沒選的理由 |
|---|---|
| 並入現有 Quartz 站 | 閱讀體驗受 Quartz 版型限制；行程與技術筆記混在同一站，分享情境奇怪；vault 一 push 就佈署，等於改筆記也重建行程站。 |
| 每份行程一個獨立 HTML 檔 | 沒有索引頁、行程之間沒有關聯、更新要重發、不易累積成「服務」。 |
| MapLibre + 免費 tile | Google 條款禁止 Places 資料與非 Google 地圖並用。 |
| Maps Embed API iframe | 免費且無上限，但無法自訂編號 pin，也無法讓列表與地圖連動——而那正是本站的核心價值。 |
| note 為 source of truth，網頁從 note 編譯 | 使用者選擇「重跑 skill 重生，不手改」，故資料檔為唯一產物。 |
| 自架 Agent SDK | 見上方比較表。唯一決定性優勢（串流進度）是產品問題而非基礎設施問題，且計費模式差距不會隨程式變好而縮小。 |
