import sys
import os
import subprocess
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, QUrl, QMimeData, QRect, QEvent, QTimer
from PySide6.QtGui import (
    QDrag, QDesktopServices, QImage, QCursor, QKeySequence, 
    QPainter, QPen, QBrush, QColor
)
from PySide6.QtWidgets import (
    QApplication, QListWidget, QMenu, QMessageBox, QStyledItemDelegate, QToolTip
)

from .sticky_note import StickyNoteWindow


class ShelfItemDelegate(QStyledItemDelegate):
    """自訂 Delegate：在項目右側繪製精緻的單獨刪除 ✕ 按鈕"""
    def __init__(self, parent_list):
        super().__init__(parent_list)
        self.list_widget = parent_list

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)

        row = index.row()
        item = self.list_widget.item(row)
        is_hovered_item = (self.list_widget.hovered_row == row)
        is_selected = item.isSelected() if item else False

        # 當滑鼠懸停於此項目，或此項目已被選取時，顯示右側刪除按鈕
        if is_hovered_item or is_selected:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)

            btn_rect = self.list_widget.get_close_btn_rect(option.rect)
            is_btn_hovered = (self.list_widget.hovered_close_btn_row == row)

            if is_btn_hovered:
                bg_color = QColor("#FEE2E2")  # 淺紅色背景
                fg_color = QColor("#EF4444")  # 紅色 ✕
            else:
                bg_color = QColor("#F1F5F9")  # 淺灰色背景
                fg_color = QColor("#94A3B8")  # 灰色 ✕

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg_color))
            painter.drawEllipse(btn_rect)

            # 繪製 ✕ 符號
            painter.setPen(QPen(fg_color, 1.6, Qt.SolidLine, Qt.RoundCap))
            m = 5
            painter.drawLine(
                btn_rect.left() + m, btn_rect.top() + m,
                btn_rect.right() - m, btn_rect.bottom() - m
            )
            painter.drawLine(
                btn_rect.right() - m, btn_rect.top() + m,
                btn_rect.left() + m, btn_rect.bottom() - m
            )
            painter.restore()


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

        self.hovered_row = -1
        self.hovered_close_btn_row = -1
        self.setMouseTracking(True)
        self.setItemDelegate(ShelfItemDelegate(self))

        self.drag_start_pos = None
        self._reorder_mode = False
        self._reorder_current_row = -1
        self.drag_start_row = -1

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
                padding: 4px 28px 4px 8px;
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
        note_data = item.data(Qt.UserRole + 1)
        if note_data and isinstance(note_data, dict) and note_data.get("type") == "sticky_note":
            self.show_sticky_note(item, note_data)
            return

        path_str = item.data(Qt.UserRole)
        if sys.platform == "win32":
            os.startfile(path_str)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))

    def show_sticky_note(self, item, note_data):
        """開啟獨立浮動的自黏便箋視窗"""
        note_win = StickyNoteWindow(
            content=note_data.get("content", ""),
            note_type=note_data.get("note_type", "text")
        )

        def on_content_updated(new_content):
            note_data["content"] = new_content
            item.setData(Qt.UserRole + 1, note_data)

            note_type = note_data.get("note_type", "text")
            if note_type == "url":
                title = new_content.replace("https://", "").replace("http://", "").rstrip("/")
                if len(title) > 30:
                    title = title[:27] + "..."
                item.setText(f"🔖 {title}")
            else:
                first_line = new_content.strip().splitlines()[0] if new_content.strip().splitlines() else ""
                if len(first_line) > 25:
                    first_line = first_line[:22] + "..."
                item.setText(f"📝 {first_line}" if first_line else "📝 自黏便箋")
            item.setToolTip(f"{new_content}\n\n💡 雙擊開啟自黏便箋｜拖出直接貼入文字")

            filepath = note_data.get("filepath")
            if filepath:
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        if note_type == "url":
                            f.write("[InternetShortcut]\n")
                            f.write(f"URL={new_content}\n")
                        else:
                            f.write(new_content)
                except Exception:
                    pass

        note_win.content_updated.connect(on_content_updated)

        cursor_pos = QCursor.pos()
        note_win.move(cursor_pos.x() + 15, cursor_pos.y() - 20)
        note_win.show()
        note_win.raise_()
        note_win.activateWindow()

        if self.shelf_window:
            if not hasattr(self.shelf_window, "active_notes"):
                self.shelf_window.active_notes = []
            self.shelf_window.active_notes.append(note_win)

    def get_close_btn_rect(self, item_rect: QRect) -> QRect:
        """計算單獨項目右側 ✕ 刪除按鈕的繪製幾何區域 (18x18)"""
        btn_size = 18
        x = item_rect.right() - btn_size - 8
        y = item_rect.top() + (item_rect.height() - btn_size) // 2
        return QRect(x, y, btn_size, btn_size)

    def get_close_btn_hit_rect(self, item_rect: QRect) -> QRect:
        """計算單獨項目右側 ✕ 的點擊判定區（寬度 36px，高度覆蓋整個項目），保證隨手一點即中，絕不漏按"""
        width = 36
        return QRect(item_rect.right() - width, item_rect.top(), width, item_rect.height())

    def event(self, event):
        # 當滑鼠懸停在 ✕ 刪除按鈕上方時，只顯示精簡提示，避免彈出佔據螢幕的大卡片預覽
        if event.type() == QEvent.ToolTip:
            pos = event.pos()
            item = self.itemAt(pos)
            if item:
                hit_rect = self.get_close_btn_hit_rect(self.visualItemRect(item))
                if hit_rect.contains(pos):
                    QToolTip.showText(event.globalPos(), "移除此項目", self)
                    return True
        return super().event(event)

    def leaveEvent(self, event):
        self.hovered_row = -1
        self.hovered_close_btn_row = -1
        self.setCursor(Qt.ArrowCursor)
        self.viewport().update()
        super().leaveEvent(event)

    def delete_item(self, item):
        """單獨刪除指定項目（0 延遲即時響應）"""
        if not item:
            return
        # 立即關閉任何殘留的懸浮預覽卡片
        QToolTip.hideText()
        path_str = item.data(Qt.UserRole)
        if self.shelf_window:
            if path_str in self.shelf_window.file_paths:
                self.shelf_window.file_paths.remove(path_str)
            self.shelf_window._delete_temp_if_sticky(path_str)
        self.takeItem(self.row(item))
        self.hovered_row = -1
        self.hovered_close_btn_row = -1
        self.setCursor(Qt.ArrowCursor)
        self.viewport().update()
        if self.shelf_window:
            self.shelf_window.update_state()
            if hasattr(self.shelf_window, "show_temporary_hint"):
                self.shelf_window.show_temporary_hint("🗑️ 已從置物架移除項目")
            if self.shelf_window.manager:
                # 存檔透過事件循環非同步執行，完全避免磁碟 I/O 阻塞主執行緒造成卡頓
                QTimer.singleShot(0, self.shelf_window.manager.save_session)

    def delete_selected_items(self):
        """批次或單獨刪除所有目前選取的項目（支援 Delete/Backspace 鍵）"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
        QToolTip.hideText()
        count = len(selected_items)
        for item in selected_items:
            path_str = item.data(Qt.UserRole)
            if self.shelf_window:
                if path_str in self.shelf_window.file_paths:
                    self.shelf_window.file_paths.remove(path_str)
                self.shelf_window._delete_temp_if_sticky(path_str)
            self.takeItem(self.row(item))

        self.hovered_row = -1
        self.hovered_close_btn_row = -1
        self.setCursor(Qt.ArrowCursor)
        self.viewport().update()
        if self.shelf_window:
            self.shelf_window.update_state()
            if hasattr(self.shelf_window, "show_temporary_hint"):
                self.shelf_window.show_temporary_hint(f"🗑️ 已從置物架移除 {count} 個項目")
            if self.shelf_window.manager:
                QTimer.singleShot(0, self.shelf_window.manager.save_session)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
            event.accept()
            return
        elif event.matches(QKeySequence.Paste) or (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V):
            if self.shelf_window and hasattr(self.shelf_window, "paste_from_clipboard"):
                self.shelf_window.paste_from_clipboard()
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            # 點擊右側 ✕ 按鈕（命中擴大判定區 36px）時直接觸發單獨刪除
            if item:
                hit_rect = self.get_close_btn_hit_rect(self.visualItemRect(item))
                if hit_rect.contains(pos):
                    QToolTip.hideText()
                    self.delete_item(item)
                    event.accept()
                    return

            self.drag_start_pos = pos
            self.drag_start_row = self.row(item) if item else -1
            self._reorder_mode = False
            self._reorder_current_row = -1
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        local_pos = event.position().toPoint()

        # 更新懸停位置以即時重繪 ✕ 刪除按鈕
        item = self.itemAt(local_pos)
        new_hover_row = self.row(item) if item else -1
        new_close_row = -1
        if item:
            if self.get_close_btn_hit_rect(self.visualItemRect(item)).contains(local_pos):
                new_close_row = new_hover_row

        # 懸停在 ✕ 上時切換為手指指針游標，提升互動靈敏回饋
        if new_close_row != -1:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if new_hover_row != self.hovered_row or new_close_row != self.hovered_close_btn_row:
            self.hovered_row = new_hover_row
            self.hovered_close_btn_row = new_close_row
            self.viewport().update()

        if not (event.buttons() & Qt.LeftButton) or not self.drag_start_pos:
            super().mouseMoveEvent(event)
            return

        local_pos = event.position().toPoint()
        delta = local_pos - self.drag_start_pos
        dx = abs(delta.x())
        dy = abs(delta.y())

        if delta.manhattanLength() < QApplication.startDragDistance():
            return

        is_inside = self.rect().contains(local_pos)
        selected_items = self.selectedItems()
        if not selected_items:
            super().mouseMoveEvent(event)
            return

        # 多選項目直接進入外部拖曳
        if len(selected_items) > 1:
            self._reorder_mode = False
            self.unsetCursor()
            self._start_external_drag(selected_items)
            return

        # 尚未進入排序模式時：判斷是要「列表內上下排序」還是「往外拖曳」
        if not self._reorder_mode:
            # 只有當位移仍在列表內、且垂直移動明顯大於水平位移 (dy > dx * 1.2) 時才進入排序模式
            if is_inside and self.drag_start_row >= 0 and dy > dx * 1.2:
                self._reorder_mode = True
                self._reorder_current_row = self.drag_start_row
                self.setCursor(Qt.SizeVerCursor)
            else:
                # 橫向拖拉或直接拖出邊界 -> 直接啟動外部拖曳！
                self._start_external_drag(selected_items)
                return

        # 若已處於排序模式：
        if self._reorder_mode:
            # 一旦使用者將滑鼠移出列表，或產生明顯橫向拖出意圖 (dx > 30) -> 立即無縫切換為外部拖曳！
            if not is_inside or dx > 30:
                self._reorder_mode = False
                self._reorder_current_row = -1
                self.drag_start_row = -1
                self.unsetCursor()
                self._start_external_drag(selected_items)
                return

            # 在列表內部即時交換順序
            target_row = self._get_target_row(local_pos.y())
            while self._reorder_current_row > target_row and self._reorder_current_row > 0:
                self._swap_rows(self._reorder_current_row - 1, self._reorder_current_row)
                self._reorder_current_row -= 1
            while self._reorder_current_row < target_row and self._reorder_current_row < self.count() - 1:
                self._swap_rows(self._reorder_current_row, self._reorder_current_row + 1)
                self._reorder_current_row += 1
            self.setCurrentRow(self._reorder_current_row)
            return

    def _start_external_drag(self, selected_items):
        """執行系統級拖曳，將檔案或文字拖放至外部應用程式"""
        if not selected_items:
            return

        if self.shelf_window:
            self.shelf_window.is_dragging_out = True

        urls = [QUrl.fromLocalFile(item.data(Qt.UserRole)) for item in selected_items]
        mime_data = QMimeData()
        mime_data.setUrls(urls)

        # 若選取項目包含自黏標籤，設置文字 MIME，拖入編輯器/網頁時可直接貼入內容
        note_texts = []
        for item in selected_items:
            nd = item.data(Qt.UserRole + 1)
            if nd and isinstance(nd, dict) and nd.get("type") == "sticky_note":
                note_texts.append(nd.get("content", ""))
        if note_texts:
            mime_data.setText("\n\n".join(note_texts))

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
        target = drag.target()

        if self.shelf_window:
            self.shelf_window.is_dragging_out = False
        self.drag_start_pos = None

        # 雙重防護：若在置物架視窗內部放開（尚未完全拖出），絕不刪除項目
        cursor_pos = QCursor.pos()
        is_dropped_inside = False
        if target and (target == self or (self.shelf_window and (target == self.shelf_window or self.shelf_window.isAncestorOf(target)))):
            is_dropped_inside = True
        elif self.shelf_window and self.shelf_window.frameGeometry().contains(cursor_pos):
            is_dropped_inside = True

        if is_dropped_inside:
            return

        if action != Qt.IgnoreAction:
            for item in selected_items:
                path = item.data(Qt.UserRole)
                self.shelf_window._delete_temp_if_sticky(path)
                if path in self.shelf_window.file_paths:
                    self.shelf_window.file_paths.remove(path)
                self.takeItem(self.row(item))

            self.shelf_window.update_state()
            if self.shelf_window.manager:
                self.shelf_window.manager.save_session()

            if len(self.shelf_window.file_paths) == 0 and not self.shelf_window.is_pinned:
                self.shelf_window.hide()

    def mouseReleaseEvent(self, event):
        if self._reorder_mode:
            self._reorder_mode = False
            self._reorder_current_row = -1
            self.drag_start_row = -1
            self.unsetCursor()
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _get_target_row(self, cursor_y: int) -> int:
        """依指標 Y 計算目標列數，輸出範圍 [0, count-1]"""
        for i in range(self.count()):
            rect = self.visualItemRect(self.item(i))
            if cursor_y < rect.center().y():
                return i
        return max(0, self.count() - 1)

    def _swap_rows(self, row_a: int, row_b: int):
        """交換兩個列數的項目，同步更新 file_paths"""
        if row_a == row_b:
            return
        if row_a > row_b:
            row_a, row_b = row_b, row_a
        # 先取出大列數，再取小列數，避免移除後下標偏移
        item_b = self.takeItem(row_b)
        item_a = self.takeItem(row_a)
        self.insertItem(row_a, item_b)
        self.insertItem(row_b, item_a)
        # 同步 file_paths
        if self.shelf_window:
            fps = self.shelf_window.file_paths
            if 0 <= row_a < len(fps) and 0 <= row_b < len(fps):
                fps[row_a], fps[row_b] = fps[row_b], fps[row_a]

    def open_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
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
            act_paste = menu.addAction("📋 貼上剪貼簿內容 (Ctrl+V)")
            act_rename = menu.addAction("✏️ 重新命名置物架...")
            menu.addSeparator()
            is_pinned = getattr(self.shelf_window, "is_pinned", False)
            act_pin = menu.addAction("📌 取消釘選" if is_pinned else "📌 釘選視窗")
            act_clear = menu.addAction("🗑️ 清空置物架")

            action = menu.exec(self.mapToGlobal(pos))
            if action == act_paste and hasattr(self.shelf_window, "paste_from_clipboard"):
                self.shelf_window.paste_from_clipboard()
            elif action == act_rename and hasattr(self.shelf_window, "prompt_rename"):
                self.shelf_window.prompt_rename()
            elif action == act_pin and hasattr(self.shelf_window, "toggle_pin"):
                self.shelf_window.toggle_pin()
            elif action == act_clear and hasattr(self.shelf_window, "clear_files"):
                self.shelf_window.clear_files()
            return

        path_str = item.data(Qt.UserRole)
        note_data = item.data(Qt.UserRole + 1)
        is_sticky = note_data and isinstance(note_data, dict) and note_data.get("type") == "sticky_note"

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

        act_open_note = None
        act_copy_content = None
        act_open_browser = None

        if is_sticky:
            act_open_note = menu.addAction("📝 開啟自黏便箋")
            if note_data.get("note_type") == "url":
                act_copy_content = menu.addAction("📋 複製網址")
                act_open_browser = menu.addAction("🌐 在預設瀏覽器開啟")
            else:
                act_copy_content = menu.addAction("📋 複製文字內容")
            menu.addSeparator()

        act_paste = menu.addAction("📋 貼上剪貼簿內容 (Ctrl+V)")
        menu.addSeparator()

        act_show = menu.addAction("在檔案總管中顯示")
        act_copy_path = menu.addAction("複製路徑")
        act_zip = menu.addAction("全部打包成 ZIP")
        
        act_attach_outlook = None
        if not is_sticky:
            act_attach_outlook = menu.addAction("附加到目前 Outlook 郵件")
        
        selected_paths = [item.data(Qt.UserRole) for item in self.selectedItems()]
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        is_all_images = (not is_sticky) and all(Path(p).suffix.lower() in image_extensions for p in selected_paths)

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
        sel_count = len(self.selectedItems())
        del_label = f"🗑️ 從置物架移除 ({sel_count} 項) (Delete)" if sel_count > 1 else "🗑️ 從置物架移除 (Delete)"
        act_delete = menu.addAction(del_label)

        action = menu.exec(self.mapToGlobal(pos))
        if act_open_note and action == act_open_note:
            self.show_sticky_note(item, note_data)
        elif act_copy_content and action == act_copy_content:
            QApplication.clipboard().setText(note_data.get("content", ""))
        elif act_open_browser and action == act_open_browser:
            url = note_data.get("content", "").strip()
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                webbrowser.open(url)
        elif action == act_paste and hasattr(self.shelf_window, "paste_from_clipboard"):
            self.shelf_window.paste_from_clipboard()
        elif action == act_show:
            norm_path = os.path.normpath(path_str)
            subprocess.run(f'explorer /select,"{norm_path}"')
        elif action == act_copy_path:
            QApplication.clipboard().setText(path_str)
        elif action == act_zip:
            self.shelf_window.zip_all_files()
        elif act_attach_outlook and action == act_attach_outlook:
            self.attach_to_outlook()
        elif action == act_img_resize_50:
            self.process_images(self.selectedItems(), "resize_50")
        elif action == act_img_convert_jpg:
            self.process_images(self.selectedItems(), "convert_jpg")
        elif action == act_img_convert_png:
            self.process_images(self.selectedItems(), "convert_png")
        elif action == act_delete:
            self.delete_selected_items()

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
