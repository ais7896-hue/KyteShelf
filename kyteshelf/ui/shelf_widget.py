import os
import re
import html
import time
import zipfile
import tempfile
import subprocess
import urllib.request
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
        footer_layout.setSpacing(5)

        self.drag_mode = "copy"
        self.btn_mode = QPushButton(t("shelf.mode_copy"), self.container)
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

        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasImage():
            event.acceptProposedAction()
            self._apply_container_style(is_drag_hover=True)

    def dragLeaveEvent(self, event):
        self._apply_container_style(is_drag_hover=False)

    def _is_image_url(self, url_str: str) -> bool:
        """判定 URL 是否為常見圖片檔案格式"""
        try:
            path = QUrl(url_str).path().lower()
            image_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
            return any(path.endswith(ext) for ext in image_exts)
        except Exception:
            return False

    def _download_and_add_remote_image(self, url_str: str) -> bool:
        """嘗試下載遠端網頁圖片，自動保存為本機實體圖片檔並入架"""
        try:
            req = urllib.request.Request(
                url_str,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = resp.read()
                img = QImage()
                if img.loadFromData(data):
                    ts = int(time.time() * 1000)
                    parsed_path = Path(QUrl(url_str).path())
                    ext = parsed_path.suffix.lower()
                    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
                        ext = ".png"
                    img_path = self.temp_dir / f"web_image_{ts}{ext}"
                    with open(img_path, "wb") as f:
                        f.write(data)
                    self.add_file_item(str(img_path))
                    return True
        except Exception:
            pass
        return False

    def dropEvent(self, event):
        self.dragLeaveEvent(None)
        self._limit_warned_this_op = False
        # 忽略自身拖出的放開事件
        if event.source() == self.list_widget or event.source() == self or self.is_dragging_out:
            event.ignore()
            return

        mime = event.mimeData()
        has_handled = False

        # 1. 優先處理直接攜帶圖片點陣圖的拖曳數據（如某些瀏覽器或圖形軟體）
        if mime.hasImage():
            image = mime.imageData()
            if image and isinstance(image, QImage) and not image.isNull():
                ts = int(time.time() * 1000)
                img_path = self.temp_dir / f"drop_image_{ts}.png"
                if image.save(str(img_path), "PNG"):
                    self.add_file_item(str(img_path))
                    has_handled = True

        # 2. 檢查 URLs（本機檔案 vs 網址）
        if not has_handled and mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    has_handled = True  # 只要是本機實體檔案，標記已處理，絕對不可降級為純文字便箋
                    path = os.path.normpath(url.toLocalFile())
                    if path and path not in self.file_paths:
                        self.add_file_item(path)
                elif url.scheme() in ["http", "https"]:
                    url_str = url.toString()
                    # 判斷是否為網頁圖片 URL，若是則自動下載為實體圖片！
                    if self._is_image_url(url_str) and self._download_and_add_remote_image(url_str):
                        has_handled = True
                    else:
                        self.add_sticky_note(url_str, note_type="url")
                        has_handled = True

        # 3. 檢查 HTML 是否包含 <img> 圖片標籤
        if not has_handled and mime.hasHtml():
            m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', mime.html(), re.IGNORECASE)
            if m:
                if self._download_and_add_remote_image(m.group(1)):
                    has_handled = True

        # 4. 純文字降級處理
        if not has_handled and mime.hasText():
            text = mime.text().strip()
            if self._is_image_url(text) and self._download_and_add_remote_image(text):
                has_handled = True
            else:
                self.add_sticky_note(mime.text(), note_type="text")

        event.acceptProposedAction()

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

        # 3. 若無實體點陣圖，檢查 HTTP/HTTPS 網址（是否為遠端圖片網址）
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
