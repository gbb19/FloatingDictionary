import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Environment ---
APP_ENV = os.getenv("APP_ENV", "prod")  # Can be 'dev' or 'prod'

# --- OCR and Language Configuration ---
OCR_ENGINE = "tesseract"
SOURCE_LANG = "auto"  # Default source language ('auto' for detection)
TARGET_LANG = "th"  # Default target language

# Languages for Tesseract to use in 'auto' mode. Add more for broader detection.
AUTO_DETECT_LANGUAGES = ["eng", "tha", "jpn", "chi_sim"]

# Mapping from general language codes to Tesseract-specific codes
LANG_CODE_MAP = {
    "en": "eng",
    "th": "tha",
    "jp": "jpn",
    "cn": "chi_sim",
    # Add other languages here if needed
}

# --- Capture Dimensions ---
# The size of the screenshot area around the cursor
CAPTURE_WIDTH = 300
CAPTURE_HEIGHT = 150
