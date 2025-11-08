import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Environment ---
APP_ENV = os.getenv("APP_ENV", "prod")  # Can be 'dev' or 'prod'

# --- Data Store Configuration ---
DATA_FILE_PATH = "dictionary_data.json"
MAX_HISTORY_ENTRIES = 100 # Maximum number of entries to keep in history

# --- Hotkey Configuration ---
SETTINGS_FILE_PATH = "settings.json"
DEFAULT_HOTKEY_WORD = "Ctrl+Alt+D"
DEFAULT_HOTKEY_SENTENCE = "Ctrl+Alt+S"
DEFAULT_HOTKEY_EXIT = "Ctrl+Alt+Q"

# --- OCR and Language Configuration ---
OCR_ENGINE = "tesseract"
SOURCE_LANG = "auto"  # Default source language ('auto' for detection)
TARGET_LANG = "th"  # Default target language

# Languages for Tesseract to use in 'auto' mode. Add more for broader detection.
AUTO_DETECT_LANGUAGES = ["eng", "tha", "jpn", "chi_sim", "kor"]

# Mapping from general language codes to Tesseract-specific codes
LANG_CODE_MAP = {
    "en": "eng",
    "th": "tha",
    "jp": "jpn",
    "cn": "chi_sim",
    "ko": "kor",
    # Add other languages here if needed
}

# --- Capture Dimensions ---
# The size of the screenshot area around the cursor
CAPTURE_WIDTH = 300
CAPTURE_HEIGHT = 150
