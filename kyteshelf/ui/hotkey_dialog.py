from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QSlider, QCheckBox, QScrollArea, QWidget, QApplication
)

from ..config import ConfigManager
from ..license import LicenseManager
from ..utils import is_autostart_enabled, set_autostart
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
        self.license_dialog = None
        
        self.setWindowTitle(t("pref.title"))
        self.setFixedWidth(510)
        screen = QApplication.primaryScreen()
        avail_geo = screen.availableGeometry() if screen else None
        avail_h = avail_geo.height() if avail_geo else 800
        target_h = min(600, max(460, int(avail_h * 0.75)))
        self.resize(510, target_h)
        if avail_geo:
            x = avail_geo.x() + (avail_geo.width() - 510) // 2
            y = avail_geo.y() + (avail_geo.height() - target_h) // 2
            self.move(x, y)
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # 頂部說明與授權膠囊 (固定 Header)
        top_header = QHBoxLayout()
        title_label = QLabel(t("pref.header_title"), self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0F172A;")
        top_header.addWidget(title_label)
        top_header.addStretch()

        self.btn_license_badge = QPushButton(self)
        self.btn_license_badge.setCursor(Qt.PointingHandCursor)
        self.btn_license_badge.clicked.connect(self.open_license_dialog)
        top_header.addWidget(self.btn_license_badge)

        main_layout.addLayout(top_header)

        # 中間滾動區域 (QScrollArea)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 3px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 4, 8, 4)
        scroll_layout.setSpacing(12)

        # 區塊 1: 召喚與操作
        group_trigger = QFrame(scroll_widget)
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

        combo_style = """
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
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                selection-background-color: #F1F5F9;
                selection-color: #0284C7;
                padding: 4px;
            }
        """

        # 召喚彈出位置
        summon_row = QHBoxLayout()
        summon_label = QLabel(t("pref.summon_pos_label"), group_trigger)
        summon_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")

        self.combo_summon_pos = QComboBox(group_trigger)
        self.combo_summon_pos.setFixedHeight(30)
        self.combo_summon_pos.setStyleSheet(combo_style)
        self.combo_summon_pos.addItem(t("pref.summon_pos_cursor"), "cursor")
        self.combo_summon_pos.addItem(t("pref.summon_pos_remember"), "remember")
        summon_row.addWidget(summon_label)
        summon_row.addStretch()
        summon_row.addWidget(self.combo_summon_pos)
        trigger_layout.addLayout(summon_row)

        scroll_layout.addWidget(group_trigger)

        # 區塊 2: 置物架與拖曳行為
        group_behavior = QFrame(scroll_widget)
        group_behavior.setObjectName("BehaviorGroup")
        group_behavior.setStyleSheet("""
            QFrame#BehaviorGroup {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
        """)
        beh_layout = QVBoxLayout(group_behavior)
        beh_layout.setContentsMargins(14, 14, 14, 14)
        beh_layout.setSpacing(10)

        beh_title = QLabel(t("pref.group_behavior"), group_behavior)
        beh_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        beh_layout.addWidget(beh_title)

        # 開機啟動
        self.cb_autostart = QCheckBox(t("pref.autostart"), group_behavior)
        self.cb_autostart.setStyleSheet("font-size: 12px; color: #334155; border: none;")
        beh_layout.addWidget(self.cb_autostart)

        # 拖出後自動移除
        self.cb_auto_clear = QCheckBox(t("pref.auto_clear_drag_out"), group_behavior)
        self.cb_auto_clear.setStyleSheet("font-size: 12px; color: #334155; border: none;")
        beh_layout.addWidget(self.cb_auto_clear)

        # 清空後自動隱藏
        self.cb_auto_hide = QCheckBox(t("pref.auto_hide_empty"), group_behavior)
        self.cb_auto_hide.setStyleSheet("font-size: 12px; color: #334155; border: none;")
        beh_layout.addWidget(self.cb_auto_hide)

        # 入架音效
        self.cb_sound = QCheckBox(t("pref.sound_enable"), group_behavior)
        self.cb_sound.setStyleSheet("font-size: 12px; color: #334155; border: none;")
        beh_layout.addWidget(self.cb_sound)

        # 與 KyteView 連動預覽
        self.cb_kyteview = QCheckBox(t("pref.kyteview_enable"), group_behavior)
        self.cb_kyteview.setStyleSheet("font-size: 12px; color: #334155; border: none;")
        beh_layout.addWidget(self.cb_kyteview)

        # 預設拖曳模式
        mode_row = QHBoxLayout()
        mode_label = QLabel(t("pref.default_mode_label"), group_behavior)
        mode_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")

        self.combo_default_mode = QComboBox(group_behavior)
        self.combo_default_mode.setFixedHeight(30)
        self.combo_default_mode.setStyleSheet(combo_style)
        self.combo_default_mode.addItem(t("pref.mode_copy_desc"), "copy")
        self.combo_default_mode.addItem(t("pref.mode_move_desc"), "move")
        mode_row.addWidget(mode_label)
        mode_row.addStretch()
        mode_row.addWidget(self.combo_default_mode)
        beh_layout.addLayout(mode_row)

        scroll_layout.addWidget(group_behavior)

        # 區塊 3: 系統與暫存管理
        group_system = QFrame(scroll_widget)
        group_system.setObjectName("SystemGroup")
        group_system.setStyleSheet("""
            QFrame#SystemGroup {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
        """)
        sys_layout = QVBoxLayout(group_system)
        sys_layout.setContentsMargins(14, 14, 14, 14)
        sys_layout.setSpacing(10)

        sys_title = QLabel(t("pref.group_system"), group_system)
        sys_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        sys_layout.addWidget(sys_title)

        # 語言設定
        lang_row = QHBoxLayout()
        lang_label = QLabel(t("pref.language"), group_system)
        lang_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")

        self.combo_language = QComboBox(group_system)
        self.combo_language.setFixedHeight(30)
        self.combo_language.setStyleSheet(combo_style)
        self.combo_language.addItem(t("pref.lang_system"), "system")
        self.combo_language.addItem(t("pref.lang_zh_tw"), "zh_TW")
        self.combo_language.addItem(t("pref.lang_en_us"), "en_US")
        lang_row.addWidget(lang_label)
        lang_row.addStretch()
        lang_row.addWidget(self.combo_language)
        sys_layout.addLayout(lang_row)

        # 暫存清理策略
        temp_row = QHBoxLayout()
        temp_label = QLabel(t("pref.temp_retention_label"), group_system)
        temp_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")

        self.combo_temp_retention = QComboBox(group_system)
        self.combo_temp_retention.setFixedHeight(30)
        self.combo_temp_retention.setStyleSheet(combo_style)
        self.combo_temp_retention.addItem(t("pref.temp_days_7"), "days_7")
        self.combo_temp_retention.addItem(t("pref.temp_exit_clear"), "exit_clear")
        self.combo_temp_retention.addItem(t("pref.temp_never"), "never")
        temp_row.addWidget(temp_label)
        temp_row.addStretch()
        temp_row.addWidget(self.combo_temp_retention)
        sys_layout.addLayout(temp_row)

        scroll_layout.addWidget(group_system)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area, 1)

        # 固定底部操作區 (Sticky Footer)
        footer_frame = QFrame(self)
        footer_frame.setObjectName("FooterFrame")
        footer_frame.setStyleSheet("""
            QFrame#FooterFrame {
                background: transparent;
                border-top: 1px solid #E2E8F0;
                padding-top: 6px;
            }
        """)
        bottom_layout = QHBoxLayout(footer_frame)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(10)

        self.btn_reset = QPushButton(t("common.reset"), footer_frame)
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
        lbl_support = QLabel(f"<a href='{mailto_support}' style='color: #0284C7; text-decoration: none;'>✉ Support</a>", footer_frame)
        lbl_support.setOpenExternalLinks(True)
        lbl_support.setStyleSheet("font-size: 11px;")
        bottom_layout.addWidget(lbl_support)

        bottom_layout.addStretch()

        self.btn_cancel = QPushButton(t("common.cancel"), footer_frame)
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

        self.btn_save = QPushButton(t("common.apply"), footer_frame)
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
        main_layout.addWidget(footer_frame)

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

        # 召喚位置
        cur_pos = cfg.get("summon_position", "cursor")
        idx_pos = self.combo_summon_pos.findData(cur_pos)
        if idx_pos >= 0:
            self.combo_summon_pos.setCurrentIndex(idx_pos)

        # 置物架與拖曳行為
        import sys
        if sys.platform == "win32":
            self.cb_autostart.setChecked(is_autostart_enabled())
        else:
            self.cb_autostart.setChecked(cfg.get("autostart", False))
        self.cb_auto_clear.setChecked(cfg.get("auto_clear_on_drag_out", True))
        self.cb_auto_hide.setChecked(cfg.get("auto_hide_on_empty", True))
        self.cb_sound.setChecked(cfg.get("sound_enabled", True))
        self.cb_kyteview.setChecked(cfg.get("kyteview_integration", True))

        cur_mode = cfg.get("default_drag_mode", "copy")
        idx_mode = self.combo_default_mode.findData(cur_mode)
        if idx_mode >= 0:
            self.combo_default_mode.setCurrentIndex(idx_mode)

        # 同步語言下拉選單
        cur_lang = cfg.get("language", "system")
        idx = self.combo_language.findData(cur_lang)
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)

        # 暫存清理策略
        cur_retention = cfg.get("temp_retention", "days_7")
        idx_retention = self.combo_temp_retention.findData(cur_retention)
        if idx_retention >= 0:
            self.combo_temp_retention.setCurrentIndex(idx_retention)

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

    def restore_defaults(self):
        defaults = self.config_manager.DEFAULT_CONFIG
        self.cb_shake.setChecked(defaults["shake_enabled"])
        self.slider_sens.setValue(defaults["shake_sensitivity"])
        self.hotkey_edit.set_hotkey(defaults["hotkey"], defaults["hotkey_display"])
        self.combo_presets.setCurrentIndex(0)
        idx_pos = self.combo_summon_pos.findData(defaults.get("summon_position", "cursor"))
        if idx_pos >= 0:
            self.combo_summon_pos.setCurrentIndex(idx_pos)
        self.cb_autostart.setChecked(defaults.get("autostart", False))
        self.cb_auto_clear.setChecked(defaults.get("auto_clear_on_drag_out", True))
        self.cb_auto_hide.setChecked(defaults.get("auto_hide_on_empty", True))
        self.cb_sound.setChecked(defaults.get("sound_enabled", True))
        self.cb_kyteview.setChecked(defaults.get("kyteview_integration", True))
        idx_mode = self.combo_default_mode.findData(defaults.get("default_drag_mode", "copy"))
        if idx_mode >= 0:
            self.combo_default_mode.setCurrentIndex(idx_mode)
        idx = self.combo_language.findData(defaults.get("language", "system"))
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)
        idx_ret = self.combo_temp_retention.findData(defaults.get("temp_retention", "days_7"))
        if idx_ret >= 0:
            self.combo_temp_retention.setCurrentIndex(idx_ret)

    def save_and_apply(self):
        selected_lang = self.combo_language.currentData()
        autostart_checked = self.cb_autostart.isChecked()
        set_autostart(autostart_checked)

        new_cfg = {
            "shake_enabled": self.cb_shake.isChecked(),
            "shake_sensitivity": self.slider_sens.value(),
            "hotkey": self.hotkey_edit.pynput_format,
            "hotkey_display": self.hotkey_edit.display_format,
            "summon_position": self.combo_summon_pos.currentData(),
            "autostart": autostart_checked,
            "auto_clear_on_drag_out": self.cb_auto_clear.isChecked(),
            "auto_hide_on_empty": self.cb_auto_hide.isChecked(),
            "default_drag_mode": self.combo_default_mode.currentData(),
            "temp_retention": self.combo_temp_retention.currentData(),
            "sound_enabled": self.cb_sound.isChecked(),
            "kyteview_integration": self.cb_kyteview.isChecked(),
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
