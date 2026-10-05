import webbrowser
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QApplication
)

from ..license import LicenseManager
from ..i18n import t


class LicenseDialog(QDialog):
    SHOPEE_URL = "https://shopee.tw"  # 可替換為使用者的實際蝦皮賣場網址
    license_updated = Signal()

    def __init__(self, license_manager: LicenseManager = None, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager or LicenseManager.get_instance()
        self.setWindowTitle(t("license.dialog_title"))
        self.setFixedSize(500, 555)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.license_manager.license_changed.connect(self.refresh_ui_state)
        self.init_ui()
        self.refresh_ui_state()

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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # 頂部標題區
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.icon_badge = QLabel("💎", self)
        self.icon_badge.setStyleSheet("font-size: 28px;")
        header_layout.addWidget(self.icon_badge)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self.title_label = QLabel(t("license.pro_title"), self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #0F172A;")
        self.subtitle_label = QLabel(t("license.pro_subtitle"), self)
        self.subtitle_label.setStyleSheet("font-size: 12px; color: #64748B;")
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 狀態卡片 (動態更新)
        self.status_card = QFrame(self)
        self.status_card.setObjectName("StatusCard")
        self.status_layout = QVBoxLayout(self.status_card)
        self.status_layout.setContentsMargins(16, 14, 16, 14)
        self.status_layout.setSpacing(8)

        self.status_badge = QLabel(self.status_card)
        self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.status_layout.addWidget(self.status_badge)

        self.status_desc = QLabel(self.status_card)
        self.status_desc.setWordWrap(True)
        self.status_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        self.status_layout.addWidget(self.status_desc)

        layout.addWidget(self.status_card)

        # 輸入序號區域 (未啟用時顯示)
        self.input_card = QFrame(self)
        self.input_card.setStyleSheet("""
            QFrame#InputCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
                padding: 14px;
            }
        """)
        self.input_card.setObjectName("InputCard")
        input_layout = QVBoxLayout(self.input_card)
        input_layout.setContentsMargins(14, 14, 14, 14)
        input_layout.setSpacing(10)

        key_label = QLabel(t("license.input_key_title"), self.input_card)
        key_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")
        input_layout.addWidget(key_label)

        self.key_input = QLineEdit(self.input_card)
        self.key_input.setPlaceholderText(t("license.input_placeholder"))
        self.key_input.setAlignment(Qt.AlignCenter)
        self.key_input.setFixedHeight(40)
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFC;
                border: 1.5px solid #CBD5E1;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                font-family: 'Consolas', 'Courier New', monospace;
                letter-spacing: 1px;
                color: #0F172A;
                padding: 0 10px;
            }
            QLineEdit:focus {
                border-color: #0284C7;
                background-color: #FFFFFF;
            }
        """)
        self.key_input.textChanged.connect(self._on_key_text_changed)
        input_layout.addWidget(self.key_input)

        # 錯誤/成功訊息提示
        self.msg_label = QLabel("", self.input_card)
        self.msg_label.setWordWrap(True)
        self.msg_label.setAlignment(Qt.AlignCenter)
        self.msg_label.setStyleSheet("font-size: 12px; font-weight: 500; min-height: 18px;")
        input_layout.addWidget(self.msg_label)

        # 立即啟用按鈕
        self.btn_activate = QPushButton(t("license.activate_btn"), self.input_card)
        self.btn_activate.setFixedHeight(40)
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QPushButton:disabled {
                background-color: #94A3B8;
            }
        """)
        self.btn_activate.clicked.connect(self.handle_activate)
        input_layout.addWidget(self.btn_activate)

        layout.addWidget(self.input_card)

        # 換機解綁按鈕 (已啟用時顯示)
        self.btn_deactivate = QPushButton(t("license.btn_deactivate"), self)
        self.btn_deactivate.setFixedHeight(38)
        self.btn_deactivate.setCursor(Qt.PointingHandCursor)
        self.btn_deactivate.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
                border-color: #EF4444;
            }
        """)
        self.btn_deactivate.clicked.connect(self.handle_deactivate)
        layout.addWidget(self.btn_deactivate)

        # 機器碼資訊與客服協助列
        hw_card = QFrame(self)
        hw_card.setStyleSheet("""
            QFrame {
                background-color: #F1F5F9;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        hw_layout = QHBoxLayout(hw_card)
        hw_layout.setContentsMargins(10, 6, 10, 6)
        hw_layout.setSpacing(8)

        hw_title = QLabel(t("license.hw_title"), hw_card)
        hw_title.setStyleSheet("font-size: 11px; color: #64748B;")
        hw_layout.addWidget(hw_title)

        self.guid_label = QLabel(self.license_manager.machine_id[:16] + "...", hw_card)
        self.guid_label.setStyleSheet("font-size: 11px; font-family: monospace; font-weight: bold; color: #334155;")
        self.guid_label.setToolTip(self.license_manager.machine_id)
        hw_layout.addWidget(self.guid_label)

        hw_layout.addStretch()

        btn_copy_guid = QPushButton(t("license.btn_copy_hw"), hw_card)
        btn_copy_guid.setCursor(Qt.PointingHandCursor)
        btn_copy_guid.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 11px;
                color: #0284C7;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #0369A1;
            }
        """)
        btn_copy_guid.clicked.connect(self.copy_machine_guid)
        hw_layout.addWidget(btn_copy_guid)

        layout.addWidget(hw_card)

        # 底部連結與關閉
        footer_layout = QHBoxLayout()
        self.btn_buy = QPushButton(t("license.btn_buy_shopee"), self)
        self.btn_buy.setCursor(Qt.PointingHandCursor)
        self.btn_buy.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 12px;
                font-weight: bold;
                color: #EA580C;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #C2410C;
            }
        """)
        self.btn_buy.clicked.connect(lambda: webbrowser.open(self.SHOPEE_URL))
        footer_layout.addWidget(self.btn_buy)

        footer_layout.addStretch()

        btn_close = QPushButton(t("common.close"), self)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(70, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-size: 12px;
                color: #334155;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        layout.addLayout(footer_layout)

        # 客服與技術支援列（預填 mailto 範本）
        mailto_url = (
            "mailto:support@aisming.com?subject=%5BSupport%5D%20KyteShelf%20License%20Inquiry"
        )
        support_lbl = QLabel(
            f"{t('license.support_footer')} <a href='{mailto_url}' style='color: #0284C7; text-decoration: underline;'>support@aisming.com</a>"
        )
        support_lbl.setOpenExternalLinks(True)
        support_lbl.setStyleSheet("font-size: 11px; color: #64748B; padding-top: 4px;")
        support_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(support_lbl)

    def _on_key_text_changed(self, text: str):
        """自動轉換大寫"""
        upper_text = text.upper()
        if text != upper_text:
            pos = self.key_input.cursorPosition()
            self.key_input.blockSignals(True)
            self.key_input.setText(upper_text)
            self.key_input.setCursorPosition(pos)
            self.key_input.blockSignals(False)

    def refresh_ui_state(self):
        """依據目前啟用狀態切換顯示元件與樣式"""
        info = self.license_manager.get_license_info()
        plan_type = info.get("plan_type", "free")
        trial_days = info.get("trial_days_left", 0)

        if plan_type == "pro":
            self.icon_badge.setText("✨")
            self.status_card.setStyleSheet("""
                QFrame#StatusCard {
                    background-color: #F0FDF4;
                    border: 1.5px solid #86EFAC;
                    border-radius: 10px;
                }
            """)
            self.status_badge.setText(t("license.status_pro_badge"))
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #15803D;")
            
            masked = info.get("masked_key", "KYTE-****-****-****")
            self.status_desc.setText(t("license.status_pro_desc", key=masked))

            self.input_card.setVisible(False)
            self.btn_deactivate.setVisible(True)
            self.btn_buy.setVisible(False)
            self.adjustSize()
        elif plan_type == "trial":
            self.icon_badge.setText("⏳")
            self.status_card.setStyleSheet("""
                QFrame#StatusCard {
                    background-color: #EFF6FF;
                    border: 1.5px solid #93C5FD;
                    border-radius: 10px;
                }
            """)
            self.status_badge.setText(t("license.status_trial_badge", days=trial_days))
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #1D4ED8;")
            self.status_desc.setText(t("license.status_trial_desc"))

            self.input_card.setVisible(True)
            self.btn_deactivate.setVisible(False)
            self.btn_buy.setVisible(True)
            self.key_input.clear()
            self.msg_label.clear()
            self.adjustSize()
        else:
            self.icon_badge.setText("💎")
            self.status_card.setStyleSheet("""
                QFrame#StatusCard {
                    background-color: #FFFBEB;
                    border: 1.5px solid #FDE68A;
                    border-radius: 10px;
                }
            """)
            self.status_badge.setText(t("license.status_free_badge"))
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #B45309;")
            self.status_desc.setText(t("license.status_free_desc"))

            self.input_card.setVisible(True)
            self.btn_deactivate.setVisible(False)
            self.btn_buy.setVisible(True)
            self.key_input.clear()
            self.msg_label.clear()
            self.adjustSize()

        self.license_updated.emit()

    def handle_activate(self):
        key = self.key_input.text().strip()
        if not key:
            self.msg_label.setText(t("license.empty_key_warn"))
            self.msg_label.setStyleSheet("color: #DC2626; font-weight: bold;")
            return

        self.btn_activate.setEnabled(False)
        self.btn_activate.setText(t("license.connecting_btn"))
        self.msg_label.setText(t("license.connecting"))
        self.msg_label.setStyleSheet("color: #0284C7; font-weight: 500;")
        QApplication.processEvents()

        # 連線啟用
        success, msg = self.license_manager.activate_online(key)
        
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText(t("license.activate_btn"))

        if success:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color: #16A34A; font-weight: bold;")
            QTimer.singleShot(800, self.refresh_ui_state)
            QMessageBox.information(self, t("license.congrats_title"), t("license.congrats_msg"))
        else:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color: #DC2626; font-weight: bold;")

    def handle_deactivate(self):
        reply = QMessageBox.question(
            self,
            t("license.deactivate_confirm_title"),
            t("license.deactivate_confirm_msg"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self.license_manager.deactivate_online()
            QMessageBox.information(self, t("common.info"), msg)
            self.refresh_ui_state()

    def copy_machine_guid(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.license_manager.machine_id)
        QMessageBox.information(
            self,
            t("license.guid_copied_title"),
            t("license.guid_copied_msg", guid=self.license_manager.machine_id)
        )
