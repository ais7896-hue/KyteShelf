import sys
import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, QUrl, QMimeData
from PySide6.QtGui import QDrag, QDesktopServices, QImage
from PySide6.QtWidgets import (
    QApplication, QListWidget, QMenu, QMessageBox
)


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
