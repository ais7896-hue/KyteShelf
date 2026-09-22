import sys
from PySide6.QtWidgets import QApplication

from dropshelf.utils import init_runtime_environment
from dropshelf.config import ConfigManager
from dropshelf.input_monitor import TriggerSignals, GlobalInputMonitor
from dropshelf.ui.shelf_manager import ShelfManager


def main():
    # 預先初始化 Windows 執行階段環境（防 --noconsole 模式崩潰）
    init_runtime_environment()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config_manager = ConfigManager()
    manager = ShelfManager(config_manager=config_manager)
    signals = TriggerSignals()
    signals.show_shelf.connect(manager.on_shake)

    monitor = GlobalInputMonitor(signals, config_manager=config_manager)
    monitor.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
