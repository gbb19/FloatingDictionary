"""
The main worker thread for handling OCR and translation tasks.
"""
import pyautogui
from queue import Queue
import threading

import asyncio
import re
import pyautogui
from queue import Queue
import threading

from config import CAPTURE_WIDTH, CAPTURE_HEIGHT
from services.ocr import get_ocr_engine, OcrError
from services.translation import async_translate, fetch_longdo_word_async, parse_longdo_data, get_google_translation_sync
from ui.formatter import format_combined_data

class TranslationWorker(threading.Thread):
    def __init__(self, emitter):
        super().__init__(daemon=True)
        self.queue = Queue()
        self.emitter = emitter
        self.translation_cache = {}
        self.last_processed_box = None
        self.ocr_engine = get_ocr_engine()

    def run(self):
        while True:
            job = self.queue.get()
            if job is None:
                break
            self._process_job(job)

    def add_job(self, source_lang, target_lang):
        x, y = pyautogui.position()
        left = max(0, x - CAPTURE_WIDTH // 2)
        top = max(0, y - CAPTURE_HEIGHT // 2)
        screenshot = pyautogui.screenshot(region=(left, top, CAPTURE_WIDTH, CAPTURE_HEIGHT))
        self.queue.put({
            'screenshot': screenshot, 
            'cursor_pos': (x, y), 
            'region_top_left': (left, top),
            'source_lang': source_lang,
            'target_lang': target_lang
        })

    def add_sentence_job(self, sentence, bounding_rect, source_lang, target_lang):
        self.queue.put({
            'text': sentence, 
            'is_sentence': True,
            'bounding_rect': bounding_rect,
            'source_lang': source_lang,
            'target_lang': target_lang
        })

    def add_pre_ocr_job(self, region, source_lang, target_lang):
        rect = region.getRect()
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put({
            'screenshot': screenshot, 
            'region_top_left': (rect[0], rect[1]),
            'is_pre_ocr': True,
            'original_region': region,
            'source_lang': source_lang,
            'target_lang': target_lang
        })

    def add_ocr_and_translate_job(self, region, bounding_rect, source_lang, target_lang):
        rect = region.getRect()
        self.queue.put({
            'screenshot': pyautogui.screenshot(region=rect), 
            'is_ocr_and_translate': True,
            'bounding_rect': bounding_rect,
            'source_lang': source_lang,
            'target_lang': target_lang
        })

    def stop(self):
        self.queue.put(None)

    def _process_job(self, job):
        if job.get('is_ocr_and_translate', False):
            self._process_sentence(job.get('screenshot'), job)
            return

        if job.get('is_pre_ocr', False):
            self._process_pre_ocr(job.get('screenshot'), job['region_top_left'], job)
            return

        if job.get('is_sentence', False):
            source = job.get('text') or job.get('screenshot')
            if source:
                self._process_sentence(source, job)
            return

        screenshot = job.get('screenshot')
        cursor_x, cursor_y = job['cursor_pos']
        left, top = job['region_top_left']

        try:
            data = self.ocr_engine.image_to_data(screenshot, lang_code=job['source_lang'])
        except OcrError as e:
            self.emitter.show_tooltip.emit(f"<i>{e}</i>", None)
            return

        text_boxes = []
        for i in range(len(data['text'])):
            if data['text'][i].strip():
                text_boxes.append({
                    'text': data['text'][i],
                    'left': int(data['left'][i]) + left, 'top': int(data['top'][i]) + top,
                    'width': int(data['width'][i]), 'height': int(data['height'][i])
                })

        found_box = None
        for box in text_boxes:
            if (box['left'] <= cursor_x <= box['left'] + box['width'] and
                box['top'] <= cursor_y <= box['top'] + box['height']):
                found_box = box
                break
        
        if found_box:
            self.emitter.show_tooltip.emit("<i>Loading...</i>", found_box)
            self.emitter.blink_box.emit(found_box)
            self._translate_and_show(found_box, job)
        else:
            self.emitter.show_tooltip.emit("", None)

    def _process_sentence(self, source, job):
        bounding_rect = job.get('bounding_rect')
        source_lang = job.get('source_lang')
        target_lang = job.get('target_lang')

        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>", bounding_rect)
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else:
            try:
                sentence = self.ocr_engine.image_to_string(source, lang_code=source_lang)
                sentence = sentence.replace('\n', ' ').replace('-\n', '').strip()
            except OcrError as e:
                self.emitter.show_tooltip.emit(f"<i>{e}</i>", bounding_rect)
                return

        if not sentence:
            self.emitter.show_tooltip.emit("", bounding_rect)
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>", bounding_rect)
        google_result = get_google_translation_sync(sentence, dest_lang=target_lang, src_lang=source_lang)
        
        google_translation = google_result.text if hasattr(google_result, 'text') else str(google_result)

        formatted_text = (f"<p style='font-size: 14pt;'><b>{source_lang.upper()}:</b> {sentence}</p><hr>"
                        f"<p style='font-size: 14pt;'><b>{target_lang.upper()}:</b> {google_translation}</p>")
        self.emitter.show_tooltip.emit(formatted_text, bounding_rect)

    def _process_pre_ocr(self, screenshot, region_top_left, job):
        left, top = region_top_left
        try:
            data = self.ocr_engine.image_to_data(screenshot, lang_code=job['source_lang'])
            
            text_boxes = []
            for i in range(len(data['text'])):
                if data['text'][i].strip():
                    text_boxes.append({
                        'text': data['text'][i],
                        'left': int(data['left'][i]) + left, 'top': int(data['top'][i]) + top,
                        'width': int(data['width'][i]), 'height': int(data['height'][i])
                    })
            self.emitter.pre_ocr_ready.emit(text_boxes, job['original_region'])
        except OcrError as e:
            print(f"Pre-OCR Error: {e}")
            self.emitter.pre_ocr_ready.emit([], job.get('original_region'))

    def _translate_and_show(self, box, job):
        self.last_processed_box = box
        search_word = box['text'].strip(".,;:?!'\"-()[]{}").lower()
        source_lang = job['source_lang']
        target_lang = job['target_lang']
        
        if not search_word:
            return

        cache_key = (search_word, source_lang, target_lang)

        if cache_key not in self.translation_cache:
            print(f"Searching online for: {search_word}")

            async def _fetch_concurrently():
                is_english_like = bool(re.match(r'^[a-z]+', search_word))
                tasks = [async_translate(search_word, dest_lang=target_lang, src_lang=source_lang)]
                should_fetch_longdo = target_lang == 'th' and (source_lang == 'en' or (source_lang == 'auto' and is_english_like))
                if should_fetch_longdo:
                    print(f"'{search_word}' looks like English, fetching from Longdo concurrently...")
                    tasks.append(fetch_longdo_word_async(search_word))
                results = await asyncio.gather(*tasks)
                google_result = results[0]
                longdo_soup = results[1] if len(results) > 1 else None
                return google_result, longdo_soup

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            google_result, longdo_soup = loop.run_until_complete(_fetch_concurrently())
            loop.close()

            if not hasattr(google_result, 'src'):
                self.emitter.show_tooltip.emit(str(google_result), box)
                return

            detected_lang = google_result.src
            google_translation = google_result.text
            print(f"Google detected '{search_word}' as language: {detected_lang}")

            longdo_data = None
            if longdo_soup:
                print("Processing Longdo data...")
                longdo_data = parse_longdo_data(longdo_soup)
            
            formatted_translation = format_combined_data(
                longdo_data, 
                google_translation, 
                search_word,
                detected_lang,
                target_lang
            )
            self.translation_cache[cache_key] = formatted_translation
        else:
            print(f"Fetching from cache: {search_word}")
            formatted_translation = self.translation_cache[cache_key]
        
        if self.last_processed_box == box:
            print(f"Showing tooltip for: {search_word}")
            self.emitter.show_tooltip.emit(formatted_translation, box)

