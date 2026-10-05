from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QSlider, QCheckBox, QColorDialog
)

from ..config import ConfigManager
from ..license import LicenseManager
from ..i18n import t, i18n
from .license_dialog import LicenseDialog


class HotkeyRecorderEdit(QLineEdit):
    hotkey_captured = Signal(str, str)  # (pynput_format, display_format)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.is_recording = False
        self.pynput_format = "<ctrl>+`"
        self.display_format = "Ctrl + `"
        self.setText(self.display_format)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(t("pref.hotkey_record_tip"))
        self.setFixedHeight(34)
        self.apply_normal_style()

    def apply_normal_style(self):
        self.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0px 10px;
                font-size: 13px;
                font-weight: 600;
                color: #0F172A;
            }
            QLineEdit:hover {
                border-color: #94A3B8;
                background-color: #F1F5F9;
            }
        """)

    def set_hotkey(self, pynput_str, display_str):
        self.pynput_format = pynput_str
        self.display_format = display_str
        self.setText(display_str)

    def mousePressEvent(self, event):
        self.start_recording()
        super().mousePressEvent(event)

    def start_recording(self):
        self.is_recording = True
        self.setText(t("pref.hotkey_recording"))
        self.setStyleSheet("""
            QLineEdit {
                background-color: #EFF6FF;
                border: 2px solid #2563EB;
                border-radius: 6px;
                padding: 0px 10px;
                font-size: 13px;
                font-weight: 600;
                color: #1D4ED8;
            }
        """)
        self.grabKeyboard()

    def stop_recording(self):
        self.is_recording = False
        self.releaseKeyboard()
        self.setText(self.display_format)
        self.apply_normal_style()

    def keyPressEvent(self, event):
        if not self.is_recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Escape:
            self.stop_recording()
            return

        # 忽略單獨按修飾鍵
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        parts = []
        pynput_parts = []

        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
            pynput_parts.append("<ctrl>")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")
            pynput_parts.append("<alt>")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")
            pynput_parts.append("<shift>")
        if modifiers & Qt.MetaModifier:
            parts.append("Win")
            pynput_parts.append("<cmd>")

        key_name = ""
        pynput_key = ""

        if Qt.Key_A <= key <= Qt.Key_Z:
            char = chr(key).upper()
            key_name = char
            pynput_key = char.lower()
        elif Qt.Key_0 <= key <= Qt.Key_9:
            char = chr(key)
            key_name = char
            pynput_key = char
        elif Qt.Key_F1 <= key <= Qt.Key_F12:
            f_num = key - Qt.Key_F1 + 1
            key_name = f"F{f_num}"
            pynput_key = f"<f{f_num}>"
        elif key == Qt.Key_QuoteLeft:
            key_name = "`"
            pynput_key = "`"
        elif key == Qt.Key_Space:
            key_name = "Space"
            pynput_key = "<space>"
        elif key == Qt.Key_Tab:
            key_name = "Tab"
            pynput_key = "<tab>"
        else:
            txt = event.text().strip()
            if txt:
                key_name = txt.upper()
                pynput_key = txt.lower()

        if not key_name or not parts:
            return

        parts.append(key_name)
        pynput_parts.append(pynput_key)

        display_str = " + ".join(parts)
        pynput_str = "+".join(pynput_parts)

        self.pynput_format = pynput_str
        self.display_format = display_str
        self.stop_recording()
        self.hotkey_captured.emit(self.pynput_format, self.display_format)


class SettingsDialog(QDialog):
    @classmethod
    def get_preset_themes(cls):
        return [
            ("#0284C7", t("theme.blue")),
            ("#16A34A", t("theme.emerald")),
            ("#EA580C", t("theme.orange")),
            ("#9333EA", t("theme.purple")),
            ("#E11D48", t("theme.rose")),
            ("#0D9488", t("theme.teal"))
        ]

    @classmethod
    def get_preset_hotkeys(cls):
        return [
            (t("hotkey_preset.ctrl_backtick"), "<ctrl>+`", "Ctrl + `"),
            ("Ctrl + Shift + D (Drop)", "<ctrl>+<shift>+d", "Ctrl + Shift + D"),
            ("Ctrl + Shift + S (Shelf)", "<ctrl>+<shift>+s", "Ctrl + Shift + S"),
            ("Alt + Space", "<alt>+<space>", "Alt + Space"),
            ("Ctrl + Alt + V", "<ctrl>+<alt>+v", "Ctrl + Alt + V"),
        ]

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.license_manager = LicenseManager.get_instance(config_manager)
        self.selected_theme_color = "#0284C7"
        self.theme_buttons = []
        self.license_dialog = None
        
        self.setWindowTitle(t("pref.title"))
        self.setFixedWidth(460)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.init_ui()
        self.load_values()

    def update_license_badge(self):
        if hasattr(self, "btn_license_badge"):
            plan = self.license_manager.get_plan_type()
            if plan == "pro":
                self.btn_license_badge.setText(t("license.pro_active"))
                self.btn_license_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #DCFCE7;
                        border: 1px solid #86EFAC;
                        border-radius: 12px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: bold;
                        color: #15803D;
                    }
                    QPushButton:hover {
                        background-color: #BBF7D0;
                    }
                """)
            elif plan == "trial":
                days = self.license_manager.get_trial_days_left()
                self.btn_license_badge.setText(t("license.trial_remaining", days=days))
                self.btn_license_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #DBEAFE;
                        border: 1px solid #93C5FD;
                        border-radius: 12px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: bold;
                        color: #1D4ED8;
                    }
                    QPushButton:hover {
                        background-color: #BFDBFE;
                    }
                """)
            else:
                self.btn_license_badge.setText(t("license.free_upgrade"))
                self.btn_license_badge.setStyleSheet("""
                    QPushButton {
                        background-color: #FEF3C7;
                        border: 1px solid #FDE68A;
                        border-radius: 12px;
                        padding: 3px 10px;
                        font-size: 11px;
                        font-weight: bold;
                        color: #B45309;
                    }
                    QPushButton:hover {
                        background-color: #FDE68A;
                    }
                """)

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
            }
            QLabel {
                color: #1E293B;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 頂部說明與授權膠囊
        top_header = QHBoxLayout()
        title_label = QLabel(t("pref.header_title"), self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0F172A;")
        top_header.addWidget(title_label)
        top_header.addStretch()

        self.btn_license_badge = QPushButton(self)
        self.btn_license_badge.setCursor(Qt.PointingHandCursor)
        self.btn_license_badge.clicked.connect(self.open_license_dialog)
        top_header.addWidget(self.btn_license_badge)

        layout.addLayout(top_header)

        # 區塊 1: 召喚與操作
        group_trigger = QFrame(self)
        group_trigger.setStyleSheet("""
            QFrame#TriggerGroup {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
        """)
        group_trigger.setObjectName("TriggerGroup")
        trigger_layout = QVBoxLayout(group_trigger)
        trigger_layout.setContentsMargins(14, 14, 14, 14)
        trigger_layout.setSpacing(10)

        trigger_title = QLabel(t("pref.group_trigger"), group_trigger)
        trigger_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        trigger_layout.addWidget(trigger_title)

        # 晃動召喚開關
        self.cb_shake = QCheckBox(t("pref.shake_enable"), group_trigger)
        self.cb_shake.setStyleSheet("font-size: 13px; font-weight: 500; border: none;")
        self.cb_shake.toggled.connect(self.on_shake_toggled)
        trigger_layout.addWidget(self.cb_shake)

        # 靈敏度調整
        sens_header = QHBoxLayout()
        sens_label = QLabel(t("pref.shake_sens"), group_trigger)
        sens_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")
        self.sens_val_label = QLabel("", group_trigger)
        self.sens_val_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0284C7; border: none;")
        sens_header.addWidget(sens_label)
        sens_header.addStretch()
        sens_header.addWidget(self.sens_val_label)
        trigger_layout.addLayout(sens_header)

        self.slider_sens = QSlider(Qt.Horizontal, group_trigger)
        self.slider_sens.setRange(1, 5)
        self.slider_sens.setTickPosition(QSlider.TicksBelow)
        self.slider_sens.setTickInterval(1)
        self.slider_sens.valueChanged.connect(self.on_sens_changed)
        trigger_layout.addWidget(self.slider_sens)

        sens_ticks = QHBoxLayout()
        lbl_low = QLabel(t("pref.shake_lbl_low"), group_trigger)
        lbl_mid = QLabel(t("pref.shake_lbl_mid"), group_trigger)
        lbl_high = QLabel(t("pref.shake_lbl_high"), group_trigger)
        for lbl in (lbl_low, lbl_mid, lbl_high):
            lbl.setStyleSheet("font-size: 11px; color: #94A3B8; border: none;")
        sens_ticks.addWidget(lbl_low)
        sens_ticks.addStretch()
        sens_ticks.addWidget(lbl_mid)
        sens_ticks.addStretch()
        sens_ticks.addWidget(lbl_high)
        trigger_layout.addLayout(sens_ticks)

        line_sep = QFrame()
        line_sep.setFrameShape(QFrame.HLine)
        line_sep.setStyleSheet("background-color: #F1F5F9; border: none; max-height: 1px;")
        trigger_layout.addWidget(line_sep)

        # 全域快捷鍵
        hotkey_label = QLabel(t("pref.hotkey_label"), group_trigger)
        hotkey_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")
        trigger_layout.addWidget(hotkey_label)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(8)
        self.hotkey_edit = HotkeyRecorderEdit(group_trigger)
        self.hotkey_edit.setFixedHeight(36)
        self.hotkey_edit.hotkey_captured.connect(self.on_custom_hotkey_captured)
        
        self.combo_presets = QComboBox(group_trigger)
        self.combo_presets.setFixedHeight(36)
        self.combo_presets.setStyleSheet("""
            QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 28px;
                background-color: #FFFFFF;
                font-size: 13px;
                font-weight: 500;
                color: #334155;
                min-height: 34px;
            }
            QComboBox:hover {
                border-color: #94A3B8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #E2E8F0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748B;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                selection-background-color: #F1F5F9;
                selection-color: #0284C7;
                padding: 4px;
            }
        """)
        for display_name, pynput_code, pure_display in self.get_preset_hotkeys():
            self.combo_presets.addItem(display_name, (pynput_code, pure_display))
        self.combo_presets.addItem(t("pref.hotkey_custom"), "custom")
        self.combo_presets.currentIndexChanged.connect(self.on_preset_hotkey_selected)

        hotkey_row.addWidget(self.hotkey_edit, stretch=2)
        hotkey_row.addWidget(self.combo_presets, stretch=3)
        trigger_layout.addLayout(hotkey_row)

        layout.addWidget(group_trigger)

        # 區塊 2: 外觀與語言
        group_appearance = QFrame(self)
        group_appearance.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        app_layout = QVBoxLayout(group_appearance)
        app_layout.setSpacing(10)

        app_title = QLabel(t("pref.group_appearance"), group_appearance)
        app_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        app_layout.addWidget(app_title)

        # 語言設定
        lang_row = QHBoxLayout()
        lang_label = QLabel(t("pref.language"), group_appearance)
        lang_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")
        
        self.combo_language = QComboBox(group_appearance)
        self.combo_language.setFixedHeight(32)
        self.combo_language.setStyleSheet("""
            QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 24px;
                background-color: #FFFFFF;
                font-size: 12px;
                color: #334155;
            }
            QComboBox:hover {
                border-color: #94A3B8;
            }
        """)
        self.combo_language.addItem(t("pref.lang_system"), "system")
        self.combo_language.addItem(t("pref.lang_zh_tw"), "zh_TW")
        self.combo_language.addItem(t("pref.lang_en_us"), "en_US")
        
        lang_row.addWidget(lang_label)
        lang_row.addStretch()
        lang_row.addWidget(self.combo_language)
        app_layout.addLayout(lang_row)

        # 預設色彩標題與按鈕
        color_header = QLabel(t("pref.theme_color"), group_appearance)
        color_header.setStyleSheet("font-size: 12px; color: #475569; border: none;")
        app_layout.addWidget(color_header)

        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        self.theme_buttons = []
        for hex_code, color_name in self.get_preset_themes():
            btn = QPushButton(group_appearance)
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(color_name)
            btn.clicked.connect(lambda checked=False, c=hex_code: self.select_color(c))
            color_layout.addWidget(btn)
            self.theme_buttons.append((btn, hex_code))

        # 自訂選色按鈕
        self.btn_custom_color = QPushButton("🎨 自訂...", group_appearance)
        self.btn_custom_color.setCursor(Qt.PointingHandCursor)
        self.btn_custom_color.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
                color: #334155;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                border-color: #94A3B8;
            }
        """)
        self.btn_custom_color.clicked.connect(self.open_color_dialog)
        color_layout.addWidget(self.btn_custom_color)
        color_layout.addStretch()
        app_layout.addLayout(color_layout)

        # 即時預覽卡片
        self.preview_card = QFrame(group_appearance)
        self.preview_card.setObjectName("PreviewCard")
        self.preview_card.setFixedHeight(50)
        self.preview_layout = QHBoxLayout(self.preview_card)
        self.preview_layout.setContentsMargins(14, 8, 14, 8)
        
        self.preview_title = QLabel("KyteShelf #1", self.preview_card)
        self.preview_title.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        self.preview_btn_new = QLabel("＋", self.preview_card)
        self.preview_btn_new.setStyleSheet("font-size: 16px; font-weight: bold; border: none; background: transparent;")
        
        self.preview_desc = QLabel("🎨 Theme Preview", self.preview_card)
        self.preview_desc.setStyleSheet("color: #64748B; font-size: 12px; border: none; background: transparent;")

        self.preview_layout.addWidget(self.preview_title)
        self.preview_layout.addWidget(self.preview_btn_new)
        self.preview_layout.addStretch()
        self.preview_layout.addWidget(self.preview_desc)

        app_layout.addWidget(self.preview_card)
        layout.addWidget(group_appearance)

        # 底部操作按鈕
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.btn_reset = QPushButton(t("common.reset"), self)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #64748B;
                font-size: 12px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        self.btn_reset.clicked.connect(self.restore_defaults)
        bottom_layout.addWidget(self.btn_reset)

        mailto_support = (
            "mailto:support@aisming.com?subject=%5BSupport%5D%20KyteShelf%20Inquiry"
        )
        lbl_support = QLabel(f"<a href='{mailto_support}' style='color: #0284C7; text-decoration: none;'>✉ Support</a>", self)
        lbl_support.setOpenExternalLinks(True)
        lbl_support.setStyleSheet("font-size: 11px;")
        bottom_layout.addWidget(lbl_support)

        bottom_layout.addStretch()

        self.btn_cancel = QPushButton(t("common.cancel"), self)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
                color: #334155;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(t("common.apply"), self)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: 600;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
        """)
        self.btn_save.clicked.connect(self.save_and_apply)
        bottom_layout.addWidget(self.btn_save)

        layout.addLayout(bottom_layout)

    def load_values(self):
        cfg = self.config_manager.config
        self.cb_shake.setChecked(cfg.get("shake_enabled", True))
        sens = cfg.get("shake_sensitivity", 3)
        self.slider_sens.setValue(sens)
        self.update_sens_label(sens)

        current_hotkey = cfg.get("hotkey", "<ctrl>+`")
        current_display = cfg.get("hotkey_display", "Ctrl + `")
        self.hotkey_edit.set_hotkey(current_hotkey, current_display)

        # 同步下拉選單
        matched_idx = -1
        for i in range(self.combo_presets.count() - 1):
            data = self.combo_presets.itemData(i)
            if data and data[0] == current_hotkey:
                matched_idx = i
                break
        if matched_idx >= 0:
            self.combo_presets.setCurrentIndex(matched_idx)
        else:
            self.combo_presets.setCurrentIndex(self.combo_presets.count() - 1)

        self.select_color(cfg.get("theme_color", "#0284C7"))

        # 同步語言下拉選單
        cur_lang = cfg.get("language", "system")
        idx = self.combo_language.findData(cur_lang)
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)

        self.update_license_badge()

    def on_shake_toggled(self, checked):
        self.slider_sens.setEnabled(checked)
        self.sens_val_label.setEnabled(checked)

    def on_sens_changed(self, val):
        self.update_sens_label(val)

    def update_sens_label(self, val):
        desc = t(f"pref.shake_desc_{val}")
        self.sens_val_label.setText(t("pref.shake_level_format", desc=desc, level=val))

    def on_preset_hotkey_selected(self, index):
        if index < 0:
            return
        data = self.combo_presets.itemData(index)
        if data == "custom":
            self.hotkey_edit.start_recording()
        elif data:
            pynput_code, pure_display = data
            self.hotkey_edit.set_hotkey(pynput_code, pure_display)

    def on_custom_hotkey_captured(self, pynput_str, display_str):
        matched = False
        for i in range(self.combo_presets.count() - 1):
            data = self.combo_presets.itemData(i)
            if data and data[0] == pynput_str:
                self.combo_presets.blockSignals(True)
                self.combo_presets.setCurrentIndex(i)
                self.combo_presets.blockSignals(False)
                matched = True
                break
        if not matched:
            self.combo_presets.blockSignals(True)
            self.combo_presets.setCurrentIndex(self.combo_presets.count() - 1)
            self.combo_presets.blockSignals(False)

    def select_color(self, hex_color):
        self.selected_theme_color = hex_color
        for btn, c in self.theme_buttons:
            if c.lower() == hex_color.lower():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c};
                        border: 3px solid #0F172A;
                        border-radius: 15px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c};
                        border: 1px solid #CBD5E1;
                        border-radius: 15px;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #64748B;
                    }}
                """)

        # 更新預覽卡片
        self.preview_card.setStyleSheet(f"""
            QFrame#PreviewCard {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 4px solid {hex_color};
                border-radius: 8px;
            }}
        """)
        self.preview_title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {hex_color}; border: none; background: transparent;")
        self.preview_btn_new.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {hex_color}; border: none; background: transparent;")

    def open_color_dialog(self):
        col = QColorDialog.getColor(QColor(self.selected_theme_color), self, "選擇主題色彩")
        if col.isValid():
            self.select_color(col.name())

    def restore_defaults(self):
        defaults = self.config_manager.DEFAULT_CONFIG
        self.cb_shake.setChecked(defaults["shake_enabled"])
        self.slider_sens.setValue(defaults["shake_sensitivity"])
        self.hotkey_edit.set_hotkey(defaults["hotkey"], defaults["hotkey_display"])
        self.combo_presets.setCurrentIndex(0)
        self.select_color(defaults["theme_color"])
        idx = self.combo_language.findData(defaults.get("language", "system"))
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)

    def save_and_apply(self):
        selected_lang = self.combo_language.currentData()
        new_cfg = {
            "shake_enabled": self.cb_shake.isChecked(),
            "shake_sensitivity": self.slider_sens.value(),
            "hotkey": self.hotkey_edit.pynput_format,
            "hotkey_display": self.hotkey_edit.display_format,
            "theme_color": self.selected_theme_color,
            "language": selected_lang
        }
        self.config_manager.save_config(new_cfg)
        self.accept()

    def open_license_dialog(self):
        if not self.license_dialog:
            self.license_dialog = LicenseDialog(self.license_manager, self)
            self.license_dialog.license_updated.connect(self.update_license_badge)
        self.license_dialog.show()
        self.license_dialog.raise_()
        self.license_dialog.activateWindow()
