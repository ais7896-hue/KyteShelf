import os
from pathlib import Path

from PySide6.QtCore import QObject, QFileSystemWatcher
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtWidgets import (
    QApplication, QMenu, QFileDialog, QSystemTrayIcon, QStyle
)

from ..config import ConfigManager
from ..license import LicenseManager
from ..session import SessionManager
from ..utils import get_resource_path
from ..i18n import t, i18n
from .hotkey_dialog import SettingsDialog
from .license_dialog import LicenseDialog
from .shelf_widget import KyteShelfWidget, DropShelfWidget


class ShelfManager(QObject):
    def __init__(self, config_manager: ConfigManager = None):
        super().__init__()
        self.config_manager = config_manager or ConfigManager()
        self.license_manager = LicenseManager.get_instance(self.config_manager)
        self.shelves = []
        self.next_id = 1
        self.current_theme = self.config_manager.config.get("theme_color", "#0284C7")
        self.colors = [self.current_theme, "#16A34A", "#EA580C", "#9333EA", "#E11D48", "#0D9488"]
        self.settings_dialog = None
        self.license_dialog = None

        self.config_manager.config_changed.connect(self.on_config_changed)
        self.license_manager.license_changed.connect(self.update_tray_license_status)
        i18n.language_changed.connect(self.on_language_changed)
        
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.watched_dir = ""
        self.known_files = set()

        self.session_manager = SessionManager(config_manager=self.config_manager)
        self.init_tray()
        self.restore_session()

    def on_language_changed(self, lang):
        """當語言切換時重建托盤選單並通知所有置物架重譯介面"""
        self.rebuild_tray_menu()
        for shelf in self.shelves:
            if hasattr(shelf, "retranslate_ui"):
                shelf.retranslate_ui()

    def on_config_changed(self, new_config):
        """當設定變更時即時套用主題色彩"""
        new_theme = new_config.get("theme_color", "#0284C7")
        self.current_theme = new_theme
        self.colors[0] = new_theme
        for shelf in self.shelves:
            shelf.update_theme_color(new_theme)

    def open_settings(self):
        """開啟偏好設定視窗"""
        if self.settings_dialog is not None:
            try:
                self.settings_dialog.close()
                self.settings_dialog.deleteLater()
            except RuntimeError:
                pass
            self.settings_dialog = None

        self.settings_dialog = SettingsDialog(self.config_manager)
        self.settings_dialog.destroyed.connect(lambda: setattr(self, "settings_dialog", None))
        self.settings_dialog.load_values()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def open_license_dialog(self):
        """開啟軟體授權管理視窗"""
        if self.license_dialog is not None:
            try:
                self.license_dialog.close()
                self.license_dialog.deleteLater()
            except RuntimeError:
                pass
            self.license_dialog = None

        self.license_dialog = LicenseDialog(self.license_manager)
        self.license_dialog.destroyed.connect(lambda: setattr(self, "license_dialog", None))
        self.license_dialog.refresh_ui_state()
        self.license_dialog.show()
        self.license_dialog.raise_()
        self.license_dialog.activateWindow()

    def update_tray_license_status(self):
        """更新托盤選單的授權狀態指示"""
        if hasattr(self, "act_license"):
            plan = self.license_manager.get_plan_type()
            if plan == "pro":
                self.act_license.setText(t("tray.license_status_pro"))
            elif plan == "trial":
                days = self.license_manager.get_trial_days_left()
                self.act_license.setText(t("tray.license_status_trial", days=days))
            else:
                self.act_license.setText(t("tray.license_status_free"))
        
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # 載入自訂圖示
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(QApplication.style().standardIcon(QStyle.SP_DirIcon))
            
        self.tray_icon.setToolTip(t("tray.tip"))
        self.rebuild_tray_menu()
        self.tray_icon.show()

    def rebuild_tray_menu(self):
        if not hasattr(self, "tray_icon") or self.tray_icon is None:
            return
        self.tray_icon.setToolTip(t("tray.tip"))
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
                color: #1E293B;
            }
            QMenu::item:selected {
                background-color: #F1F5F9;
                color: #0284C7;
            }
        """)
        
        act_show = self.tray_menu.addAction(t("tray.show_all"))
        act_show.triggered.connect(self.show_all)

        act_paste = self.tray_menu.addAction(t("tray.paste_clipboard"))
        act_paste.triggered.connect(self.paste_clipboard_to_shelf)

        self.shelves_menu = self.tray_menu.addMenu(t("tray.shelves_list"))
        self.tray_menu.aboutToShow.connect(self.update_tray_shelves_menu)
        self.tray_menu.addSeparator()

        act_settings = self.tray_menu.addAction(t("tray.preferences"))
        act_settings.triggered.connect(self.open_settings)

        self.act_license = self.tray_menu.addAction(t("tray.license_mgr"))
        self.act_license.triggered.connect(self.open_license_dialog)
        self.update_tray_license_status()
        self.tray_menu.addSeparator()
        
        act_watch = self.tray_menu.addAction(t("tray.watch_folder"))
        act_watch.triggered.connect(self.set_watch_folder)
        self.act_stop_watch = self.tray_menu.addAction(t("tray.stop_watch"))
        self.act_stop_watch.triggered.connect(self.stop_watch_folder)
        self.act_stop_watch.setVisible(bool(self.watched_dir))
        if self.watched_dir:
            self.act_stop_watch.setText(t("tray.stop_watch_named", name=Path(self.watched_dir).name))
        self.tray_menu.addSeparator()
        
        act_new = self.tray_menu.addAction(t("tray.summon_shelf"))
        act_new.triggered.connect(self.create_and_show_shelf)
        self.tray_menu.addSeparator()
        
        act_exit = self.tray_menu.addAction(t("tray.quit"))
        act_exit.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)

    def update_tray_shelves_menu(self):
        self.shelves_menu.clear()
        valid_shelves = [s for s in self.shelves if s.isVisible() or s.file_paths or s.is_pinned or s.custom_name]
        if not valid_shelves:
            act_none = self.shelves_menu.addAction(t("tray.no_shelves"))
            act_none.setEnabled(False)
            return

        for shelf in valid_shelves:
            display_name = shelf.get_display_name()
            count = len(shelf.file_paths)
            pin_mark = " 📌" if shelf.is_pinned else ""
            status_text = f"{display_name} ({count}){pin_mark}"
            
            sub_menu = self.shelves_menu.addMenu(status_text)
            
            act_locate = sub_menu.addAction(t("tray.locate_shelf"))
            act_locate.triggered.connect(lambda checked=False, s=shelf: self.locate_shelf(s))

            act_paste = sub_menu.addAction(t("tray.paste_to_shelf"))
            act_paste.triggered.connect(lambda checked=False, s=shelf: self.paste_to_specific_shelf(s))
            
            act_rename = sub_menu.addAction(t("tray.rename_shelf"))
            act_rename.triggered.connect(lambda checked=False, s=shelf: self.rename_shelf(s))
            
            sub_menu.addSeparator()
            act_clear = sub_menu.addAction(t("tray.clear_shelf"))
            act_clear.triggered.connect(lambda checked=False, s=shelf: s.clear_files())

    def locate_shelf(self, shelf):
        if not shelf.isVisible():
            shelf.popup_at(QCursor.pos().x(), QCursor.pos().y())
        else:
            shelf.show()
            shelf.raise_()
            shelf.activateWindow()

    def rename_shelf(self, shelf):
        self.locate_shelf(shelf)
        shelf.prompt_rename()

    def paste_to_specific_shelf(self, shelf):
        self.locate_shelf(shelf)
        shelf.paste_from_clipboard()

    def paste_clipboard_to_shelf(self):
        target_shelf = None
        for shelf in reversed(self.shelves):
            if shelf.isVisible():
                target_shelf = shelf
                break

        if not target_shelf:
            for shelf in self.shelves:
                if not shelf.isVisible():
                    target_shelf = shelf
                    break

        if not target_shelf:
            target_shelf = self.create_shelf()

        cursor_pos = QCursor.pos()
        target_shelf.popup_at(cursor_pos.x(), cursor_pos.y())
        added = target_shelf.paste_from_clipboard()
        if added > 0:
            self.tray_icon.showMessage(
                "KyteShelf",
                t("tray.pasted_notify", count=added, name=target_shelf.get_display_name()),
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.tray_icon.showMessage(
                "KyteShelf",
                t("tray.pasted_empty"),
                QSystemTrayIcon.Warning,
                2000
            )
        
    def create_shelf(self):
        color = self.colors[(self.next_id - 1) % len(self.colors)]
        shelf = KyteShelfWidget(manager=self, shelf_id=self.next_id, color=color)
        self.shelves.append(shelf)
        self.next_id += 1
        return shelf

    def restore_session(self):
        """從 session.json 還原上次工作階段，若無記錄則建立空置物架"""
        states = self.session_manager.load()
        if not states:
            self.create_shelf()
            return

        for state in states:
            shelf = self.create_shelf()
            # 沿用儲存的 shelf_id（維持「置物架 #N」編號一致性）
            saved_id = state.get("shelf_id")
            if saved_id is not None:
                shelf.shelf_id = saved_id
            shelf.restore_from_state(state)

            # 有內容、有自訂名稱或有釘選才自動顯示
            if shelf.file_paths or shelf.is_pinned or shelf.custom_name:
                shelf.show()
                shelf.raise_()

        # 確保 next_id 不與已還原的 ID 衝突
        if states:
            max_id = max(s.get("shelf_id", 1) for s in states)
            self.next_id = max(self.next_id, max_id + 1)

    def save_session(self):
        """序列化所有置物架狀態至 session.json"""
        self.session_manager.save(self.shelves)

    def create_and_show_shelf(self):
        # 檢查是否達到置物架上限
        visible_shelves = [s for s in self.shelves if s.isVisible()]
        can_create, reason = self.license_manager.can_create_shelf(len(visible_shelves))
        if not can_create:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(None, t("license.free_limit_title"), reason, QMessageBox.Ok)
            self.open_license_dialog()
            return

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
            # 晃動如果當前已經有開著的架子且達到上限，直接喚醒既有的第一個架子
            visible_shelves = [s for s in self.shelves if s.isVisible()]
            can_create, _ = self.license_manager.can_create_shelf(len(visible_shelves))
            if not can_create and visible_shelves:
                target_shelf = visible_shelves[0]
            else:
                target_shelf = self.create_shelf()
            
        target_shelf.popup_at(x, y)

    def set_watch_folder(self):
        can_watch, reason = self.license_manager.can_use_folder_watch()
        if not can_watch:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(None, t("license.pro_feature_title"), reason, QMessageBox.Ok)
            self.open_license_dialog()
            return

        folder = QFileDialog.getExistingDirectory(None, t("msg.select_watch_folder"))
        if folder:
            self.stop_watch_folder()
            self.watched_dir = folder
            self.watcher.addPath(folder)
            
            try:
                self.known_files = set(os.listdir(folder))
            except Exception:
                self.known_files = set()
                
            self.act_stop_watch.setVisible(True)
            self.act_stop_watch.setText(t("tray.stop_watch_named", name=Path(folder).name))
            self.tray_icon.showMessage("KyteShelf", t("tray.watch_started", name=Path(folder).name), QSystemTrayIcon.Information, 3000)

    def stop_watch_folder(self):
        if self.watched_dir:
            self.watcher.removePath(self.watched_dir)
            self.watched_dir = ""
            self.known_files.clear()
            self.act_stop_watch.setVisible(False)
            self.tray_icon.showMessage("KyteShelf", t("tray.watch_stopped"), QSystemTrayIcon.Information, 2000)
            
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
