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

        # State flag to prevent hotkey spam while an action is active.

        self.is_action_active = False

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

            # Check for hotkey combinations

            if "ctrl" in self.current_keys and "alt" in self.current_keys:
                if hasattr(key, "vk"):
                    # If an action is already active from a previous press, do nothing.

                    if self.is_action_active:
                        return

                    # Ctrl+Alt+D (D = 68)

                    if key.vk == 68:
                        self.is_action_active = True

                        debug_print("Hotkey 'Ctrl+Alt+D' triggered (Translate Word).")

                        self.capture_callback()

                    # Ctrl+Alt+S (S = 83)

                    elif key.vk == 83:
                        self.is_action_active = True

                        debug_print(
                            "Hotkey 'Ctrl+Alt+S' triggered (Translate Sentence)."
                        )

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
            key_released = None

            if key in {
                pynput_keyboard.Key.ctrl_l,
                pynput_keyboard.Key.ctrl_r,
                pynput_keyboard.Key.ctrl,
            }:
                self.current_keys.discard("ctrl")

                key_released = "ctrl"

            if key in {
                pynput_keyboard.Key.alt_l,
                pynput_keyboard.Key.alt_r,
                pynput_keyboard.Key.alt,
            }:
                self.current_keys.discard("alt")

                key_released = "alt"

            # If a modifier key was released, reset the action flag.

            if key_released:
                self.is_action_active = False

        except (AttributeError, KeyError):
            pass

    def start(self):
        """Starts the hotkey listener."""
        self.listener.start()
