"""
Handles loading and saving application settings, such as hotkeys.
"""

import json
from utils.app_logger import debug_print

def load_settings(file_path: str, defaults: dict) -> dict:
    """
    Loads settings from a JSON file. If the file doesn't exist or is invalid,
    it returns the default settings.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # Ensure all default keys are present
            for key, value in defaults.items():
                settings.setdefault(key, value)
            return settings
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(f"Settings file not found or invalid at '{file_path}'. Using default settings.")
        return defaults

def save_settings(file_path: str, settings: dict):
    """
    Saves the settings dictionary to a JSON file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving settings to file '{file_path}': {e}")