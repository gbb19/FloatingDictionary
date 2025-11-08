"""
Handles reading from and writing to a file-based JSON history for translated words.
"""

import json
from datetime import datetime
from utils.app_logger import debug_print

def load_history(file_path: str, max_entries: int) -> list:
    """
    Loads the translation history from a JSON file.
    Returns an empty list if the file doesn't exist or is invalid.
    Each entry is a dict: {'cache_key': (word, src, dest), 'timestamp': 'ISO_FORMAT_STRING'}
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history_raw = json.load(f)
            # Convert string keys back to tuples for cache_key
            history = []
            for entry in history_raw:
                if 'cache_key' in entry and isinstance(entry['cache_key'], list):
                    entry['cache_key'] = tuple(entry['cache_key'])
                history.append(entry)
            return history[-max_entries:] # Ensure history is limited on load
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(f"History file not found or invalid at '{file_path}'. Starting with an empty history.")
        return []

def save_history(file_path: str, history_data: list):
    """
    Saves the translation history to a JSON file.
    """
    try:
        # Convert tuple cache_key back to list for JSON serialization
        history_to_save = []
        for entry in history_data:
            entry_copy = entry.copy()
            if 'cache_key' in entry_copy and isinstance(entry_copy['cache_key'], tuple):
                entry_copy['cache_key'] = list(entry_copy['cache_key'])
            history_to_save.append(entry_copy)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history_to_save, f, ensure_ascii=False, indent=4)
    except IOError as e:
        debug_print(f"Error saving history to file '{file_path}': {e}")

def add_history_entry(history_data: list, cache_key: tuple, max_entries: int):
    """Adds a new entry to the history, ensuring uniqueness and limiting size."""
    # Remove existing entry with the same cache_key to avoid duplicates and bring to front
    history_data[:] = [entry for entry in history_data if entry['cache_key'] != cache_key]
    
    new_entry = {
        'cache_key': cache_key,
        'timestamp': datetime.now().isoformat()
    }
    history_data.append(new_entry)
    
    # Keep only the most recent entries
    history_data[:] = history_data[-max_entries:]