import sys
import os
import subprocess
import time
import zipfile
import tempfile
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
    QFileDialog, QMessageBox, QSystemTrayIcon, QStyle
)
from pynput import mouse, keyboard


# ==========================================
# 1. 跨執行緒通訊訊號
# ==========================================
class TriggerSignals(QObject):
    show_shelf = Signal(int, int)


# ==========================================
# 2. 全域輸入監聽器（晃動演算法 + 快捷鍵備援）
# ==========================================
class GlobalInputMonitor:
    def __init__(self, signals: TriggerSignals):
        self.signals = signals
        self.is_left_pressed = False
        self.history = deque(maxlen=20)
        self.last_trigger_time = 0
        self.current_cursor = (300, 300)

    def on_click(self, x, y, button, pressed):
        self.current_cursor = (int(x), int(y))
        if button == mouse.Button.left:
            self.is_left_pressed = pressed
            if not pressed:
                self.history.clear()

    def on_move(self, x, y):
        self.current_cursor = (int(x), int(y))
        if not self.is_left_pressed:
            return

        now = time.time()
        if now - self.last_trigger_time < 1.0:
            return

        self.history.append((x, now))
        recent = [p for p in self.history if now - p[1] <= 0.45]
        if len(recent) < 4:
            return

        reversals = 0
        last_dir = 0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            if abs(dx) > 10:
                cur_dir = 1 if dx > 0 else -1
                if last_dir != 0 and cur_dir != last_dir:
                    reversals += 1
                last_dir = cur_dir

        if reversals >= 2:
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

        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+`': self.trigger_by_hotkey
        })
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()


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
        self.btn_select_all.setStyleSheet("border: none; color: #0284C7; font-size: 12px; margin: 0 2px;")

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
    def __init__(self):
        super().__init__()
        self.shelves = []
        self.next_id = 1
        self.colors = ["#0284C7", "#16A34A", "#EA580C", "#9333EA", "#E11D48", "#0D9488"]
        
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.watched_dir = ""
        self.known_files = set()
        
        self.init_tray()
        self.create_shelf()
        
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

    manager = ShelfManager()
    signals = TriggerSignals()
    signals.show_shelf.connect(manager.on_shake)

    monitor = GlobalInputMonitor(signals)
    monitor.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()