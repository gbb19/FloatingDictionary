"""
Windows-specific utility functions using ctypes.
"""

import ctypes
from utils.app_logger import debug_print


def force_set_focus(hwnd):
    """
    Forces focus to the specified window handle (hwnd) using the AttachThreadInput technique.
    """
    if not hwnd:
        return
    try:
        our_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        target_thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)

        if our_thread_id != target_thread_id:
            ctypes.windll.user32.AttachThreadInput(
                our_thread_id, target_thread_id, True
            )
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)
            ctypes.windll.user32.AttachThreadInput(
                our_thread_id, target_thread_id, False
            )
        else:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)

        # "Wake up" the window by simulating an Alt key press.
        # This ensures the window is ready to receive keyboard input immediately.
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Press Alt
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Release Alt

    except Exception as e:
        debug_print(f"Force set focus error: {e}")
