import os
import json
import time
import tempfile
from pathlib import Path


class SessionManager:
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.session_file = self._get_session_path()
        self._cleanup_old_temp_files()

    def _get_session_path(self) -> Path:
        """取得 session.json 路徑，與 config.json 同目錄"""
        try:
            if self.config_manager and hasattr(self.config_manager, "config_file"):
                return Path(self.config_manager.config_file).parent / "session.json"
        except Exception:
            pass
        appdata = Path(os.environ.get("APPDATA", Path.home())) / "KyteShelf"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata / "session.json"

    def _cleanup_old_temp_files(self, max_age_days: int = 7):
        """清除 %TEMP%\\KyteShelf 內超過 N 天的舊暫存檔"""
        cutoff = time.time() - max_age_days * 86400
        for dir_name in ["KyteShelf", "DropShelf"]:
            temp_dir = Path(tempfile.gettempdir()) / dir_name
            if not temp_dir.exists():
                continue
            for f in temp_dir.iterdir():
                try:
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        f.unlink()
                except Exception:
                    pass

    def save(self, shelves) -> None:
        """序列化所有置物架狀態至 session.json"""
        data = {"shelves": []}
        for shelf in shelves:
            state = shelf.get_state()
            # 只儲存有內容或有釘選的架子
            if state["items"] or state["is_pinned"]:
                data["shelves"].append(state)

        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存工作階段失敗: {e}")

    def load(self) -> list:
        """讀取 session.json，失敗時回傳空 list"""
        if not self.session_file.exists():
            return []
        try:
            if self.session_file.stat().st_size == 0:
                return []
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("shelves", [])
        except Exception as e:
            print(f"讀取工作階段失敗: {e}")
            return []
