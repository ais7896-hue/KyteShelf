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
