import time
import unittest
from unittest.mock import MagicMock, patch
from pynput import mouse

from tests.test_helpers import get_qapp
from kyteshelf.input_monitor import GlobalInputMonitor, TriggerSignals


class TestInputMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_qapp()

    def setUp(self):
        self.signals = TriggerSignals()
        self.mock_config = MagicMock()
        self.mock_config.config = {
            "shake_enabled": True,
            "shake_sensitivity": 3,
            "hotkey": "<ctrl>+`"
        }
        self.mock_config.config_changed = MagicMock()

    @patch.object(GlobalInputMonitor, "restart_hotkey_listener")
    def test_sensitivity_mapping(self, mock_hotkey):
        monitor = GlobalInputMonitor(self.signals, self.mock_config)

        # Default sensitivity 3
        self.assertEqual(monitor.min_dx, 10)
        self.assertEqual(monitor.reversals_needed, 2)
        self.assertEqual(monitor.time_window, 0.45)

        # Sensitivity 1 (blunt)
        monitor.apply_config({"shake_enabled": True, "shake_sensitivity": 1, "hotkey": ""})
        self.assertEqual(monitor.min_dx, 18)
        self.assertEqual(monitor.reversals_needed, 3)

        # Sensitivity 5 (sensitive)
        monitor.apply_config({"shake_enabled": True, "shake_sensitivity": 5, "hotkey": ""})
        self.assertEqual(monitor.min_dx, 5)
        self.assertEqual(monitor.reversals_needed, 2)

    @patch.object(GlobalInputMonitor, "restart_hotkey_listener")
    def test_shake_requires_left_mouse_down(self, mock_hotkey):
        monitor = GlobalInputMonitor(self.signals, self.mock_config)

        triggered_coords = []
        self.signals.show_shelf.connect(lambda x, y: triggered_coords.append((x, y)))

        # Move mouse without left click pressed -> should not trigger
        for x in [100, 150, 100, 150, 100]:
            monitor.on_move(x, 200)

        self.assertEqual(len(triggered_coords), 0)

    @patch.object(GlobalInputMonitor, "restart_hotkey_listener")
    def test_successful_shake_trigger(self, mock_hotkey):
        monitor = GlobalInputMonitor(self.signals, self.mock_config)

        triggered_coords = []
        self.signals.show_shelf.connect(lambda x, y: triggered_coords.append((x, y)))

        # Simulate left mouse button press
        monitor.on_click(100, 200, mouse.Button.left, True)

        # Simulate shaking motion (left-right reversals)
        # Sens 3 requires min_dx = 10, reversals >= 2
        # Movements: 100 -> 130 (+30) -> 90 (-40, rev 1) -> 130 (+40, rev 2) -> trigger!
        monitor.on_move(100, 200)
        monitor.on_move(130, 200)
        monitor.on_move(90, 200)
        monitor.on_move(130, 200)

        self.assertEqual(len(triggered_coords), 1)
        self.assertEqual(triggered_coords[0], (130, 200))

    @patch.object(GlobalInputMonitor, "restart_hotkey_listener")
    def test_shake_cooldown_prevents_spam(self, mock_hotkey):
        monitor = GlobalInputMonitor(self.signals, self.mock_config)

        triggered_coords = []
        self.signals.show_shelf.connect(lambda x, y: triggered_coords.append((x, y)))

        monitor.on_click(100, 200, mouse.Button.left, True)

        # First shake
        monitor.on_move(100, 200)
        monitor.on_move(130, 200)
        monitor.on_move(90, 200)
        monitor.on_move(130, 200)
        self.assertEqual(len(triggered_coords), 1)

        # Immediate second shake (within 1.0 second cooldown)
        monitor.on_move(90, 200)
        monitor.on_move(130, 200)
        monitor.on_move(90, 200)
        monitor.on_move(130, 200)
        # Still only 1 trigger
        self.assertEqual(len(triggered_coords), 1)

    @patch.object(GlobalInputMonitor, "restart_hotkey_listener")
    def test_disabled_shake(self, mock_hotkey):
        self.mock_config.config["shake_enabled"] = False
        monitor = GlobalInputMonitor(self.signals, self.mock_config)

        triggered_coords = []
        self.signals.show_shelf.connect(lambda x, y: triggered_coords.append((x, y)))

        monitor.on_click(100, 200, mouse.Button.left, True)
        monitor.on_move(100, 200)
        monitor.on_move(130, 200)
        monitor.on_move(90, 200)
        monitor.on_move(130, 200)

        self.assertEqual(len(triggered_coords), 0)


if __name__ == "__main__":
    unittest.main()
