"""
Manages system-wide hotkeys using pynput.
"""

from pynput import keyboard as pynput_keyboard
from utils.app_logger import debug_print


class HotkeyManager:
    def __init__(
        self, capture_callback, sentence_callback, exit_callback, hide_callback
    ):
        self.capture_callback = capture_callback
        self.sentence_callback = sentence_callback
        self.exit_callback = exit_callback
        self.hide_callback = hide_callback
        self.current_keys = set()
        self.listener = pynput_keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )

    def on_press(self, key):
        """Callback function for key presses."""
        try:
            # Track modifier keys
            if key in {
                pynput_keyboard.Key.ctrl_l,
                pynput_keyboard.Key.ctrl_r,
                pynput_keyboard.Key.ctrl,
            }:
                self.current_keys.add("ctrl")
            if key in {
                pynput_keyboard.Key.alt_l,
                pynput_keyboard.Key.alt_r,
                pynput_keyboard.Key.alt,
            }:
                self.current_keys.add("alt")

            # Check for hotkey combinations using virtual key codes (vk)
            # This is more reliable for combinations with modifiers than using key.char
            if "ctrl" in self.current_keys and "alt" in self.current_keys:
                if hasattr(key, "vk"):
                    # Ctrl+Alt+D (D = 68)
                    if key.vk == 68:
                        debug_print("Hotkey 'Ctrl+Alt+D' pressed (Translate Word).")
                        self.capture_callback()
                    # Ctrl+Alt+S (S = 83)
                    elif key.vk == 83:
                        debug_print("Hotkey 'Ctrl+Alt+S' pressed (Translate Sentence).")
                        self.sentence_callback()
                    # Ctrl+Alt+Q (Q = 81)
                    elif key.vk == 81:
                        debug_print("Hotkey 'Ctrl+Alt+Q' pressed. Exiting...")
                        self.exit_callback()

            # Check for Escape key
            if key == pynput_keyboard.Key.esc:
                debug_print("Hotkey 'Esc' pressed.")
                self.hide_callback()

        except AttributeError:
            pass

    def on_release(self, key):
        """Callback function for key releases."""
        try:
            if key in {
                pynput_keyboard.Key.ctrl_l,
                pynput_keyboard.Key.ctrl_r,
                pynput_keyboard.Key.ctrl,
            }:
                self.current_keys.discard("ctrl")
            if key in {
                pynput_keyboard.Key.alt_l,
                pynput_keyboard.Key.alt_r,
                pynput_keyboard.Key.alt,
            }:
                self.current_keys.discard("alt")
        except (AttributeError, KeyError):
            pass

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()
