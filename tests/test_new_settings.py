import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_helpers import get_qapp
from kyteshelf.config import ConfigManager
from kyteshelf.utils import set_autostart, is_autostart_enabled, play_feedback_sound
from kyteshelf.ui.hotkey_dialog import SettingsDialog


class TestNewSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "test_config.json"
        self.config_manager = ConfigManager()
        self.config_manager.config_file = self.config_file
        self.config_manager.config = self.config_manager.DEFAULT_CONFIG.copy()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config_has_all_new_keys(self):
        cfg = self.config_manager.DEFAULT_CONFIG
        expected_keys = [
            "autostart",
            "auto_clear_on_drag_out",
            "auto_hide_on_empty",
            "default_drag_mode",
            "summon_position",
            "temp_retention",
            "sound_enabled",
            "kyteview_integration",
        ]
        for k in expected_keys:
            self.assertIn(k, cfg, f"Missing key {k} in DEFAULT_CONFIG")

    def test_save_and_reload_new_settings(self):
        new_values = {
            "autostart": True,
            "auto_clear_on_drag_out": False,
            "auto_hide_on_empty": False,
            "default_drag_mode": "move",
            "summon_position": "remember",
            "temp_retention": "exit_clear",
            "sound_enabled": False,
        }
        self.config_manager.save_config(new_values)
        loaded = self.config_manager.load_config()
        for k, v in new_values.items():
            self.assertEqual(loaded[k], v, f"Key {k} did not match expected value")

    def test_settings_dialog_initialization_and_save(self):
        dlg = SettingsDialog(self.config_manager)
        dlg.load_values()

        # 驗證 UI 控制元件已正確建立
        self.assertTrue(hasattr(dlg, "cb_autostart"))
        self.assertTrue(hasattr(dlg, "cb_auto_clear"))
        self.assertTrue(hasattr(dlg, "cb_auto_hide"))
        self.assertTrue(hasattr(dlg, "cb_sound"))
        self.assertTrue(hasattr(dlg, "combo_default_mode"))
        self.assertTrue(hasattr(dlg, "combo_summon_pos"))
        self.assertTrue(hasattr(dlg, "combo_temp_retention"))

        # 修改值並儲存
        dlg.cb_auto_clear.setChecked(False)
        dlg.combo_default_mode.setCurrentIndex(1)  # move
        dlg.combo_summon_pos.setCurrentIndex(1)     # remember

        with patch("kyteshelf.ui.hotkey_dialog.set_autostart") as mock_auto:
            dlg.save_and_apply()
            mock_auto.assert_called_once()

        self.assertEqual(self.config_manager.get("auto_clear_on_drag_out"), False)
        self.assertEqual(self.config_manager.get("default_drag_mode"), "move")
        self.assertEqual(self.config_manager.get("summon_position"), "remember")
        dlg.close()

    def test_play_feedback_sound_safe(self):
        # 測試音效函式呼叫安全不崩潰
        try:
            play_feedback_sound()
        except Exception as e:
            self.fail(f"play_feedback_sound raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
