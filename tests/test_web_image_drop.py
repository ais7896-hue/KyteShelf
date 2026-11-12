import sys
import unittest
import tempfile
import struct
from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtCore import QMimeData, QUrl, QByteArray
from PySide6.QtGui import QImage, QPixmap

from tests.test_helpers import get_qapp
from kyteshelf.ui.shelf_widget import KyteShelfWidget

class TestWebImageDrop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.notes_dir = Path(self.temp_dir.name) / "notes_temp"
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        self.mock_manager = MagicMock()
        self.mock_license = MagicMock()
        self.mock_license.can_add_files.return_value = (10, "")
        self.mock_manager.license_manager = self.mock_license

        self.shelf = KyteShelfWidget(manager=self.mock_manager, shelf_id=99)
        self.shelf.temp_dir = self.notes_dir

    def tearDown(self):
        self.shelf.clear_files()
        self.shelf.close()
        self.temp_dir.cleanup()

    def test_file_contents_binary_png(self):
        mime = QMimeData()
        # 1x1 transparent PNG
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        mime.setData('application/x-qt-windows-mime;value="FileContents"', QByteArray(png_bytes))

        # Also mock FileGroupDescriptorW with filename "sample_picture.png"
        # Struct: num_files(4) + FILEDESCRIPTORW (offset 72 is cFileName wchar[260])
        fgd = bytearray(4 + 592)
        struct.pack_into("<I", fgd, 0, 1)
        name_bytes = "sample_picture.png".encode("utf-16le")
        fgd[76 : 76 + len(name_bytes)] = name_bytes
        mime.setData('application/x-qt-windows-mime;value="FileGroupDescriptorW"', QByteArray(bytes(fgd)))

        saved_path = self.shelf._try_extract_binary_image_from_mime(mime)
        self.assertTrue(bool(saved_path), "Should extract image from FileContents")
        self.assertTrue(Path(saved_path).exists())
        self.assertTrue(saved_path.endswith(".png"))

    def test_extract_image_url_from_html_variants(self):
        html1 = '<html><body><!--StartFragment--><img src="https://example.com/photo.jpg" alt="test"><!--EndFragment--></body></html>'
        url1 = self.shelf._extract_image_url_from_html(html1)
        self.assertEqual(url1, "https://example.com/photo.jpg")

        # Lazy load data-src with 1x1 gif src
        html2 = '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-src="https://example.com/real.png">'
        url2 = self.shelf._extract_image_url_from_html(html2)
        self.assertEqual(url2, "https://example.com/real.png")

        # Relative URL resolved with base_url
        html3 = '<html><head><base href="https://mysite.org/sub/"></head><body><img src="images/cat.jpg"></body></html>'
        url3 = self.shelf._extract_image_url_from_html(html3, base_url="https://mysite.org/sub/")
        self.assertEqual(url3, "https://mysite.org/sub/images/cat.jpg")

        # Protocol relative URL
        html4 = '<img src="//cdn.example.net/icon.webp">'
        url4 = self.shelf._extract_image_url_from_html(html4)
        self.assertEqual(url4, "https://cdn.example.net/icon.webp")

    def test_is_image_url_variants(self):
        self.assertTrue(self.shelf._is_image_url("https://example.com/image.png"))
        self.assertTrue(self.shelf._is_image_url("https://example.com/image.jpg?v=123"))
        self.assertTrue(self.shelf._is_image_url("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR..."))
        self.assertTrue(self.shelf._is_image_url("https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format"))
        self.assertTrue(self.shelf._is_image_url("https://pbs.twimg.com/media/xyz?format=jpg&name=large"))
        self.assertFalse(self.shelf._is_image_url("https://github.com/google/gemini"))

    def test_download_and_add_remote_image_success(self):
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.read.return_value = png_bytes
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = self.shelf._download_and_add_remote_image("https://example.com/logo.png")
            self.assertTrue(res)
            self.assertEqual(len(self.shelf.file_paths), 1)
            saved_p = self.shelf.file_paths[0]
            self.assertTrue("web_image_" in saved_p)
            self.assertTrue(saved_p.endswith(".png"))
            self.assertTrue(Path(saved_p).exists())

if __name__ == "__main__":
    unittest.main()
