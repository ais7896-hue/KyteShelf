import time
from collections import deque
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor
from pynput import mouse, keyboard

from .config import ConfigManager


class TriggerSignals(QObject):
    show_shelf = Signal(int, int)


class GlobalInputMonitor:
    def __init__(self, signals: TriggerSignals, config_manager: ConfigManager):
        self.signals = signals
        self.config_manager = config_manager
        self.is_left_pressed = False
        self.history = deque(maxlen=20)
        self.last_trigger_time = 0
        self.current_cursor = (300, 300)

        self.mouse_listener = None
        self.hotkey_listener = None
        self.current_hotkey_str = ""

        self.apply_config(self.config_manager.config)
        self.config_manager.config_changed.connect(self.apply_config)

    def apply_config(self, config):
        self.shake_enabled = config.get("shake_enabled", True)
        sens = config.get("shake_sensitivity", 3)
        # 靈敏度等級映射 (min_dx, reversals, time_window)
        sens_map = {
            1: (18, 3, 0.40),  # 偏鈍（防誤觸）
            2: (14, 2, 0.42),  # 略鈍
            3: (10, 2, 0.45),  # 標準（預設）
            4: (8, 2, 0.50),   # 靈敏
            5: (5, 2, 0.55),   # 極靈敏
        }
        self.min_dx, self.reversals_needed, self.time_window = sens_map.get(sens, (10, 2, 0.45))

        new_hotkey = config.get("hotkey", "<ctrl>+`")
        if new_hotkey != self.current_hotkey_str:
            self.restart_hotkey_listener(new_hotkey)

    def restart_hotkey_listener(self, hotkey_str):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None

        self.current_hotkey_str = hotkey_str
        if not hotkey_str:
            return

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                hotkey_str: self.trigger_by_hotkey
            })
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
        except Exception as e:
            print(f"註冊全域快捷鍵 '{hotkey_str}' 失敗: {e}")

    def on_click(self, x, y, button, pressed):
        self.current_cursor = (int(x), int(y))
        if button == mouse.Button.left:
            self.is_left_pressed = pressed
            if not pressed:
                self.history.clear()

    def on_move(self, x, y):
        self.current_cursor = (int(x), int(y))
        if not self.is_left_pressed or not self.shake_enabled:
            return

        now = time.time()
        if now - self.last_trigger_time < 1.0:
            return

        self.history.append((x, now))
        recent = [p for p in self.history if now - p[1] <= self.time_window]
        if len(recent) < 4:
            return

        reversals = 0
        last_dir = 0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            if abs(dx) > self.min_dx:
                cur_dir = 1 if dx > 0 else -1
                if last_dir != 0 and cur_dir != last_dir:
                    reversals += 1
                last_dir = cur_dir

        if reversals >= self.reversals_needed:
            self.last_trigger_time = now
            self.history.clear()
            self.signals.show_shelf.emit(int(x), int(y))

    def trigger_by_hotkey(self):
        pos = QCursor.pos()
        self.signals.show_shelf.emit(pos.x(), pos.y())

    def start(self):
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move, 
            on_click=self.on_click
        )
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

        self.restart_hotkey_listener(self.current_hotkey_str)
