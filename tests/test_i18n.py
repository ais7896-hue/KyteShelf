import unittest
from unittest.mock import patch

from tests.test_helpers import get_qapp
from kyteshelf.i18n import I18nManager, detect_system_language, t


class TestI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.i18n = I18nManager()

    def tearDown(self):
        # Reset to default setting
        self.i18n.apply_language("zh_TW")

    def test_apply_language_and_signal(self):
        emitted_languages = []
        self.i18n.language_changed.connect(emitted_languages.append)

        self.i18n.apply_language("en_US")
        self.assertEqual(self.i18n.current_language, "en_US")
        self.assertEqual(self.i18n.setting, "en_US")

        self.i18n.apply_language("zh_TW")
        self.assertEqual(self.i18n.current_language, "zh_TW")
        self.assertEqual(self.i18n.setting, "zh_TW")

        self.assertIn("en_US", emitted_languages)
        self.assertIn("zh_TW", emitted_languages)

    def test_translation_switch(self):
        self.i18n.apply_language("zh_TW")
        zh_ok = t("common.ok")
        self.assertEqual(zh_ok, "確定")
        zh_copy = t("shelf.mode_copy")
        self.assertEqual(zh_copy, "📋 複製模式")

        self.i18n.apply_language("en_US")
        en_ok = t("common.ok")
        self.assertEqual(en_ok, "OK")
        en_copy = t("shelf.mode_copy")
        self.assertEqual(en_copy, "📋 Copy Mode")

    def test_translation_with_formatting(self):
        self.i18n.apply_language("zh_TW")
        zh_fmt = t("shelf.default_name_format", id=3)
        self.assertEqual(zh_fmt, "置物架 #3")

        self.i18n.apply_language("en_US")
        en_fmt = t("shelf.default_name_format", id=3)
        self.assertEqual(en_fmt, "Shelf #3")

    def test_missing_key_fallback(self):
        # Nonexistent key should return the default value or the key itself
        result_with_default = t("non_existent_key_xyz", default="預設值")
        self.assertEqual(result_with_default, "預設值")

        result_without_default = t("non_existent_key_xyz")
        self.assertEqual(result_without_default, "non_existent_key_xyz")

    def test_system_language_detection(self):
        with patch("ctypes.windll.kernel32.GetUserDefaultUILanguage", return_value=0x0404):
            lang = detect_system_language()
            self.assertEqual(lang, "zh_TW")

        with patch("ctypes.windll.kernel32.GetUserDefaultUILanguage", return_value=0x0409), \
             patch("locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
            lang = detect_system_language()
            self.assertEqual(lang, "en_US")

    def test_tray_and_license_translations(self):
        self.i18n.apply_language("en_US")
        self.assertEqual(t("tray.check_update"), "Check for Updates...")
        self.assertIn("Free Edition Limit", t("license.limit_shelves_msg", max_count=1))
        
        self.i18n.apply_language("zh_TW")
        self.assertEqual(t("tray.check_update"), "檢查版本更新...")
        self.assertIn("基礎免費版限制", t("license.limit_shelves_msg", max_count=1))

    def test_translate_with_key_keyword_arg(self):
        # 測試 t() 傳入 key 關鍵字參數不會與函式本體參數衝突
        text = t("license.status_pro_desc", key="KS-TEST-1234")
        self.assertIn("KS-TEST-1234", text)


if __name__ == "__main__":
    unittest.main()
