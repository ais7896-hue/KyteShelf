import os
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .i18n import i18n


class ConfigManager(QObject):
    config_changed = Signal(dict)

    DEFAULT_CONFIG = {
        "shake_enabled": True,
        "shake_sensitivity": 3,
        "hotkey": "<ctrl>+`",
        "hotkey_display": "Ctrl + `",
        "theme_color": "#0284C7",
        "language": "system",
        "last_update_check_time": 0.0,
        "skipped_version": ""
    }

    def __init__(self):
        super().__init__()
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = self._get_config_path()
        self.config = self.load_config()
        i18n.apply_language(self.config.get("language", "system"))

    def _get_config_path(self):
        import sys
        # 若為 PyInstaller 打包環境，直接使用 AppData，避免寫入臨時目錄導致重啟後設定遺失
        if getattr(sys, "frozen", False):
            return self._get_appdata_config_path()

        try:
            # 開發環境下以專案根目錄優先
            local_dir = Path(__file__).resolve().parent.parent
            local_cfg = local_dir / "config.json"
            if local_cfg.exists():
                return local_cfg
            # 測試寫入權限
            with open(local_cfg, "w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            return local_cfg
        except Exception:
            return self._get_appdata_config_path()

    def _get_appdata_config_path(self):
        appdata = Path(os.environ.get("APPDATA", Path.home())) / "KyteShelf"
        old_appdata = Path(os.environ.get("APPDATA", Path.home())) / "DropShelf"
        if old_appdata.exists() and not appdata.exists():
            try:
                import shutil
                shutil.copytree(old_appdata, appdata)
            except Exception:
                pass
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata / "config.json"

    def load_config(self):
        cfg = self.DEFAULT_CONFIG.copy()
        if self.config_file.exists():
            try:
                if self.config_file.stat().st_size > 0:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cfg.update(data)
                else:
                    self.save_config(cfg)
            except Exception as e:
                print(f"讀取設定檔失敗: {e}")
        else:
            self.save_config(cfg)
        return cfg

    def save_config(self, new_config):
        self.config.update(new_config)
        if "language" in new_config:
            i18n.apply_language(new_config["language"])
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
        self.config_changed.emit(self.config)

    def get(self, key, default=None):
        return self.config.get(key, default)

