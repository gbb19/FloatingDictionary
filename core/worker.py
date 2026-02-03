"""
The main worker thread for handling OCR and translation tasks.
"""

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

        if cache_key not in self.dictionary_data:
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
        else:
            debug_print(f"Fetching from cache: {search_word}")
            debug_print("[PROFILING] Translation from cache took: 0.0000 seconds")
            # Backwards-compatible retrieval:
            # - New format: self.dictionary_data[cache_key] -> {'result': {...}, 'timestamp': ...}
            # - Older format: self.dictionary_data[cache_key] -> {'html': '...', 'timestamp': ...} or similar
            entry = self.dictionary_data.get(cache_key)
            formatted_translation = ""
            if isinstance(entry, dict):
                # Prefer structured payload if present
                if "result" in entry and isinstance(entry["result"], dict):
                    payload = entry["result"]
                    formatted_translation = (
                        payload.get("html") or payload.get("google_translation") or ""
                    )
                else:
                    # Older entry where HTML was stored at the top-level
                    formatted_translation = entry.get("html") or ""
            else:
                # Fallback: stringify whatever we have
                formatted_translation = str(entry)

        if self.last_processed_box == box:
            debug_print(f"Showing tooltip for: {search_word}")
            self.emitter.show_tooltip.emit(formatted_translation, box)
