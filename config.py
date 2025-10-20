"""
Configuration file for the application.
Stores constants and settings.
"""

# --- Language Settings ---
# Use 2-letter ISO 639-1 codes. These will be mapped to Tesseract's 3-letter codes.
SOURCE_LANG = 'ja'
TARGET_LANG = 'th'

# Maps 2-letter language codes to Tesseract's 3-letter codes.
LANG_CODE_MAP = {
    'en': 'eng',
    'th': 'tha',
    'ja': 'jpn',
    'ko': 'kor',
    'zh-cn': 'chi_sim',
    'zh-tw': 'chi_tra',
    'fr': 'fra',
    'es': 'spa',
    'de': 'deu',
}


# --- OCR Capture Dimensions ---
CAPTURE_WIDTH = 400
CAPTURE_HEIGHT = 300