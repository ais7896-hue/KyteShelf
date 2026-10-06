import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_helpers import get_qapp
from kyteshelf.config import ConfigManager
from kyteshelf.license import LicenseManager
from kyteshelf.session import SessionManager
from kyteshelf.ui.shelf_manager import ShelfManager


class TestShelfManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "config.json"
        self.session_file = Path(self.temp_dir.name) / "session.json"
        self.license_file = Path(self.temp_dir.name) / "license.dat"
        self.trial_file = Path(self.temp_dir.name) / "trial.dat"

        LicenseManager._instance = None

    def tearDown(self):
        self.temp_dir.cleanup()
        LicenseManager._instance = None

    def _create_shelf_manager(self):
        with patch.object(ConfigManager, "_get_config_path", return_value=self.config_file), \
             patch.object(SessionManager, "_get_session_path", return_value=self.session_file), \
             patch.object(SessionManager, "_cleanup_old_temp_files"), \
             patch.object(LicenseManager, "_get_license_file_path", return_value=self.license_file), \
             patch.object(LicenseManager, "_get_trial_file_path", return_value=self.trial_file), \
             patch.object(ShelfManager, "init_tray"):
            cfg = ConfigManager()
            return ShelfManager(cfg)

    def test_create_and_manage_shelves(self):
        mgr = self._create_shelf_manager()
        # By default on empty session, restore_session creates 1 initial shelf
        self.assertEqual(len(mgr.shelves), 1)
        self.assertEqual(mgr.shelves[0].shelf_id, 1)

        # Create second shelf
        shelf2 = mgr.create_shelf()
        self.assertEqual(shelf2.shelf_id, 2)
        self.assertEqual(len(mgr.shelves), 2)

    def test_save_and_restore_session_lifecycle(self):
        mgr = self._create_shelf_manager()

        # Shelf 1: pinned with file
        test_file = Path(self.temp_dir.name) / "doc.txt"
        test_file.write_text("hello")
        mgr.shelves[0].is_pinned = True
        mgr.shelves[0].add_file_item(str(test_file))

        # Shelf 2: custom name
        shelf2 = mgr.create_shelf()
        shelf2.custom_name = "我的收藏"

        # Save session
        mgr.save_session()
        self.assertTrue(self.session_file.exists())

        # Create new manager and verify restored state
        mgr2 = self._create_shelf_manager()
        self.assertEqual(len(mgr2.shelves), 2)
        self.assertEqual(mgr2.shelves[0].is_pinned, True)
        self.assertEqual(len(mgr2.shelves[0].file_paths), 1)
        self.assertEqual(mgr2.shelves[1].custom_name, "我的收藏")

    def test_folder_watch_directory_changed(self):
        mgr = self._create_shelf_manager()
        watch_dir = Path(self.temp_dir.name) / "watched"
        watch_dir.mkdir(parents=True, exist_ok=True)

        mgr.watched_dir = str(watch_dir)
        mgr.known_files = set()

        # Add a new file and a temporary file into watched dir
        valid_file = watch_dir / "invoice.pdf"
        valid_file.write_text("invoice")
        tmp_file = watch_dir / "download.crdownload"
        tmp_file.write_text("partial")

        # Trigger directory change
        mgr.on_directory_changed(str(watch_dir))

        # The valid file should be added to shelf, tmp file must be ignored
        target_shelf = mgr.shelves[0]
        self.assertEqual(len(target_shelf.file_paths), 1)
        self.assertTrue(target_shelf.file_paths[0].endswith("invoice.pdf"))


if __name__ == "__main__":
    unittest.main()
