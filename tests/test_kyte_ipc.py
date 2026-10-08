import os
import sys
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QKeyEvent, QContextMenuEvent

from kyteshelf.kyte_ipc import (
    _find_kyteview_launcher,
    trigger_kyteview_preview_async,
    update_kyteview_preview_async
)
from kyteshelf.ui.shelf_list import ShelfFileList
from kyteshelf.config import ConfigManager

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestKyteIPC(unittest.TestCase):
    def test_find_kyteview_launcher_safe(self):
        """測試尋找 KyteView 啟動器函式安全返回元組"""
        launcher, args = _find_kyteview_launcher()
        self.assertIsInstance(args, list)
        if launcher is not None:
            self.assertIsInstance(launcher, str)

    def test_async_ipc_calls_non_blocking_and_safe(self):
        """測試在無 IPC Server 運行的情況下，呼叫發送不會引發例外，能安全非同步退出"""
        test_file = __file__
        try:
            trigger_kyteview_preview_async(test_file)
            update_kyteview_preview_async(test_file)
            trigger_kyteview_preview_async(None)
            update_kyteview_preview_async("")
        except Exception as e:
            self.fail(f"IPC async calls raised exception: {e}")

    def test_shelf_list_space_key_preview_trigger(self):
        """測試在 ShelfFileList 中選取檔案項目時按下 Space 鍵的行為"""
        shelf_list = ShelfFileList(parent=None)
        
        # 加入虛擬項目與真實檔案項目
        shelf_list.addItem("VirtualNote")
        item = shelf_list.item(0)
        item.setData(Qt.UserRole, __file__)
        shelf_list.setCurrentItem(item)

        # 模擬按下 Space 鍵
        key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
        shelf_list.keyPressEvent(key_event)
        self.assertTrue(key_event.isAccepted())

    def test_shelf_list_arrow_keys_navigation_sync(self):
        """測試在清單按方向鍵時能安全調用同步不崩潰"""
        shelf_list = ShelfFileList(parent=None)
        shelf_list.addItem("Item 1")
        shelf_list.addItem("Item 2")
        item1 = shelf_list.item(0)
        item1.setData(Qt.UserRole, __file__)
        item2 = shelf_list.item(1)
        item2.setData(Qt.UserRole, __file__)
        shelf_list.setCurrentItem(item1)

        # 按向下鍵
        down_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
        shelf_list.keyPressEvent(down_event)
        self.assertEqual(shelf_list.currentRow(), 1)


if __name__ == "__main__":
    unittest.main()
