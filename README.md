# 🗂️ KyteShelf

> 專為 Windows 打造的輕量桌面拖曳暫存置物架（macOS Dropover / Yoink 最佳替代方案）

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6-41CD52.svg)](https://wiki.qt.io/Qt_for_Python)
[![Platform](https://img.shields.io/badge/Platform-Windows_x64-0078D6.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Personal_Use_Only-orange.svg)](LICENSE)

**KyteShelf** 讓你在 Windows 上進行跨資料夾、跨應用程式移動檔案時不再手忙腳亂。當你抓住檔案並輕微晃動滑鼠，置物架便會自動浮現在游標旁，讓你暫存檔案，隨後拖入任何目的地。

---

## ✨ 核心特色

- 🎯 **晃動即召喚 (Shake to Summon)**：按住檔案並左右晃動滑鼠游標，置物架立即浮現於手邊。
- 📋 **剪貼簿快速入架**：隨時按下 `Ctrl + V` 或點擊「貼上」，智慧解析檔案、截圖點陣圖、網頁圖片 URL 與文字便箋。
- 🔍 **縮圖懸停即時預覽**：滑鼠移至圖片項目即刻彈出高畫質縮圖與像素尺寸，大圖載入小於 10ms 零延遲。
- 🏷️ **多置物架自訂命名**：支援新增多個置物架，雙擊標題或右鍵即可自訂專屬名稱，重啟自動完整保留。
- 📝 **智慧自黏標籤 (Sticky Notes)**：拖入或貼上文字網址自動轉化為便箋，支援雙擊獨立編輯與跨視窗拖出純文字。
- 🗑️ **單項目刪除與鍵盤支援**：項目懸浮圓形 `✕` 按鈕單獨刪除，支援 `Delete` / `Backspace` 與 `Ctrl + A` 快捷鍵。
- 🎨 **現代極簡 UI 與空狀態引導**：全新 Header 降噪、精美虛線 Drop Zone 卡片與底部快捷模式工具列。
- ⌨️ **全域快捷鍵**：隨時按下 `Ctrl + ~` 快速開啟或隱藏置物架。
- 📦 **多檔案集中暫存**：支援多次收集不同路徑的檔案，再一口氣拖曳釋放至目標資料夾。
- ✉️ **Outlook 附件一鍵附加**：右鍵直接將選取檔案自動掛載到正在編輯的 Outlook 郵件中。
- 🖼️ **影像快速處理**：內建圖片批次縮小 50%、轉 JPG、轉 PNG 格式。
- 🗜️ **一鍵打包壓縮**：快速將置物架內的所有檔案直接壓縮為 `.zip`。
- 🖥️ **系統托盤導航管理**：右下角系統匣動態列出所有置物架名稱與狀態，隨時一鍵置頂跳轉。

---

## 🚀 快速開始

### 環境需求
- **作業系統**：Windows 10 / 11（**必須為 64 位元架構**）
- **Python**：Python 3.10 ~ 3.13（64-bit）

### 1. 安裝步驟

```powershell
# 複製專案庫
git clone https://github.com/ais7896-hue/KyteShelf.git
cd KyteShelf

# 建立 64 位元虛擬環境
py -3-64 -m venv .venv

# 啟用虛擬環境
.\.venv\Scripts\Activate.ps1

# 安裝相依套件
pip install -r requirements.txt
```

### 2. 啟動程式

```powershell
python main.py
```

---

## 📁 專案架構

```text
KyteShelf/
├── main.py              # 主程式進入點
├── kyteshelf/           # 核心模組套件
│   ├── utils.py         # 跨平臺資源載入與相容性工具
│   ├── config.py        # 設定檔管理器 (ConfigManager)
│   ├── input_monitor.py # 全域滑鼠晃動與鍵盤熱鍵監聽
│   ├── session.py       # 工作階段管理員 (SessionManager)
│   └── ui/              # 使用者介面模組
│       ├── hotkey_dialog.py # 熱鍵錄製與偏好設定面板
│       ├── shelf_list.py    # 置物架檔案清單與右鍵動作
│       ├── shelf_widget.py  # 浮動置物架主視窗
│       ├── shelf_manager.py # 托盤管理員與資料夾監控
│       └── sticky_note.py   # 自黏便箋視窗
├── icon.ico             # 應用程式圖示
├── config.json          # 本機偏好設定
└── setup.iss            # Inno Setup 打包腳本
```

---

## 🎮 操作指南

| 操作 | 動作 |
| :--- | :--- |
| **召喚置物架** | 按住檔案並**左右輕微晃動**游標，或按下 `Ctrl + ~` |
| **置物架改名** | **按兩下**置物架標題列文字，或在標題／空白處按右鍵選擇「✏️ 重新命名」 |
| **貼上剪貼簿** | 按下 `Ctrl + V` 或點擊底部「貼上」，自動解析檔案、截圖、圖片網址或文字便箋 |
| **圖片縮圖預覽** | 滑鼠移動至圖片項目上方，即刻彈出高畫質縮圖與影像尺寸 Tooltip |
| **單獨/批次刪除** | 滑過項目點擊右側 `✕` 按鈕，或選取後按鍵盤 `Delete` / `Backspace` 鍵刪除 |
| **偏好設定** | 點擊置物架頂部的「⚙」按鈕，或右下角系統匣選單「⚙️ 偏好設定」 |
| **暫存檔案/文字** | 將任何檔案、圖片、文字或網址直接拖入置物架視窗內（文字自動變為便箋） |
| **釋放檔案** | 從置物架選取檔案，直接拖曳到檔案總管、桌面或其他程式 |
| **自黏便箋編輯** | 雙擊自黏便箋項目開啟獨立編輯視窗，拖出可直接貼入純文字至任一文字框 |
| **右鍵選單** | 對檔案點擊右鍵：開啟目錄、複製路徑、打包 ZIP、批次圖片處理或附加至 Outlook |
| **托盤切換/管理** | 右鍵點擊系統托盤圖示，進入「📑 置物架清單」可查看所有名稱並快速跳轉或改名 |
| **隱藏置物架** | 點擊置物架右上角關閉按鈕，或按鍵盤 `Esc` 取消顯示 |

---

## 🛠️ 打包為獨立執行檔 (.exe)

使用 PyInstaller 進行打包（無主控台視窗 + 嵌入圖示）：

```powershell
python -m PyInstaller --noconsole --onefile --icon=icon.ico --name=KyteShelf main.py
```

> 搭配 Inno Setup 腳本（`setup.iss`）可進一步封裝成標準安裝程式精靈。

---

## 📦 相依元件

- [PySide6](https://pypi.org/project/PySide6/) - Qt 現代化 GUI 介面框架
- [pynput](https://pypi.org/project/pynput/) - 全域滑鼠晃動與全域鍵盤監聽
- [pywin32](https://pypi.org/project/pywin32/) - Windows COM 介面串接（Outlook 自動附加）
- [pyinstaller](https://pypi.org/project/pyinstaller/) - 執行檔打包發佈

---

## 📝 更新履歷

詳細版本演進紀錄請參閱 [CHANGELOG.md](CHANGELOG.md)。

---

## 📄 授權條款

本專案原始碼僅供個人學習與檢閱用途，嚴格禁止未經授權的商業用途、轉售或重新打包發布。商業使用或官方封裝成品請洽原作者購買正式授權，詳見 [LICENSE](LICENSE)。

