"""
Manages system-wide hotkeys using pynput.
"""

from pynput import keyboard as pynput_keyboard

from utils.app_logger import debug_print


class HotkeyManager:
    def __init__(self, hotkey_config, callbacks, hide_callback):
        self.hide_callback = hide_callback
        self.callbacks = callbacks
        self.hotkey_config = hotkey_config

        self.hotkeys = [
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse(
                    self._to_pynput_format(hotkey_config["word"])
                ),
                lambda: self._on_activate("word", callbacks["capture"]),
            ),
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse(
                    self._to_pynput_format(hotkey_config["sentence"])
                ),
                lambda: self._on_activate("sentence", callbacks["sentence"]),
            ),
            pynput_keyboard.HotKey(
                pynput_keyboard.HotKey.parse(
                    self._to_pynput_format(hotkey_config["exit"])
                ),
                lambda: self._on_activate("exit", callbacks["exit"]),
            ),
        ]
        self.listener = pynput_keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )

    def _on_activate(self, hotkey_name, callback):
        """Wrapper to print a debug message before executing the callback."""
        debug_print(
            f"Hotkey '{self.hotkey_config[hotkey_name]}' triggered ({hotkey_name.capitalize()})."
        )
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

    def _to_pynput_format(self, qt_key_sequence: str) -> str:
        """Converts a Qt key sequence string (e.g., 'Ctrl+Alt+D') to pynput format (e.g., '<ctrl>+<alt>+d')."""
        parts = qt_key_sequence.lower().split("+")
        pynput_parts = []
        for part in parts:
            # Modifier keys and special keys go in angle brackets
            if part in ["ctrl", "alt", "shift", "cmd", "win", "command"]:
                pynput_parts.append(f"<{part}>")
            else:
                # Regular character keys do not
                pynput_parts.append(part)
        return "+".join(pynput_parts)
