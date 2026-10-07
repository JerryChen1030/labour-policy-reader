# 政策資料單頁閱讀室

非官方、人工維護的政策來源閱讀工具。歷史資料截至 2026-10-05，並非即時、完整或法律效力資料庫。來源內容可能已更正，請回原文核實。

## 內容與獨立運行

- `docs/`：可直接由 GitHub Pages 提供的 HTML、CSS、JavaScript 與 JSON，94 筆歷史公開線索、16 筆官方選讀及 91 個來源入口
- `collector/`：Python 3.10+ 標準函式庫候選蒐集器，48 項離線測試；來源全部預設停用
- `tools/verify_public.py`：清單雜湊、檔案邊界與靜態資料檢查

沒有後端、OpenAI runtime、模型 API、金鑰、付費服務或排程。原先的 ChatGPT Site 僅為展示位置，執行此版本不需要該 Site 或 OpenAI 帳號。GitHub Pages 的免費方案、額度及可用性由 GitHub 決定，不能保證永久免費或永久在線。

## 安装、重建與測試

安裝 Python 3.10+。下載此儲存庫或已核對 SHA-256 的 source release，解壓後執行：

```sh
python3 tools/verify_public.py
(cd collector && python3 -m unittest discover -s tests -v)
python3 -m http.server 8000 --directory docs
```

在瀏覽器開啟 `http://localhost:8000`。不要直接以 file:// 開啟。靜態網站已是可執行原始碼，不需 npm 或建置步驟；重建即重新核對清單並以 HTTP 提供 `docs/` 的檔案。若另有 Node.js，可加跑 `node --check docs/app.js`。

## GitHub Pages 發布

新 public repo 應位於個人帳號 `JerryChen1030`，不更改任何既有私有 repo。推送前先核對 PUBLIC-MANIFEST.json 和差異，僅加入清單列明的檔案。

在此 repo 的 Settings → Pages，Source 選 Deploy from a branch，Branch 選 main，資料夾選 /docs，儲存。所有靜態資產保持同層，使用相對路徑並保留 `.nojekyll`。等待 Pages build/deployment 成功；核對 main commit SHA、網站首頁及四個 JSON 的 HTTP 200，並測試搜尋、篩選、排序及空結果後，才算完成發布。

本文件是可重現操作說明，不是已上線證明。以實際 GitHub repo、Pages 部署狀態及 release 記錄為準。

## 手動蒐集與公開審核

獨立 collector CLI 的少量官方 RSS 實測在此執行環境因 DNS 解析失敗，尚未接通。另一次經 Firecrawl MCP 手動讀取，確認 MHLW 與 WDA feed 回傳 HTTP 200 且 XML 可解析；這不代表此獨立蒐集器已可運行，也不構成再散布授權。來源全數停用，詳見 `collector/README.md`。以下 smoke test 不抓取網路，也不發布資料：

```sh
cd collector
python3 collector.py --sources sources.json --state-dir private-state
```

未審核候選資料只留在私人 `private-state/`。未來先核對來源條款和實際 feed，在有網路的操作環境用本地來源清單做手動測試；不能因來源官方、HTTP 成功或 XML 可解析，就視為真實、完整或可再散布。日本 MHLW RSS 使用條款對 feed-based 網站及再散布有限制；不要把其候選文字直接移入本 public repo。

人工逐項核對原文、日期、權利及隱私，再另外撰寫中性短摘要；取得公開核准後才更新 `docs/data.json` 與對應 HTML 卡片。`grok.json` 保持獨立歷史集合，不能用候選 feed 自動覆蓋。更新後重建對應檔案雜湊、檢查差異並重新測試，最後手動提交與發布。

蒐集器沒有 cron、背景 daemon、自動核准或自動發布；collector 模板留在 templates；另有下述明確授權的手動健康檢查 workflow。Pages 會在人工推送 main 的 docs 變更後進行平台部署，只提供已提交的靜態資料，不會代跑蒐集器。

[GitHub 官方 Pages 發布來源說明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)（2026-10-06 核對）

## 備份與回退

保存每次 release source archive、PUBLIC-MANIFEST.json 和其外部 SHA-256。GitHub 產生的 ZIP 位元可能隨打包變化；解壓檔案內容以 manifest 為準。此公開備份只含安全整理後內容，不含原始 CSV/交接附件、29 筆隔離內容、私人候選或內部研究。

回退時先保留當前版本，在工作分支將 `docs/` 恢復成選定 release 的完整內容及配套 manifest，確認差異、執行測試後提交；核准並合入 main 後再確認 Pages build 與 HTTP/互動結果。不要 force-push 或改動其他 repo。若需回退 collector，用同一 release 的完整 collector 目錄，停止執行後先備份私人 state，保持 state 版本相容與退避紀錄，不將它上傳。

## 內容權利

本站提供短摘要及來源導航，不授予第三方原文、圖片或附件再散布權，也不是政府官方網站或法律意見。來源權利由各自權利人保有；未額外替第三方內容授予授權。


## 一次性手動 RSS 健康檢查

使用者已授權 `.github/workflows/manual-rss-health.yml`，只接受 `workflow_dispatch`；不接受 push、PR 或 cron 觸發，不自動發布文章。到 Actions → Manual RSS health metadata → Run workflow → 已核對 commit 的候選分支手動執行。不要短時間重複執行；本次授權每源一次，未來重試先另行確認。沒有持久化退避狀態，不能當成例行蒐集器。

工作限 5 分鐘、單一 `ubuntu-latest` 標準 GitHub-hosted runner、僅 `contents: read`，checkout 不保留憑證。沒有自訂 secrets、付費 runner、快取、artifact、git push 或候選資料檔案。先跑 48 項 collector 及 14 項 probe 離線測試，再各試 MHLW、MOEL、WDA 一次；每源子程序 70 秒上限，沿用 collector 的 HTTPS/public DNS/IP pin/TLS、15 秒 socket、2 MiB、最多 2,000 項、最多 3 次同 allowlist redirect 等限制。不繞過安全驗證、代理或來源存取限制。

只在記憶體複製設定用於 probe，repository 的三源仍 disabled。body 與候選內容只存在短命程序記憶體，不寫入檔案、log、摘要或 artifact。公開 log 只記來源 ID、HTTP/parse 狀態、accepted/skipped 數量、已知日期欄位覆盖、最後可解析日期、bytes、SHA-256 、白名單 MIME 與固定 parser 錯誤碼；不含標題、正文、個人姓名、email、原始日期字串或例外訊息。`last_date` 是已解析 publication/update 欄位最大值，不是生效日；MOEL 與 WDA 的來源當地日期另記 `published_local`，保留秒精度及 `timezone_unknown: true`，不擅自推算 UTC。`last_source_local_date` 是另列的來源當地曆日；`date_status` 區分 UTC 已知、當地日期但時區未知、資料不全與空 feed。未知格式仍保持未知。

失敗、部分解析、日期未知不等於沒有新政策。成功亦只證明該次回應可讀，不證明內容正確、全面或可再散布。MHLW 使用限制仍適用，嚴禁將 feed 內容移入公開網站。這個工作不改 `docs/`，既有 Pages 平台部署只提供已提交靜態資料。

費用：依 2026-10-06 核對的 [GitHub 官方規則](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)，public repository 的標準 GitHub-hosted runner 使用免費，本次預期 runner 費用 US$0。這不是永久免費承諾；平台仍有服務、並行及使用限制，改成 private repository 或非標準 runner 前必須重新核對並取得授權。

候選修正與限制詳見 [parser repair receipt](collector/PARSER-REPAIR.md)。先前 WDA 2,414-byte 回應的根因仍未知；現在有效的 RSS 回應不能倒推該次失敗原因。三源手動驗證要以候選 commit 的實際 run 為準。
