import os
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal


class ConfigManager(QObject):
    config_changed = Signal(dict)

    DEFAULT_CONFIG = {
        "shake_enabled": True,
        "shake_sensitivity": 3,
        "hotkey": "<ctrl>+`",
        "hotkey_display": "Ctrl + `",
        "theme_color": "#0284C7"
    }

    def __init__(self):
        super().__init__()
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = self._get_config_path()
        self.config = self.load_config()

    def _get_config_path(self):
        try:
            # 專案根目錄優先
            local_dir = Path(__file__).resolve().parent.parent
            local_cfg = local_dir / "config.json"
            if local_cfg.exists():
                return local_cfg
            # 測試寫入權限
            with open(local_cfg, "w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            return local_cfg
        except Exception:
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
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
        self.config_changed.emit(self.config)
