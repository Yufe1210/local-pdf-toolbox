# 0.1.0 驗收紀錄

> 更新日期：2026-07-15
>
> 本文件記錄實際執行結果；產品需求仍以 `requirements.md` 為準。

## 本機已完成驗證

| 驗收項目 | 結果 | 證據 |
| --- | --- | --- |
| Python 3.13 與 uv 鎖定 | 通過 | `.python-version`、`pyproject.toml`、`uv.lock` |
| 合併順序、頁數、尺寸與方向 | 通過 | `uv run pytest` 及直向／橫向 A4 渲染檢查 |
| 中文與重複檔名 | 通過 | 核心及完整合併互動測試 |
| 空白、損壞、非 PDF、加密及少於兩份 | 通過 | 核心拒絕測試，錯誤不產生部分結果 |
| 首頁與合併介面 | 通過 | 本機瀏覽器檢查首頁、導覽、版本、中文命名與停用狀態 |
| 排序、移除、清除、合併及下載狀態 | 通過 | Streamlit 應用測試以真實 PDF bytes 驗證完整狀態流程 |
| 只監聽 loopback | 通過 | 原始碼服務實測與啟動器設定測試均為 `127.0.0.1` |
| 啟動器結束子程序 | 通過 | 正常關閉、runtime 清理及子程序終止測試 |
| 更新提示安全 | 通過 | HTTPS、重新導向、手動 feed、GitHub Release 開啟及舊有下載驗證元件測試 |
| 公開 GitHub repository 與更新資訊 | 通過 | `Yufe1210/local-pdf-toolbox` 為 Public、`main` 已推送，raw `updates/update.json` 回傳 HTTP 200 |
| PyInstaller onedir | 建置通過、GUI 待驗收 | Python 3.13.14 建置成功；`PYZ-00.toc` 中 11 個必要模組全數存在，實際 GUI 仍待其他電腦驗收 |
| Inno Setup 單一離線安裝包 | 通過 | 繁體中文 installer 成功編譯，未使用 `external` 或 `download` flags |
| 安裝後不自動啟動 | 通過 | installer 不含 `[Run]`／`postinstall`，仍建立桌面與開始功能表捷徑 |
| 版本與發布設定一致性 | 通過 | Python 3.13.14 環境執行 34 項測試全數通過 |

執行指令：

```powershell
uv run python -m pytest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -ReleaseBuild -SkipPackagedSmokeTest
```

2026-07-15 實際安裝舊候選檔後，瀏覽器顯示 `ModuleNotFoundError: No module named 'pdf_toolbox.ui'`。原因是 `app.py` 由 Streamlit 動態載入，而舊封裝未完整收集其匯入；僅檢查 `/_stcore/health` 未觸發頁面程式，因此沒有提早發現。下列舊候選檔已判定無效，不得上傳 GitHub Release：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：62,245,509 bytes（約 59.36 MiB）
- 版本：0.1.0.0
- SHA-256：`6f85aab1a884a5172ef28942f38442373fe0bb8bd3e181ec7425b6126567f19d`
- 簽章狀態：`NotSigned`

修正版改用明確必要模組清單，並在 PyInstaller 完成後逐一核對 `PYZ-00.toc`；安裝程式也不再於安裝完成後自動啟動。

修正版未簽章候選檔已於 Python 3.13.14 環境完成建置；之後仍需在其他乾淨 Windows 電腦實際開啟首頁與合併頁：

- 檔名：`本機PDF工具箱-安裝程式.exe`
- 大小：62,794,809 bytes（約 59.89 MiB）
- onedir 大小：211,774,371 bytes（約 201.96 MiB）
- 版本：0.1.0.0
- SHA-256：`8de14fd8f17d73f69eda2d479732915a420f39ac4970ea9af7d9892ae4b67a48`
- 簽章狀態：`NotSigned`
- 封裝模組核對：`packaging/required_toolbox_modules.txt` 所列 11 個模組全部存在

`build/`、`dist/`、`release/` 與上述安裝包都在 Git ignore 範圍；每次重新建置後雜湊會改變，正式發布應以該次 `.sha256` 檔為準。

## 正式發布前尚待驗證

| 驗收項目 | 狀態 | 尚缺條件 |
| --- | --- | --- |
| 正式 Authenticode 簽章 | 延後 | 0.1.0 已決定採未簽章公開測試版；未來恢復自動更新或擴大發布前再取得 |
| HTTPS 更新來源 | 已配置 | 公開 repository 的 `updates/update.json` 與 GitHub Releases |
| 未簽章封裝後 smoke test | 待處理 | 目前主機的 Smart App Control 會封鎖，需移至其他乾淨 Windows 電腦 |
| 無 Python 電腦離線安裝 | 待處理 | 目前主機未安裝 Windows Sandbox，也沒有可用的既存 Windows VM |
| 捷徑雙擊、GUI、關閉及無背景程序 | 待處理 | 需在未簽章安裝後以允許旗標執行 `scripts/verify-release.ps1` |
| 解除安裝與資料清理 | 待處理 | 需在同一乾淨 Windows 環境完成驗收腳本 |
| Windows 10／11 x64 相容性 | 待處理 | 至少各使用一個目標版本驗收 |
| 0.1.0 更新至後續版本 | 待處理 | 待下一個版本驗證提示、GitHub 下載與手動覆蓋安裝 |

## 目前主機限制

本機 Windows Code Integrity 原則會阻擋新產生的未簽章應用程式。事件記錄 `Microsoft-Windows-CodeIntegrity/Operational` 中可見事件 3033 與 3077，指出 `本機PDF工具箱.exe` 未達 Enterprise signing level，政策 ID 為 `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`。

因此本機只能略過「未簽章封裝執行」來產生候選檔。建置腳本會明確警告未簽章風險；是否可發布改由其他乾淨 Windows 電腦的完整安裝、啟動、合併及解除安裝驗收決定。
