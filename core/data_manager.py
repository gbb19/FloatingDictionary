"""
Handles reading from and writing to a single file-based JSON data store
that contains both translation cache and history timestamps.
"""

import json
from datetime import datetime

from utils.app_logger import debug_print


def load_data(file_path: str) -> dict:
    """
    Loads the dictionary data from a single JSON file.
    The structure is { cache_key_str: {'html': '...', 'timestamp': '...'} }
    Returns an empty dictionary if the file doesn't exist or is invalid.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Convert string keys back to tuples
            return {eval(key): value for key, value in data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(f"Data file not found or invalid at '{file_path}'. Starting fresh.")
        return {}


def save_data(file_path: str, data: dict):
    """
    Saves the entire dictionary data to a single JSON file.
    """
    try:
        # JSON keys must be strings, so we convert the tuple keys
        string_key_data = {str(key): value for key, value in data.items()}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(string_key_data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving data to file '{file_path}': {e}")


def update_entry(data: dict, cache_key: tuple, html_content: str, max_entries: int):
    """Adds or updates an entry and ensures the total number of entries does not exceed the max."""
    data[cache_key] = {"html": html_content, "timestamp": datetime.now().isoformat()}

    # If the number of entries exceeds the max, remove the oldest one(s)
    if len(data) > max_entries:
        # Sort items by timestamp (oldest first)
        sorted_items = sorted(data.items(), key=lambda item: item[1]["timestamp"])
        num_to_remove = len(sorted_items) - max_entries
        for i in range(num_to_remove):
            del data[sorted_items[i][0]]
