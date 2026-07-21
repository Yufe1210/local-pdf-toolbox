# 本機 PDF 工具箱

這是一個以 Streamlit、pypdf 與 pypdfium2 製作的本機 PDF 工具箱。目前提供合併 PDF，以及將一份或多份 PDF 的每一頁轉成 PNG／JPEG 並以 ZIP 下載；第一頁預覽、拖曳卡片與 PDF 處理都只在程式記憶體中完成。

目前已發布 [0.2.0 未簽章公開測試版](https://github.com/Yufe1210/local-pdf-toolbox/releases/tag/v0.2.0)，包含合併 PDF 與多 PDF 逐頁轉 PNG／JPEG。程式會提示已發布的新版並開啟 GitHub Releases，由使用者手動下載更新。詳細資訊請參閱 [專案文件](docs/README.md)。

## 環境需求

- [uv](https://docs.astral.sh/uv/)
- 專案指定的 Python 3.13 會由 uv 管理

## 安裝與啟動

```powershell
uv sync
uv run python -m streamlit run app.py
```

啟動後，Streamlit 會顯示本機網址。加入 PDF 後，以卡片縮圖確認文件，直接用滑鼠拖曳卡片調整順序、輸入輸出檔名，再按下「合併 PDF」。卡片會隨視窗寬度自動分欄，檔案較多時在卡片區內捲動。

## 測試

```powershell
uv run python -m pytest
```

## 隱私與限制

- PDF 不會傳送至外部服務，也不會永久保存。
- 合併頁最多保留 50 份、總計 500 MB；縮圖逐份低解析度產生，不寫入磁碟。
- 需要輸入非空密碼的 PDF 仍不支援；使用空密碼且可直接開啟的權限保護 PDF 可正常處理。
- 合併主要保留頁面視覺內容，不承諾保留書籤、互動表單、數位簽章或文件中繼資料。
- Streamlit 預設限制單一上傳檔案大小；可依其設定文件調整 `server.maxUploadSize`。
