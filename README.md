# 政策資料單頁閱讀室

非官方、人工維護的政策來源閱讀工具。歷史資料截至 2026-10-05，並非即時、完整或法律效力資料庫。來源內容可能已更正，請回原文核實。

## 內容與獨立運行

- `docs/`：可直接由 GitHub Pages 提供的 HTML、CSS、JavaScript 與 JSON，94 筆歷史公開線索、16 筆官方選讀及 91 個來源入口
- `collector/`：Python 3.10+ 標準函式庫候選蒐集器，40 項離線測試；來源全部預設停用
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

蒐集器沒有 cron、背景 daemon、自動核准或自動發布；collector 模板留在 templates，不是啟用的 workflow。Pages 會在人工推送 main 的 docs 變更後進行平台部署，只提供已提交的靜態資料，不會代跑蒐集器。

[GitHub 官方 Pages 發布來源說明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)（2026-10-06 核對）

## 備份與回退

保存每次 release source archive、PUBLIC-MANIFEST.json 和其外部 SHA-256。GitHub 產生的 ZIP 位元可能隨打包變化；解壓檔案內容以 manifest 為準。此公開備份只含安全整理後內容，不含原始 CSV/交接附件、29 筆隔離內容、私人候選或內部研究。

回退時先保留當前版本，在工作分支將 `docs/` 恢復成選定 release 的完整內容及配套 manifest，確認差異、執行測試後提交；核准並合入 main 後再確認 Pages build 與 HTTP/互動結果。不要 force-push 或改動其他 repo。若需回退 collector，用同一 release 的完整 collector 目錄，停止執行後先備份私人 state，保持 state 版本相容與退避紀錄，不將它上傳。

## 內容權利

本站提供短摘要及來源導航，不授予第三方原文、圖片或附件再散布權，也不是政府官方網站或法律意見。來源權利由各自權利人保有；未額外替第三方內容授予授權。
