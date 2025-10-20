"""
Manages system-wide hotkeys using pynput.
"""
from pynput import keyboard as pynput_keyboard

class HotkeyManager:
    def __init__(self, capture_callback, sentence_callback, exit_callback, hide_callback):
        self.capture_callback = capture_callback
        self.sentence_callback = sentence_callback
        self.exit_callback = exit_callback
        self.hide_callback = hide_callback
        self.current_keys = set()
        self.listener = pynput_keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )

    def on_press(self, key):
        """Callback function for key presses."""
        try:
            # Track Ctrl and Alt keys
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r, pynput_keyboard.Key.ctrl}:
                self.current_keys.add('ctrl')
            
            # Check for Ctrl+D (char code '\x04')
            if hasattr(key, 'char') and key.char == '\x04':
                if 'ctrl' in self.current_keys:
                    print("Hotkey 'Ctrl+D' pressed (Translate Word).")
                    self.capture_callback()
            
            # Check for Ctrl+S (char code '\x13')
            if hasattr(key, 'char') and key.char == '\x13':
                if 'ctrl' in self.current_keys:
                    print("Hotkey 'Ctrl+S' pressed (Translate Sentence).")
                    self.sentence_callback()
            
            # Check for Escape key
            if key == pynput_keyboard.Key.esc:
                print("Hotkey 'Esc' pressed.")
                self.hide_callback()
            
            # Check for Ctrl+Q (char code '\x11')
            if hasattr(key, 'char') and key.char == '\x11':
                if 'ctrl' in self.current_keys:
                    print("Hotkey 'Ctrl+Q' pressed. Exiting...")
                    self.exit_callback()

        except AttributeError:
            pass

    def on_release(self, key):
        """Callback function for key releases."""
        try:
            if key in {pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r, pynput_keyboard.Key.ctrl}:
                self.current_keys.discard('ctrl')
        except (AttributeError, KeyError):
            pass

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()