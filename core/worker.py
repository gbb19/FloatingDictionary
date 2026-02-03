"""
The main worker thread for handling OCR and translation tasks.
"""

import ast
import asyncio
import re
import threading
import time
from queue import Queue

import pyautogui
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from googletrans.models import Translated

from config import CAPTURE_HEIGHT, CAPTURE_WIDTH, DATA_FILE_PATH, MAX_HISTORY_ENTRIES
from core.data_manager import load_data, save_data, update_entry
from services.ocr import OcrError, get_ocr_engine
from services.translation import (
    async_translate,
    fetch_longdo_word_async,
    parse_longdo_data,
)
from ui.formatter import format_combined_data
from utils.app_logger import debug_print


class TranslationWorker(threading.Thread):
    def __init__(self, emitter):
        super().__init__(daemon=True)
        self.queue = Queue()
        self.emitter = emitter
        self.last_processed_box = None
        self.dictionary_data = self._load_initial_data()
        self.ocr_engine = get_ocr_engine()
        # Runtime-only alias pointers: mapping cache_key -> canonical_key (tuple)
        # These aliases are kept in memory and not persisted to disk to avoid
        # storing redundant entries. They accelerate lookups for 'auto' source
        # language cases without polluting persistent storage.
        self.runtime_aliases = {}

    def _run_async_task(self, task):
        """Runs an async task in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(task)
        loop.close()
        return result

    def run(self):
        while True:
            job = self.queue.get()
            if job is None:
                break
            self._process_job(job)

    def _load_initial_data(self):
        """Loads the dictionary data from the file at startup."""
        debug_print(f"Loading data from '{DATA_FILE_PATH}'...")
        return load_data(DATA_FILE_PATH)

    def clear_history_and_cache(self):
        """Clears both in-memory and file-based history and cache."""
        debug_print("Clearing all history and cache...")
        self.dictionary_data.clear()
        save_data(DATA_FILE_PATH, self.dictionary_data)
        # Notify UI to update
        self.emitter.history_updated.emit(self.dictionary_data)

    def delete_entries(self, cache_keys: list):
        """Deletes specific entries from the dictionary data."""
        debug_print(f"Deleting {len(cache_keys)} entries...")
        for key in cache_keys:
            if key in self.dictionary_data:
                del self.dictionary_data[key]
        save_data(DATA_FILE_PATH, self.dictionary_data)
        self.emitter.history_updated.emit(self.dictionary_data)

    def add_job(self, source_lang, target_lang):
        x, y = pyautogui.position()
        left = max(0, x - CAPTURE_WIDTH // 2)
        top = max(0, y - CAPTURE_HEIGHT // 2)
        screenshot = pyautogui.screenshot(
            region=(left, top, CAPTURE_WIDTH, CAPTURE_HEIGHT)
        )
        self.queue.put(
            {
                "screenshot": screenshot,
                "cursor_pos": (x, y),
                "region_top_left": (left, top),
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
        )

    def add_sentence_job(self, sentence, bounding_rect, source_lang, target_lang):
        self.queue.put(
            {
                "text": sentence,
                "is_sentence": True,
                "bounding_rect": bounding_rect,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
        )

    def add_pre_ocr_job(self, region, source_lang, target_lang):
        rect = region.getRect()
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put(
            {
                "screenshot": screenshot,
                "region_top_left": (rect[0], rect[1]),
                "is_pre_ocr": True,
                "original_region": region,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
        )

    def add_ocr_and_translate_job(
        self, region, bounding_rect, source_lang, target_lang
    ):
        rect = region.getRect()
        self.queue.put(
            {
                "screenshot": pyautogui.screenshot(region=rect),
                "is_ocr_and_translate": True,
                "bounding_rect": bounding_rect,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
        )

    def stop(self):
        self.queue.put(None)
        save_data(DATA_FILE_PATH, self.dictionary_data)  # Save data on exit

    def _process_job(self, job):
        if job.get("is_ocr_and_translate", False):
            self._process_sentence(job.get("screenshot"), job)
            return

        if job.get("is_pre_ocr", False):
            self._process_pre_ocr(job.get("screenshot"), job["region_top_left"], job)
            return

        if job.get("is_sentence", False):
            source = job.get("text") or job.get("screenshot")
            if source:
                self._process_sentence(source, job)
            return

        screenshot = job.get("screenshot")
        cursor_x, cursor_y = job["cursor_pos"]
        left, top = job["region_top_left"]

        t_start = time.time()
        try:
            # Convert to grayscale for better OCR performance
            grayscale_screenshot = screenshot.convert("L")
            data = self.ocr_engine.image_to_data(
                grayscale_screenshot, lang_code=job["source_lang"]
            )
        except OcrError as e:
            self.emitter.show_tooltip.emit(f"<i>{e}</i>", None)
            return
        t_ocr_done = time.time()
        debug_print(
            f"[PROFILING] OCR processing took: {t_ocr_done - t_start:.4f} seconds"
        )

        text_boxes = []
        for i in range(len(data["text"])):
            if data["text"][i].strip():
                text_boxes.append(
                    {
                        "text": data["text"][i],
                        "left": int(data["left"][i]) + left,
                        "top": int(data["top"][i]) + top,
                        "width": int(data["width"][i]),
                        "height": int(data["height"][i]),
                    }
                )

        found_box = None
        for box in text_boxes:
            if (
                box["left"] <= cursor_x <= box["left"] + box["width"]
                and box["top"] <= cursor_y <= box["top"] + box["height"]
            ):
                found_box = box
                break

        if found_box:
            self.emitter.show_tooltip.emit("<i>Loading...</i>", found_box)
            self.emitter.blink_box.emit(found_box)
            self._translate_and_show(found_box, job)
        else:
            self.emitter.show_tooltip.emit("", None)

    def _process_sentence(self, source, job):
        bounding_rect = job.get("bounding_rect")
        source_lang = job.get("source_lang")
        target_lang = job.get("target_lang")

        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>", bounding_rect)
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else:
            try:
                sentence = self.ocr_engine.image_to_string(
                    source, lang_code=source_lang
                )
                sentence = sentence.replace("\n", " ").replace("-\n", "").strip()
            except OcrError as e:
                self.emitter.show_tooltip.emit(f"<i>{e}</i>", bounding_rect)
                return

        if not sentence:
            self.emitter.show_tooltip.emit("", bounding_rect)
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>", bounding_rect)

        task = async_translate(sentence, dest_lang=target_lang, src_lang=source_lang)
        google_result = self._run_async_task(task)

        # googletrans may return a Translated object (with .text and .src),
        # or HTML/Tag objects from other services, or plain strings.
        if isinstance(google_result, (Tag, NavigableString)):
            google_translation = google_result.text
        elif isinstance(google_result, Translated):
            # Extract the translated text from the Translated object
            google_translation = google_result.text
        else:
            google_translation = str(google_result)

        formatted_text = (
            f"<p style='font-size: 14pt;'><b>{source_lang.upper()}:</b> {sentence}</p><hr>"
            f"<p style='font-size: 14pt;'><b>{target_lang.upper()}:</b> {google_translation}</p>"
        )
        self.emitter.show_tooltip.emit(formatted_text, bounding_rect)

    def _process_pre_ocr(self, screenshot, region_top_left, job):
        left, top = region_top_left
        try:
            data = self.ocr_engine.image_to_data(
                screenshot, lang_code=job["source_lang"]
            )

            text_boxes = []
            for i in range(len(data["text"])):
                if data["text"][i].strip():
                    text_boxes.append(
                        {
                            "text": data["text"][i],
                            "left": int(data["left"][i]) + left,
                            "top": int(data["top"][i]) + top,
                            "width": int(data["width"][i]),
                            "height": int(data["height"][i]),
                        }
                    )
            self.emitter.pre_ocr_ready.emit(text_boxes, job["original_region"])
        except OcrError as e:
            debug_print(f"Pre-OCR Error: {e}")
            self.emitter.pre_ocr_ready.emit([], job.get("original_region"))

    def _translate_and_show(self, box, job):
        self.last_processed_box = box
        search_word = box["text"].strip(".,;:?!'\"-()[]{} ").lower()
        source_lang = job["source_lang"]
        target_lang = job["target_lang"]

        if not search_word:
            return

        cache_key = (search_word, source_lang, target_lang)

        # Smarter cache lookup: try exact match first, then look for any cache
        # entry with the same word and target_lang (covers cases where previous
        # runs cached detected language instead of 'auto').
        def _find_cache_alias():
            """
            Find a cache entry for the current request but resolve alias chains
            recursively so we always return a canonical stored entry (preferably
            the object that contains 'result' or top-level 'html').

            Returns:
                (canonical_key, canonical_entry) or (None, None)
            """

            def _resolve_chain(start_key, max_depth=10):
                """
                Follow alias pointers starting from start_key. Protect against cycles
                and malformed alias_for values. Returns (final_key, final_entry).

                This version consults runtime-only aliases (self.runtime_aliases)
                first so ephemeral in-memory aliases are used for resolution before
                inspecting persistent entries on disk.
                """
                visited = set()
                # Allow runtime alias to shortcut to a canonical key if present
                if isinstance(start_key, tuple) and getattr(
                    self, "runtime_aliases", None
                ):
                    runtime_target = self.runtime_aliases.get(start_key)
                    if runtime_target:
                        current_key = runtime_target
                    else:
                        current_key = start_key
                else:
                    current_key = start_key

                for _ in range(max_depth):
                    # Protect against cycles
                    if current_key in visited:
                        return current_key, self.dictionary_data.get(current_key)
                    visited.add(current_key)

                    # If a runtime alias exists for this key, follow it
                    if (
                        getattr(self, "runtime_aliases", None)
                        and current_key in self.runtime_aliases
                    ):
                        current_key = self.runtime_aliases[current_key]
                        continue

                    entry = self.dictionary_data.get(current_key)
                    # If entry is not an alias pointer, we've reached canonical
                    if not (isinstance(entry, dict) and "alias_for" in entry):
                        return current_key, entry

                    # Parse alias target robustly
                    alias_raw = entry.get("alias_for")
                    try:
                        alias_key = (
                            ast.literal_eval(alias_raw)
                            if isinstance(alias_raw, str)
                            else alias_raw
                        )
                    except Exception:
                        # Can't parse alias target; treat current as canonical
                        return current_key, entry

                    # Ensure alias_key is a tuple to be a valid cache key
                    if not isinstance(alias_key, tuple):
                        return current_key, entry

                    # If a runtime alias exists for the parsed alias_key, prefer it
                    if (
                        getattr(self, "runtime_aliases", None)
                        and alias_key in self.runtime_aliases
                    ):
                        alias_key = self.runtime_aliases[alias_key]

                    # Move to next target in chain
                    current_key = alias_key

                # Max depth reached; return what we have
                return current_key, self.dictionary_data.get(current_key)

            # 1) Exact match: if cache_key exists, resolve any alias chain starting there.
            if cache_key in self.dictionary_data:
                # Resolve chain starting from the exact key (this handles alias -> alias -> canonical)
                final_key, final_entry = _resolve_chain(cache_key)
                # If resolution found a different canonical entry, return it.
                if final_entry is not None:
                    return final_key, final_entry
                # Fallback: return the raw entry under cache_key
                return cache_key, self.dictionary_data.get(cache_key)

            # 2) Fallback search: look for any entry with same word and same target_lang.
            for k, v in self.dictionary_data.items():
                try:
                    if isinstance(k, tuple) and len(k) == 3:
                        if k[0] == search_word and k[2] == target_lang:
                            # If this stored key is an alias chain, resolve it from that key.
                            final_key, final_entry = _resolve_chain(k)
                            if final_entry is not None:
                                return final_key, final_entry
                            # Otherwise return the stored value as-is
                            return k, v
                except Exception:
                    continue

            return None, None

        found_key, cached_entry = _find_cache_alias()

        if cached_entry is not None:
            debug_print(f"Fetching from cache (alias key: {found_key}): {search_word}")
            debug_print("[PROFILING] Translation from cache took: 0.0000 seconds")
            # Normalize payload: support new structured format and older top-level HTML
            if (
                isinstance(cached_entry, dict)
                and "result" in cached_entry
                and isinstance(cached_entry["result"], dict)
            ):
                # structured format: prefer the pre-generated HTML at top-level if present.
                # If top-level html is missing, attempt to regenerate HTML from the structured 'result'
                # so cached entries remain displayable even if earlier runs didn't store top-level html.
                payload = cached_entry["result"]
                # Prefer an explicit top-level html stored on the entry, then any html inside the payload.
                formatted_translation = cached_entry.get("html") or payload.get("html")
                if not formatted_translation:
                    # Try to rebuild the HTML from structured parts using the formatter.
                    try:
                        formatted_translation = format_combined_data(
                            payload.get("longdo"),
                            payload.get("google_translation") or "",
                            payload.get("word") or search_word,
                            payload.get("detected_lang") or source_lang,
                            target_lang,
                        )
                    except Exception:
                        # As a fallback, show the best textual field available.
                        formatted_translation = (
                            payload.get("google_translation") or str(payload) or ""
                        )
            elif isinstance(cached_entry, dict):
                # older format where HTML/metadata stored at top-level
                formatted_translation = cached_entry.get("html") or ""
                payload = {
                    "html": formatted_translation,
                    "timestamp": cached_entry.get("timestamp"),
                }
            else:
                formatted_translation = str(cached_entry)
                payload = {"html": formatted_translation}

            # If we found an alias (e.g. cached under detected language) and the incoming
            # request used 'auto', create a lightweight alias entry so future lookups
            # using the same (word, 'auto', target) will hit the cache directly.
            if found_key != cache_key and source_lang == "auto":
                try:
                    # Create a lightweight pointer alias instead of duplicating the full result.
                    # Prefer to use the canonical tuple key we already found. If found_key
                    # is not a tuple (unexpected), fall back to cache_key so we don't pass None.
                    if isinstance(found_key, tuple):
                        canonical_key_for_alias = found_key
                    else:
                        # As a safe fallback, attempt to parse if it's a string representation
                        try:
                            parsed = (
                                ast.literal_eval(found_key)
                                if isinstance(found_key, str)
                                else None
                            )
                            canonical_key_for_alias = (
                                parsed if isinstance(parsed, tuple) else cache_key
                            )
                        except Exception:
                            canonical_key_for_alias = cache_key
                    # Store the canonical key as a string so it survives JSON serialization.

                    # Only insert alias pointer if it doesn't already exist and point to the same canonical.
                    # We prefer to keep pointer aliases in-memory only to avoid persisting redundant entries.
                    existing_runtime = getattr(self, "runtime_aliases", {}).get(
                        cache_key
                    )
                    existing_disk = self.dictionary_data.get(cache_key)

                    # Determine where the existing alias points to, if any
                    existing_points_to = None
                    if existing_runtime is not None:
                        existing_points_to = existing_runtime
                    elif isinstance(existing_disk, dict) and isinstance(
                        existing_disk.get("alias_for"), str
                    ):
                        try:
                            # Only call literal_eval when alias_for is a string to avoid
                            # passing None or other unexpected types to ast.literal_eval.
                            existing_points_to = ast.literal_eval(
                                existing_disk["alias_for"]
                            )
                        except Exception:
                            existing_points_to = None

                    if existing_points_to != canonical_key_for_alias:
                        # Store alias in-memory only
                        if not hasattr(self, "runtime_aliases"):
                            self.runtime_aliases = {}
                        self.runtime_aliases[cache_key] = canonical_key_for_alias
                        debug_print(
                            f"Created in-memory pointer cache alias for key: {cache_key} -> {canonical_key_for_alias}"
                        )
                    else:
                        debug_print(
                            f"Alias for {cache_key} already exists and points to {canonical_key_for_alias}; skipping"
                        )
                except Exception as e:
                    debug_print(f"Failed to create cache alias for {cache_key}: {e}")
        else:
            debug_print(f"Searching online for: {search_word}")
            t_translate_start = time.time()

            async def _fetch_concurrently():
                is_english_like = bool(re.match(r"^[a-z]+", search_word))
                tasks = [
                    async_translate(
                        search_word, dest_lang=target_lang, src_lang=source_lang
                    )
                ]
                should_fetch_longdo = target_lang == "th" and (
                    source_lang == "en" or (source_lang == "auto" and is_english_like)
                )
                if should_fetch_longdo:
                    debug_print(
                        f"'{search_word}' looks like English, fetching from Longdo concurrently..."
                    )
                    tasks.append(fetch_longdo_word_async(search_word))
                results = await asyncio.gather(*tasks)
                google_result = results[0]
                longdo_soup = results[1] if len(results) > 1 else None
                return google_result, longdo_soup

            google_result, longdo_soup = self._run_async_task(_fetch_concurrently())

            t_translate_done = time.time()
            debug_print(
                f"[PROFILING] Network translation took: {t_translate_done - t_translate_start:.4f} seconds"
            )

            if not hasattr(google_result, "src"):
                self.emitter.show_tooltip.emit(str(google_result), box)
                return

            if isinstance(google_result, Translated):
                detected_lang = google_result.src
                google_translation = google_result.text
            else:
                detected_lang = source_lang
                google_translation = str(google_result)

            debug_print(f"Google detected '{search_word}' as language: {detected_lang}")

            longdo_data = None
            if isinstance(longdo_soup, BeautifulSoup):
                debug_print("Processing Longdo data...")
                longdo_data = parse_longdo_data(longdo_soup)

            # Build a structured result to store in history/cache instead of raw HTML.
            result = {
                "word": search_word,
                "detected_lang": detected_lang,
                "target_lang": target_lang,
                "google_translation": google_translation,
                "longdo": longdo_data,
            }

            # Pre-generate the HTML for quick display but keep structured data too.
            formatted_translation = format_combined_data(
                longdo_data,
                google_translation,
                search_word,
                detected_lang,
                target_lang,
            )
            result["html"] = formatted_translation

            # If the original source was 'auto', create a new, more specific cache key
            # with the language that Google actually detected.
            final_cache_key = (
                (search_word, detected_lang, target_lang)
                if source_lang == "auto"
                else cache_key
            )

            # Update the central data store with structured entry
            update_entry(
                self.dictionary_data,
                final_cache_key,
                result,
                MAX_HISTORY_ENTRIES,
            )

            # Notify main thread about update and persist to disk
            self.emitter.history_updated.emit(self.dictionary_data)
            save_data(DATA_FILE_PATH, self.dictionary_data)

        if self.last_processed_box == box:
            debug_print(f"Showing tooltip for: {search_word}")
            # Debug: inspect formatted_translation before emitting to UI.
            # Log a truncated preview and length to avoid flooding logs with huge HTML.
            try:
                if isinstance(formatted_translation, str):
                    preview = formatted_translation[:1000]
                    debug_print(
                        f"formatted_translation length={len(formatted_translation)} preview={preview!s}"
                    )
                else:
                    # Not a string (unexpected) — log its repr safely.
                    debug_print(
                        f"formatted_translation repr: {repr(formatted_translation)}"
                    )
            except Exception as _exc:
                # Ensure we never crash while attempting to log debug info.
                try:
                    debug_print("formatted_translation: <unprintable>")
                except Exception:
                    pass
            self.emitter.show_tooltip.emit(formatted_translation, box)
