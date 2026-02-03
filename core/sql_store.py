"""
SQLite-backed store for dictionary cache entries.

This module provides a small synchronous API to persist and retrieve
translation cache entries using SQLite. Each entry is stored as a row
(key TEXT PRIMARY KEY, value TEXT JSON, timestamp TEXT).

Design notes:
- Keys are stored as stringified tuple representations (e.g. "('word','en','th')")
  to preserve the existing format used elsewhere in the project.
- Values are stored as JSON text so complex structured payloads can be persisted.
- API is intentionally small and synchronous; the worker thread uses it
  on cache misses and when persisting newly fetched translations.

Public functions:
- init_db(db_path: str) -> None
- get_all(db_path: str) -> Dict[Tuple|str, Any]
- get_entry(db_path: str, key: Tuple|str) -> Optional[Any]
- save_all(db_path: str, data: Dict[Tuple, Any]) -> bool
- save_entry(db_path: str, key: Tuple|str, value: Any) -> bool
- delete_entry(db_path: str, key: Tuple|str) -> bool
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, Optional, Tuple

# Local logger used in project
try:
    from utils.app_logger import debug_print
except Exception:  # pragma: no cover - defensive in case imports differ in test env

    def debug_print(*args, **kwargs):
        try:
            print(*args, **kwargs)
        except Exception:
            pass


def _ensure_db(db_path: str) -> sqlite3.Connection:
    """
    Ensure the SQLite database exists and the `cache` table is present.
    Returns an open sqlite3.Connection. Caller must close the connection.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    # Use a short timeout to reduce risk of long blocking on Windows locks.
    conn = sqlite3.connect(db_path, timeout=5)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    return conn


def init_db(db_path: str) -> None:
    """
    Initialize the database file and table if not present.
    """
    conn = _ensure_db(db_path)
    conn.close()


def ast_literal_eval_safe(s: str):
    """
    Safely attempt to convert a stringified Python literal back to a Python object.
    Falls back to returning the original string on failure.
    """
    import ast

    try:
        return ast.literal_eval(s)
    except Exception:
        return s


def get_all(db_path: str) -> Dict[Tuple[Any, ...] | str, Any]:
    """
    Return a dict of all entries in the DB. Keys will be converted to tuples
    where possible using ast.literal_eval, otherwise left as strings.
    """
    try:
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM cache")
        rows = cur.fetchall()
        conn.close()
        out: Dict[Tuple[Any, ...] | str, Any] = {}
        for key_str, value_text in rows:
            key = ast_literal_eval_safe(key_str)
            try:
                val = json.loads(value_text)
            except Exception:
                # If value isn't valid JSON, return raw text
                val = value_text
            out[key] = val
        return out
    except Exception as e:
        debug_print(f"[sql_store] get_all error: {e}")
        return {}


def get_entry(db_path: str, key: Tuple[Any, ...] | str) -> Optional[Any]:
    """
    Retrieve a single entry by key (tuple or string). Returns parsed value or None.
    """
    key_str = str(key)
    try:
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM cache WHERE key = ?", (key_str,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        value_text = row[0]
        try:
            return json.loads(value_text)
        except Exception:
            return value_text
    except Exception as e:
        debug_print(f"[sql_store] get_entry error for {key_str}: {e}")
        return None


def find_by_word_target(
    db_path: str, word: str, target_lang: str
) -> Dict[Tuple[Any, ...] | str, Any]:
    """
    Find entries whose key corresponds to a tuple of the form (word, src_lang, target_lang).
    Returns a mapping of parsed key -> value for entries that match the provided word and target_lang.

    Implementation notes:
    - Keys are stored as their stringified tuple representation (e.g. \"('dispatch','en','th')\").
    - SQLite does not easily support parsing Python tuple text; we read candidate rows and
      filter in Python using a safe ast literal eval helper (`ast_literal_eval_safe`).
    - This function is intended for on-demand lookups by word+target without loading the entire DB.
    """
    results: Dict[Tuple[Any, ...] | str, Any] = {}
    try:
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        # Fetch keys and values; we perform filtering in Python for robustness.
        cur.execute("SELECT key, value FROM cache")
        rows = cur.fetchall()
        conn.close()

        for key_str, value_text in rows:
            parsed_key = ast_literal_eval_safe(key_str)
            # Expect parsed_key to be a tuple like (word, src, tgt)
            if isinstance(parsed_key, tuple) and len(parsed_key) >= 3:
                k_word = parsed_key[0]
                k_target = parsed_key[2]
                if isinstance(k_word, str) and isinstance(k_target, str):
                    if k_word == word and k_target == target_lang:
                        try:
                            val = json.loads(value_text)
                        except Exception:
                            val = value_text
                        results[parsed_key] = val
        return results
    except Exception as e:
        debug_print(f"[sql_store] find_by_word_target error: {e}")
        return {}


def save_all(db_path: str, data: Dict[Tuple[Any, ...], Any]) -> bool:
    """
    Replace the entire cache table contents with the provided data dict.
    This is done in a single transaction for atomicity.
    """
    try:
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        cur.execute("BEGIN")
        try:
            cur.execute("DELETE FROM cache")
            items = []
            for k, v in data.items():
                key_str = str(k)
                try:
                    val_text = json.dumps(v, ensure_ascii=False)
                except Exception:
                    # Fallback to string representation
                    val_text = str(v)
                items.append((key_str, val_text, time.strftime("%Y-%m-%dT%H:%M:%S")))
            if items:
                cur.executemany(
                    "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
                    items,
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return True
    except Exception as e:
        debug_print(f"[sql_store] save_all error: {e}")
        return False


def save_entry(db_path: str, key: Tuple[Any, ...] | str, value: Any) -> bool:
    """
    Upsert a single entry into the cache table.
    """
    try:
        key_str = str(key)
        try:
            val_text = json.dumps(value, ensure_ascii=False)
        except Exception:
            val_text = str(value)
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, datetime('now'))",
            (key_str, val_text),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        debug_print(f"[sql_store] save_entry error for {key}: {e}")
        return False


def delete_entry(db_path: str, key: Tuple[Any, ...] | str) -> bool:
    """
    Delete a single entry identified by key. Returns True on success.
    """
    try:
        key_str = str(key)
        conn = _ensure_db(db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM cache WHERE key = ?", (key_str,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        debug_print(f"[sql_store] delete_entry error for {key}: {e}")
        return False
