import os
import sys
from pathlib import Path

# Ensure offscreen Qt platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

_qapp_instance = None


def get_qapp():
    """Ensure a global headless QApplication instance exists for GUI tests."""
    global _qapp_instance
    if _qapp_instance is None:
        _qapp_instance = QApplication.instance()
        if _qapp_instance is None:
            _qapp_instance = QApplication(["-platform", "offscreen"])
    return _qapp_instance
