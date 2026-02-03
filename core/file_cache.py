"""
Handles reading from and writing to a file-based JSON cache.
"""

import ast
import json

from utils.app_logger import debug_print


def load_cache(file_path: str) -> dict:
    """
    Loads the translation cache from a JSON file.
    Returns an empty dictionary if the file doesn't exist or is invalid.

    Notes:
    - JSON stores dictionary keys as strings. Older code used `eval()` to convert
      those back into tuple keys; that is unsafe and has been replaced by
      `ast.literal_eval()` which only evaluates literals.
    - If a key cannot be parsed as a Python literal tuple, we fall back to keeping
      the original string key to avoid raising on malformed data.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Convert string keys back to tuples using ast.literal_eval for safety.
            converted = {}
            for key, value in data.items():
                try:
                    converted_key = ast.literal_eval(key)
                except Exception:
                    # Keep original string key if it can't be parsed as a literal.
                    converted_key = key
                converted[converted_key] = value
            return converted
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(
            f"Cache file not found or invalid at '{file_path}'. Starting with an empty cache."
        )
        return {}
    except Exception as e:
        # Unexpected errors should be logged and result in an empty cache.
        debug_print(f"Error loading cache from '{file_path}': {e}")
        return {}


def save_cache(file_path: str, cache_data: dict):
    """
    Saves the entire translation cache to a JSON file.
    """
    try:
        # JSON keys must be strings, so we convert the tuple keys
        string_key_cache = {str(key): value for key, value in cache_data.items()}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(string_key_cache, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving cache to file '{file_path}': {e}")


def append_to_cache(file_path: str, key: tuple, value: str):
    """Appends a single entry to the cache file."""
    # For simplicity and to avoid race conditions, we read-modify-write the whole file.
    # This can be optimized later if performance becomes an issue.
    pass  # This function is not used in the current implementation.
