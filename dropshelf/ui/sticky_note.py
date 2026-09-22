import os
import subprocess
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QIcon, QPixmap, 
    QFont, QTextCursor
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QGraphicsDropShadowEffect,
    QSizeGrip
)


def create_sticky_icon(note_type: str = "text") -> QIcon:
    """動態繪製精美的自黏標籤（Sticky Note）圖示"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 便籤陰影
    painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(6, 10, 52, 50, 6, 6)

    # 便籤底色（經典便籤柔黃 / 網址用柔和淺藍黃）
    if note_type == "url":
        base_color = QColor("#E0F2FE")  # 淺天藍
        header_color = QColor("#38BDF8")  # 天藍膠帶
        stripe_color = QColor("#0284C7")
    else:
        base_color = QColor("#FEF08A")  # 柔黃
        header_color = QColor("#F59E0B")  # 琥珀黃膠帶
        stripe_color = QColor("#CA8A04")

    painter.setBrush(QBrush(base_color))
    painter.setPen(QPen(QColor(0, 0, 0, 25), 1))
    painter.drawRoundedRect(4, 6, 52, 52, 6, 6)

    # 頂部自黏膠帶條
    painter.setBrush(QBrush(header_color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(16, 3, 28, 8, 2, 2)

    # 便籤內部紋理/文字線條
    painter.setPen(QPen(stripe_color, 2, Qt.SolidLine, Qt.RoundCap))
    if note_type == "url":
        # 繪製迷你連結符號或三條長短橫線
        painter.drawLine(14, 24, 46, 24)
        painter.drawLine(14, 33, 40, 33)
        painter.drawLine(14, 42, 32, 42)
    else:
        # 繪製三條微縮文字條紋
        painter.drawLine(14, 22, 46, 22)
        painter.drawLine(14, 31, 46, 31)
        painter.drawLine(14, 40, 34, 40)

    # 右下折角效果
    corner_poly = [QPoint(46, 58), QPoint(56, 48), QPoint(46, 48)]
    painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
    painter.drawPolygon(corner_poly)

    painter.end()
    return QIcon(pixmap)


class StickyNoteWindow(QWidget):
    """獨立的自黏便箋（Sticky Note）浮動視窗"""
    content_updated = Signal(str)

    def __init__(self, content: str = "", note_type: str = "text", parent=None):
        super().__init__(parent)
        self.note_type = note_type
        self.content = content
        self.is_pinned = True
        self.drag_pos = None

        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(300, 260)

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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 便籤本體容器
        self.container = QWidget(self)
        self.container.setObjectName("StickyContainer")
        self.container.setAttribute(Qt.WA_StyledBackground, True)

        bg_color = "#E0F2FE" if self.note_type == "url" else "#FEF9C3"
        border_color = "#7DD3FC" if self.note_type == "url" else "#FDE047"
        header_color = "#0284C7" if self.note_type == "url" else "#CA8A04"
        sel_bg = "#BAE6FD" if self.note_type == "url" else "#FDE047"
        sel_color = "#0369A1" if self.note_type == "url" else "#854D0E"

        self.container.setStyleSheet(f"""
            QWidget#StickyContainer {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
        """)

        # 陰影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 8, 10, 8)
        container_layout.setSpacing(6)

        # 頂部控制列
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        type_icon = "🔗 網址標籤" if self.note_type == "url" else "📝 自黏便箋"
        self.title_label = QLabel(type_icon, self.container)
        self.title_label.setStyleSheet(f"font-weight: bold; color: {header_color}; font-size: 12px;")

        # 按鈕群
        # 瀏覽器開啟（網址專用）
        if self.note_type == "url":
            self.btn_open_url = QPushButton("🌐", self.container)
            self.btn_open_url.setFixedSize(22, 22)
            self.btn_open_url.setCursor(Qt.PointingHandCursor)
            self.btn_open_url.setToolTip("在預設瀏覽器開啟網址")
            self.btn_open_url.setStyleSheet("""
                QPushButton { border: none; background: transparent; font-size: 13px; border-radius: 4px; }
                QPushButton:hover { background: rgba(0, 0, 0, 0.08); }
            """)
            self.btn_open_url.clicked.connect(self.open_url_in_browser)
            header_layout.addWidget(self.btn_open_url)

        # 複製按鈕
        self.btn_copy = QPushButton("📋", self.container)
        self.btn_copy.setFixedSize(22, 22)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setToolTip("複製內容至剪貼簿")
        self.btn_copy.setStyleSheet("""
            QPushButton { border: none; background: transparent; font-size: 12px; border-radius: 4px; }
            QPushButton:hover { background: rgba(0, 0, 0, 0.08); }
        """)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)

        # 釘選按鈕
        self.btn_pin = QPushButton("📌", self.container)
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip("切換置頂固定")
        self.btn_pin.setStyleSheet("border: none; background: rgba(0, 0, 0, 0.12); border-radius: 4px; font-size: 12px;")
        self.btn_pin.clicked.connect(self.toggle_pin)

        # 關閉按鈕
        self.btn_close = QPushButton("✕", self.container)
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("關閉便箋視窗")
        self.btn_close.setStyleSheet("""
            QPushButton { border: none; color: #64748B; font-weight: bold; font-size: 13px; border-radius: 4px; }
            QPushButton:hover { background: rgba(0, 0, 0, 0.1); color: #0F172A; }
        """)
        self.btn_close.clicked.connect(self.close)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_copy)
        header_layout.addWidget(self.btn_pin)
        header_layout.addWidget(self.btn_close)

        container_layout.addLayout(header_layout)

        # 內容編輯區
        self.text_edit = QTextEdit(self.container)
        self.text_edit.setFrameShape(QTextEdit.NoFrame)
        self.text_edit.setPlainText(self.content)
        self.text_edit.setPlaceholderText("請在此輸入便箋內容...")
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_color};
                border: none;
                font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
                font-size: 13px;
                color: #1E293B;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
            }}
            QScrollBar:vertical {{
                width: 5px;
                background: transparent;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 0, 0, 0.15);
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 0, 0, 0.3);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        self.text_edit.textChanged.connect(self.on_text_changed)
        container_layout.addWidget(self.text_edit)

        # 底部縮放握把
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()
        size_grip = QSizeGrip(self.container)
        size_grip.setFixedSize(14, 14)
        bottom_layout.addWidget(size_grip)
        container_layout.addLayout(bottom_layout)

        main_layout.addWidget(self.container)

    def on_text_changed(self):
        new_text = self.text_edit.toPlainText()
        self.content = new_text
        self.content_updated.emit(new_text)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.content)
        orig_text = self.title_label.text()
        self.title_label.setText("✓ 已複製到剪貼簿")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.title_label.setText(orig_text))

    def open_url_in_browser(self):
        url = self.content.strip()
        if url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.btn_pin.setStyleSheet("border: none; background: rgba(0, 0, 0, 0.12); border-radius: 4px; font-size: 12px;")
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.btn_pin.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        self.show()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)
