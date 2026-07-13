# 0.1.0 驗收紀錄

> 更新日期：2026-07-13
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
| 更新下載安全 | 通過 | HTTPS、重新導向、大小、SHA-256、簽章入口及殘檔清理測試 |
| PyInstaller onedir | 通過 | Python 3.13、Streamlit、pypdf 與應用資源成功封裝 |
| Inno Setup 單一離線安裝包 | 通過 | 繁體中文 installer 成功編譯，未使用 `external` 或 `download` flags |
| 版本與發布設定一致性 | 通過 | 30 項測試全數通過 |

執行指令：

```powershell
uv run pytest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipPackagedSmokeTest
```

最近一次未簽章測試產物僅供本機建置核對，不得發布：

- 檔名：`本機PDF工具箱-安裝程式-未簽章測試版.exe`
- 大小：62,244,427 bytes（約 59.36 MiB）
- 版本：0.1.0.0
- SHA-256：`901d8bb345adaac98e3b5158eb2d3b31ca73833900edca8f1aad32d248a4d604`
- 簽章狀態：`NotSigned`

`build/`、`dist/`、`release/` 與上述安裝包都在 Git ignore 範圍；每次重新建置後雜湊會改變，正式發布應以該次 `.sha256` 檔為準。

## 正式發布前尚待驗證

| 驗收項目 | 狀態 | 尚缺條件 |
| --- | --- | --- |
| 正式 Authenticode 簽章 | 待處理 | 需取得含私密金鑰的正式程式碼簽章憑證 |
| HTTPS 更新來源 | 待處理 | 需提供正式版本資訊與安裝包託管網址 |
| 簽章版封裝後 smoke test | 待處理 | 需以正式憑證執行不可略過的 `build.ps1 -ReleaseBuild` |
| 無 Python 電腦離線安裝 | 待處理 | 目前主機未安裝 Windows Sandbox，也沒有可用的既存 Windows VM |
| 捷徑雙擊、GUI、關閉及無背景程序 | 待處理 | 需在簽章版安裝後執行 `scripts/verify-release.ps1` |
| 解除安裝與資料清理 | 待處理 | 需在同一乾淨 Windows 環境完成驗收腳本 |
| Windows 10／11 x64 相容性 | 待處理 | 至少各使用一個目標版本驗收 |
| 0.1.0 更新至後續版本 | 待處理 | 待正式更新來源及下一個可安裝版本 |

## 目前主機限制

本機 Windows Code Integrity 原則會阻擋新產生的未簽章應用程式。事件記錄 `Microsoft-Windows-CodeIntegrity/Operational` 中可見事件 3033 與 3077，指出 `本機PDF工具箱.exe` 未達 Enterprise signing level，政策 ID 為 `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`。

因此本機只略過「未簽章封裝執行」這一步來檢查建置內容。正式建置腳本禁止在 `-ReleaseBuild` 時使用 `-SkipPackagedSmokeTest`，避免受限的開發結果被誤當成可發布版本。
