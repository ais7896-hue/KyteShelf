; ==========================================
; 基本資訊與安裝設定
; ==========================================
[Setup]
; 應用程式名稱與版本
AppName=DropShelf 置物架
AppVersion=1.0.0
AppPublisher=Personal Studio
; 預設安裝目錄：{autopf} 會自動根據系統判定 Program Files 或使用者目錄
DefaultDirName={autopf}\DropShelf
; 開始功能表資料夾名稱
DefaultGroupName=DropShelf
; 安裝檔輸出目錄與檔名
OutputDir=Output
OutputBaseFilename=DropShelf_Setup_v1.0
; 壓縮方式（lzma2 壓縮率極高）
Compression=lzma2/ultra64
SolidCompression=yes
; 安裝檔與反安裝的圖示
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\DropShelf.exe
; 關閉必須管理員權限的強制要求（允許一般使用者目錄安裝，體驗更佳）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
[Languages]
Name: "chinesetrad"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
; ==========================================
; 安裝過程中讓使用者勾選的項目
; ==========================================
[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "額外圖示:"
Name: "startup"; Description: "開機時自動啟動置物架"; GroupDescription: "開機設定:"

; ==========================================
; 要打包進安裝包的檔案
; ==========================================
[Files]
; 來源指向 PyInstaller 產生的 dist\DropShelf 目錄
; 請確保本 .iss 檔案位於與 dist 資料夾相同的專案根目錄下
Source: "dist\DropShelf\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ==========================================
; 捷徑建立設定
; ==========================================
[Icons]
; 開始功能表捷徑
Name: "{group}\DropShelf"; Filename: "{app}\DropShelf.exe"
Name: "{group}\解除安裝 DropShelf"; Filename: "{uninstallexe}"
; 桌面捷徑（由使用者勾選決定）
Name: "{autodesktop}\DropShelf"; Filename: "{app}\DropShelf.exe"; Tasks: desktopicon
; 開機自動啟動捷徑（由使用者勾選決定，放入使用者的 Startup 目錄）
Name: "{userstartup}\DropShelf"; Filename: "{app}\DropShelf.exe"; Tasks: startup

; ==========================================
; 安裝完成後的動作
; ==========================================
[Run]
; 提示是否立即啟動程式
Filename: "{app}\DropShelf.exe"; Description: "立即啟動 DropShelf"; Flags: nowait postinstall skipifsilent