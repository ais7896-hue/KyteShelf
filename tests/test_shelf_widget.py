import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

from tests.test_helpers import get_qapp
from kyteshelf.i18n import i18n
from kyteshelf.ui.shelf_widget import KyteShelfWidget


class TestKyteShelfWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.orig_lang = i18n.current_language
        i18n.apply_language("zh_TW")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.user_dir = Path(self.temp_dir.name) / "user_docs"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir = Path(self.temp_dir.name) / "notes_temp"
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        self.mock_manager = MagicMock()
        self.mock_license = MagicMock()
        self.mock_license.can_add_files.return_value = (10, "")
        self.mock_manager.license_manager = self.mock_license

        self.shelf = KyteShelfWidget(
            manager=self.mock_manager,
            shelf_id=1,
            color="#0284C7"
        )
        # Override shelf temp_dir to isolated notes_temp directory
        self.shelf.temp_dir = self.notes_dir

    def tearDown(self):
        self.shelf.clear_files()
        self.shelf.close()
        self.temp_dir.cleanup()
        i18n.apply_language(self.orig_lang)

    def test_initial_empty_state(self):
        self.assertEqual(len(self.shelf.file_paths), 0)
        self.assertEqual(self.shelf.list_widget.count(), 0)
        self.assertEqual(self.shelf.stack.currentIndex(), 0, "Empty page should be shown initially")
        self.assertFalse(self.shelf.btn_zip.isEnabled(), "ZIP button should be disabled when empty")
        self.assertFalse(self.shelf.btn_clear.isEnabled(), "Clear button should be disabled when empty")
        self.assertEqual(self.shelf.get_display_name(), "置物架 #1")

    def test_add_file_item_and_duplicate_prevention(self):
        test_file = self.user_dir / "document.pdf"
        test_file.write_text("dummy")

        # First addition: success
        self.shelf.add_file_item(str(test_file))
        self.assertEqual(len(self.shelf.file_paths), 1)
        self.assertEqual(self.shelf.list_widget.count(), 1)
        self.assertEqual(self.shelf.stack.currentIndex(), 1, "List page should be shown after adding file")
        self.assertTrue(self.shelf.btn_zip.isEnabled())
        self.assertTrue(self.shelf.btn_clear.isEnabled())

        # Second addition: duplicate rejected
        res = self.shelf.add_file_item(str(test_file))
        self.assertFalse(res)
        self.assertEqual(len(self.shelf.file_paths), 1)
        self.assertEqual(self.shelf.list_widget.count(), 1)

    def test_add_sticky_notes(self):
        # 1. Text note
        self.shelf.add_sticky_note("重要待辦事項：完成測試", note_type="text")
        self.assertEqual(len(self.shelf.file_paths), 1)
        item1 = self.shelf.list_widget.item(0)
        self.assertIn("重要待辦事項", item1.text())
        note_meta = item1.data(Qt.UserRole + 1)
        self.assertEqual(note_meta["type"], "sticky_note")
        self.assertEqual(note_meta["note_type"], "text")
        self.assertEqual(note_meta["content"], "重要待辦事項：完成測試")

        # Verify physical text file created
        txt_path = Path(note_meta["filepath"])
        self.assertTrue(txt_path.exists())
        self.assertEqual(txt_path.read_text(encoding="utf-8"), "重要待辦事項：完成測試")

        # 2. URL note
        self.shelf.add_sticky_note("https://github.com/test", note_type="url")
        self.assertEqual(len(self.shelf.file_paths), 2)
        item2 = self.shelf.list_widget.item(1)
        self.assertIn("🔖", item2.text())
        url_meta = item2.data(Qt.UserRole + 1)
        self.assertEqual(url_meta["note_type"], "url")

        # Verify physical .url shortcut created
        url_path = Path(url_meta["filepath"])
        self.assertTrue(url_path.exists())
        self.assertIn("URL=https://github.com/test", url_path.read_text(encoding="utf-8"))

    def test_toggle_pin_and_drag_mode(self):
        self.assertFalse(self.shelf.is_pinned)
        self.shelf.toggle_pin()
        self.assertTrue(self.shelf.is_pinned)
        self.shelf.toggle_pin()
        self.assertFalse(self.shelf.is_pinned)

        self.assertEqual(self.shelf.drag_mode, "copy")
        self.shelf.toggle_drag_mode()
        self.assertEqual(self.shelf.drag_mode, "move")
        self.shelf.toggle_drag_mode()
        self.assertEqual(self.shelf.drag_mode, "copy")

    def test_clear_files_and_cleanup_temp_files(self):
        # Add normal user document and sticky note
        normal_file = self.user_dir / "normal.txt"
        normal_file.write_text("keep me")
        self.shelf.add_file_item(str(normal_file))
        self.shelf.add_sticky_note("臨時筆記", note_type="text")

        note_file = Path(self.shelf.file_paths[1])
        self.assertTrue(note_file.exists())

        # Clear
        self.shelf.clear_files()
        self.assertEqual(len(self.shelf.file_paths), 0)
        self.assertEqual(self.shelf.list_widget.count(), 0)
        self.assertEqual(self.shelf.stack.currentIndex(), 0)

        # Sticky note temporary file should be deleted
        self.assertFalse(note_file.exists(), "Temporary sticky note file should be removed on clear")
        # Normal source file must NOT be deleted
        self.assertTrue(normal_file.exists(), "Original user file must not be deleted on clear")

    def test_state_serialization_and_restoration(self):
        real_file = self.user_dir / "save_test.txt"
        real_file.write_text("content")

        self.shelf.custom_name = "我的工作架"
        self.shelf.is_pinned = True
        self.shelf.drag_mode = "move"
        self.shelf.add_file_item(str(real_file))
        self.shelf.add_sticky_note("保存的便簽", note_type="text")

        state = self.shelf.get_state()
        self.assertEqual(state["name"], "我的工作架")
        self.assertEqual(state["is_pinned"], True)
        self.assertEqual(state["drag_mode"], "move")
        self.assertEqual(len(state["items"]), 2)

        # Restore into another shelf
        new_shelf = KyteShelfWidget(manager=self.mock_manager, shelf_id=2)
        new_shelf.temp_dir = self.notes_dir
        new_shelf.restore_from_state(state)

        self.assertEqual(new_shelf.custom_name, "我的工作架")
        self.assertTrue(new_shelf.is_pinned)
        self.assertEqual(new_shelf.drag_mode, "move")
        self.assertEqual(len(new_shelf.file_paths), 2)
        self.assertEqual(new_shelf.list_widget.count(), 2)

        new_shelf.clear_files()
        new_shelf.close()

    def test_retranslate_ui(self):
        i18n.apply_language("en_US")
        self.shelf.retranslate_ui()
        self.assertEqual(self.shelf.get_display_name(), "Shelf #1")

        i18n.apply_language("zh_TW")
        self.shelf.retranslate_ui()
        self.assertEqual(self.shelf.get_display_name(), "置物架 #1")


if __name__ == "__main__":
    unittest.main()
