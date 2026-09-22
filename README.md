# 🗂️ DropShelf

> 專為 Windows 打造的輕量桌面拖曳暫存置物架（macOS Dropover / Yoink 最佳替代方案）

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6-41CD52.svg)](https://wiki.qt.io/Qt_for_Python)
[![Platform](https://img.shields.io/badge/Platform-Windows_x64-0078D6.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Personal_Use_Only-orange.svg)](LICENSE)

**DropShelf** 讓你在 Windows 上進行跨資料夾、跨應用程式移動檔案時不再手忙腳亂。當你抓住檔案並輕微晃動滑鼠，置物架便會自動浮現在游標旁，讓你暫存檔案，隨後拖入任何目的地。

---

## ✨ 核心特色

- 🎯 **晃動即召喚 (Shake to Summon)**：按住檔案並左右晃動滑鼠游標，置物架立即浮現於手邊。
- ⌨️ **全域快捷鍵**：隨時按下 `Ctrl + ~` 快速開啟或隱藏置物架。
- 📦 **多檔案集中暫存**：支援多次收集不同路徑的檔案，再一口氣拖曳釋放至目標資料夾。
- ✉️ **Outlook 附件一鍵附加**：右鍵直接將選取檔案自動掛載到正在編輯的 Outlook 郵件中。
- 🖼️ **影像快速處理**：內建圖片批次縮小 50%、轉 JPG、轉 PNG 格式。
- 🗜️ **一鍵打包壓縮**：快速將置物架內的所有檔案直接壓縮為 `.zip`。
- 🖥️ **系統托盤常駐**：最小化至右下角系統匣，記憶體佔用極低。

---

## 🚀 快速開始

### 環境需求
- **作業系統**：Windows 10 / 11（**必須為 64 位元架構**）
- **Python**：Python 3.10 ~ 3.13（64-bit）

### 1. 安裝步驟

```powershell
# 複製專案庫
git clone https://github.com/ais7896-hue/DropShelf.git
cd DropShelf

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
DropShelf/
├── main.py              # 主程式進入點
├── dropshelf/           # 核心模組套件
│   ├── utils.py         # 跨平臺資源載入與相容性工具
│   ├── config.py        # 設定檔管理器 (ConfigManager)
│   ├── input_monitor.py # 全域滑鼠晃動與鍵盤熱鍵監聽
│   └── ui/              # 使用者介面模組
│       ├── hotkey_dialog.py # 熱鍵錄製與偏好設定面板
│       ├── shelf_list.py    # 置物架檔案清單與右鍵動作
│       ├── shelf_widget.py  # 浮動置物架主視窗
│       └── shelf_manager.py # 托盤管理員與資料夾監控
├── icon.ico             # 應用程式圖示
├── config.json          # 本機偏好設定
└── DropShelf.spec       # PyInstaller 打包規格檔
```

---

## 🎮 操作指南

| 操作 | 動作 |
| :--- | :--- |
| **召喚置物架** | 按住檔案並**左右輕微晃動**游標，或按下 `Ctrl + ~` |
| **偏好設定** | 點擊置物架頂部的「⚙️」按鈕，或右下角系統匣選單「⚙️ 偏好設定」 |
| **暫存檔案** | 將任何檔案、圖片直接拖入置物架視窗內 |
| **釋放檔案** | 從置物架選取檔案，直接拖曳到檔案總管、桌面或其他程式 |
| **右鍵選單** | 對置物架內的檔案點擊右鍵：可開啟檔案所在目錄、複製路徑、打包 ZIP、轉換圖片或附加至 Outlook |
| **隱藏置物架** | 點擊置物架右上角關閉按鈕，或透過右下角系統匣圖示管理 |

---

## 🛠️ 打包為獨立執行檔 (.exe)

使用 PyInstaller 進行打包（無主控台視窗 + 嵌入圖示）：

```powershell
# 方式一：直接透過專案 Spec 檔打包
pyinstaller DropShelf.spec

# 方式二：單行指令打包
pyinstaller --noconsole --onefile --icon=icon.ico main.py
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

