import sys
import os
from pathlib import Path


def init_runtime_environment():
    """防止 PyInstaller 在 --noconsole 模式下因為找不到 stdout/stderr 而崩潰"""
    if sys.platform == "win32":
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")


def get_resource_path(relative_path: str) -> str:
    """取得資源絕對路徑 (支援 PyInstaller 打包與本機開發環境)"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    
    # 優先從專案根目錄尋找
    project_root = Path(__file__).resolve().parent.parent
    target = project_root / relative_path
    if target.exists():
        return str(target)
    
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)


def set_autostart(enabled: bool) -> bool:
    """設定或移除 Windows 開機自動啟動註冊表項目"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "KyteShelf"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    main_py = os.path.abspath(sys.argv[0])
                    cmd = f'"{sys.executable}" "{main_py}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    """檢查目前是否已啟用 Windows 開機自啟動"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, "KyteShelf")
            return True
    except Exception:
        return False


def play_feedback_sound():
    """播放簡短入架成功反饋音效"""
    if sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
