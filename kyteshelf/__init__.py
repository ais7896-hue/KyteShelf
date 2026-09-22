"""
KyteShelf - 靈活的浮動檔案暫存與工作流效率工具
"""

from .utils import get_resource_path, init_runtime_environment
from .config import ConfigManager
from .input_monitor import TriggerSignals, GlobalInputMonitor
from .ui import ShelfManager, KyteShelfWidget, DropShelfWidget, SettingsDialog

__version__ = "1.3.0"

__all__ = [
    "get_resource_path",
    "init_runtime_environment",
    "ConfigManager",
    "TriggerSignals",
    "GlobalInputMonitor",
    "ShelfManager",
    "KyteShelfWidget",
    "DropShelfWidget",
    "SettingsDialog",
]
