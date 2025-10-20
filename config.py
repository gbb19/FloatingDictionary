"""
Configuration file for the application.
Stores constants and settings.
"""

# --- OCR Engine Settings ---
# 'tesseract' 
OCR_ENGINE = 'tesseract'

# --- Language Settings ---
# Use 2-letter ISO 639-1 codes, or 'auto' to enable auto-detection from the list below.
SOURCE_LANG = 'en'
TARGET_LANG = 'th'

# List of languages to use for auto-detection. These must match the available .traineddata files.
AUTO_DETECT_LANGUAGES = ['eng', 'tha', 'jpn', 'rus', 'chi_sim']

# Maps 2-letter language codes to Tesseract's 3-letter codes for single-language mode.
LANG_CODE_MAP = {
    'en': 'eng',
    'th': 'tha',
    'ja': 'jpn',
    'zh-cn': 'chi_sim',
    'ru': 'rus',
}


# --- OCR Capture Dimensions ---
CAPTURE_WIDTH = 400
CAPTURE_HEIGHT = 300
