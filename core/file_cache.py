"""
Handles reading from and writing to a file-based JSON cache.
"""

import json
from utils.app_logger import debug_print

def load_cache(file_path: str) -> dict:
    """
    Loads the translation cache from a JSON file.
    Returns an empty dictionary if the file doesn't exist or is invalid.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # The cache saves keys as strings, so we need to convert them back to tuples
            return {eval(key): value for key, value in data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(f"Cache file not found or invalid at '{file_path}'. Starting with an empty cache.")
        return {}

def save_cache(file_path: str, cache_data: dict):
    """
    Saves the entire translation cache to a JSON file.
    """
    try:
        # JSON keys must be strings, so we convert the tuple keys
        string_key_cache = {str(key): value for key, value in cache_data.items()}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(string_key_cache, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving cache to file '{file_path}': {e}")

def append_to_cache(file_path: str, key: tuple, value: str):
    """Appends a single entry to the cache file."""
    # For simplicity and to avoid race conditions, we read-modify-write the whole file.
    # This can be optimized later if performance becomes an issue.
    pass # This function is not used in the current implementation.