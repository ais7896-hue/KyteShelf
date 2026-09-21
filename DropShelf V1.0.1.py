import sys
import os
import subprocess
import time
import zipfile
import tempfile
import json
from collections import deque
from pathlib import Path

# 防止 PyInstaller 在 --noconsole 模式下因為找不到 stdout/stderr 而崩潰
if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

from PySide6.QtCore import (
    Qt, QPoint, QSize, Signal, QObject, QMimeData, 
    QUrl, QEvent, QFileInfo, QPropertyAnimation, QEasingCurve, QFileSystemWatcher
)
from PySide6.QtGui import (
    QIcon, QDrag, QPixmap, QColor, QCursor, QDesktopServices, QImage
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QListWidgetItem, QLabel, QPushButton, 
    QFileIconProvider, QGraphicsDropShadowEffect, QMenu,
    QFileDialog, QMessageBox, QSystemTrayIcon, QStyle,
    QDialog, QSlider, QCheckBox, QColorDialog, QLineEdit,
    QComboBox, QFrame
)
from pynput import mouse, keyboard


# ==========================================
# 1. 跨執行緒通訊訊號
# ==========================================
class TriggerSignals(QObject):
    show_shelf = Signal(int, int)


# ==========================================
# 2. 設定檔管理器 (ConfigManager)
# ==========================================
class ConfigManager(QObject):
    config_changed = Signal(dict)

    DEFAULT_CONFIG = {
        "shake_enabled": True,
        "shake_sensitivity": 3,
        "hotkey": "<ctrl>+`",
        "hotkey_display": "Ctrl + `",
        "theme_color": "#0284C7"
    }

    def __init__(self):
        super().__init__()
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = self._get_config_path()
        self.config = self.load_config()

    def _get_config_path(self):
        try:
            local_dir = Path(__file__).resolve().parent
            local_cfg = local_dir / "config.json"
            if local_cfg.exists():
                return local_cfg
            # 測試寫入權限
            with open(local_cfg, "w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            return local_cfg
        except Exception:
            appdata = Path(os.environ.get("APPDATA", Path.home())) / "DropShelf"
            appdata.mkdir(parents=True, exist_ok=True)
            return appdata / "config.json"

    def load_config(self):
        cfg = self.DEFAULT_CONFIG.copy()
        if self.config_file.exists():
            try:
                if self.config_file.stat().st_size > 0:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cfg.update(data)
                else:
                    self.save_config(cfg)
            except Exception as e:
                print(f"讀取設定檔失敗: {e}")
        else:
            self.save_config(cfg)
        return cfg

    def save_config(self, new_config):
        self.config.update(new_config)
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
        self.config_changed.emit(self.config)


# ==========================================
# 3. 全域輸入監聽器（支援動態靈敏度與熱鍵更新）
# ==========================================
class GlobalInputMonitor:
    def __init__(self, signals: TriggerSignals, config_manager: ConfigManager):
        self.signals = signals
        self.config_manager = config_manager
        self.is_left_pressed = False
        self.history = deque(maxlen=20)
        self.last_trigger_time = 0
        self.current_cursor = (300, 300)

        self.mouse_listener = None
        self.hotkey_listener = None
        self.current_hotkey_str = ""

        self.apply_config(self.config_manager.config)
        self.config_manager.config_changed.connect(self.apply_config)

    def apply_config(self, config):
        self.shake_enabled = config.get("shake_enabled", True)
        sens = config.get("shake_sensitivity", 3)
        # 靈敏度等級映射 (min_dx, reversals, time_window)
        sens_map = {
            1: (18, 3, 0.40),  # 偏鈍（防誤觸）
            2: (14, 2, 0.42),  # 略鈍
            3: (10, 2, 0.45),  # 標準（預設）
            4: (8, 2, 0.50),   # 靈敏
            5: (5, 2, 0.55),   # 極靈敏
        }
        self.min_dx, self.reversals_needed, self.time_window = sens_map.get(sens, (10, 2, 0.45))

        new_hotkey = config.get("hotkey", "<ctrl>+`")
        if new_hotkey != self.current_hotkey_str:
            self.restart_hotkey_listener(new_hotkey)

    def restart_hotkey_listener(self, hotkey_str):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None

        self.current_hotkey_str = hotkey_str
        if not hotkey_str:
            return

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                hotkey_str: self.trigger_by_hotkey
            })
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
        except Exception as e:
            print(f"註冊全域快捷鍵 '{hotkey_str}' 失敗: {e}")

    def on_click(self, x, y, button, pressed):
        self.current_cursor = (int(x), int(y))
        if button == mouse.Button.left:
            self.is_left_pressed = pressed
            if not pressed:
                self.history.clear()

    def on_move(self, x, y):
        self.current_cursor = (int(x), int(y))
        if not self.is_left_pressed or not self.shake_enabled:
            return

        now = time.time()
        if now - self.last_trigger_time < 1.0:
            return

        self.history.append((x, now))
        recent = [p for p in self.history if now - p[1] <= self.time_window]
        if len(recent) < 4:
            return

        reversals = 0
        last_dir = 0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            if abs(dx) > self.min_dx:
                cur_dir = 1 if dx > 0 else -1
                if last_dir != 0 and cur_dir != last_dir:
                    reversals += 1
                last_dir = cur_dir

        if reversals >= self.reversals_needed:
            self.last_trigger_time = now
            self.history.clear()
            self.signals.show_shelf.emit(int(x), int(y))

    def trigger_by_hotkey(self):
        pos = QCursor.pos()
        self.signals.show_shelf.emit(pos.x(), pos.y())

    def start(self):
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move, 
            on_click=self.on_click
        )
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

        self.restart_hotkey_listener(self.current_hotkey_str)


# ==========================================
# 4. 熱鍵錄製與設定面板元件
# ==========================================
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
        self.setToolTip("點擊以錄製快捷鍵，按下 Esc 取消")
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
                min-height: 32px;
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
        self.setText("請按下組合鍵（Esc 取消）...")
        self.setStyleSheet("""
            QLineEdit {
                background-color: #EFF6FF;
                border: 2px solid #2563EB;
                border-radius: 6px;
                padding: 0px 10px;
                font-size: 13px;
                font-weight: 700;
                color: #1D4ED8;
                min-height: 32px;
            }
        """)

    def stop_recording(self):
        self.is_recording = False
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

        if key == Qt.Key_QuoteLeft:
            key_name = "`"
            pynput_key = "`"
        elif key == Qt.Key_AsciiTilde:
            key_name = "~"
            pynput_key = "~"
        elif key == Qt.Key_Space:
            key_name = "Space"
            pynput_key = "<space>"
        elif Qt.Key_A <= key <= Qt.Key_Z:
            char = chr(key).upper()
            key_name = char
            pynput_key = char.lower()
        elif Qt.Key_0 <= key <= Qt.Key_9:
            char = chr(key)
            key_name = char
            pynput_key = char
        elif Qt.Key_F1 <= key <= Qt.Key_F12:
            num = key - Qt.Key_F1 + 1
            key_name = f"F{num}"
            pynput_key = f"<f{num}>"
        else:
            txt = event.text()
            if txt and txt.isprintable():
                key_name = txt.upper()
                pynput_key = txt.lower()

        if not key_name:
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
    PRESET_THEMES = [
        ("#0284C7", "蔚藍"),
        ("#16A34A", "翡翠綠"),
        ("#EA580C", "活力橘"),
        ("#9333EA", "紫羅蘭"),
        ("#E11D48", "薔薇紅"),
        ("#0D9488", "石青綠")
    ]

    PRESET_HOTKEYS = [
        ("Ctrl + ` (單手預設)", "<ctrl>+`", "Ctrl + `"),
        ("Ctrl + Shift + D (Drop)", "<ctrl>+<shift>+d", "Ctrl + Shift + D"),
        ("Ctrl + Shift + S (Shelf)", "<ctrl>+<shift>+s", "Ctrl + Shift + S"),
        ("Alt + Space", "<alt>+<space>", "Alt + Space"),
        ("Ctrl + Alt + V", "<ctrl>+<alt>+v", "Ctrl + Alt + V"),
    ]

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.selected_theme_color = "#0284C7"
        self.theme_buttons = []
        
        self.setWindowTitle("DropShelf 偏好設定")
        self.setMinimumSize(480, 600)
        self.resize(480, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.init_ui()
        self.load_values()

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

        # 頂部說明
        title_label = QLabel("⚙️ 偏好設定", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0F172A;")
        layout.addWidget(title_label)

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

        trigger_title = QLabel("⚡ 召喚與觸發行為", group_trigger)
        trigger_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        trigger_layout.addWidget(trigger_title)

        # 晃動召喚開關
        self.cb_shake = QCheckBox("啟用滑鼠晃動召喚 (Shake to Summon)", group_trigger)
        self.cb_shake.setStyleSheet("font-size: 13px; font-weight: 500; border: none;")
        self.cb_shake.toggled.connect(self.on_shake_toggled)
        trigger_layout.addWidget(self.cb_shake)

        # 靈敏度調整
        sens_header = QHBoxLayout()
        sens_label = QLabel("晃動靈敏度：", group_trigger)
        sens_label.setStyleSheet("font-size: 12px; color: #475569; border: none;")
        self.sens_val_label = QLabel("標準 (等級 3)", group_trigger)
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
        lbl_low = QLabel("偏鈍 (防誤觸)", group_trigger)
        lbl_mid = QLabel("標準", group_trigger)
        lbl_high = QLabel("極靈敏", group_trigger)
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
        hotkey_label = QLabel("全域召喚快捷鍵：", group_trigger)
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
        for display_name, pynput_code, pure_display in self.PRESET_HOTKEYS:
            self.combo_presets.addItem(display_name, (pynput_code, pure_display))
        self.combo_presets.addItem("自訂錄製...", "custom")
        self.combo_presets.currentIndexChanged.connect(self.on_preset_hotkey_selected)

        hotkey_row.addWidget(self.hotkey_edit, stretch=2)
        hotkey_row.addWidget(self.combo_presets, stretch=3)
        trigger_layout.addLayout(hotkey_row)

        layout.addWidget(group_trigger)

        layout.addWidget(group_trigger)

        # 區塊 2: 外觀主題
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

        app_title = QLabel("🎨 外觀與主題色", group_appearance)
        app_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A; border: none;")
        app_layout.addWidget(app_title)

        # 預設色彩按鈕
        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        self.theme_buttons = []
        for hex_code, color_name in self.PRESET_THEMES:
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
        
        self.preview_title = QLabel("置物架 #1", self.preview_card)
        self.preview_title.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        self.preview_btn_new = QLabel("＋", self.preview_card)
        self.preview_btn_new.setStyleSheet("font-size: 16px; font-weight: bold; border: none; background: transparent;")
        
        self.preview_desc = QLabel("🎨 即時樣式預覽", self.preview_card)
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

        self.btn_reset = QPushButton("恢復預設值", self)
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

        bottom_layout.addStretch()

        self.btn_cancel = QPushButton("取消", self)
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

        self.btn_save = QPushButton("儲存並套用", self)
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

    def on_shake_toggled(self, checked):
        self.slider_sens.setEnabled(checked)
        self.sens_val_label.setEnabled(checked)

    def on_sens_changed(self, val):
        self.update_sens_label(val)

    def update_sens_label(self, val):
        labels = {
            1: "偏鈍 (防誤觸)",
            2: "略鈍",
            3: "標準 (推薦)",
            4: "靈敏",
            5: "極靈敏"
        }
        self.sens_val_label.setText(f"{labels.get(val, '')} (等級 {val})")

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

    def save_and_apply(self):
        new_cfg = {
            "shake_enabled": self.cb_shake.isChecked(),
            "shake_sensitivity": self.slider_sens.value(),
            "hotkey": self.hotkey_edit.pynput_format,
            "hotkey_display": self.hotkey_edit.display_format,
            "theme_color": self.selected_theme_color
        }
        self.config_manager.save_config(new_cfg)
        self.accept()



# ==========================================
# 3. 專屬強化型清單元件
# ==========================================
class ShelfFileList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shelf_window = parent
        self.setIconSize(QSize(32, 32))
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setSpacing(4)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_menu)
        self.itemDoubleClicked.connect(self.open_file)

        self.drag_start_pos = None

        self.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 4px 8px;
                color: #1E293B;
            }
            QListWidget::item:hover {
                background: #F1F5F9;
                border-color: #CBD5E1;
            }
            QListWidget::item:selected {
                background: #E2E8F0;
                border-color: #94A3B8;
                color: #0F172A;
            }
        """)

    def open_file(self, item):
        path_str = item.data(Qt.UserRole)
        if sys.platform == "win32":
            os.startfile(path_str)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or not self.drag_start_pos:
            super().mouseMoveEvent(event)
            return

        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        selected_items = self.selectedItems()
        if not selected_items:
            super().mouseMoveEvent(event)
            return

        if self.shelf_window:
            self.shelf_window.is_dragging_out = True

        urls = [QUrl.fromLocalFile(item.data(Qt.UserRole)) for item in selected_items]
        mime_data = QMimeData()
        mime_data.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime_data)

        first_icon = selected_items[0].icon()
        if not first_icon.isNull():
            drag.setPixmap(first_icon.pixmap(32, 32))
            drag.setHotSpot(QPoint(16, 16))

        # 根據模式嚴格限制拖放行為
        if self.shelf_window and getattr(self.shelf_window, 'drag_mode', 'copy') == 'move':
            supported_actions = Qt.CopyAction | Qt.MoveAction
            default_action = Qt.MoveAction
        else:
            supported_actions = Qt.CopyAction
            default_action = Qt.CopyAction

        action = drag.exec(supported_actions, default_action)

        if self.shelf_window:
            self.shelf_window.is_dragging_out = False

        if action != Qt.IgnoreAction:
            for item in selected_items:
                path = item.data(Qt.UserRole)
                if path in self.shelf_window.file_paths:
                    self.shelf_window.file_paths.remove(path)
                self.takeItem(self.row(item))

            self.shelf_window.update_state()

            if len(self.shelf_window.file_paths) == 0 and not self.shelf_window.is_pinned:
                self.shelf_window.hide()

    def open_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return

        path_str = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px; }")

        act_show = menu.addAction("在檔案總管中顯示")
        act_copy_path = menu.addAction("複製路徑")
        act_zip = menu.addAction("全部打包成 ZIP")
        act_attach_outlook = menu.addAction("附加到目前 Outlook 郵件")
        
        selected_paths = [item.data(Qt.UserRole) for item in self.selectedItems()]
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        is_all_images = all(Path(p).suffix.lower() in image_extensions for p in selected_paths)

        if is_all_images and len(selected_paths) > 0:
            menu.addSeparator()
            img_menu = menu.addMenu("🖼️ 影像快速處理")
            act_img_resize_50 = img_menu.addAction("縮小至 50%")
            act_img_convert_jpg = img_menu.addAction("轉換為 JPG")
            act_img_convert_png = img_menu.addAction("轉換為 PNG")
        else:
            act_img_resize_50 = None
            act_img_convert_jpg = None
            act_img_convert_png = None

        menu.addSeparator()
        act_delete = menu.addAction("從置物架移除")

        action = menu.exec(self.mapToGlobal(pos))
        if action == act_show:
            norm_path = os.path.normpath(path_str)
            subprocess.run(f'explorer /select,"{norm_path}"')
        elif action == act_copy_path:
            QApplication.clipboard().setText(path_str)
        elif action == act_zip:
            self.shelf_window.zip_all_files()
        elif action == act_attach_outlook:
            self.attach_to_outlook()
        elif action == act_img_resize_50:
            self.process_images(self.selectedItems(), "resize_50")
        elif action == act_img_convert_jpg:
            self.process_images(self.selectedItems(), "convert_jpg")
        elif action == act_img_convert_png:
            self.process_images(self.selectedItems(), "convert_png")
        elif action == act_delete:
            if path_str in self.shelf_window.file_paths:
                self.shelf_window.file_paths.remove(path_str)
            self.takeItem(self.row(item))
            self.shelf_window.update_state()

    def attach_to_outlook(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
            
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            inspector = outlook.ActiveInspector()
            
            if inspector and inspector.CurrentItem:
                mail_item = inspector.CurrentItem
                for item in selected_items:
                    path_str = os.path.normpath(item.data(Qt.UserRole))
                    mail_item.Attachments.Add(path_str)
                
                # 自動清除置物架中的項目
                for item in selected_items:
                    path_str = item.data(Qt.UserRole)
                    if path_str in self.shelf_window.file_paths:
                        self.shelf_window.file_paths.remove(path_str)
                    self.takeItem(self.row(item))
                self.shelf_window.update_state()
            else:
                QMessageBox.warning(self.shelf_window, "錯誤", "找不到正在獨立視窗編輯的 Outlook 郵件。\n請先在 Outlook「彈出」一封新郵件或回覆郵件視窗。")
        except Exception as e:
            QMessageBox.warning(self.shelf_window, "錯誤", f"無法連接到 Outlook，請確認 Outlook 已經開啟：\n{str(e)}")

    def process_images(self, items, action_type):
        for item in items:
            path_str = item.data(Qt.UserRole)
            path = Path(path_str)
            img = QImage(path_str)
            if img.isNull():
                continue
            
            new_filename = path.stem
            new_ext = path.suffix
            
            if action_type == "resize_50":
                img = img.scaled(img.width() // 2, img.height() // 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                new_filename += "_50pct"
            elif action_type == "convert_jpg":
                new_ext = ".jpg"
                img = img.convertToFormat(QImage.Format_RGB32)
            elif action_type == "convert_png":
                new_ext = ".png"
                
            new_filepath = self.shelf_window.temp_dir / f"{new_filename}{new_ext}"
            if new_filepath.exists():
                new_filepath = self.shelf_window.temp_dir / f"{new_filename}_{int(time.time())}{new_ext}"
                
            if action_type == "convert_jpg":
                img.save(str(new_filepath), "JPG", 90)
            elif action_type == "convert_png":
                img.save(str(new_filepath), "PNG")
            else:
                img.save(str(new_filepath))
                
            # 將處理完的新檔案加入置物架，並將原本的項目從置物架移除（不刪除實體檔案）
            if path_str in self.shelf_window.file_paths:
                self.shelf_window.file_paths.remove(path_str)
            self.takeItem(self.row(item))
            self.shelf_window.add_file_item(str(new_filepath))
        self.shelf_window.update_state()


# ==========================================
# 4. 置物架主視窗
# ==========================================
class DropShelfWidget(QWidget):
    def __init__(self, manager=None, shelf_id=1, color="#0284C7"):
        super().__init__()
        self.manager = manager
        self.shelf_id = shelf_id
        self.theme_color = color
        
        self.file_paths = []
        self.icon_provider = QFileIconProvider()
        self.is_dragging_out = False
        self.is_pinned = False
        self.window_drag_pos = None

        # 建立暫存目錄以存放拖入的純文字與網址
        self.temp_dir = Path(tempfile.gettempdir()) / "DropShelf"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(280, 360)

        # 初始化動畫
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(150)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.container = QWidget(self)
        self.container.setObjectName("Container")
        self.container.setStyleSheet(f"""
            QWidget#Container {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 4px solid {self.theme_color};
                border-radius: 12px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)

        # 頂部控制列
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(f"置物架 #{self.shelf_id}", self)
        self.title_label.setStyleSheet(f"font-weight: bold; color: {self.theme_color}; font-size: 14px;")

        # 新增按鈕
        self.btn_new = QPushButton("＋", self)
        self.btn_new.setFixedSize(24, 24)
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.setToolTip("新增置物架")
        self.btn_new.setStyleSheet(f"border: none; background: transparent; font-size: 16px; color: {self.theme_color}; margin: 0 2px;")
        if self.manager:
            self.btn_new.clicked.connect(self.manager.create_and_show_shelf)

        # 打包成 ZIP 按鈕
        self.btn_zip = QPushButton("📦", self)
        self.btn_zip.setFixedSize(24, 24)
        self.btn_zip.setCursor(Qt.PointingHandCursor)
        self.btn_zip.setToolTip("將清單內所有檔案打包成 ZIP")
        self.btn_zip.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        self.btn_zip.clicked.connect(self.zip_all_files)

        # 釘選按鈕
        self.btn_pin = QPushButton("📌", self)
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip("釘選視窗（點擊外部不關閉）")
        self.btn_pin.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        self.btn_pin.clicked.connect(self.toggle_pin)

        # 偏好設定按鈕
        self.btn_settings = QPushButton("⚙️", self)
        self.btn_settings.setFixedSize(24, 24)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip("偏好設定")
        self.btn_settings.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        if self.manager:
            self.btn_settings.clicked.connect(self.manager.open_settings)

        # 模式切換按鈕
        self.drag_mode = "copy"
        self.btn_mode = QPushButton("複製", self)
        self.btn_mode.setCursor(Qt.PointingHandCursor)
        self.btn_mode.setStyleSheet("border: 1px solid #CBD5E1; border-radius: 4px; background: #E2E8F0; font-size: 11px; padding: 2px 4px; color: #334155; margin: 0 2px;")
        self.btn_mode.setToolTip("點擊切換拖曳模式（複製/搬移）")
        self.btn_mode.clicked.connect(self.toggle_drag_mode)

        # 全選按鈕
        self.btn_select_all = QPushButton("全選", self)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setStyleSheet(f"border: none; color: {self.theme_color}; font-size: 12px; margin: 0 2px;")

        # 清空按鈕
        self.btn_clear = QPushButton("清空", self)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet("border: none; color: #EF4444; font-size: 12px; margin: 0 2px;")
        self.btn_clear.clicked.connect(self.clear_files)

        # 關閉按鈕
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("border: none; color: #94A3B8; font-weight: bold; font-size: 13px;")
        self.btn_close.clicked.connect(self.hide)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_new)
        header_layout.addWidget(self.btn_mode)
        header_layout.addWidget(self.btn_select_all)
        header_layout.addWidget(self.btn_zip)
        header_layout.addWidget(self.btn_pin)
        header_layout.addWidget(self.btn_settings)
        header_layout.addWidget(self.btn_clear)
        header_layout.addWidget(self.btn_close)
        container_layout.addLayout(header_layout)

        # 檔案清單
        self.list_widget = ShelfFileList(self)
        container_layout.addWidget(self.list_widget)
        self.btn_select_all.clicked.connect(self.list_widget.selectAll)

        # 底部引導
        self.hint_label = QLabel("拖入暫存 ｜ 拖出傳遞\n按住上方可拖移視窗", self)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 4px;")
        container_layout.addWidget(self.hint_label)

        main_layout.addWidget(self.container)

    def update_theme_color(self, new_color):
        """即時套用並更新主題色"""
        self.theme_color = new_color
        self.container.setStyleSheet(f"""
            QWidget#Container {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 4px solid {self.theme_color};
                border-radius: 12px;
            }}
        """)
        self.title_label.setStyleSheet(f"font-weight: bold; color: {self.theme_color}; font-size: 14px;")
        self.btn_new.setStyleSheet(f"border: none; background: transparent; font-size: 16px; color: {self.theme_color}; margin: 0 2px;")
        self.btn_select_all.setStyleSheet(f"border: none; color: {self.theme_color}; font-size: 12px; margin: 0 2px;")

    def zip_all_files(self):
        if not self.file_paths:
            return

        desktop = Path.home() / "Desktop"
        default_name = str(desktop / f"archive_{int(time.time())}.zip")
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "儲存 ZIP 壓縮檔", 
            default_name, 
            "ZIP Files (*.zip)"
        )
        if not save_path:
            return

        try:
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for path_str in self.file_paths:
                    p = Path(path_str)
                    if not p.exists():
                        continue
                    
                    if p.is_file():
                        zipf.write(p, arcname=p.name)
                    elif p.is_dir():
                        for root, _, files in os.walk(p):
                            for file in files:
                                full_file_path = Path(root) / file
                                rel_path = full_file_path.relative_to(p.parent)
                                zipf.write(full_file_path, arcname=str(rel_path))

            subprocess.run(f'explorer /select,"{os.path.normpath(save_path)}"')
        except Exception as e:
            QMessageBox.warning(self, "壓縮失敗", f"打包過程發生錯誤：\n{str(e)}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window_drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.window_drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.window_drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.window_drag_pos = None
        super().mouseReleaseEvent(event)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.btn_pin.setStyleSheet("border: none; background: #E2E8F0; border-radius: 4px; font-size: 12px;")
        else:
            self.btn_pin.setStyleSheet("border: none; background: transparent; font-size: 12px;")

    def toggle_drag_mode(self):
        if self.drag_mode == "copy":
            self.drag_mode = "move"
            self.btn_mode.setText("搬移")
            self.btn_mode.setStyleSheet("border: 1px solid #FCA5A5; border-radius: 4px; background: #FEE2E2; font-size: 11px; padding: 2px 4px; color: #991B1B; margin: 0 2px;")
        else:
            self.drag_mode = "copy"
            self.btn_mode.setText("複製")
            self.btn_mode.setStyleSheet("border: 1px solid #CBD5E1; border-radius: 4px; background: #E2E8F0; font-size: 11px; padding: 2px 4px; color: #334155; margin: 0 2px;")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if not self.is_dragging_out and not self.is_pinned and self.window_drag_pos is None:
                    self.hide()
        super().changeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()
            self.container.setStyleSheet(f"""
                QWidget#Container {{
                    background-color: #F0F9FF;
                    border: 2px dashed {self.theme_color};
                    border-radius: 12px;
                }}
            """)

    def dragLeaveEvent(self, event):
        self.container.setStyleSheet(f"""
            QWidget#Container {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 4px solid {self.theme_color};
                border-radius: 12px;
            }}
        """)

    def dropEvent(self, event):
        self.dragLeaveEvent(None)
        mime = event.mimeData()
        has_handled = False
        
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path and path not in self.file_paths:
                        self.add_file_item(path)
                        has_handled = True
                elif url.scheme() in ["http", "https"]:
                    self.create_temp_url_file(url.toString())
                    has_handled = True
                    
        if not has_handled and mime.hasText():
            self.create_temp_text_file(mime.text())
            
        event.acceptProposedAction()

    def create_temp_url_file(self, url_str: str):
        safe_name = "".join(c for c in url_str.split("://")[-1][:30] if c.isalnum() or c in ".-_")
        if not safe_name:
            safe_name = "link"
        filename = f"{safe_name}_{int(time.time())}.url"
        filepath = self.temp_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("[InternetShortcut]\n")
            f.write(f"URL={url_str}\n")
            
        self.add_file_item(str(filepath))

    def create_temp_text_file(self, text: str):
        snippet = text[:15].replace("\n", " ").strip()
        safe_name = "".join(c for c in snippet if c.isalnum() or c == " " or '\u4e00' <= c <= '\u9fa5')
        if not safe_name:
            safe_name = "text_snippet"
        filename = f"{safe_name}_{int(time.time())}.txt"
        filepath = self.temp_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
            
        self.add_file_item(str(filepath))

    def add_file_item(self, path_str: str):
        if path_str in self.file_paths:
            return
            
        path = Path(path_str)
        self.file_paths.append(path_str)

        item = QListWidgetItem()
        item.setText(path.name)
        item.setToolTip(path_str)
        item.setData(Qt.UserRole, path_str)
        item.setSizeHint(QSize(0, 44))

        if path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            pix = QPixmap(path_str)
            if not pix.isNull():
                pix = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(pix))
            else:
                item.setIcon(self.icon_provider.icon(QFileInfo(path_str)))
        else:
            item.setIcon(self.icon_provider.icon(QFileInfo(path_str)))

        self.list_widget.addItem(item)
        self.update_state()

    def clear_files(self):
        self.file_paths.clear()
        self.list_widget.clear()
        self.update_state()

    def update_state(self):
        count = len(self.file_paths)
        self.title_label.setText(f"置物架 #{self.shelf_id} ({count})")
        self.hint_label.setVisible(count == 0)

    def popup_at(self, x: int, y: int):
        screen_rect = QApplication.primaryScreen().availableGeometry()

        # 預設顯示在游標右側偏下，讓標題列靠近游標，不會跑到太上面
        target_x = x + 20
        target_y = y - 30

        # 確保不會超出螢幕邊界
        if target_x + self.width() > screen_rect.right():
            target_x = x - self.width() - 20

        # 如果底部超出螢幕，就往上拉
        if target_y + self.height() > screen_rect.bottom():
            target_y = screen_rect.bottom() - self.height() - 20
            
        # 如果頂部超出螢幕，就往下拉
        if target_y < screen_rect.top():
            target_y = screen_rect.top() + 20

        self.move(target_x, target_y)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()

        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.start()


def get_resource_path(relative_path):
    """取得資源絕對路徑 (支援 PyInstaller 打包)"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)

# ==========================================
# 5. 置物架管理員與程式進入點
# ==========================================
class ShelfManager(QObject):
    def __init__(self, config_manager: ConfigManager = None):
        super().__init__()
        self.config_manager = config_manager or ConfigManager()
        self.shelves = []
        self.next_id = 1
        self.current_theme = self.config_manager.config.get("theme_color", "#0284C7")
        self.colors = [self.current_theme, "#16A34A", "#EA580C", "#9333EA", "#E11D48", "#0D9488"]
        self.settings_dialog = None

        self.config_manager.config_changed.connect(self.on_config_changed)
        
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.watched_dir = ""
        self.known_files = set()
        
        self.init_tray()
        self.create_shelf()

    def on_config_changed(self, new_config):
        """當設定變更時即時套用主題色彩"""
        new_theme = new_config.get("theme_color", "#0284C7")
        self.current_theme = new_theme
        self.colors[0] = new_theme
        for shelf in self.shelves:
            shelf.update_theme_color(new_theme)

    def open_settings(self):
        """開啟偏好設定視窗"""
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self.config_manager)
        self.settings_dialog.load_values()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
        
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # 載入自訂圖示
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(QApplication.style().standardIcon(QStyle.SP_DirIcon))
            
        self.tray_icon.setToolTip("置物架")
        
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F1F5F9;
                color: #0284C7;
            }
        """)
        
        act_show = self.tray_menu.addAction("顯示所有置物架")
        act_show.triggered.connect(self.show_all)
        self.tray_menu.addSeparator()

        act_settings = self.tray_menu.addAction("⚙️ 偏好設定...")
        act_settings.triggered.connect(self.open_settings)
        self.tray_menu.addSeparator()
        
        act_watch = self.tray_menu.addAction("👀 設定監控資料夾...")
        act_watch.triggered.connect(self.set_watch_folder)
        self.act_stop_watch = self.tray_menu.addAction("停止監控資料夾")
        self.act_stop_watch.triggered.connect(self.stop_watch_folder)
        self.act_stop_watch.setVisible(False)
        self.tray_menu.addSeparator()
        
        act_new = self.tray_menu.addAction("新增置物架")
        act_new.triggered.connect(self.create_and_show_shelf)
        self.tray_menu.addSeparator()
        
        act_exit = self.tray_menu.addAction("退出")
        act_exit.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
    def create_shelf(self):
        color = self.colors[(self.next_id - 1) % len(self.colors)]
        shelf = DropShelfWidget(manager=self, shelf_id=self.next_id, color=color)
        self.shelves.append(shelf)
        self.next_id += 1
        return shelf
        
    def create_and_show_shelf(self):
        target_shelf = None
        # 優先尋找已經隱藏的閒置置物架來重複使用
        for shelf in self.shelves:
            if not shelf.isVisible():
                target_shelf = shelf
                break
                
        if not target_shelf:
            target_shelf = self.create_shelf()
            
        target_shelf.popup_at(QCursor.pos().x(), QCursor.pos().y())
        
    def show_all(self):
        offset = 0
        for shelf in self.shelves:
            if len(shelf.file_paths) > 0 or shelf.is_pinned:
                shelf.popup_at(QCursor.pos().x() + offset, QCursor.pos().y() + offset)
                offset += 40
            
    def on_shake(self, x, y):
        target_shelf = None
        for shelf in self.shelves:
            if not shelf.isVisible():
                target_shelf = shelf
                break
                
        if not target_shelf:
            target_shelf = self.create_shelf()
            
        target_shelf.popup_at(x, y)

    def set_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "選擇要監控的資料夾")
        if folder:
            self.stop_watch_folder()
            self.watched_dir = folder
            self.watcher.addPath(folder)
            
            try:
                self.known_files = set(os.listdir(folder))
            except Exception:
                self.known_files = set()
                
            self.act_stop_watch.setVisible(True)
            self.act_stop_watch.setText(f"停止監控: {Path(folder).name}")
            self.tray_icon.showMessage("置物架", f"已開始監控：{Path(folder).name}\n新檔案會自動加入置物架！", QSystemTrayIcon.Information, 3000)

    def stop_watch_folder(self):
        if self.watched_dir:
            self.watcher.removePath(self.watched_dir)
            self.watched_dir = ""
            self.known_files.clear()
            self.act_stop_watch.setVisible(False)
            self.tray_icon.showMessage("置物架", "已停止監控資料夾", QSystemTrayIcon.Information, 2000)
            
    def on_directory_changed(self, path):
        if path != self.watched_dir:
            return
            
        try:
            current_files = set(os.listdir(path))
        except Exception:
            return
            
        new_files = current_files - self.known_files
        self.known_files = current_files
        
        added_paths = []
        for f in new_files:
            if f.startswith('.') or f.endswith(('.tmp', '.crdownload', '.part')):
                continue
            full_path = os.path.join(path, f)
            if os.path.isfile(full_path):
                added_paths.append(full_path)
                
        if added_paths:
            target_shelf = None
            
            # 優先尋找目前已經顯示在畫面上的置物架（集中管理，不狂開新視窗）
            for shelf in reversed(self.shelves):
                if shelf.isVisible():
                    target_shelf = shelf
                    break
                    
            # 如果畫面上完全沒有置物架，才找隱藏的來重複使用
            if not target_shelf:
                for shelf in self.shelves:
                    if not shelf.isVisible():
                        target_shelf = shelf
                        break
                        
            # 真的都沒有才建立全新的
            if not target_shelf:
                target_shelf = self.create_shelf()
                
            for p in added_paths:
                target_shelf.add_file_item(p)
                
            cursor_pos = QCursor.pos()
            target_shelf.popup_at(cursor_pos.x(), cursor_pos.y())


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config_manager = ConfigManager()
    manager = ShelfManager(config_manager=config_manager)
    signals = TriggerSignals()
    signals.show_shelf.connect(manager.on_shake)

    monitor = GlobalInputMonitor(signals, config_manager=config_manager)
    monitor.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()