import html
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, QTimer
from PySide6.QtGui import QPixmap, QImageReader, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, 
    QGraphicsDropShadowEffect, QApplication
)


class ImagePreviewPopup(QWidget):
    """獨立懸浮圖片縮圖預覽卡片：
    採用原生獨立 Popup 視窗，徹底繞過 Windows DWM 對 QToolTip 的 UpdateLayeredWindowIndirect 限制與髒矩形報錯。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.ToolTip | 
            Qt.FramelessWindowHint | 
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._current_path = ""

        # 主佈局留邊界以供陰影繪製
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # 內部深色容器
        self.card = QWidget(self)
        self.card.setObjectName("PreviewCard")
        self.card.setStyleSheet("""
            QWidget#PreviewCard {
                background-color: #0F172A;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)

        # 精緻陰影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 9, 10, 10)
        card_layout.setSpacing(6)

        # 檔案名稱
        self.title_label = QLabel(self.card)
        self.title_label.setStyleSheet("""
            color: #F8FAFC;
            font-size: 12px;
            font-weight: 600;
            font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
        """)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(230)
        card_layout.addWidget(self.title_label)

        # 圖片縮圖
        self.img_label = QLabel(self.card)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("""
            background-color: #020617;
            border: 1px solid #1E293B;
            border-radius: 6px;
        """)
        card_layout.addWidget(self.img_label)

        # 尺寸與容量資訊
        self.meta_label = QLabel(self.card)
        self.meta_label.setStyleSheet("""
            color: #94A3B8;
            font-size: 11px;
            font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
        """)
        card_layout.addWidget(self.meta_label)

        # 路徑資訊
        self.path_label = QLabel(self.card)
        self.path_label.setStyleSheet("""
            color: #64748B;
            font-size: 10px;
            line-height: 1.2;
            font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif;
        """)
        self.path_label.setWordWrap(True)
        self.path_label.setMaximumWidth(230)
        card_layout.addWidget(self.path_label)

        main_layout.addWidget(self.card)

    def show_preview(self, path_str: str, global_pos: QPoint):
        """依據檔案路徑載入縮圖並在滑鼠附近合適位置展示"""
        if not path_str or not Path(path_str).exists():
            self.hide()
            return

        self._current_path = path_str
        path = Path(path_str)

        # 1. 檔名
        self.title_label.setText(path.name)

        # 2. 檔案容量計算
        size_str = ""
        try:
            sz_bytes = path.stat().st_size
            if sz_bytes < 1024:
                size_str = f"{sz_bytes} B"
            elif sz_bytes < 1024 * 1024:
                size_str = f"{sz_bytes / 1024:.1f} KB"
            elif sz_bytes < 1024 * 1024 * 1024:
                size_str = f"{sz_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{sz_bytes / (1024 * 1024 * 1024):.2f} GB"
        except Exception:
            pass

        # 3. 讀取影像與等比縮圖
        dim_str = ""
        max_w, max_h = 220, 160
        try:
            reader = QImageReader(path_str)
            img_size = reader.size()
            if img_size.isValid() and img_size.width() > 0 and img_size.height() > 0:
                dim_str = f"📐 {img_size.width()} × {img_size.height()} px"
                # 等比計算顯示尺寸
                reader.setScaledSize(img_size.scaled(max_w, max_h, Qt.KeepAspectRatio))
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img)
                    self.img_label.setPixmap(pix)
                    self.img_label.setVisible(True)
                else:
                    self.img_label.setVisible(False)
            else:
                self.img_label.setVisible(False)
        except Exception:
            self.img_label.setVisible(False)

        # 4. 元數據行
        meta_items = [dim_str] if dim_str else []
        if size_str:
            meta_items.append(f"📦 {size_str}")
        self.meta_label.setText("  •  ".join(meta_items))
        self.meta_label.setVisible(bool(meta_items))

        # 5. 路徑展示
        self.path_label.setText(str(path))

        self.adjustSize()

        # 6. 計算視窗座標，確保不被螢幕邊界裁切
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        card_w = self.sizeHint().width()
        card_h = self.sizeHint().height()

        target_x = global_pos.x() + 18
        target_y = global_pos.y() + 14

        # 右側超出時，顯示在游標左側
        if target_x + card_w > screen_geo.right():
            target_x = global_pos.x() - card_w - 12

        # 底部超出時，往上浮動
        if target_y + card_h > screen_geo.bottom():
            target_y = screen_geo.bottom() - card_h - 10

        target_x = max(screen_geo.left() + 5, target_x)
        target_y = max(screen_geo.top() + 5, target_y)

        self.move(target_x, target_y)
        self.show()
        self.raise_()

    def hide_preview(self):
        """隱藏預覽彈窗"""
        self._current_path = ""
        self.hide()
