"""
Handles reading from and writing to a single file-based JSON data store
that contains both translation cache and history timestamps.

New behavior: store structured translation results (not only HTML) so the
UI can reformat or extract fields later. Each entry's value is a dict and
must contain at least a `timestamp` field. Older files that contain an
`html` field will still be supported for backward compatibility.
"""

import json
from datetime import datetime

from utils.app_logger import debug_print


def load_data(file_path: str) -> dict:
    """
    Loads the dictionary data from a single JSON file.
    Keys in the saved JSON are the stringified tuple cache keys.

    Returns a mapping of tuple -> entry_dict. Entry dicts are left as-is
    (they may contain `html` for older versions or structured fields for
    newer versions).
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
    The values are arbitrary JSON-serializable dicts (entry dicts).
    """
    try:
        # JSON keys must be strings, so we convert the tuple keys
        string_key_data = {str(key): value for key, value in data.items()}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(string_key_data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving data to file '{file_path}': {e}")


def update_entry(data: dict, cache_key: tuple, result: dict, max_entries: int):
    """Adds or updates an entry storing a structured `result` dict and ensures the total number of entries does not exceed the max."""

    # Store structured translation result instead of raw HTML. The consumer code should
    # store whatever structured payload is appropriate under the 'result' key.
    def update_entry(data: dict, cache_key: tuple, result: dict, max_entries: int):
        """Adds or updates an entry storing a structured `result` dict and ensures the total number of entries does not exceed the max."""
        # Ensure timestamp is present and up-to-date
        entry = dict(result)  # shallow copy to avoid mutating caller data
        entry["timestamp"] = datetime.now().isoformat()

        # Store structured translation result instead of raw HTML. The consumer code should
        # store whatever structured payload is appropriate under the 'result' key.
        data[cache_key] = {"result": entry, "timestamp": entry["timestamp"]}

        # If the number of entries exceeds the max, remove the oldest one(s)
        if len(data) > max_entries:
            # Sort items by timestamp (oldest first)
            sorted_items = sorted(data.items(), key=lambda item: item[1]["timestamp"])
            num_to_remove = len(sorted_items) - max_entries
            for i in range(num_to_remove):
                del data[sorted_items[i][0]]
