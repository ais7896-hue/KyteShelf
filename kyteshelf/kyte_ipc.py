"""
KyteShelf - KyteView IPC 跨進程預覽通訊
- 優先使用 Qt 原生 QLocalSocket 通訊 (連線超時 25ms，極致低延遲非阻塞)
- 協議對齊 KyteView Single Instance: 'PREVIEW:<path>\\n'
- 若 KyteView 尚未啟動，自動嘗試在背景喚起 KyteView 並直接預覽
- 支援選取切換時非同步同步預覽: 'PREVIEW_UPDATE:<path>\\n'
"""
import os
import sys
import shutil
import subprocess
import threading
from pathlib import Path
from PySide6.QtNetwork import QLocalSocket

IPC_SERVER_NAME = "KyteView_SingleInstance_IPC"


def _find_kyteview_launcher() -> tuple:
    """嘗試尋找本機 KyteView 的啟動途徑 (執行檔或原始碼)"""
    # 1. 檢查 PATH 是否有 KyteView
    which_exe = shutil.which("KyteView.exe") or shutil.which("KyteView")
    if which_exe and os.path.exists(which_exe):
        return (str(which_exe), [])

    # 2. 檢查常見安裝路徑 (如 LocalAppData)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        cand_installed = Path(local_app_data) / "Programs" / "KyteView" / "KyteView.exe"
        if cand_installed.exists():
            return (str(cand_installed), [])

    # 3. 尋找相鄰同目錄下的 KyteView 開發專案
    shelf_root = Path(__file__).resolve().parent.parent
    workspace_root = shelf_root.parent
    kyteview_dir = workspace_root / "KyteView"

    if kyteview_dir.exists():
        # 檢查編譯好的 dist/KyteView.exe
        dist_exe = kyteview_dir / "dist" / "KyteView.exe"
        if dist_exe.exists():
            return (str(dist_exe), [])

        # 檢查原始碼 main.py 與其專屬虛擬環境
        main_py = kyteview_dir / "main.py"
        venv_py = kyteview_dir / ".venv" / "Scripts" / "python.exe"
        if main_py.exists():
            py_exe = str(venv_py) if venv_py.exists() else sys.executable
            return (py_exe, [str(main_py)])

    return (None, [])


def trigger_kyteview_preview_async(file_path: object):
    """
    非同步發送檔案預覽請求至 KyteView (Toggle 模式)
    1. 嘗試連線至執行中的 KyteView (極短超時保護 25ms)
    2. 若未啟動，自動在背景喚醒 KyteView
    """
    if not file_path:
        return
    path_str = str(file_path)

    def _do_send():
        # 1. 嘗試連線已在運行的 KyteView
        socket = QLocalSocket()
        socket.connectToServer(IPC_SERVER_NAME)
        if socket.waitForConnected(50):
            payload = f"PREVIEW:{path_str}\n".encode("utf-8")
            socket.write(payload)
            socket.waitForBytesWritten(80)
            socket.disconnectFromServer()
            return

        # 2. 連線失敗 (代表 KyteView 未啟動)，自動嘗試在背景喚醒
        launcher, args = _find_kyteview_launcher()
        if launcher:
            try:
                cmd = [launcher] + args + [path_str]
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(
                    cmd,
                    creationflags=CREATE_NO_WINDOW,
                    close_fds=True
                )
            except Exception:
                pass

    t = threading.Thread(target=_do_send, daemon=True)
    t.start()


def update_kyteview_preview_async(file_path: object):
    """
    當列表焦點上下切換時非同步送出更新 (僅在 KyteView 已顯示時更新，不搶焦點、不冷啟動)
    """
    if not file_path:
        return
    path_str = str(file_path)

    def _do_update():
        socket = QLocalSocket()
        socket.connectToServer(IPC_SERVER_NAME)
        if socket.waitForConnected(50):
            payload = f"PREVIEW_UPDATE:{path_str}\n".encode("utf-8")
            socket.write(payload)
            socket.waitForBytesWritten(80)
            socket.disconnectFromServer()

    t = threading.Thread(target=_do_update, daemon=True)
    t.start()
