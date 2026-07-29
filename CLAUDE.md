# CLAUDE.md — job_auto_search

每週自動搜尋台灣的資料／商業分析職缺，依履歷適配度評分，產出可直接瀏覽的 dashboard。

Remote：`bill8345/job_search` ｜ Dashboard：https://bill8345.github.io/job_search/

---

## 執行流程

```
三來源爬取 → 職稱硬過濾 → 本次 URL 去重 → 跨週去重 → 104 補抓 JD 內文
→ 評分 → 併入累積池 → 輸出 CSV / dashboard → 回寫去重庫
```

GitHub Actions（`.github/workflows/job-search.yml`）每週一 UTC 00:00（台灣 08:00）自動跑，
把 `data/*.json` commit 回 repo，並將 dashboard 部署到 GitHub Pages。

## 檔案結構

| 路徑 | 用途 |
|---|---|
| `main.py` | 流程編排 |
| `config.yaml` | 關鍵字、地區、各平台開關與頁數 |
| `resume.md` | 評分基準（技能、期望職位），**改這裡就會改變評分結果** |
| `scrapers/scraper_104.py` | 104 搜尋 API + 詳細內容 API |
| `scrapers/scraper_cake.py` | CakeResume，走 Next.js `_next/data` JSON |
| `scrapers/scraper_linkedin.py` | LinkedIn guest API |
| `scoring/filters.py` | 職稱硬過濾（決定職缺進不進清單） |
| `scoring/scorer.py` | 適配度評分 |
| `storage/dedup.py` | 跨週去重庫，28 天 TTL |
| `storage/pool.py` | Dashboard 累積池，45 天 TTL |
| `templates/dashboard.html` | Dashboard 版型 + 投遞標記的前端邏輯 |

## 常用指令

```bash
python main.py                          # 照 config.yaml 跑
python main.py --platform cakeresume    # 只跑單一平台
python main.py --no-dedup               # 略過跨週去重（測試用）
python main.py --no-filter              # 略過職稱過濾（測試用）
python main.py --config <path>          # 用別的設定檔（測試時搭配 scratchpad 的輸出路徑）

gh workflow run job-search.yml --repo bill8345/job_search   # 手動觸發
```

**測試時務必**：用 `--config` 指向暫存設定檔、輸出路徑改到 scratchpad，並先備份
`data/dashboard_pool.json`——`update_pool()` 走的是預設路徑，會污染正式資料。

---

## 評分邏輯（2026-07-29 定案）

| 維度 | 配分 | 說明 |
|---|---|---|
| 技能匹配 | 40 | `resume.md` 的技能出現在 JD 或 tag，命中 6 個滿分 |
| 職稱匹配 | 30 | 對 `resume.md` 的期望職位做雙向包含比對 |
| 關鍵字重疊 | 20 | 履歷 vs JD 的中文 n-gram + 英文字重疊 |
| 資歷 | ± | 資深 +8／初階、新鮮人 −25 |

滿分 98。**地點不計分**：爬蟲已按 area 篩過，97% 拿滿分，只會把分數整體推向 100 分
上限造成大量同分（實測 513 筆有 22 筆觸頂）。地點仍顯示在 dashboard 供人判斷。

### 職稱硬過濾為什麼是必要的

平台的 keyword 搜尋比對的是 **JD 內文而非職稱**，所以 JD 裡提到一句「需具備資料分析能力」
的倉管、理財專員、電話行銷都會被撈進來（實測佔 41%）。這種噪音**評分救不了**——
它們的 JD 提到 SQL、Dashboard、自動化，照樣拿得到技能分。所以必須在進清單前擋掉。

`filters.py` 的規則：職稱要命中分析職核心字，且不是實習或系統分析師（SA 是需求工程，
不同職種）。

---

## 已驗證、不要再重做的判斷

這幾件事查證過，之後不要再繞回來提：

- **不要重新配分**。頂端同分的根因是「維度飽和」（技能 28%、職稱 59% 拿滿分），不是權重
  不對。實測放大權重（技能 60 / 職稱 40）反而讓前 50 名的不重複分數從 23 掉到 2
- **不要用「來源偏誤」當理由調技能權重**。曾觀察到 104 平均分遠低於 LinkedIn／Cake，
  但那是 104 抓不到 JD 內文造成的假象；接上 `get_job_detail` 後三來源平均分已幾乎相同
  （104 技能分 13.6 → 24.4）
- **104 的 YAML int key bug 刻意不修**。`config.yaml` 的 `104:` 會被 YAML 解析成 int，
  程式用字串查所以拿不到 `job_searches`，實際走的是 keyword-only 模式。這雖非原設計，
  但召回比 jobcat 模式更廣（能撈到跨分類的分析職），對這個用途更有利

---

## 平台特性與陷阱

- **CakeResume 有 Cloudflare managed challenge**：`/jobs` 的 HTML 頁面擋 bot，`curl_cffi`
  的 TLS 指紋偽裝也過不了。改走 Next.js 的 `_next/data/{buildId}/en/jobs/{keyword}.json`
  ——這個端點沒有被擋。`buildId` 要從首頁 HTML 的 `"buildId":"..."` 抓，**會隨 Cake 部署變動**，
  不能寫死
- **104 需要 `curl_cffi` 的 `impersonate="chrome"`**：純 `requests` 會被 TLS 指紋擋掉
- **104 搜尋 API 只回傳 JD 摘要**：完整內容要另外打 `get_job_detail`，不補抓的話技能分會
  被系統性低估
- **職稱有異體字與 CJK 隨機空白**：`臺北市` vs `台北市`、`商業分析 師`（約 4%）。中文比對前
  一律先過 `filters.strip_cjk_gaps()`

## 資料檔與重置

`data/seen_jobs.json`（去重庫）與 `data/dashboard_pool.json`（累積池）都是 URL 為 key 的 dict，
由 GitHub Actions commit 回 repo。

改動評分邏輯後想讓既有職缺套用新分數，**兩個都要清成 `{}`**——只清池子的話跨週去重會讓
`new_jobs` 是空的，`main.py` 會在輸出前就 return，dashboard 根本不會重新產生。

Dashboard 的「已投遞」狀態存在瀏覽器 localStorage（`appliedJobs_v1`，靜態頁沒有後端），
清資料檔不會影響它。
