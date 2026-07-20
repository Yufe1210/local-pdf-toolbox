# 發布與驗收紀錄

> 更新日期：2026-07-20
>
> 本文件記錄實際執行結果；產品需求仍以 `requirements.md` 為準。

## 0.1.0 已完成驗證

| 驗收項目 | 結果 | 證據 |
| --- | --- | --- |
| Python 3.13 與 uv 鎖定 | 通過 | `.python-version`、`pyproject.toml`、`uv.lock` |
| 合併順序、頁數、尺寸與方向 | 通過 | `uv run pytest` 及直向／橫向 A4 渲染檢查 |
| 中文與重複檔名 | 通過 | 核心及完整合併互動測試 |
| 空白、損壞、非 PDF、加密及少於兩份 | 通過 | 核心拒絕測試，錯誤不產生部分結果 |
| 首頁與合併介面 | 通過 | 本機瀏覽器檢查首頁、導覽、版本、中文命名與停用狀態 |
| 排序、移除、清除、合併及下載狀態 | 通過 | Streamlit 應用測試以真實 PDF bytes 驗證完整狀態流程 |
| 單一上傳狀態、響應式卡片及拖曳事件 | 通過 | 上傳器重設、唯一 ID、重複中文檔名、純拖曳排序與移除均使用同一 `pdf_items`；本機及外部 Windows 安裝版人工驗收均正常 |
| 第一頁縮圖、旋轉及記憶體保護 | 通過 | PDFium 直向、旋轉與極端長頁測試；220 × 400 像素上限、50 份／500 MB 邊界及成功／失敗路徑資源釋放測試 |
| 只監聽 loopback | 通過 | 原始碼服務實測與啟動器設定測試均為 `127.0.0.1` |
| 啟動器結束子程序 | 通過 | 正常關閉、runtime 清理及子程序終止測試 |
| 更新提示安全 | 通過 | HTTPS、重新導向、版本比較、每日自動檢查、同日手動重新檢查及 GitHub Release 開啟測試；程式不含自動下載或執行流程 |
| 公開 GitHub repository、Release 與更新資訊 | 通過 | `main`、`v0.1.0`、latest GitHub Release、兩個下載資產與 raw `updates/update.json` 均已公開驗證 |
| PyInstaller onedir | 通過 | Python 3.13.14 建置成功；`PYZ-00.toc` 中 15 個必要模組全數存在，PDFium DLL、pypdfium2 授權檔與四個離線拖曳網格前端檔案均存在；外部 Windows 安裝版可正常操作 |
| 安裝版 `--self-test` | 最終 onedir 通過 | 實際執行封裝內首頁與合併頁、建立兩張重複中文檔名 PDF 卡片、載入自訂拖曳網格後端並核對離線前端資源，完成代表性 PDF 驗證、PDFium 縮圖與二頁合併 |
| Inno Setup 單一離線安裝包 | 通過 | 繁體中文 installer 成功編譯，未使用 `external` 或 `download` flags |
| 安裝後不自動啟動 | 通過 | installer 不含 `[Run]`／`postinstall`，仍建立桌面與開始功能表捷徑 |
| 版本與發布設定一致性 | 通過 | Python 3.13.14 與 Streamlit 1.59.1 環境執行 51 項測試全數通過 |

執行指令：

```powershell
uv run python -m pytest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipInstaller
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -ReleaseBuild
```

2026-07-15 實際安裝舊候選檔後，瀏覽器顯示 `ModuleNotFoundError: No module named 'pdf_toolbox.ui'`。原因是 `app.py` 由 Streamlit 動態載入，而舊封裝未完整收集其匯入；僅檢查 `/_stcore/health` 未觸發頁面程式，因此沒有提早發現。下列舊候選檔已判定無效，不得上傳 GitHub Release：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：62,245,509 bytes（約 59.36 MiB）
- 版本：0.1.0.0
- SHA-256：`6f85aab1a884a5172ef28942f38442373fe0bb8bd3e181ec7425b6126567f19d`
- 簽章狀態：`NotSigned`

修正版改用明確必要模組清單，並在 PyInstaller 完成後逐一核對 `PYZ-00.toc`；安裝程式也不再於安裝完成後自動啟動。

先前不含縮圖功能的修正版未簽章候選檔已於 Python 3.13.14 環境完成建置；它已被本次新候選檔取代：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：62,794,809 bytes（約 59.89 MiB）
- onedir 大小：211,774,371 bytes（約 201.96 MiB）
- 版本：0.1.0.0
- SHA-256：`8de14fd8f17d73f69eda2d479732915a420f39ac4970ea9af7d9892ae4b67a48`
- 簽章狀態：`NotSigned`
- 封裝模組核對：`packaging/required_toolbox_modules.txt` 所列 11 個模組全部存在

2026-07-15 含第一頁預覽與舊拖曳元件的候選檔已被 2026-07-17 響應式拖曳網格候選檔取代：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：65,766,246 bytes（約 62.72 MiB）
- onedir 大小：219,748,540 bytes（約 209.57 MiB；3,336 個檔案）
- 版本：0.1.0
- SHA-256：`64380d35597d6a901ecc89203383cc526a7fa4bc94d3f532501190e349286f4f`
- 簽章狀態：`NotSigned`
- 封裝核對：14 個自家模組、`pdfium.dll`、pypdfium2／PDFium 完整 BUILD_LICENSES 與舊第三方拖曳套件授權檔
- 視覺核對：代表性直向紅色頁、橫向藍色頁及第一頁縮圖均清楚，順序、方向與頁面交界正常
- 本機執行證據：加入實際桌面捷徑與互動 GUI 驗收流程後，再次執行 `-ReleaseBuild` 且未略過任何步驟；強化版 `--self-test` 實際執行封裝內首頁、合併頁、兩張卡片與舊拖曳元件後端，封裝後 loopback smoke test 亦通過且只監聽 `127.0.0.1`
- 限制：此候選檔不再代表目前原始碼，不得上傳 GitHub Release

2026-07-17 純拖曳響應式多欄網格候選檔已完成未略過步驟的完整編譯，於 2026-07-19 由使用者完成外部 Windows 人工驗收，並發布為 `v0.1.0`：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：65,743,796 bytes（約 62.70 MiB）
- onedir 大小：219,670,996 bytes（約 209.49 MiB；3,329 個檔案）
- 版本：0.1.0
- SHA-256：`64580daddbb96b06dad5dcb9f86fa17096f08a58f11901d60b573e61488fcb6d`
- 簽章狀態：`NotSigned`
- 封裝核對：15 個自家模組、`pdfium.dll`、pypdfium2／PDFium 完整 BUILD_LICENSES，以及自訂拖曳網格的 HTML、JavaScript、CSS 與 Streamlit protocol 檔案
- 本機 GUI 證據：六份直向／橫向代表性 PDF 於一般瀏覽器顯示第一頁縮圖；預設寬度四欄、640 像素寬度兩欄，跨列拖曳後順序、移除、六頁合併及下載狀態正確
- 本機封裝證據：`-ReleaseBuild` 未略過任何步驟；最終 onedir 的 `--self-test`、拖曳網格資源核對及 loopback smoke test 通過，且服務只監聽 `127.0.0.1`
- 外部 Windows 驗收：離線安裝、安裝後不自動啟動、桌面捷徑、啟動器、瀏覽器介面、PDF 預覽與拖曳、合併下載、更新入口、服務結束、背景程序及解除安裝均正常
- 已接受行為：結束後原瀏覽器分頁未顯示指定的「本機 PDF 工具箱已關閉」文字，但可清楚辨識服務已停止；0.1.0 不為此延後發布
- GitHub Release：<https://github.com/Yufe1210/local-pdf-toolbox/releases/tag/v0.1.0>
- 公開資產：`LocalPDFToolbox-Setup-v0.1.0.exe` 與 `LocalPDFToolbox-Setup-v0.1.0.exe.sha256`
- 發布後核對：從 GitHub 重新下載的安裝程式為 65,743,796 bytes，SHA-256 仍為 `64580daddbb96b06dad5dcb9f86fa17096f08a58f11901d60b573e61488fcb6d`

`build/`、`dist/`、`release/` 與上述安裝包都在 Git ignore 範圍；每次重新建置後雜湊會改變，正式發布應以該次 `.sha256` 檔為準。

## 0.2.0 PDF 轉圖片候選驗證

2026-07-19 已完成目前原始碼的本機功能、視覺、瀏覽器及未簽章候選打包驗證；2026-07-20 使用者回報 0.2.0 新增功能操作正常，且 `verify-release.ps1` 與 `verify-upgrade.ps1` 均通過。驗收涵蓋 0.2.0 完整安裝生命週期及 0.1.0 → 0.2.0 原地覆蓋升級；本次未記錄外部電腦的確切 Windows 版本。

- 自動化：加入升級驗證腳本測試後共 74 項；2026-07-20 發布資訊更新後重新執行 `uv run python -m pytest`，74 項全數通過。當天較早一次執行曾有 4 項既有 Streamlit UI／自我檢查測試因本機 Application Control 暫時阻擋未簽章 `pyarrow` DLL 而無法載入，後續重跑已恢復正常；間歇性政策風險仍保留於本文件的主機限制。
- 核心：一份及多份 PDF、PNG、JPEG、150／200／300 DPI、JPEG 品質、子資料夾與 ZIP 根目錄結構、中文及重複名稱、至少三位頁碼、ZIP 檔名、整批先驗證、加密／損壞／非 PDF／空白拒絕及單頁像素上限均有測試。
- 視覺：以有文字、色塊、斜線及圓形的直向、橫向、90° 旋轉及第二份方形 PDF 實際轉換；PNG 與 JPEG 的內容、方向、裁切、文字邊緣及頁面尺寸正常，並以 Poppler 交叉核對來源頁。
- 瀏覽器：實際加入兩份共四頁 PDF，第一頁預覽、響應式雙欄卡片、頁數統計、轉換及完成下載狀態正確，瀏覽器主控台無錯誤。
- 封裝：`.\scripts\build.ps1 -ReleaseBuild` 未使用略過參數；72 項測試、18 個自家模組、PDFium DLL、第三方授權、自訂拖曳網格、安裝版 `--self-test`、loopback smoke test 及 Inno Setup 全部通過。
- 候選安裝程式：`本機PDF工具箱-安裝程式.exe`，65,760,417 bytes，產品版本 0.2.0，SHA-256 `d9b0adb1029632a9851590e10fbe295861a465cd144103d34644cafc5af4e789`，簽章狀態 `NotSigned`。
- 公開 `updates/update.json` 已切換至 0.2.0，並指向 GitHub Releases 的 `latest` 頁面。
- 單版驗收：使用者回報 `verify-release.ps1 -ExpectedVersion 0.2.0 -AllowUnsignedDevelopmentBuild -InteractiveGuiCheck` 通過。
- 升級驗收：使用者回報 `verify-upgrade.ps1 -AllowUnsignedDevelopmentBuild` 通過，包含兩版安裝程式與 SHA-256 核對、0.1.0 乾淨安裝、0.2.0 原地覆蓋、兩版 `--self-test`、同一安裝位置、單一解除安裝紀錄及最終清理。

後續建置已改採版本化輸出：正式候選為 `LocalPDFToolbox-Setup-v版本.exe`，一般測試建置為 `LocalPDFToolbox-Setup-v版本-unsigned-test.exe`，SHA-256 清單使用相同檔名再加 `.sha256`。上方固定中文檔名保留為歷史建置紀錄；未來不同版本不再互相覆蓋。

版本化輸出已用完整 `-ReleaseBuild` 實測：新產生的 `LocalPDFToolbox-Setup-v0.2.0.exe` 為 65,764,188 bytes，產品版本 0.2.0，SHA-256 `a66e1296297034a75a1271f247bf0bc5468ace396bb970d460e67de2877e8acb`；建置前既有的固定中文檔名候選檔仍維持 SHA-256 `d9b0adb1029632a9851590e10fbe295861a465cd144103d34644cafc5af4e789`，修改時間與內容均未改變。

0.2.0 已發布為一般 GitHub Release：

- tag：`v0.2.0`，指向 `f8313fb67a9f3485884ec4ebd3352b234e93b31a`。
- Release：<https://github.com/Yufe1210/local-pdf-toolbox/releases/tag/v0.2.0>。
- 公開資產：`LocalPDFToolbox-Setup-v0.2.0.exe` 與 `LocalPDFToolbox-Setup-v0.2.0.exe.sha256`。
- GitHub 資產狀態：兩個檔案均為 `uploaded`；安裝程式大小為 65,764,188 bytes，GitHub SHA-256 digest 為 `a66e1296297034a75a1271f247bf0bc5468ace396bb970d460e67de2877e8acb`，與本機候選檔一致。

## 已接受風險與後續驗證

| 驗收項目 | 狀態 | 尚缺條件 |
| --- | --- | --- |
| 正式 Authenticode 簽章 | 延後 | 0.1.0 已決定採未簽章公開測試版；未來恢復自動更新或擴大發布前再取得 |
| HTTPS 更新來源 | 已配置 | 公開 repository 的 `updates/update.json` 與 GitHub Releases |
| 最新候選檔封裝後 smoke test | 通過 | 0.2.0 完整建置未使用略過參數；最終 onedir 的新功能 `--self-test`、健康檢查與 loopback 監聽通過 |
| 無 Python 電腦離線安裝 | 通過 | 使用者回報外部 Windows 環境的安裝與日常操作皆正常 |
| 捷徑雙擊、GUI、拖曳、結束狀態及無背景程序 | 通過 | 桌面捷徑啟動、PDF 預覽與跨列拖曳、合併下載、啟動器結束及背景程序檢查正常；瀏覽器可辨識服務已停止，不要求指定關閉文字 |
| 解除安裝與資料清理 | 通過 | 使用者完成解除安裝檢查，未回報異常 |
| Windows 10／11 x64 相容性 | 部分確認 | 外部 Windows 驗收通過；本次回報未記錄確切 Windows 版本，未宣稱 Windows 10 與 11 已各自驗收 |
| 0.2.0 無 Python 電腦離線安裝與 GUI | 通過 | 使用者回報 `verify-release.ps1` 完整驗收通過 |
| 0.1.0 更新至 0.2.0 | 通過 | 使用者回報 `verify-upgrade.ps1` 原地覆蓋升級及清理通過；公開 Release 與下載資產已建立 |

## 目前主機限制

本機 Windows Code Integrity 原則會阻擋新產生的未簽章應用程式。事件記錄 `Microsoft-Windows-CodeIntegrity/Operational` 中可見事件 3033 與 3077，指出 `本機PDF工具箱.exe` 未達 Enterprise signing level，政策 ID 為 `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`。

實測顯示此政策對重新建置後的不同未簽章雜湊可能有不同結果：一組 onedir 通過自我檢查及服務 smoke test，中間建置曾在 `Start-Process` 被 Application Control 封鎖，最終 onedir 重試後又通過。因此本機成功不能視為其他電腦也可執行，建置腳本仍會明確警告未簽章風險；是否可發布改由其他乾淨 Windows 電腦的完整安裝、啟動、合併及解除安裝驗收決定。
