import webbrowser
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QApplication
)

from ..license import LicenseManager


class LicenseDialog(QDialog):
    SHOPEE_URL = "https://shopee.tw"  # 可替換為使用者的實際蝦皮賣場網址

    def __init__(self, license_manager: LicenseManager = None, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager or LicenseManager.get_instance()
        self.setWindowTitle("KyteShelf 軟體授權與專業版開通")
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
        self.title_label = QLabel("KyteShelf 專業版授權", self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #0F172A;")
        self.subtitle_label = QLabel("終身買斷制・單組序號支援 2 台電腦同時啟用", self)
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

        key_label = QLabel("輸入授權序號：", self.input_card)
        key_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")
        input_layout.addWidget(key_label)

        self.key_input = QLineEdit(self.input_card)
        self.key_input.setPlaceholderText("例：KYTE-XXXX-XXXX-XXXX")
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
        self.btn_activate = QPushButton("立即驗證並開通", self.input_card)
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
        self.btn_deactivate = QPushButton("🔄 解除此電腦綁定 (更換電腦釋放名額)", self)
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

        hw_title = QLabel("本機識別碼：", hw_card)
        hw_title.setStyleSheet("font-size: 11px; color: #64748B;")
        hw_layout.addWidget(hw_title)

        self.guid_label = QLabel(self.license_manager.machine_id[:16] + "...", hw_card)
        self.guid_label.setStyleSheet("font-size: 11px; font-family: monospace; font-weight: bold; color: #334155;")
        self.guid_label.setToolTip(self.license_manager.machine_id)
        hw_layout.addWidget(self.guid_label)

        hw_layout.addStretch()

        btn_copy_guid = QPushButton("複製完整識別碼", hw_card)
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
        self.btn_buy = QPushButton("🛒 前往蝦皮官方賣場購買序號 (NT$ 399)", self)
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

        btn_close = QPushButton("關閉", self)
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
            "mailto:support@aisming.com?subject=%5B%E5%95%8F%E9%A1%8C%E5%9B%9E%E5%A0%B1%5D%20KyteShelf%20%E4%BD%BF%E7%94%A8%E8%AB%AE%E8%A9%A2%20-%20%E8%A8%82%E5%96%AE/%E5%BA%8F%E8%99%9F%EF%BC%9A(%E8%8B%A5%E6%9C%89%E8%AB%8B%E5%A1%AB%E5%AF%AB)"
            "&body=1.%20%E4%BD%9C%E6%A5%AD%E7%B3%BB%E7%B5%B1%E7%89%88%E6%9C%AC%20(%E4%BE%8B%E5%A6%82%20Win11%2023H2)%EF%BC%9A%0A"
            "2.%20%E7%99%BC%E7%94%9F%E7%9A%84%E5%95%8F%E9%A1%8C%E6%8F%8F%E8%BF%B0%EF%BC%9A%0A"
            "3.%20%E6%88%AA%E5%9C%96%E6%88%96%E9%8C%AF%E8%AA%A4%E8%A8%8A%E6%81%AF%EF%BC%9A%0A"
        )
        support_lbl = QLabel(
            f"技術支援與售後聯絡：<a href='{mailto_url}' style='color: #0284C7; text-decoration: underline;'>support@aisming.com</a>"
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
            self.status_badge.setText("🟢 已開通永久專業版 (Pro Lifetime)")
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #15803D;")
            
            masked = info.get("masked_key", "KYTE-****-****-****")
            self.status_desc.setText(
                f"感謝您的支持！授權序號：<b>{masked}</b><br>"
                "本電腦已獲得正版憑證簽署，日常運行 100% 離線可用。單組序號最多可同時啟用 2 台電腦。"
            )

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
            self.status_badge.setText(f"🔵 專業版全功能試用中（剩餘 {trial_days} 天）")
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #1D4ED8;")
            self.status_desc.setText(
                f"您目前享有專業版全部無限制功能（無限置物架、無限檔案容量、ZIP 打包、資料夾即時監控）。<br>"
                f"試用期滿後將自動切換為基礎免費版。您隨時可以購買序號開通永久買斷版。"
            )

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
            self.status_badge.setText("🟡 基礎免費版模式")
            self.status_badge.setStyleSheet("font-size: 14px; font-weight: bold; color: #B45309;")
            self.status_desc.setText(
                "您的 14 天全功能試用已結束，軟體已切換為【基礎免費版】（支援 1 個置物架、單架上限 5 個檔案）。<br>"
                "歡迎以 NT$ 399 購買序號解鎖永久無限制專業版，感謝支持獨立開發者！"
            )

            self.input_card.setVisible(True)
            self.btn_deactivate.setVisible(False)
            self.btn_buy.setVisible(True)
            self.key_input.clear()
            self.msg_label.clear()
            self.adjustSize()

    def handle_activate(self):
        key = self.key_input.text().strip()
        if not key:
            self.msg_label.setText("請先輸入授權序號")
            self.msg_label.setStyleSheet("color: #DC2626; font-weight: bold;")
            return

        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("連線驗證中...")
        self.msg_label.setText("正在連接授權伺服器...")
        self.msg_label.setStyleSheet("color: #0284C7; font-weight: 500;")
        QApplication.processEvents()

        # 連線啟用
        success, msg = self.license_manager.activate_online(key)
        
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText("立即驗證並開通")

        if success:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color: #16A34A; font-weight: bold;")
            QTimer.singleShot(800, self.refresh_ui_state)
            QMessageBox.information(self, "開通成功", "🎉 恭喜！KyteShelf 專業版已成功開通並綁定本機。")
        else:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color: #DC2626; font-weight: bold;")

    def handle_deactivate(self):
        reply = QMessageBox.question(
            self,
            "確認解除綁定",
            "確定要解除此電腦的授權綁定嗎？\n\n"
            "解除後，此電腦將恢復為免費模式，該名額將立即釋放，可移至新電腦輸入原序號繼續使用。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self.license_manager.deactivate_online()
            QMessageBox.information(self, "提示", msg)
            self.refresh_ui_state()

    def copy_machine_guid(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.license_manager.machine_id)
        QMessageBox.information(
            self,
            "已複製",
            f"本機識別碼已複製至剪貼簿：\n{self.license_manager.machine_id}\n\n如遇開通問題可將此代碼提供給客服。"
        )
