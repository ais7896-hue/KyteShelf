import sys
from PySide6.QtWidgets import QApplication

from kyteshelf.utils import init_runtime_environment
from kyteshelf.config import ConfigManager
from kyteshelf.input_monitor import TriggerSignals, GlobalInputMonitor
from kyteshelf.ui.shelf_manager import ShelfManager


def main():
    # 預先初始化 Windows 執行階段環境（防 --noconsole 模式崩潰）
    init_runtime_environment()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 全域設定現代精美 ToolTip 樣式，徹底修復 Windows 原生主題產生的純黑方塊瑕疵
    app.setStyleSheet("""
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

    config_manager = ConfigManager()
    manager = ShelfManager(config_manager=config_manager)
    signals = TriggerSignals()
    signals.show_shelf.connect(manager.on_shake)

    monitor = GlobalInputMonitor(signals, config_manager=config_manager)
    monitor.start()

    app.aboutToQuit.connect(manager.save_session)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
