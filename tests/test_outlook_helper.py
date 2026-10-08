import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QMimeData
from kyteshelf.outlook_helper import (
    is_outlook_mime_data,
    get_unique_temp_filepath,
    extract_attachments_from_outlook_com,
    extract_virtual_files_from_clipboard,
)


class TestOutlookHelper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_outlook_mime_data(self):
        # 1. 空或無格式
        mime_empty = QMimeData()
        self.assertFalse(is_outlook_mime_data(mime_empty))

        # 2. 一般文字或網址
        mime_text = QMimeData()
        mime_text.setText("Hello World")
        self.assertFalse(is_outlook_mime_data(mime_text))

        # 3. 模擬包含 FileGroupDescriptorW 的自訂格式
        mime_outlook = QMimeData()
        mime_outlook.setData("application/x-qt-windows-mime;value=\"FileGroupDescriptorW\"", b"test")
        self.assertTrue(is_outlook_mime_data(mime_outlook))

        # 4. 包含 FileContents
        mime_contents = QMimeData()
        mime_contents.setData("application/x-qt-windows-mime;value=\"FileContents\"", b"test")
        self.assertTrue(is_outlook_mime_data(mime_contents))

    def test_get_unique_temp_filepath(self):
        # 1. 正常檔名
        p1 = get_unique_temp_filepath(self.target_dir, "report.xlsx")
        self.assertEqual(p1.name, "report.xlsx")

        # 2. 檔案已存在時自動重命名
        p1.write_text("dummy")
        p2 = get_unique_temp_filepath(self.target_dir, "report.xlsx")
        self.assertEqual(p2.name, "report_1.xlsx")

        # 3. 包含非法 Windows 字元
        p3 = get_unique_temp_filepath(self.target_dir, "invalid:file*name?.pdf")
        self.assertNotIn(":", p3.name)
        self.assertNotIn("*", p3.name)
        self.assertNotIn("?", p3.name)
        self.assertTrue(p3.name.endswith(".pdf"))

    def test_extract_virtual_files_empty_clipboard(self):
        # 當剪貼簿無內容或不包含 FileGroupDescriptor 時應安全回傳空串列
        result = extract_virtual_files_from_clipboard(self.target_dir)
        self.assertIsInstance(result, list)

    def test_extract_attachments_from_outlook_com_mock(self):
        # 測試 COM 提取與 SaveAsFile 流程
        mock_outlook = MagicMock()
        mock_inspector = MagicMock()
        mock_att_sel = MagicMock()
        mock_att = MagicMock()

        mock_att.FileName = "9681客诉单.xlsx"
        mock_att.SaveAsFile = MagicMock(side_effect=lambda p: Path(p).write_text("test_content"))
        mock_att_sel.Count = 1
        mock_att_sel.Item.return_value = mock_att
        mock_inspector.AttachmentSelection = mock_att_sel
        mock_outlook.ActiveInspector.return_value = mock_inspector

        with patch("win32com.client.Dispatch", return_value=mock_outlook):
            saved = extract_attachments_from_outlook_com(self.target_dir)
            self.assertEqual(len(saved), 1)
            self.assertTrue(Path(saved[0]).exists())
            self.assertIn("9681客诉单.xlsx", saved[0])
            mock_att.SaveAsFile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
