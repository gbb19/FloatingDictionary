"""
Handles the setup and initialization of Tesseract OCR.
"""
import sys
import os
import pytesseract

def get_executable_path(name):
    """
    Finds the path of a file bundled with the application (for PyInstaller).
    """
    if getattr(sys, 'frozen', False):
        # Running from a bundled .exe
        base_path = sys._MEIPASS
    else:
        # Running from a .py script
        base_path = os.path.abspath(".")
    return os.path.join(base_path, name)

def initialize_tesseract():
    """
    Sets up the TESSDATA_PREFIX environment variable and verifies Tesseract installation.
    """
    try:
        # Set TESSDATA_PREFIX environment variable
        tessdata_dir = get_executable_path(os.path.join("Tesseract-OCR", "tessdata"))
        tessdata_dir_forward = tessdata_dir.replace('\\', '/')
        os.environ['TESSDATA_PREFIX'] = tessdata_dir_forward
        print(f"✓ ตั้ง TESSDATA_PREFIX = {tessdata_dir_forward}")

        # Set Tesseract command path and verify
        tesseract_path = get_executable_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        pytesseract.get_tesseract_version()
        print("✓ Tesseract เตรียมพร้อมแล้ว")
        return True
    except Exception as e:
        print("="*50)
        print("!!! Tesseract OCR ไม่ถูกต้อง !!!")
        print(f"Error: {e}")
        print("="*50)
        return False