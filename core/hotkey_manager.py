"""
Manages system-wide hotkeys using pynput.
"""

from pynput import keyboard as pynput_keyboard
from utils.app_logger import debug_print


class HotkeyManager:
    def __init__(
        self, capture_callback, sentence_callback, exit_callback, hide_callback
    ):
        self.hide_callback = hide_callback
        self.hotkeys = [
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse("<ctrl>+<alt>+d"),
                lambda: self._on_activate(
                    "Hotkey 'Ctrl+Alt+D' triggered (Translate Word).", capture_callback
                ),
            ),
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse("<ctrl>+<alt>+s"),
                lambda: self._on_activate(
                    "Hotkey 'Ctrl+Alt+S' triggered (Translate Sentence).",
                    sentence_callback,
                ),
            ),
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse("<ctrl>+<alt>+q"),
                lambda: self._on_activate(
                    "Hotkey 'Ctrl+Alt+Q' pressed. Exiting...", exit_callback
                ),
            ),
        ]
        self.listener = pynput_keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )

    def _on_activate(self, message, callback):
        """Wrapper to print a debug message before executing the callback."""
        debug_print(message)
        callback()

    def on_press(self, key):
        """Callback for all key presses."""
        # Pass the key to all HotKey objects
        for hotkey in self.hotkeys:
            hotkey.press(self.listener.canonical(key))

        # Handle single key presses like Escape
        if key == pynput_keyboard.Key.esc:
            debug_print("Hotkey 'Esc' pressed.")
            self.hide_callback()

    def on_release(self, key):
        """Callback for all key releases."""
        # Pass the key to all HotKey objects
        for hotkey in self.hotkeys:
            hotkey.release(self.listener.canonical(key))

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()

    def stop(self):
        """Stops the hotkey listener."""
        self.listener.stop()
