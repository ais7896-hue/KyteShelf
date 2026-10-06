import os
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_helpers import get_qapp
from kyteshelf.session import SessionManager


class DummyShelf:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state


class TestSessionManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_path = Path(self.temp_dir.name) / "session.json"

        self.mock_config = MagicMock()
        self.mock_config.config_file = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch.object(SessionManager, "_cleanup_old_temp_files")
    def test_session_path_from_config(self, mock_cleanup):
        manager = SessionManager(config_manager=self.mock_config)
        self.assertEqual(manager.session_file, self.session_path)

    @patch.object(SessionManager, "_cleanup_old_temp_files")
    def test_save_and_load_valid_shelves(self, mock_cleanup):
        manager = SessionManager(config_manager=self.mock_config)

        shelves = [
            # Shelf 1: has items
            DummyShelf({
                "shelf_id": 1,
                "name": "",
                "is_pinned": False,
                "items": [{"type": "file", "path": "C:/dummy/test.txt"}]
            }),
            # Shelf 2: pinned even if empty
            DummyShelf({
                "shelf_id": 2,
                "name": "",
                "is_pinned": True,
                "items": []
            }),
            # Shelf 3: custom name even if empty
            DummyShelf({
                "shelf_id": 3,
                "name": "專案暫存",
                "is_pinned": False,
                "items": []
            }),
            # Shelf 4: empty, not pinned, no name -> SHOULD NOT BE SAVED
            DummyShelf({
                "shelf_id": 4,
                "name": "",
                "is_pinned": False,
                "items": []
            }),
        ]

        manager.save(shelves)
        self.assertTrue(self.session_path.exists())

        loaded = manager.load()
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["shelf_id"], 1)
        self.assertEqual(loaded[1]["shelf_id"], 2)
        self.assertEqual(loaded[2]["name"], "專案暫存")

    @patch.object(SessionManager, "_cleanup_old_temp_files")
    def test_load_nonexistent_or_empty_session(self, mock_cleanup):
        manager = SessionManager(config_manager=self.mock_config)
        # Nonexistent file
        self.assertEqual(manager.load(), [])

        # Empty file
        self.session_path.touch()
        self.assertEqual(manager.load(), [])

        # Corrupted JSON
        with open(self.session_path, "w", encoding="utf-8") as f:
            f.write("{corrupt: [}")
        self.assertEqual(manager.load(), [])

    def test_cleanup_old_temp_files(self):
        # Create a mock temporary dir structure simulating tempfile.gettempdir()
        temp_root = tempfile.TemporaryDirectory()
        shelf_temp_dir = Path(temp_root.name) / "KyteShelf"
        shelf_temp_dir.mkdir(parents=True, exist_ok=True)

        # 1. An old unreferenced file (> 7 days) -> should be deleted
        old_file = shelf_temp_dir / "old_unreferenced.txt"
        old_file.write_text("old")
        old_mtime = time.time() - (8 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))

        # 2. A recent file (< 7 days) -> should NOT be deleted
        recent_file = shelf_temp_dir / "recent.txt"
        recent_file.write_text("recent")

        # 3. An old file that IS referenced in active session -> should NOT be deleted
        active_old_file = shelf_temp_dir / "active_old.txt"
        active_old_file.write_text("active")
        os.utime(active_old_file, (old_mtime, old_mtime))

        # Save session referencing active_old_file
        session_data = {
            "shelves": [
                {
                    "items": [{"path": str(active_old_file.resolve())}]
                }
            ]
        }
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f)

        # Run cleanup with tempfile.gettempdir mocked
        with patch("tempfile.gettempdir", return_value=temp_root.name):
            manager = SessionManager(config_manager=self.mock_config)
            manager._cleanup_old_temp_files(max_age_days=7)

        self.assertFalse(old_file.exists(), "Old unreferenced file should be cleaned up")
        self.assertTrue(recent_file.exists(), "Recent file should NOT be cleaned up")
        self.assertTrue(active_old_file.exists(), "Active referenced file should NOT be cleaned up")

        temp_root.cleanup()


if __name__ == "__main__":
    unittest.main()
