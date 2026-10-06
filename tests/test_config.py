import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_helpers import get_qapp
from kyteshelf.config import ConfigManager
from kyteshelf.i18n import i18n


class TestConfigManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch.object(ConfigManager, "_get_config_path")
    def test_default_config_creation(self, mock_get_path):
        mock_get_path.return_value = self.config_path

        manager = ConfigManager()
        self.assertEqual(manager.config["shake_enabled"], True)
        self.assertEqual(manager.config["shake_sensitivity"], 3)
        self.assertEqual(manager.config["hotkey"], "<ctrl>+`")
        self.assertEqual(manager.config["theme_color"], "#0284C7")
        self.assertEqual(manager.config["language"], "system")
        self.assertTrue(self.config_path.exists())

    @patch.object(ConfigManager, "_get_config_path")
    def test_save_and_reload_config(self, mock_get_path):
        mock_get_path.return_value = self.config_path

        manager = ConfigManager()
        emitted_configs = []
        manager.config_changed.connect(emitted_configs.append)

        new_settings = {
            "shake_sensitivity": 5,
            "theme_color": "#16A34A",
            "language": "en_US"
        }
        manager.save_config(new_settings)

        # Check in-memory update
        self.assertEqual(manager.config["shake_sensitivity"], 5)
        self.assertEqual(manager.config["theme_color"], "#16A34A")
        self.assertEqual(manager.config["language"], "en_US")
        # Check signal emission
        self.assertEqual(len(emitted_configs), 1)
        self.assertEqual(emitted_configs[0]["theme_color"], "#16A34A")

        # Check persistent file content
        with open(self.config_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data["shake_sensitivity"], 5)
        self.assertEqual(saved_data["language"], "en_US")

        # Reload with new instance
        reloaded_mgr = ConfigManager()
        self.assertEqual(reloaded_mgr.config["shake_sensitivity"], 5)
        self.assertEqual(reloaded_mgr.config["theme_color"], "#16A34A")

    @patch.object(ConfigManager, "_get_config_path")
    def test_corrupt_config_fallback(self, mock_get_path):
        mock_get_path.return_value = self.config_path
        # Write corrupted JSON
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid_json: 123")

        manager = ConfigManager()
        # Should gracefully fallback to defaults
        self.assertEqual(manager.config["shake_sensitivity"], ConfigManager.DEFAULT_CONFIG["shake_sensitivity"])
        self.assertEqual(manager.config["theme_color"], ConfigManager.DEFAULT_CONFIG["theme_color"])

    @patch.object(ConfigManager, "_get_config_path")
    def test_empty_config_handling(self, mock_get_path):
        mock_get_path.return_value = self.config_path
        # Create empty file
        self.config_path.touch()

        manager = ConfigManager()
        # Should save default config into empty file
        self.assertTrue(self.config_path.stat().st_size > 0)
        self.assertEqual(manager.config["theme_color"], "#0284C7")


if __name__ == "__main__":
    unittest.main()
