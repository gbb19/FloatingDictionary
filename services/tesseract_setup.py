"""
Handles the setup and initialization of Tesseract OCR.
"""

import os
import platform
import subprocess
import sys

import pytesseract

from utils.app_logger import debug_print


def get_executable_path(name: str) -> str:
    """
    Finds the path of a file bundled with the application (for PyInstaller).
    """
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, name)


def initialize_tesseract():
    """
    Sets up Tesseract and applies a patch to hide subprocess console on Windows.
    """
    # --- Monkey-patch subprocess.Popen to hide console window on Windows ---
    if platform.system() == "Windows":
        _original_popen = subprocess.Popen

        def _patched_popen(*args, **kwargs):
            if "creationflags" not in kwargs:
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            return _original_popen(*args, **kwargs)

        subprocess.Popen = _patched_popen
        debug_print("Applied Windows-specific patch to hide subprocess consoles.")

    try:
        # Set TESSDATA_PREFIX environment variable
        tessdata_dir = get_executable_path(os.path.join("Tesseract-OCR", "tessdata"))
        tessdata_dir_forward = tessdata_dir.replace("\\", "/")
        os.environ["TESSDATA_PREFIX"] = tessdata_dir_forward
        debug_print(f"✓ TESSDATA_PREFIX set to: {tessdata_dir_forward}")

        # Set Tesseract command path and verify
        tesseract_path = get_executable_path(
            os.path.join("Tesseract-OCR", "tesseract.exe")
        )
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        pytesseract.get_tesseract_version()
        debug_print("✓ Tesseract is ready.")
        return True
    except Exception as e:
        debug_print("=" * 50)
        debug_print("!!! Tesseract OCR not found or configured correctly !!!")
        debug_print(f"Error: {e}")
        debug_print(
            "Please ensure Tesseract-OCR is copied to the project root as per the README."
        )
        debug_print("=" * 50)
        return False
