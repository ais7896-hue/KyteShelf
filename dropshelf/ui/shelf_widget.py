import os
import time
import zipfile
import tempfile
import subprocess
from pathlib import Path

from PySide6.QtCore import (
    Qt, QSize, QEvent, QFileInfo, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QIcon, QPixmap, QColor
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidgetItem, QLabel, QPushButton, 
    QFileIconProvider, QGraphicsDropShadowEffect, 
    QFileDialog, QMessageBox
)

from .shelf_list import ShelfFileList


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
