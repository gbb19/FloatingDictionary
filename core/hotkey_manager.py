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
            on_press=self.on_press,
            on_release=self.on_release
        )

    def on_press(self, key):
        """Callback function for key presses."""
        try:
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r}:
                self.current_keys.add('ctrl')
            
            # Check for Ctrl+D
            if hasattr(key, 'char') and key.char == '\x04' and 'ctrl' in self.current_keys:
                print("Hotkey 'Ctrl+D' pressed.")
                self.capture_callback()
            
            # Check for Ctrl+Q
            if hasattr(key, 'char') and key.char == '\x11' and 'ctrl' in self.current_keys:
                print("Hotkey 'Ctrl+Q' pressed. Exiting...")
                self.exit_callback()

        except AttributeError:
            pass

    def on_release(self, key):
        """Callback function for key releases."""
        try:
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r}:
                self.current_keys.discard('ctrl')
        except (AttributeError, KeyError):
            pass

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()