import os
import re
import ssl
import html
import time
import struct
import zipfile
import tempfile
import subprocess
import urllib.request
import urllib.parse
import base64
import threading
from pathlib import Path

from PySide6.QtCore import (
    Qt, QSize, QEvent, QFileInfo, QPropertyAnimation, QEasingCurve, QTimer, QUrl
)
from PySide6.QtGui import (
    QIcon, QPixmap, QColor, QBrush, QKeySequence, QImage, QShortcut, QImageReader
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidgetItem, QLabel, QPushButton, QLineEdit, QDialog, QMenu,
    QFileIconProvider, QGraphicsDropShadowEffect, 
    QFileDialog, QMessageBox, QStackedWidget, QFrame
)

from .shelf_list import ShelfFileList
from .sticky_note import StickyNoteWindow, create_sticky_icon
from ..i18n import t, i18n
from ..utils import play_feedback_sound
from ..outlook_helper import (
    is_outlook_mime_data, is_browser_mime_data, extract_attachments_from_outlook_com, extract_virtual_files_from_clipboard
)


class RenameDialog(QDialog):
    def __init__(self, current_name: str, default_name: str, theme_color: str = "#0284C7", parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("rename.title"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(300, 140)
        self.theme_color = theme_color
        self.default_name = default_name
        self.new_name = current_name
        self.init_ui(current_name)

    def init_ui(self, current_name):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
                font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
            }}
            QLabel {{
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }}
            QLineEdit {{
                border: 1.5px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #0F172A;
                background-color: #F8FAFC;
            }}
            QLineEdit:focus {{
                border-color: {self.theme_color};
                background-color: #FFFFFF;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton#SaveBtn {{
                background-color: {self.theme_color};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#SaveBtn:hover {{
                background-color: {self.theme_color}DD;
            }}
            QPushButton#CancelBtn {{
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #E2E8F0;
            }}
            QPushButton#CancelBtn:hover {{
                background-color: #E2E8F0;
            }}
            QPushButton#ResetBtn {{
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 11px;
                text-decoration: underline;
                padding: 4px;
            }}
            QPushButton#ResetBtn:hover {{
                color: #64748B;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        lbl_hint = QLabel(t("rename.hint"), self)
        layout.addWidget(lbl_hint)

        self.input_edit = QLineEdit(self)
        self.input_edit.setText(current_name)
        self.input_edit.setPlaceholderText(self.default_name)
        self.input_edit.selectAll()
        layout.addWidget(self.input_edit)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        btn_reset = QPushButton(t("rename.reset"), self)
        btn_reset.setObjectName("ResetBtn")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip(t("rename.reset_tip"))
        btn_reset.clicked.connect(self.reset_to_default)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton(t("common.cancel"), self)
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton(t("common.save"), self)
        btn_save.setObjectName("SaveBtn")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.on_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        self.input_edit.returnPressed.connect(self.on_save)

    def reset_to_default(self):
        self.input_edit.setText(self.default_name)
        self.input_edit.selectAll()
        self.input_edit.setFocus()

    def on_save(self):
        self.new_name = self.input_edit.text().strip()
        self.accept()


class EditableTitleLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("ShelfTitleLabel")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(t("shelf.rename_tip"))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            shelf = self.window()
            if hasattr(shelf, "prompt_rename"):
                shelf.prompt_rename()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                color: #1E293B;
            }
            QMenu::item:selected {
                background-color: #F1F5F9;
                color: #0284C7;
            }
        """)
        shelf = self.window()
        act_paste = menu.addAction(t("menu.paste"))
        act_rename = menu.addAction(t("menu.rename_shelf"))
        menu.addSeparator()
        is_pinned = getattr(shelf, "is_pinned", False)
        act_pin = menu.addAction(t("menu.unpin_window") if is_pinned else t("menu.pin_window"))
        act_clear = menu.addAction(t("menu.clear_shelf"))

        action = menu.exec(event.globalPos())
        if action == act_paste and hasattr(shelf, "paste_from_clipboard"):
            shelf.paste_from_clipboard()
        elif action == act_rename and hasattr(shelf, "prompt_rename"):
            shelf.prompt_rename()
        elif action == act_pin and hasattr(shelf, "toggle_pin"):
            shelf.toggle_pin()
        elif action == act_clear and hasattr(shelf, "clear_files"):
            shelf.clear_files()



class KyteShelfWidget(QWidget):
    def __init__(self, manager=None, shelf_id=1, color="#0284C7"):
        super().__init__()
        self.manager = manager
        self.shelf_id = shelf_id
        self.custom_name = ""
        self.theme_color = color
        
        self.file_paths = []
        self.icon_provider = QFileIconProvider()
        self.is_dragging_out = False
        self.is_pinned = False
        self.window_drag_pos = None

        # 建立暫存目錄以存放拖入的純文字與網址
        self.temp_dir = Path(tempfile.gettempdir()) / "KyteShelf"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.active_notes = []
        self.suppress_auto_hide = False

        self.init_ui()
        self.update_state()

    def _apply_container_style(self, is_drag_hover=False):
        if is_drag_hover:
            self.container.setStyleSheet(f"""
                QWidget#Container {{
                    background-color: #F0F9FF;
                    border: 2px dashed {self.theme_color};
                    border-radius: 14px;
                }}
            """)
        else:
            self.container.setStyleSheet("""
                QWidget#Container {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 14px;
                }
            """)

    def _set_btn_disabled_style(self, btn):
        btn.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                color: #CBD5E1;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 8px;
                height: 22px;
            }
        """)

    def _restore_toolbar_btn_style(self, btn):
        btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                color: #475569;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 8px;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
                border-color: #CBD5E1;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #F1F5F9;
            }
        """)

    def _restore_clear_btn_style(self):
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #FFF5F5;
                border: 1px solid #FED7D7;
                border-radius: 6px;
                color: #DC2626;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #FEB2B2;
            }
            QPushButton:pressed {
                background-color: #FECACA;
            }
        """)

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(320, 410)

        self.setStyleSheet("""
            QToolTip {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
            }
        """)

        # 初始化動畫
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(150)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.container = QWidget(self)
        self.container.setObjectName("Container")
        self._apply_container_style(is_drag_hover=False)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 38))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 9, 12, 11)
        container_layout.setSpacing(9)

        # 頂部裝飾膠囊 Accent Handle
        self.top_handle = QWidget(self.container)
        self.top_handle.setFixedHeight(3)
        self.top_handle.setFixedWidth(36)
        self.top_handle.setStyleSheet(f"background-color: {self.theme_color}; border-radius: 1.5px;")

        handle_layout = QHBoxLayout()
        handle_layout.setContentsMargins(0, 0, 0, 0)
        handle_layout.addStretch()
        handle_layout.addWidget(self.top_handle)
        handle_layout.addStretch()
        container_layout.addLayout(handle_layout)

        # 1. 頂部 Header 控制列
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_box = QHBoxLayout()
        title_box.setSpacing(6)

        self.dot_indicator = QLabel("●", self.container)
        self.dot_indicator.setStyleSheet(f"color: {self.theme_color}; font-size: 10px; margin-top: 1px;")

        self.title_label = EditableTitleLabel(self.get_display_name(), self)
        self.update_title_style()

        self.count_badge = QLabel("0", self.container)
        self.count_badge.setStyleSheet("""
            background-color: #F1F5F9;
            color: #64748B;
            font-size: 11px;
            font-weight: 600;
            padding: 1px 7px;
            border-radius: 10px;
        """)

        title_box.addWidget(self.dot_indicator)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.count_badge)

        icon_btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                color: #64748B;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #E2E8F0;
            }
        """

        self.btn_new = QPushButton("＋", self.container)
        self.btn_new.setFixedSize(24, 24)
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.setToolTip(t("shelf.new_tip"))
        self.btn_new.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                color: #64748B;
                font-size: 15px;
                font-weight: bold;
                padding-bottom: 1px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #E2E8F0;
            }
        """)
        if self.manager:
            self.btn_new.clicked.connect(self.manager.create_and_show_shelf)

        self.btn_pin = QPushButton("📌", self.container)
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip(t("shelf.pin_tip"))
        self.btn_pin.setStyleSheet(icon_btn_style)
        self.btn_pin.clicked.connect(self.toggle_pin)

        self.btn_settings = QPushButton("⚙", self.container)
        self.btn_settings.setFixedSize(24, 24)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip(t("shelf.settings_tip"))
        self.btn_settings.setStyleSheet(icon_btn_style)
        if self.manager:
            self.btn_settings.clicked.connect(self.manager.open_settings)

        self.btn_close = QPushButton("✕", self.container)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip(t("shelf.close_tip"))
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                color: #94A3B8;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                color: #EF4444;
            }
            QPushButton:pressed {
                background-color: #FECACA;
            }
        """)
        self.btn_close.clicked.connect(self.hide)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(2)
        btn_box.addWidget(self.btn_new)
        btn_box.addWidget(self.btn_pin)
        btn_box.addWidget(self.btn_settings)
        btn_box.addWidget(self.btn_close)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addLayout(btn_box)
        container_layout.addLayout(header_layout)

        # 2. 中間內容區（Empty State vs 檔案清單）
        self.stack = QStackedWidget(self.container)

        # 頁面 0：Empty State 拖曳區
        self.empty_page = QFrame()
        self.empty_page.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1.5px dashed #CBD5E1;
                border-radius: 10px;
            }
        """)
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(16, 20, 16, 16)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignCenter)

        icon_circle = QLabel("📥", self.empty_page)
        icon_circle.setAlignment(Qt.AlignCenter)
        icon_circle.setStyleSheet("""
            background: #EDF7FD;
            border: 1px solid #BAE6FD;
            border-radius: 20px;
            font-size: 20px;
            padding: 8px;
        """)
        icon_circle.setFixedSize(46, 46)

        self.empty_title_label = QLabel(t("shelf.empty_title"), self.empty_page)
        self.empty_title_label.setStyleSheet("color: #334155; font-size: 13px; font-weight: 600; border: none; background: transparent;")

        self.empty_sub_label = QLabel(t("shelf.empty_subtitle"), self.empty_page)
        self.empty_sub_label.setStyleSheet("color: #94A3B8; font-size: 11px; border: none; background: transparent;")

        self.btn_paste_main = QPushButton(t("shelf.paste_btn"), self.empty_page)
        self.btn_paste_main.setCursor(Qt.PointingHandCursor)
        self.btn_paste_main.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: #F1F5F9;
                border-color: {self.theme_color};
                color: {self.theme_color};
            }}
            QPushButton:pressed {{
                background-color: #E2E8F0;
            }}
        """)
        self.btn_paste_main.clicked.connect(self.paste_from_clipboard)

        empty_layout.addStretch()
        empty_layout.addWidget(icon_circle, alignment=Qt.AlignCenter)
        empty_layout.addWidget(self.empty_title_label, alignment=Qt.AlignCenter)
        empty_layout.addWidget(self.empty_sub_label, alignment=Qt.AlignCenter)
        empty_layout.addSpacing(2)
        empty_layout.addWidget(self.btn_paste_main, alignment=Qt.AlignCenter)
        empty_layout.addStretch()

        # 頁面 1：檔案清單
        self.list_widget = ShelfFileList(self)

        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.list_widget)
        self.stack.setCurrentIndex(0)
        container_layout.addWidget(self.stack)

        # 提示訊息條（Toast 反饋，預設隱藏）
        self.toast_label = QLabel("", self.container)
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setStyleSheet("color: #0284C7; font-weight: bold; font-size: 11px; padding: 2px;")
        self.toast_label.setVisible(False)
        self.hint_label = self.toast_label
        container_layout.addWidget(self.toast_label)

        # 3. 底部快捷工具列 (Footer Toolbar)
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 1, 0, 0)
        default_mode = "copy"
        if self.manager and hasattr(self.manager, "config_manager"):
            try:
                cfg_obj = getattr(self.manager, "config_manager", None)
                if cfg_obj and hasattr(cfg_obj, "get"):
                    val = cfg_obj.get("default_drag_mode", "copy")
                    if isinstance(val, str) and val in ("copy", "move"):
                        default_mode = val
            except Exception:
                pass
        self.drag_mode = default_mode
        mode_btn_text = t("shelf.mode_move") if self.drag_mode == "move" else t("shelf.mode_copy")
        self.btn_mode = QPushButton(mode_btn_text, self.container)
        self.btn_mode.setCursor(Qt.PointingHandCursor)
        self.btn_mode.setToolTip(t("shelf.mode_tip"))
        self.btn_mode.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                color: #475569;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                border-color: #CBD5E1;
            }
        """)
        self.btn_mode.clicked.connect(self.toggle_drag_mode)

        self.btn_paste = QPushButton(t("shelf.paste_action"), self.container)
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.setToolTip(t("shelf.paste_tip"))
        self._restore_toolbar_btn_style(self.btn_paste)
        self.btn_paste.clicked.connect(self.paste_from_clipboard)

        self.btn_select_all = QPushButton(t("shelf.select_all"), self.container)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setToolTip(t("shelf.select_all_tip"))
        self._restore_toolbar_btn_style(self.btn_select_all)
        self.btn_select_all.clicked.connect(self.select_all_and_focus)

        self.btn_zip = QPushButton("ZIP", self.container)
        self.btn_zip.setCursor(Qt.PointingHandCursor)
        self.btn_zip.setToolTip(t("shelf.zip_tip"))
        self._restore_toolbar_btn_style(self.btn_zip)
        self.btn_zip.clicked.connect(self.zip_all_files)

        self.btn_clear = QPushButton(t("shelf.clear"), self.container)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setToolTip(t("shelf.clear_tip"))
        self._restore_clear_btn_style()
        self.btn_clear.clicked.connect(self.clear_files)

        # 設定所有按鈕不奪取鍵盤焦點
        for btn in (
            self.btn_new, self.btn_pin, self.btn_settings, self.btn_close,
            self.btn_paste_main, self.btn_mode, self.btn_paste,
            self.btn_select_all, self.btn_zip, self.btn_clear
        ):
            btn.setFocusPolicy(Qt.NoFocus)

        footer_layout.addWidget(self.btn_mode)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_paste)
        footer_layout.addWidget(self.btn_select_all)
        footer_layout.addWidget(self.btn_zip)
        footer_layout.addWidget(self.btn_clear)
        container_layout.addLayout(footer_layout)

        main_layout.addWidget(self.container)

        # 視窗全域快捷鍵守護
        QShortcut(QKeySequence.Delete, self, activated=self.list_widget.delete_selected_items)
        QShortcut(QKeySequence("Backspace"), self, activated=self.list_widget.delete_selected_items)
        QShortcut(QKeySequence.Paste, self, activated=self.paste_from_clipboard)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.select_all_and_focus)

    def select_all_and_focus(self):
        """全選項目並將鍵盤焦點鎖定回清單"""
        if self.list_widget.count() > 0:
            self.list_widget.selectAll()
            self.list_widget.setFocus()

    def update_title_style(self):
        self.title_label.setStyleSheet("""
            QLabel#ShelfTitleLabel {
                color: #0F172A;
                font-size: 13px;
                font-weight: 700;
                font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
                padding: 2px 4px;
                border-radius: 4px;
            }
            QLabel#ShelfTitleLabel:hover {
                background-color: #F1F5F9;
            }
        """)

    def update_theme_color(self, new_color):
        """即時套用並更新主題色"""
        self.theme_color = new_color
        self._apply_container_style(is_drag_hover=False)
        self.top_handle.setStyleSheet(f"background-color: {self.theme_color}; border-radius: 1.5px;")
        self.dot_indicator.setStyleSheet(f"color: {self.theme_color}; font-size: 10px; margin-top: 1px;")
        self.update_title_style()
        self.update_state()

    def zip_all_files(self):
        if not self.file_paths:
            return

        if self.manager and hasattr(self.manager, "license_manager"):
            can_zip, reason = self.manager.license_manager.can_use_zip()
            if not can_zip:
                from PySide6.QtWidgets import QMessageBox
                self.suppress_auto_hide = True
                try:
                    QMessageBox.information(self, t("license.pro_feature_title"), reason, QMessageBox.Ok)
                    self.manager.open_license_dialog()
                finally:
                    self.suppress_auto_hide = False
                return

        self.suppress_auto_hide = True
        try:
            desktop = Path.home() / "Desktop"
            default_name = str(desktop / f"archive_{int(time.time())}.zip")
            
            save_path, _ = QFileDialog.getSaveFileName(
                self, 
                t("shelf.zip_dialog_title"), 
                default_name, 
                "ZIP Files (*.zip)"
            )
            if not save_path:
                return

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
            QMessageBox.warning(self, t("shelf.zip_failed_title"), t("shelf.zip_failed_msg", err=str(e)))
        finally:
            self.suppress_auto_hide = False

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        elif event.key() == Qt.Key_Space:
            if hasattr(self, "list_widget") and self.list_widget.is_kyteview_enabled():
                item = self.list_widget.currentItem()
                if item:
                    path_str = item.data(Qt.UserRole)
                    if path_str and os.path.exists(path_str):
                        self.suppress_auto_hide = True
                        QTimer.singleShot(3000, lambda: setattr(self, "suppress_auto_hide", False))
                        from ..kyte_ipc import trigger_kyteview_preview_async
                        trigger_kyteview_preview_async(path_str)
                        QTimer.singleShot(60, self.list_widget.setFocus)
                        event.accept()
                        return
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if hasattr(self, "list_widget"):
                self.list_widget.delete_selected_items()
                event.accept()
                return
        elif event.matches(QKeySequence.Paste) or (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V):
            self.paste_from_clipboard()
            event.accept()
            return
        super().keyPressEvent(event)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.btn_pin.setStyleSheet(f"""
                QPushButton {{
                    background-color: #E0F2FE;
                    border: 1px solid #BAE6FD;
                    border-radius: 5px;
                    font-size: 12px;
                }}
            """)
        else:
            self.btn_pin.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 5px;
                    color: #64748B;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #0F172A;
                }
            """)

    def toggle_drag_mode(self):
        if self.drag_mode == "copy":
            self.drag_mode = "move"
            self.btn_mode.setText(t("shelf.mode_move"))
            self.btn_mode.setStyleSheet("""
                QPushButton {
                    background-color: #FEF2F2;
                    border: 1px solid #FCA5A5;
                    border-radius: 6px;
                    color: #DC2626;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                    height: 22px;
                }
                QPushButton:hover {
                    background-color: #FEE2E2;
                }
            """)
        else:
            self.drag_mode = "copy"
            self.btn_mode.setText(t("shelf.mode_copy"))
            self.btn_mode.setStyleSheet("""
                QPushButton {
                    background-color: #F1F5F9;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    color: #475569;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                    height: 22px;
                }
                QPushButton:hover {
                    background-color: #E2E8F0;
                }
            """)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if getattr(self, "suppress_auto_hide", False):
                    super().changeEvent(event)
                    return

                active_win = QApplication.activeWindow()
                if active_win:
                    if active_win == self or self.isAncestorOf(active_win) or active_win.parent() == self:
                        super().changeEvent(event)
                        return
                    if hasattr(self, "active_notes") and active_win in self.active_notes:
                        super().changeEvent(event)
                        return
                    if self.manager and getattr(self.manager, "settings_dialog", None) == active_win:
                        super().changeEvent(event)
                        return

                if not self.is_dragging_out and not self.is_pinned and self.window_drag_pos is None:
                    self.hide()
        super().changeEvent(event)

    def dragEnterEvent(self, event):
        # 忽略本視窗自己正在向外拖曳的事件，防止在視窗內部放開時自吞自吃
        if event.source() == self.list_widget or event.source() == self or self.is_dragging_out:
            event.ignore()
            return
        event.acceptProposedAction()
        self._apply_container_style(is_drag_hover=True)

    def dragMoveEvent(self, event):
        # 高頻觸發事件（每秒上百次）：嚴禁在此處呼叫 mime.formats() 或任何 COM RPC 查詢，防止主執行緒死鎖卡死
        if event.source() == self.list_widget or event.source() == self or self.is_dragging_out:
            event.ignore()
            return
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._apply_container_style(is_drag_hover=False)

    def _is_image_url(self, url_str: str) -> bool:
        """判定 URL 是否為常見圖片檔案格式或圖片託管 CDN"""
        if not url_str or not isinstance(url_str, str):
            return False
        clean_url = url_str.strip()
        if clean_url.startswith("data:image/"):
            return True
        try:
            parsed = urllib.parse.urlparse(clean_url)
            if parsed.scheme not in ("http", "https"):
                return False
            path = parsed.path.lower()
            image_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico", ".jfif", ".avif")
            if any(path.endswith(ext) for ext in image_exts):
                return True
            query = parsed.query.lower()
            if any(ext.lstrip(".") in query for ext in image_exts):
                return True
            netloc = parsed.netloc.lower()
            cdn_patterns = (
                "images.unsplash.com",
                "gstatic.com",
                "pbs.twimg.com",
                "i.imgur.com",
                "i.redd.it",
                "media.discordapp.net",
                "cdn.discordapp.com",
                "res.cloudinary.com",
                "image.",
                "img.",
                "photo.",
                "staticflickr.com",
            )
            if any(cp in netloc for cp in cdn_patterns):
                return True
            if any(seg in path for seg in ["/image", "/img", "/photo", "/picture", "/avatar"]):
                return True
        except Exception:
            pass
        return False

    def _save_base64_image(self, data_url: str) -> bool:
        """解析並儲存 data:image/...;base64,... 圖片至暫存檔並加入置物架"""
        try:
            m = re.match(r'^data:image/([a-zA-Z0-9\+\-]+);base64,(.+)$', data_url.strip(), re.DOTALL)
            if not m:
                return False
            ext = m.group(1).lower()
            if ext == "jpeg":
                ext = "jpg"
            elif ext == "svg+xml":
                ext = "svg"
            b64_str = m.group(2).strip()
            img_bytes = base64.b64decode(b64_str)
            if not img_bytes:
                return False
            ts = int(time.time() * 1000)
            img_path = self.temp_dir / f"web_image_{ts}.{ext}"
            with open(img_path, "wb") as f:
                f.write(img_bytes)
            if self.add_file_item(str(img_path)):
                self.update_state()
                if self.manager:
                    self.manager.save_session()
                self.show_temporary_hint("📥 圖片已成功加入置物架！")
                return True
        except Exception:
            pass
        return False

    def _dib_to_qimage(self, dib_bytes: bytes) -> QImage:
        """將 Windows DeviceIndependentBitmap (DIB) 轉換為 QImage"""
        if not dib_bytes or len(dib_bytes) < 40:
            return QImage()
        try:
            bi_size = struct.unpack_from("<I", dib_bytes, 0)[0]
            bi_bit_count = struct.unpack_from("<H", dib_bytes, 14)[0]
            bi_clr_used = struct.unpack_from("<I", dib_bytes, 32)[0]
            offset = 14 + bi_size
            if bi_clr_used > 0:
                offset += bi_clr_used * 4
            elif bi_bit_count <= 8:
                offset += (1 << bi_bit_count) * 4
            elif bi_size >= 40:
                bi_compression = struct.unpack_from("<I", dib_bytes, 16)[0]
                if bi_compression == 3:  # BI_BITFIELDS
                    offset += 12
            total_size = 14 + len(dib_bytes)
            file_header = struct.pack("<2sIHHI", b"BM", total_size, 0, 0, offset)
            img = QImage()
            if img.loadFromData(file_header + dib_bytes, "BMP"):
                return img
        except Exception:
            pass
        return QImage()

    def _try_extract_binary_image_from_mime(self, mime) -> str:
        """
        嘗試從 QMimeData 原生拖放格式中直接提取本機二進位點陣圖（免聯網、支援 Blob/防盜鏈）
        支援 Chromium / Edge / Firefox 拖曳的 FileContents, DIB, PNG, JFIF, QImage 等
        """
        ts = int(time.time() * 1000)

        # 1. 檢查直接點陣圖 (QImage / QPixmap)
        if mime.hasImage():
            try:
                img_data = mime.imageData()
                img = None
                if isinstance(img_data, QImage) and not img_data.isNull():
                    img = img_data
                elif isinstance(img_data, QPixmap) and not img_data.isNull():
                    img = img_data.toImage()
                elif img_data is not None and hasattr(img_data, "canConvert") and img_data.canConvert(QImage):
                    img = img_data.value()

                if img and not img.isNull():
                    img_path = self.temp_dir / f"drop_image_{ts}.png"
                    if img.save(str(img_path), "PNG"):
                        return str(img_path)
            except Exception:
                pass

        # 2. 遍歷 formats 搜尋 Windows 原生格式
        try:
            formats = mime.formats()
        except Exception:
            formats = []

        # 3. 核心支援：Chromium / Edge 原生拖放 FileGroupDescriptorW + FileContents
        # 當從瀏覽器拖曳網頁圖片時，Windows Chromium 會將圖片實體以 OLE 虛擬檔案提供
        fc_fmt = next((f for f in formats if "filecontents" in f.lower()), None)
        if fc_fmt:
            try:
                fc_bytes = bytes(mime.data(fc_fmt))
                if fc_bytes and len(fc_bytes) > 0:
                    filename = ""
                    fgd_fmt = next((f for f in formats if "filegroupdescriptor" in f.lower()), None)
                    if fgd_fmt:
                        try:
                            fgd_bytes = bytes(mime.data(fgd_fmt))
                            if len(fgd_bytes) >= 76:
                                is_unicode = "w" in fgd_fmt.lower()
                                if is_unicode:
                                    raw_name = fgd_bytes[76:596]
                                    filename = raw_name.decode("utf-16le", errors="ignore").split("\x00", 1)[0]
                                else:
                                    raw_name = fgd_bytes[76:336]
                                    filename = raw_name.decode("mbcs", errors="ignore").split("\x00", 1)[0]
                                filename = os.path.basename(filename.strip())
                        except Exception:
                            filename = ""

                    ext = ""
                    if filename:
                        suffix = Path(filename).suffix.lower()
                        if suffix in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico", ".jfif", ".avif"]:
                            ext = suffix
                    if not ext:
                        if fc_bytes.startswith(b"\x89PNG"):
                            ext = ".png"
                        elif fc_bytes.startswith(b"\xff\xd8"):
                            ext = ".jpg"
                        elif fc_bytes.startswith(b"GIF8"):
                            ext = ".gif"
                        elif b"WEBP" in fc_bytes[:16]:
                            ext = ".webp"
                        elif fc_bytes.startswith(b"BM"):
                            ext = ".bmp"
                        elif fc_bytes.lstrip().startswith(b"<svg") or fc_bytes.lstrip().startswith(b"<?xml"):
                            ext = ".svg"
                        elif fc_bytes.startswith(b"\x00\x00\x01\x00"):
                            ext = ".ico"

                    is_valid_image = bool(ext)
                    if not is_valid_image:
                        test_img = QImage()
                        if test_img.loadFromData(fc_bytes):
                            ext = ".png"
                            is_valid_image = True

                    if is_valid_image:
                        target_name = filename if (filename and Path(filename).suffix.lower() == ext) else f"drop_image_{ts}{ext}"
                        from ..outlook_helper import get_unique_temp_filepath
                        dest_path = get_unique_temp_filepath(self.temp_dir, target_name)
                        with open(dest_path, "wb") as f:
                            f.write(fc_bytes)
                        if dest_path.exists() and dest_path.stat().st_size > 0:
                            return str(dest_path)
            except Exception:
                pass

        # 4. 優先搜尋 PNG
        for fmt in formats:
            if "png" in fmt.lower() and "file" not in fmt.lower():
                try:
                    data = bytes(mime.data(fmt))
                    if data.startswith(b"\x89PNG"):
                        img_path = self.temp_dir / f"drop_image_{ts}.png"
                        with open(img_path, "wb") as f:
                            f.write(data)
                        return str(img_path)
                except Exception:
                    pass

        # 5. 搜尋 JPEG / JFIF
        for fmt in formats:
            fl = fmt.lower()
            if ("jfif" in fl or "jpeg" in fl or "jpg" in fl) and "file" not in fl:
                try:
                    data = bytes(mime.data(fmt))
                    if data.startswith(b"\xff\xd8"):
                        img_path = self.temp_dir / f"drop_image_{ts}.jpg"
                        with open(img_path, "wb") as f:
                            f.write(data)
                        return str(img_path)
                except Exception:
                    pass

        # 6. 搜尋 Windows 原生 DeviceIndependentBitmap (DIB / DIBV5)
        for fmt in formats:
            if "deviceindependentbitmap" in fmt.lower():
                try:
                    dib_data = bytes(mime.data(fmt))
                    if dib_data and len(dib_data) >= 40:
                        img = self._dib_to_qimage(dib_data)
                        if img and not img.isNull():
                            img_path = self.temp_dir / f"drop_image_{ts}.png"
                            if img.save(str(img_path), "PNG"):
                                return str(img_path)
                except Exception:
                    pass

        return ""

    def _extract_image_url_from_html(self, html_text: str, base_url: str = "") -> str:
        """從 HTML 原始碼中寬容提取圖片 URL 或 Base64 Data URL，並自動結合 base_url 轉為絕對網址"""
        if not html_text:
            return ""

        # 嘗試從 HTML 自身解析 <base href="..."> 或 SourceURL
        if not base_url:
            base_match = re.search(r'<base\b[^>]*?\bhref=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            if base_match:
                base_url = base_match.group(1).strip()
            else:
                source_match = re.search(r'SourceURL:(https?://[^\r\n\s]+)', html_text, re.IGNORECASE)
                if source_match:
                    base_url = source_match.group(1).strip()

        patterns = [
            r'<img\b[^>]*?\bsrc=["\']([^"\']+)["\']',
            r'<img\b[^>]*?\bdata-src=["\']([^"\']+)["\']',
            r'<img\b[^>]*?\bdata-original=["\']([^"\']+)["\']',
            r'<img\b[^>]*?\bsrcset=["\']([^"\'\s,]+)',
            # 無引號容錯
            r'<img\b[^>]*?\bsrc=([^\s>]+)',
            r'<img\b[^>]*?\bdata-src=([^\s>]+)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html_text, re.IGNORECASE):
                raw_url = html.unescape(m.group(1).strip())
                if raw_url.startswith("data:image/gif;base64,R0lGOD") or raw_url.startswith("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"):
                    continue
                if raw_url.startswith("data:image/"):
                    return raw_url
                if raw_url.startswith("//"):
                    return f"https:{raw_url}"
                if raw_url.startswith("http://") or raw_url.startswith("https://"):
                    return raw_url
                if base_url:
                    try:
                        return urllib.parse.urljoin(base_url, raw_url)
                    except Exception:
                        pass
                if raw_url.startswith("/"):
                    return raw_url

        return ""

    def _download_and_add_remote_image(self, url_str: str, referer: str = "") -> bool:
        """嘗試下載遠端網頁圖片，自動保存為本機實體圖片檔並直接入架"""
        try:
            parsed = urllib.parse.urlparse(url_str)
            origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else ""
            ref = referer or origin

            attempts = [ref, ""] if ref else [""]
            data = None

            for current_ref in attempts:
                try:
                    ssl_ctx = ssl._create_unverified_context()
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Sec-Fetch-Dest": "image",
                        "Sec-Fetch-Mode": "no-cors",
                        "Sec-Fetch-Site": "cross-site",
                    }
                    if current_ref:
                        headers["Referer"] = current_ref

                    req = urllib.request.Request(url_str, headers=headers)
                    with urllib.request.urlopen(req, timeout=3.5, context=ssl_ctx) as resp:
                        read_bytes = resp.read()
                        if read_bytes and len(read_bytes) > 0:
                            data = read_bytes
                            break
                except Exception:
                    continue

            if data and len(data) > 0:
                ext = ""
                if data.startswith(b"\x89PNG"):
                    ext = ".png"
                elif data.startswith(b"\xff\xd8"):
                    ext = ".jpg"
                elif data.startswith(b"GIF8"):
                    ext = ".gif"
                elif b"WEBP" in data[:16]:
                    ext = ".webp"
                elif data.startswith(b"BM"):
                    ext = ".bmp"
                elif data.lstrip().startswith(b"<svg") or data.lstrip().startswith(b"<?xml"):
                    ext = ".svg"
                else:
                    parsed_path = Path(parsed.path)
                    suffix = parsed_path.suffix.lower()
                    if suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg", ".ico", ".jfif", ".avif"]:
                        ext = suffix
                    else:
                        test_img = QImage()
                        if test_img.loadFromData(data):
                            ext = ".png"

                if ext:
                    ts = int(time.time() * 1000)
                    img_path = self.temp_dir / f"web_image_{ts}{ext}"
                    with open(img_path, "wb") as f:
                        f.write(data)

                    if self.add_file_item(str(img_path)):
                        self.update_state()
                        if self.manager:
                            self.manager.save_session()
                        self.show_temporary_hint("📥 圖片已成功加入置物架！")
                        return True
        except Exception:
            pass

        return False

    def _handle_image_drop(self, mime) -> bool:
        """
        全方位處理來自任何來源（特別是現代瀏覽器）的圖片拖曳：
        1. 優先直接從拖曳資料流提取本機二進位點陣圖（FileContents / DIB / PNG / JFIF）
           → 0 毫秒極速儲存，免網路請求，支援 Blob URL 與防盜鏈
        2. HTML 內嵌 Base64 圖片 (data:image/...)
        3. HTML 提取遠端圖片網址並下載實體圖片入架
        4. URLs / 純文字遠端圖片網址下載
        """
        # 1. 優先提取本機二進位點陣圖（Chrome / Edge / Firefox 均會提供）
        saved_local_img = self._try_extract_binary_image_from_mime(mime)
        if saved_local_img:
            if self.add_file_item(saved_local_img):
                self.update_state()
                if self.manager:
                    self.manager.save_session()
                self.show_temporary_hint("📥 圖片已成功加入置物架！")
                return True

        # 取得可能的 base_url
        base_url = ""
        if mime.hasUrls():
            for u in mime.urls():
                if not u.isLocalFile() and u.scheme() in ("http", "https"):
                    base_url = u.toString()
                    break

        # 2. HTML 檢查（Base64 或 遠端 URL）
        if mime.hasHtml():
            try:
                html_content = mime.html()
                img_url = self._extract_image_url_from_html(html_content, base_url=base_url)
                if img_url:
                    if img_url.startswith("data:image/"):
                        if self._save_base64_image(img_url):
                            return True
                    elif img_url.startswith("http://") or img_url.startswith("https://"):
                        if self._download_and_add_remote_image(img_url, referer=base_url):
                            return True
            except Exception:
                pass

        # 3. URLs 檢查（若 URL 是圖片副檔名或包含 Data URL）
        if mime.hasUrls():
            found_image = False
            for url in mime.urls():
                if not url.isLocalFile():
                    url_str = url.toString()
                    if url_str.startswith("data:image/"):
                        if self._save_base64_image(url_str):
                            found_image = True
                    elif self._is_image_url(url_str):
                        if self._download_and_add_remote_image(url_str, referer=base_url):
                            found_image = True
            if found_image:
                return True

        # 4. 純文字若為 Data URL 或 圖片網址
        if mime.hasText():
            text = mime.text().strip()
            if text.startswith("data:image/"):
                if self._save_base64_image(text):
                    return True
            elif self._is_image_url(text):
                if self._download_and_add_remote_image(text, referer=base_url):
                    return True

        return False

    def dropEvent(self, event):
        self.dragLeaveEvent(None)
        self._limit_warned_this_op = False
        # 忽略自身拖出的放開事件
        if event.source() == self.list_widget or event.source() == self or self.is_dragging_out:
            event.ignore()
            return

        try:
            mime = event.mimeData()
            has_handled = False

            # 0. 最高絕對優先級：本機實體檔案與資料夾（從檔案總管、桌面拖曳的檔案或資料夾）
            # 必須最優先處理並直接 return，零延遲，徹底隔絕後續 OLE 格式或網路下載！
            if mime.hasUrls():
                local_paths = [os.path.normpath(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
                if local_paths:
                    for p in local_paths:
                        if p and p not in self.file_paths:
                            self.add_file_item(p)
                    self.update_state()
                    if self.manager:
                        self.manager.save_session()
                    event.acceptProposedAction()
                    return

            # 1. 檢查是否為 Outlook 附件
            if is_outlook_mime_data(mime) and not is_browser_mime_data(mime):
                try:
                    formats = [f.lower() for f in mime.formats()]
                    if any("renprivate" in fmt for fmt in formats):
                        saved = extract_attachments_from_outlook_com(self.temp_dir)
                        if saved:
                            count = 0
                            for p in saved:
                                if p not in self.file_paths:
                                    if self.add_file_item(p):
                                        count += 1
                            if count > 0:
                                has_handled = True
                                self.update_state()
                                if self.manager:
                                    self.manager.save_session()
                                self.show_temporary_hint(f"📥 已從 Outlook 加入 {count} 個附件！")
                except Exception:
                    pass

            # 2. 處理網頁圖片拖曳（DIB 點陣圖、PNG 二進位資料、Base64 或 遠端 URL）
            if not has_handled:
                has_handled = self._handle_image_drop(mime)

            # 3. 處理遠端 HTTP/HTTPS 網址便箋
            if not has_handled and mime.hasUrls():
                for url in mime.urls():
                    if url.scheme() in ["http", "https"]:
                        url_str = url.toString()
                        self.add_sticky_note(url_str, note_type="url")
                        has_handled = True

            # 4. 純文字便箋降級處理
            if not has_handled and mime.hasText():
                text = mime.text().strip()
                if text:
                    self.add_sticky_note(text, note_type="text")
                    has_handled = True

            event.acceptProposedAction()
        except Exception:
            event.ignore()

    def add_sticky_note(self, content: str, note_type: str = "text"):
        """將純文字或網址以自黏標籤形式加入置物架"""
        content = content.strip()
        if not content:
            return

        ts = int(time.time() * 1000)
        if note_type == "url":
            # 建立 URL 快捷關聯檔案（以便支援外部檔案拖曳相容）
            filename = f"note_url_{ts}.url"
            filepath = self.temp_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("[InternetShortcut]\n")
                f.write(f"URL={content}\n")

            title = content.replace("https://", "").replace("http://", "").rstrip("/")
            if len(title) > 30:
                title = title[:27] + "..."
            item_text = f"🔖 {title}"
        else:
            filename = f"note_text_{ts}.txt"
            filepath = self.temp_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            first_line = content.splitlines()[0].strip() if content.splitlines() else ""
            if len(first_line) > 25:
                first_line = first_line[:22] + "..."
            item_text = f"📝 {first_line}" if first_line else f"📝 {t('note.title')}"

        path_str = str(filepath)
        self.file_paths.append(path_str)

        item = QListWidgetItem()
        item.setText(item_text)
        item.setToolTip(t("shelf.text_item_tip", content=content))
        item.setData(Qt.UserRole, path_str)
        item.setData(Qt.UserRole + 1, {
            "type": "sticky_note",
            "note_type": note_type,
            "content": content,
            "filepath": path_str
        })
        item.setSizeHint(QSize(0, 44))
        item.setIcon(create_sticky_icon(note_type))
        item.setBackground(QBrush(QColor("#FEFCE8" if note_type == "text" else "#F0F9FF")))
        item.setForeground(QBrush(QColor("#854D0E" if note_type == "text" else "#0369A1")))

        self.list_widget.addItem(item)
        self.update_state()

    def create_temp_url_file(self, url_str: str):
        self.add_sticky_note(url_str, note_type="url")

    def create_temp_text_file(self, text: str):
        self.add_sticky_note(text, note_type="text")

    def _create_file_tooltip(self, path_str: str) -> str:
        """為檔案建立現代美觀的 ToolTip，包含尺寸資訊與路徑"""
        path = Path(path_str)
        clean_name = html.escape(path.name)

        # 格式化檔案路徑（適度折行，避免橫向過寬）
        parts = path_str.replace('\\', '/').split('/')
        path_lines = []
        curr = ""
        for part in parts:
            if curr:
                if len(curr) + len(part) + 1 > 38:
                    path_lines.append(curr + "/")
                    curr = part
                else:
                    curr += "/" + part
            else:
                curr = part
        if curr:
            path_lines.append(curr)
        formatted_path = "<br/>".join(html.escape(l) for l in path_lines)

        size_str = ""
        try:
            if path.exists():
                size_bytes = path.stat().st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        except Exception:
            pass

        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".ico", ".svg", ".jfif", ".tif", ".tiff"}
        dim_info = ""
        if path.suffix.lower() in img_exts and path.exists():
            try:
                reader = QImageReader(path_str)
                sz = reader.size()
                if sz.isValid() and sz.width() > 0 and sz.height() > 0:
                    dim_info = f"📐 {sz.width()} &times; {sz.height()} px &nbsp;|&nbsp; "
            except Exception:
                pass

        size_line = f"<span>{dim_info}📦 {size_str}</span><br/>" if size_str or dim_info else ""
        return f"""<html><body>
<div style="font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif; max-width: 280px;">
    <div style="font-weight: bold; font-size: 12px; color: #F8FAFC; word-break: break-all; margin-bottom: 2px;">{clean_name}</div>
    <div style="font-size: 11px; color: #94A3B8; line-height: 1.4;">
        {size_line}
        <span style="color: #64748B; font-size: 10px;">{formatted_path}</span>
    </div>
</div>
</body></html>"""

    def add_file_item(self, path_str: str) -> bool:
        path_str = os.path.normpath(path_str)
        if path_str in self.file_paths:
            return False

        if self.manager and hasattr(self.manager, "license_manager"):
            allowed, reason = self.manager.license_manager.can_add_files(len(self.file_paths), 1)
            if allowed <= 0:
                if not getattr(self, "_limit_warned_this_op", False):
                    self._limit_warned_this_op = True
                    from PySide6.QtWidgets import QMessageBox
                    self.suppress_auto_hide = True
                    try:
                        QMessageBox.information(self, t("license.free_limit_title"), reason, QMessageBox.Ok)
                        self.manager.open_license_dialog()
                    finally:
                        self.suppress_auto_hide = False
                return False
            
        path = Path(path_str)
        self.file_paths.append(path_str)

        item = QListWidgetItem()
        item.setText(path.name)
        item.setToolTip(self._create_file_tooltip(path_str))
        item.setData(Qt.UserRole, path_str)
        item.setSizeHint(QSize(0, 44))

        if path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".ico", ".svg", ".jfif"]:
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
        self._trigger_sound_feedback()
        return True

    def _trigger_sound_feedback(self):
        try:
            if self.manager and hasattr(self.manager, "config_manager"):
                if not self.manager.config_manager.get("sound_enabled", True):
                    return
            play_feedback_sound()
        except Exception:
            pass

    def paste_from_clipboard(self) -> int:
        """從系統剪貼簿讀取檔案、圖片、文字或網址並加入置物架，回傳加入的項目數量"""
        self._limit_warned_this_op = False
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        added_count = 0

        # 1. 優先檢查是否為本機實體檔案 (Local Files)
        local_files = []
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = os.path.normpath(url.toLocalFile())
                    if path and path not in self.file_paths and Path(path).exists():
                        local_files.append(path)

        if local_files:
            for p in local_files:
                self.add_file_item(p)
                added_count += 1
            self.update_state()
            if self.manager:
                self.manager.save_session()
            self.show_temporary_hint(f"📋 已從剪貼簿貼入 {added_count} 個檔案！")
            return added_count

        # 2. 核心修復：優先檢查剪貼簿中的實體影像 (Image)
        # （當使用者在網頁右鍵點選「複製影像」，或使用 Windows 截圖時，瀏覽器會放入解碼後的 QImage）
        image = clipboard.image()
        if not image.isNull():
            ts = int(time.time() * 1000)
            img_path = self.temp_dir / f"clip_image_{ts}.png"
            if image.save(str(img_path), "PNG"):
                self.add_file_item(str(img_path))
                added_count += 1
                self.update_state()
                if self.manager:
                    self.manager.save_session()
                self.show_temporary_hint("📋 已貼入 1 張圖片檔案！")
                return added_count

        # 3. 核心新增：檢查是否為 Outlook 附件或 Windows 虛擬檔案（自 Outlook 附件 Ctrl+C）
        saved_outlook_files = []
        if is_outlook_mime_data(mime) or sys.platform == "win32":
            saved_outlook_files = extract_virtual_files_from_clipboard(self.temp_dir)
            if not saved_outlook_files:
                saved_outlook_files = extract_attachments_from_outlook_com(self.temp_dir)

        if saved_outlook_files:
            for p in saved_outlook_files:
                if p not in self.file_paths:
                    if self.add_file_item(p):
                        added_count += 1
            if added_count > 0:
                self.update_state()
                if self.manager:
                    self.manager.save_session()
                self.show_temporary_hint(f"📋 已從 Outlook 貼入 {added_count} 個附件！")
                return added_count

        # 4. 若無實體點陣圖，檢查 HTTP/HTTPS 網址（是否為遠端圖片網址）
        if mime.hasUrls():
            for url in mime.urls():
                if url.scheme() in ["http", "https"]:
                    url_str = url.toString()
                    if self._is_image_url(url_str) and self._download_and_add_remote_image(url_str):
                        added_count += 1
                    else:
                        self.add_sticky_note(url_str, note_type="url")
                        added_count += 1

        # 4. 檢查 HTML 中是否含有 <img> 圖片
        if added_count == 0 and mime.hasHtml():
            m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', mime.html(), re.IGNORECASE)
            if m:
                if self._download_and_add_remote_image(m.group(1)):
                    added_count += 1

        # 5. 檢查純文字（多行本地路徑 vs 圖片網址 vs 一般文字/網址）
        if added_count == 0 and mime.hasText():
            text = mime.text().strip()
            if text:
                lines = [l.strip().strip('"') for l in text.splitlines() if l.strip()]
                all_valid_files = len(lines) > 0 and all(Path(l).exists() for l in lines)
                if all_valid_files:
                    for l in lines:
                        if l not in self.file_paths:
                            self.add_file_item(l)
                            added_count += 1
                else:
                    if text.startswith(("http://", "https://")) and "\n" not in text:
                        if self._is_image_url(text) and self._download_and_add_remote_image(text):
                            added_count += 1
                        else:
                            self.add_sticky_note(text, note_type="url")
                            added_count += 1
                    else:
                        self.add_sticky_note(text, note_type="text")
                        added_count += 1

        if added_count > 0:
            self.update_state()
            if self.manager:
                self.manager.save_session()
            self.show_temporary_hint(f"📋 已從剪貼簿貼入 {added_count} 個項目！")
        else:
            self.show_temporary_hint("⚠️ 剪貼簿內無可貼入的內容", is_warning=True)

        return added_count

    def show_temporary_hint(self, text: str, duration_ms: int = 2200, is_warning: bool = False):
        """短暫在提示列顯示操作反饋"""
        color = "#EF4444" if is_warning else self.theme_color
        self.toast_label.setText(text)
        self.toast_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; padding: 2px;")
        self.toast_label.setVisible(True)
        QTimer.singleShot(duration_ms, self._restore_hint)

    def _restore_hint(self):
        self.toast_label.setVisible(False)

    def clear_files(self):
        for path_str in list(self.file_paths):
            self._delete_temp_if_sticky(path_str)
        self.file_paths.clear()
        self.list_widget.clear()
        self.update_state()

    def _delete_temp_if_sticky(self, path_str: str):
        """若路徑屬於自黏便箋暫存檔（在 temp_dir 內），立刻刪除實體檔案"""
        try:
            # 純字串前綴比對，避免 Path.resolve() 在 Windows 雲端硬碟/網路路徑阻塞主執行緒
            temp_prefix = str(self.temp_dir).rstrip("/\\").lower()
            norm = path_str.replace("/", "\\").lower()
            if norm.startswith(temp_prefix):
                p = Path(path_str)
                if p.exists():
                    p.unlink()
        except Exception:
            pass

    def get_state(self) -> dict:
        """序列化自身狀態以供 SessionManager 儲存"""
        items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            note_data = item.data(Qt.UserRole + 1)
            if note_data and isinstance(note_data, dict) and note_data.get("type") == "sticky_note":
                items.append({
                    "type": "sticky_note",
                    "note_type": note_data.get("note_type", "text"),
                    "content": note_data.get("content", ""),
                    "display_text": item.text(),
                })
            else:
                path_str = item.data(Qt.UserRole)
                if path_str:
                    items.append({
                        "type": "file",
                        "path": path_str,
                    })
        return {
            "shelf_id": self.shelf_id,
            "name": self.custom_name,
            "window_x": self.x(),
            "window_y": self.y(),
            "is_pinned": self.is_pinned,
            "drag_mode": self.drag_mode,
            "items": items,
        }

    def restore_from_state(self, state: dict):
        """從序列化狀態還原置物架內容、位置與模式"""
        if "name" in state:
            self.custom_name = state.get("name", "")

        for item_data in state.get("items", []):
            if item_data.get("type") == "file":
                path = item_data.get("path", "")
                if path and Path(path).exists():
                    self.add_file_item(path)
            elif item_data.get("type") == "sticky_note":
                self.add_sticky_note(
                    item_data.get("content", ""),
                    item_data.get("note_type", "text"),
                )

        # 還原拖曳模式（預設 copy，只有存 move 時才切換）
        if state.get("drag_mode") == "move" and self.drag_mode != "move":
            self.toggle_drag_mode()

        # 還原釘選狀態
        if state.get("is_pinned") and not self.is_pinned:
            self.toggle_pin()

        # 還原視窗位置（clamp 到可用螢幕範圍內）
        x = state.get("window_x")
        y = state.get("window_y")
        if x is not None and y is not None:
            screen_rect = QApplication.primaryScreen().availableGeometry()
            x = max(screen_rect.left(), min(x, screen_rect.right() - self.width()))
            y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height()))
            self.move(x, y)

        self.update_state()

    def get_display_name(self) -> str:
        if self.custom_name and self.custom_name.strip():
            name = self.custom_name.strip()
            # 若符合系統預設自動編號格式（「置物架 #N」或「Shelf #N」），動態跟隨目前語系
            if re.match(r"^(置物架|Shelf)\s*#\d+$", name, re.IGNORECASE):
                return t("shelf.default_name_format", id=self.shelf_id)
            return name
        return t("shelf.default_name_format", id=self.shelf_id)

    def retranslate_ui(self):
        """即時更新所有介面文字（響應語系切換）"""
        # 1. 頂部按鈕 ToolTips
        if hasattr(self, "btn_new"):
            self.btn_new.setToolTip(t("shelf.new_tip"))
        if hasattr(self, "btn_pin"):
            self.btn_pin.setToolTip(t("shelf.pin_tip"))
        if hasattr(self, "btn_settings"):
            self.btn_settings.setToolTip(t("shelf.settings_tip"))
        if hasattr(self, "btn_close"):
            self.btn_close.setToolTip(t("shelf.close_tip"))

        # 2. 中間空白區 Empty State
        if hasattr(self, "empty_title_label"):
            self.empty_title_label.setText(t("shelf.empty_title"))
        if hasattr(self, "empty_sub_label"):
            self.empty_sub_label.setText(t("shelf.empty_subtitle"))
        if hasattr(self, "btn_paste_main"):
            self.btn_paste_main.setText(t("shelf.paste_btn"))

        # 3. 底部按鈕文字與 ToolTips
        if hasattr(self, "btn_mode"):
            mode_text = t("shelf.mode_move") if self.drag_mode == "move" else t("shelf.mode_copy")
            self.btn_mode.setText(mode_text)
            self.btn_mode.setToolTip(t("shelf.mode_tip"))

        if hasattr(self, "btn_paste"):
            self.btn_paste.setText(t("shelf.paste_action"))
            self.btn_paste.setToolTip(t("shelf.paste_tip"))

        if hasattr(self, "btn_select_all"):
            self.btn_select_all.setText(t("shelf.select_all"))
            self.btn_select_all.setToolTip(t("shelf.select_all_tip"))

        if hasattr(self, "btn_zip"):
            self.btn_zip.setText("ZIP")
            self.btn_zip.setToolTip(t("shelf.zip_tip"))

        if hasattr(self, "btn_clear"):
            self.btn_clear.setText(t("shelf.clear"))
            self.btn_clear.setToolTip(t("shelf.clear_tip"))

        # 4. 刷新標題
        self.update_state()

    def prompt_rename(self):
        self.suppress_auto_hide = True
        try:
            default_name = t("shelf.default_name_format", id=self.shelf_id)
            current = self.custom_name if self.custom_name else default_name
            dialog = RenameDialog(
                current_name=current,
                default_name=default_name,
                theme_color=self.theme_color,
                parent=self
            )
            if dialog.exec() == QDialog.Accepted:
                new_name = dialog.new_name.strip()
                if not new_name or new_name == default_name:
                    self.custom_name = ""
                else:
                    self.custom_name = new_name
                self.update_state()
                if self.manager:
                    self.manager.save_session()
        finally:
            self.suppress_auto_hide = False

    def update_state(self):
        count = len(self.file_paths)
        display_name = self.get_display_name()
        self.title_label.setText(display_name)
        self.count_badge.setText(str(count))

        if count == 0:
            self.stack.setCurrentIndex(0)
            self.count_badge.setStyleSheet("""
                background-color: #F1F5F9;
                color: #64748B;
                font-size: 11px;
                font-weight: 600;
                padding: 1px 7px;
                border-radius: 10px;
            """)
            self.btn_select_all.setEnabled(False)
            self.btn_zip.setEnabled(False)
            self.btn_clear.setEnabled(False)
            self._set_btn_disabled_style(self.btn_select_all)
            self._set_btn_disabled_style(self.btn_zip)
            self._set_btn_disabled_style(self.btn_clear)
        else:
            self.stack.setCurrentIndex(1)
            self.count_badge.setStyleSheet(f"""
                background-color: #E0F2FE;
                color: {self.theme_color};
                font-size: 11px;
                font-weight: 700;
                padding: 1px 7px;
                border-radius: 10px;
            """)
            self.btn_select_all.setEnabled(True)
            self.btn_zip.setEnabled(True)
            self.btn_clear.setEnabled(True)
            self._restore_toolbar_btn_style(self.btn_select_all)
            self._restore_toolbar_btn_style(self.btn_zip)
            self._restore_clear_btn_style()

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


# 向下相容別名
DropShelfWidget = KyteShelfWidget
