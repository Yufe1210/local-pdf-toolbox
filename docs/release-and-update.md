# 發布、安裝與更新策略

## 打包與安裝

PyInstaller 負責把啟動器、Python 解譯器、Streamlit、pypdf及應用程式模組整理成 `onedir`。Inno Setup 再把整個資料夾壓縮成單一安裝程式。

```mermaid
flowchart LR
    Source["原始碼與 uv.lock"] --> Tests["測試"]
    Tests --> PyInstaller["PyInstaller onedir"]
    PyInstaller --> Smoke["打包後 smoke test"]
    Smoke --> Inno["Inno Setup"]
    Inno --> Installer["本機PDF工具箱-安裝程式.exe"]
```

安裝程式預設包含所有執行所需內容，不使用 Inno Setup 的 `external` 或 `download` 模式。因此使用者安裝及日常使用不需網路，也不需另外安裝 Python。

安裝與解除安裝精靈使用專案內固定版本的 Inno Setup 官方繁體中文翻譯 `packaging/languages/ChineseTraditional.isl`，避免建置電腦是否額外安裝語言檔影響結果。更新翻譯時需以 Inno Setup 官方翻譯來源為準並重新編譯驗證。

發行版的更新來源由 `update-config.json` 提供。Repository 內的預設值保持空白，避免開發版連線到不存在或未受控的服務；正式建置必須注入實際 HTTPS 來源，並維持 `require_signed_updates: true`。

建置產物 `build/`、`dist/`、`release/` 及安裝程式不得提交 Git；正式發布的安裝程式應放在受控的發布平台。

### Windows 建置指令

開發用未簽章安裝包：

```powershell
.\scripts\build.ps1
```

腳本會依序執行 `uv sync`、`pytest`、PyInstaller、封裝後本機服務 smoke test、Inno Setup，最後在 `release/` 產生安裝程式與 UTF-8 格式的 SHA-256 清單。

正式建置必須同時提供 HTTPS 更新資訊網址及安裝在 Windows 憑證存放區內的程式碼簽章憑證指紋：

```powershell
.\scripts\build.ps1 `
  -ReleaseBuild `
  -UpdateFeedUrl "https://example.com/pdf-toolbox/update.json" `
  -CertificateThumbprint "憑證指紋"
```

正式建置會簽署應用程式與安裝程式，且不可略過封裝後 smoke test。`-SkipPackagedSmokeTest` 只供受到 Windows 應用程式控制政策限制的未簽章開發環境檢查建置內容；以此方式產生的檔案不得發布。

## 版本策略

- 使用 `MAJOR.MINOR.PATCH`。
- 0.1.0：合併 PDF、離線安裝與更新基礎架構。
- 0.2.0：新增拆分 PDF。
- 修正但不新增功能時增加 PATCH。
- 新增向後相容功能時增加 MINOR。
- 發生不相容的設定、資料或更新協議變更時增加 MAJOR。
- 版本需在專案設定、執行檔資訊、Inno Setup 與更新資訊中保持一致。
- Inno Setup `AppId` 一旦首次發布就永久固定，讓新版能覆蓋安裝舊版。

## 更新流程

更新能力必須在第一個交付版本中存在，否則已安裝的舊版無法自行取得更新提示。

1. 啟動器每日最多檢查一次 HTTPS 版本資訊。
2. 比較目前版本與最新版本。
3. 顯示版本、更新說明、稍後提醒與立即更新。
4. 使用者同意後下載新版完整安裝程式到暫存目錄。
5. 驗證 Authenticode 簽章及檔案雜湊。
6. 關閉目前程式，執行新版安裝程式覆蓋原安裝。
7. 安裝精靈完成後重新啟動；啟動器會在後續啟動時清除先前下載的完整安裝檔與未完成檔案。

版本資訊至少包含：

```json
{
  "version": "0.2.0",
  "download_url": "https://example.com/releases/pdf-toolbox-0.2.0.exe",
  "sha256": "...",
  "release_notes": [
    "新增拆分 PDF",
    "改善大型 PDF 處理"
  ]
}
```

雜湊必須透過受保護的 HTTPS 來源提供；正式發布仍應以程式碼簽章作為主要信任依據。更新檢查無網路、逾時或伺服器錯誤時應靜默略過，不能阻止既有功能啟動。更新來源與下載位置若重新導向到非 HTTPS 的外部網址，必須拒絕更新；僅測試用 loopback 網址例外。

## 發布檢查清單

- 更新版本與發布說明。
- 同步更新 `docs/` 中的需求、狀態及發布資訊。
- 執行全部測試與 PDF 渲染檢查。
- 建立乾淨的 PyInstaller onedir。
- 測試打包後啟動、PDF 操作與完整結束。
- 建立並簽署 Inno Setup 安裝程式。
- 在無 Python 的乾淨 Windows 環境驗證安裝與解除安裝。
- 產生並驗證 SHA-256。
- 上傳安裝程式，再更新版本資訊；不得先發布指向不存在安裝程式的版本資訊。
- 從上一個正式版本測試完整更新流程。
