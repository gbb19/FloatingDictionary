"""
Handles reading from and writing to a single file-based JSON data store
that contains both translation cache and history timestamps.

This module stores translation cache entries keyed by a tuple:
    (search_word, source_lang, target_lang)

Each stored value is a dict. New entries use the structure:
    {
        "result": { ... structured result ... , "timestamp": "ISO..." },
        "timestamp": "ISO..."
    }

Older versions may have stored HTML directly under a top-level "html"
key; this module keeps backward-compatibility when loading existing files.

Functions:
- load_data(file_path) -> dict
- save_data(file_path, data) -> bool
- update_entry(data, cache_key, result, max_entries) -> None
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import time
from datetime import datetime
from typing import Any, Dict, Tuple

from utils.app_logger import debug_print


def load_data(file_path: str) -> Dict[Any, Any]:
    """
    Load the dictionary data from persistent storage.

    Behavior:
    - If the configured data store is SQLite (recommended), load from the SQLite DB.
    - Otherwise fall back to loading the JSON file as before.
    - Returns an empty dict if the file/DB is not found or invalid.
    """
    # Prefer SQLite when configured
    try:
        from config import DATA_STORE, SQLITE_DB_PATH

        if DATA_STORE == "sqlite":
            try:
                # local import to avoid import cycles at module import time
                from core.sql_store import get_all

                data = get_all(SQLITE_DB_PATH)
                if isinstance(data, dict):
                    return data
            except Exception as e_sql:
                # Fall back to JSON if any sqlite issue occurs, but log it.
                debug_print(f"sqlite load error, falling back to JSON: {e_sql}")
    except Exception:
        # If config import or attributes missing, fall back to JSON below.
        pass

    # Fallback: JSON file load (existing behavior)
    try:
        with open(str(file_path), "r", encoding="utf-8") as f:
            raw = json.load(f)
            # Convert string keys back to tuples using ast.literal_eval for safety.
            # We avoid using eval() on file contents. If a key cannot be parsed by
            # literal_eval, fall back to the original string key to avoid crashing.
            converted = {}
            for k, v in raw.items():
                try:
                    converted_key = ast.literal_eval(k)
                except Exception:
                    # Fallback: keep original string key (will be accessed as string)
                    converted_key = k
                converted[converted_key] = v
            return converted
    except (FileNotFoundError, json.JSONDecodeError):
        debug_print(f"Data file not found or invalid at '{file_path}'. Starting fresh.")
        return {}
    except Exception as e:
        # Unexpected errors should be visible in logs/console
        try:
            print(f"[FloatingDictionary] Error loading data from '{file_path}': {e}")
        except Exception:
            pass
        debug_print(f"Error loading data from '{file_path}': {e}")
        return {}


def save_data(file_path: str, data: Dict[Tuple[Any, ...], Any]) -> bool:
    """
    Persist the entire dictionary data.

    Behavior:
    - If configured to use SQLite, persist to the SQLite DB (preferred).
    - Otherwise fall back to atomic JSON write (existing behavior).
    Returns True on success, False on failure.
    """
    # Prefer SQLite when configured
    try:
        from config import DATA_STORE, SQLITE_DB_PATH

        if DATA_STORE == "sqlite":
            try:
                from core.sql_store import save_all

                return bool(save_all(SQLITE_DB_PATH, data))
            except Exception as e_sql:
                debug_print(f"sqlite save error, falling back to JSON: {e_sql}")
    except Exception:
        # Fall back to JSON if config not available
        pass

    # Fallback: atomic JSON write (existing implementation)
    file_path = str(file_path)
    tmp_path = None
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # Convert tuple keys to string keys (JSON-safe)
        string_key_data = {str(k): v for k, v in data.items()}

        tmp_path = f"{file_path}.tmp"

        # Write to temporary file first
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(string_key_data, f, ensure_ascii=False, indent=4)
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                # Not fatal if fsync isn't available
                pass

        # Attempt atomic replace with retries (handles transient locks on Windows)
        last_err = None
        for attempt in range(3):
            try:
                os.replace(tmp_path, file_path)
                try:
                    print(f"[FloatingDictionary] Saved data to '{file_path}'")
                except Exception:
                    pass
                debug_print(f"Saved data to '{file_path}' (replace)")
                return True
            except PermissionError as e:
                last_err = e
                debug_print(f"os.replace PermissionError attempt {attempt + 1}: {e}")
                # backoff to allow other processes to release file
                time.sleep(0.12 * (attempt + 1))
            except Exception as e:
                last_err = e
                debug_print(f"os.replace error attempt {attempt + 1}: {e}")
                # For unexpected errors, break to try fallbacks
                break

        # Fallback 1: try remove existing destination and replace
        try:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    debug_print(
                        f"Removed existing target file '{file_path}' to allow replace."
                    )
                except Exception as e_rm:
                    debug_print(f"Failed to remove existing file '{file_path}': {e_rm}")
            os.replace(tmp_path, file_path)
            try:
                print(f"[FloatingDictionary] Saved data to '{file_path}'")
            except Exception:
                pass
            debug_print(f"Saved data to '{file_path}' (replace after remove)")
            return True
        except Exception as e_replace_after_rm:
            last_err = e_replace_after_rm
            debug_print(f"os.replace after remove failed: {e_replace_after_rm}")

        # Fallback 2: shutil.move
        try:
            shutil.move(tmp_path, file_path)
            try:
                print(f"[FloatingDictionary] Saved data to '{file_path}' (shutil.move)")
            except Exception:
                pass
            debug_print(f"Saved data to '{file_path}' (shutil.move)")
            return True
        except Exception as e_shutil:
            last_err = e_shutil
            debug_print(f"shutil.move fallback failed: {e_shutil}")

        # Fallback 3: read tmp and write directly to destination
        try:
            with open(tmp_path, "r", encoding="utf-8") as fin:
                content = fin.read()
            with open(file_path, "w", encoding="utf-8") as fout:
                fout.write(content)
                try:
                    fout.flush()
                    os.fsync(fout.fileno())
                except Exception:
                    pass
            # Cleanup tmp
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            try:
                print(
                    f"[FloatingDictionary] Saved data to '{file_path}' (direct write)"
                )
            except Exception:
                pass
            debug_print(f"Saved data to '{file_path}' (direct write)")
            return True
        except Exception as e_final:
            last_err = e_final
            debug_print(f"Final write fallback failed: {e_final}")

        # All attempts failed
        try:
            print(
                f"[FloatingDictionary] Error saving data to '{file_path}': {last_err}"
            )
        except Exception:
            pass
        debug_print(f"Error saving data to file '{file_path}': {last_err}")

        # Clean up tmp if present
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        return False

    except Exception as e:
        # Unexpected top-level error
        try:
            print(f"[FloatingDictionary] Error saving data to '{file_path}': {e}")
        except Exception:
            pass
        debug_print(f"Error saving data to file '{file_path}': {e}")
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False


def update_entry(
    data: Dict[Tuple[Any, ...], Any],
    cache_key: Tuple[Any, ...],
    result: Dict[str, Any],
    max_entries: int,
):
    """
    Adds or updates an entry storing a structured `result` dict and ensures the
    total number of entries does not exceed `max_entries`.

    The `result` parameter is the structured translation payload (e.g.
    {'word':..., 'google_translation':..., 'longdo':..., 'html':..., ...}).
    This function will shallow-copy `result`, attach a fresh timestamp and
    store the value under 'result' with a top-level timestamp for easier sorting.
    """
    # Copy the provided result but DO NOT persist HTML inside the data file.
    # We will keep only structured fields under 'result' and a top-level timestamp.
    entry = dict(result)  # shallow copy to avoid mutating caller data

    # Remove any 'html' field from the payload so HTML/styling is not stored on disk.
    # HTML will be generated on-the-fly by the UI formatter when displaying entries.
    entry.pop("html", None)

    # Top-level timestamp for the stored entry
    top_timestamp = datetime.now().isoformat()

    # Build stored structure: 'result' contains structured fields (without html/timestamp)
    stored = {"result": entry, "timestamp": top_timestamp}

    data[cache_key] = stored

    # Trim oldest entries if exceeding max_entries
    if len(data) > max_entries:

        def _get_timestamp(item):
            # item is (key, value)
            val = item[1]
            if isinstance(val, dict):
                # Prefer top-level timestamp (string) if present
                ts = val.get("timestamp")
                if isinstance(ts, str) and ts:
                    return ts
                # Fall back to result.timestamp
                res = val.get("result")
                if isinstance(res, dict):
                    r_ts = res.get("timestamp")
                    if isinstance(r_ts, str):
                        return r_ts
            # Fallback very small/old value
            return ""

        sorted_items = sorted(data.items(), key=_get_timestamp)
        num_to_remove = len(sorted_items) - max_entries
        for i in range(num_to_remove):
            try:
                del data[sorted_items[i][0]]
            except Exception:
                # ignore deletion failures here (should not normally happen)
                pass
