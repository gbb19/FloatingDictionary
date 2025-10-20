"""
Manages system-wide hotkeys using pynput.
"""

from pynput import keyboard as pynput_keyboard


class HotkeyManager:
    def __init__(self, capture_callback, exit_callback):
        self.capture_callback = capture_callback
        self.exit_callback = exit_callback
        self.current_keys = set()
        self.listener = pynput_keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )

    def on_press(self, key):
        """Callback function for key presses."""
        try:
            # Track Ctrl and Alt keys
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r}:
                self.current_keys.add("ctrl")

            if key in {pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r}:
                self.current_keys.add("alt")

            # Check for Ctrl+Alt+D (key.vk = 68)
            if hasattr(key, "vk") and key.vk == 68:
                if "ctrl" in self.current_keys and "alt" in self.current_keys:
                    print("Hotkey 'Ctrl+Alt+D' pressed.")
                    self.capture_callback()

            # Check for Ctrl+Alt+Q (key.vk = 81)
            if hasattr(key, "vk") and key.vk == 81:
                if "ctrl" in self.current_keys and "alt" in self.current_keys:
                    print("Hotkey 'Ctrl+Alt+Q' pressed. Exiting...")
                    self.exit_callback()

        except AttributeError:
            pass

    def on_release(self, key):
        """Callback function for key releases."""
        try:
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r}:
                self.current_keys.discard("ctrl")

            if key in {pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r}:
                self.current_keys.discard("alt")
        except (AttributeError, KeyError):
            pass

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()
