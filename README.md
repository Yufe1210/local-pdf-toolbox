# 本機 PDF 工具箱

這是一個以 Streamlit 與 pypdf 製作的本機 PDF 工具箱。目前可以調整多份 PDF 的順序、合併並下載結果；所有 PDF 都只在程式記憶體中處理。

目前完成合併 PDF、工具箱架構、桌面啟動器及離線安裝建置腳本。0.1.0 採未簽章公開測試版，程式會提示新版並開啟 GitHub Releases，由使用者手動下載更新；發布前仍需乾淨 Windows 驗收。拆分 PDF 預計在 0.2.0 開發。詳細資訊請參閱 [專案文件](docs/README.md)。

## 環境需求

- [uv](https://docs.astral.sh/uv/)
- 專案指定的 Python 3.13 會由 uv 管理

## 安裝與啟動

```powershell
uv sync
uv run python -m streamlit run app.py
```

啟動後，Streamlit 會顯示本機網址。依序上傳 PDF、用箭頭調整順序、輸入輸出檔名，再按下「合併 PDF」。

## 測試

```powershell
uv run python -m pytest
```

## 隱私與限制

- PDF 不會傳送至外部服務，也不會永久保存。
- 第一版不支援密碼保護 PDF、壓縮、頁面範圍、附件或浮水印。
- 合併主要保留頁面視覺內容，不承諾保留書籤、互動表單、數位簽章或文件中繼資料。
- Streamlit 預設限制單一上傳檔案大小；可依其設定文件調整 `server.maxUploadSize`。
