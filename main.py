import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from kyteshelf.utils import init_runtime_environment
from kyteshelf.config import ConfigManager
from kyteshelf.input_monitor import TriggerSignals, GlobalInputMonitor
from kyteshelf.ui.shelf_manager import ShelfManager
from kyteshelf.i18n import t

IPC_SERVER_NAME = "KyteShelf_SingleInstance_IPC"


def main():
    # 預先初始化 Windows 執行階段環境（防 --noconsole 模式崩潰）
    init_runtime_environment()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # ── 單一實例防多開檢測 (Single Instance Check) ──────────────────────────
    socket = QLocalSocket()
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(300):
        socket.write(b"SHOW_ALIVE")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        print("[INFO] KyteShelf 已在執行中，已向主行程發送提示並安全退出。")
        sys.exit(0)

    # 首次啟動：建立 IPC 伺服器
    QLocalServer.removeServer(IPC_SERVER_NAME)
    local_server = QLocalServer()
    if not local_server.listen(IPC_SERVER_NAME):
        print(f"[WARN] QLocalServer 監聽失敗: {local_server.errorString()}")

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

    def _on_ipc_connection():
        sock = local_server.nextPendingConnection()
        if not sock:
            return
        sock.waitForReadyRead(300)
        data = sock.readAll().data().decode("utf-8", errors="ignore").strip()
        sock.disconnectFromServer()
        if "SHOW_ALIVE" in data:
            manager.show_all()
            if hasattr(manager, "tray_icon") and manager.tray_icon:
                manager.tray_icon.showMessage(
                    t("tray.already_running_title", default="KyteShelf 已在運行中"),
                    t("tray.already_running_msg", default="程式已在系統托盤常駐運行中，已為您顯示置物架。\n請勿重複啟動。"),
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )

    local_server.newConnection.connect(_on_ipc_connection)

    signals = TriggerSignals()
    signals.show_shelf.connect(manager.on_shake)

    monitor = GlobalInputMonitor(signals, config_manager=config_manager)
    monitor.start()

    def _cleanup():
        local_server.close()
        manager.save_session()

    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
