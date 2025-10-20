"""
The main worker thread for handling OCR and translation tasks.
"""
import pyautogui
from queue import Queue
import threading

from config import CAPTURE_WIDTH, CAPTURE_HEIGHT, SOURCE_LANG, TARGET_LANG
from services.ocr import get_ocr_engine, OcrError
from services.translation import fetch_longdo_word, parse_longdo_data, get_google_translation_sync
from ui.formatter import format_combined_data

class TranslationWorker(threading.Thread):
    def __init__(self, emitter):
        super().__init__(daemon=True)
        self.queue = Queue()
        self.emitter = emitter
        self.translation_cache = {}
        self.last_processed_box = None
        # Get the configured OCR engine instance.
        self.ocr_engine = get_ocr_engine()

    def run(self):
        """The main loop of the worker thread."""
        while True:
            job = self.queue.get()
            if job is None:
                break
            
            self._process_job(job)

    def add_job(self):
        """Captures a screenshot around the cursor and adds it as a job to the queue."""
        x, y = pyautogui.position()
        left = max(0, x - CAPTURE_WIDTH // 2)
        top = max(0, y - CAPTURE_HEIGHT // 2)
        
        screenshot = pyautogui.screenshot(region=(left, top, CAPTURE_WIDTH, CAPTURE_HEIGHT))
        self.queue.put({'screenshot': screenshot, 'cursor_pos': (x, y), 'region_top_left': (left, top)})

    def add_sentence_job(self, sentence, bounding_rect):
        """Adds a job to translate a pre-defined sentence string."""
        self.queue.put({
            'text': sentence, 
            'is_sentence': True,
            'bounding_rect': bounding_rect
        })

    def add_pre_ocr_job(self, region):
        """Captures a user-defined region for pre-OCR to find all word boxes for selection."""
        rect = region.getRect()
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put({
            'screenshot': screenshot, 
            'region_top_left': (rect[0], rect[1]),
            'is_pre_ocr': True,
            'original_region': region
        })

    def add_ocr_and_translate_job(self, region, bounding_rect):
        """Adds a job to perform OCR on a region and then immediately translate the entire result."""
        rect = region.getRect()
        self.queue.put({
            'screenshot': pyautogui.screenshot(region=rect), 
            'is_ocr_and_translate': True,
            'bounding_rect': bounding_rect
        })

    def stop(self):
        """Signals the worker thread to stop by putting a None job in the queue."""
        self.queue.put(None)

    def _process_job(self, job):
        """Handles OCR, word finding, and initiates translation for a job."""
        screenshot = job.get('screenshot')
        
        if job.get('is_ocr_and_translate', False):
            self._process_sentence(screenshot, job.get('bounding_rect'))
            return

        if job.get('is_pre_ocr', False):
            self._process_pre_ocr(screenshot, job['region_top_left'], job)
            return

        if job.get('is_sentence', False):
            source = job.get('text') or screenshot
            if source:
                self._process_sentence(source, job.get('bounding_rect'))
            return

        cursor_x, cursor_y = job['cursor_pos']
        left, top = job['region_top_left']

        try:
            data = self.ocr_engine.image_to_data(screenshot, lang_code=SOURCE_LANG)
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
            self._translate_and_show(found_box)
        else:
            self.emitter.show_tooltip.emit("", None)

    def _process_sentence(self, source, bounding_rect=None):
        """Processes an entire image or a string as a single sentence for translation."""
        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>", bounding_rect)
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else: # The source is a screenshot
            try:
                sentence = self.ocr_engine.image_to_string(source, lang_code=SOURCE_LANG)
                sentence = sentence.replace('\n', ' ').replace('-\n', '').strip()
            except OcrError as e:
                self.emitter.show_tooltip.emit(f"<i>{e}</i>", bounding_rect)
                return

        if not sentence:
            self.emitter.show_tooltip.emit("", bounding_rect)
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>", bounding_rect)
        google_result = get_google_translation_sync(sentence, dest_lang=TARGET_LANG, src_lang=SOURCE_LANG)
        
        # Handle cases where translation might fail and return a string
        google_translation = google_result.text if hasattr(google_result, 'text') else str(google_result)

        formatted_text = (f"<p style='font-size: 14pt;'><b>{SOURCE_LANG.upper()}:</b> {sentence}</p><hr>"
                        f"<p style='font-size: 14pt;'><b>{TARGET_LANG.upper()}:</b> {google_translation}</p>")
        self.emitter.show_tooltip.emit(formatted_text, bounding_rect)

    def _process_pre_ocr(self, screenshot, region_top_left, job):
        """Performs OCR on a region and emits the found word boxes for the UI to handle."""
        left, top = region_top_left
        try:
            data = self.ocr_engine.image_to_data(screenshot, lang_code=SOURCE_LANG)
            
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

    def _translate_and_show(self, box):
        """Fetches translations, formats, and emits a signal to show them."""
        self.last_processed_box = box
        search_word = box['text'].strip(".,;:?!'\"-").lower()
        
        if not search_word:
            return

        cache_key = (search_word, SOURCE_LANG, TARGET_LANG)

        if cache_key not in self.translation_cache:
            print(f"Searching online for: {search_word}")

            # Always get Google translation first to detect the source language.
            google_result = get_google_translation_sync(search_word, dest_lang=TARGET_LANG, src_lang=SOURCE_LANG)

            # Handle cases where translation might fail and return a string error
            if not hasattr(google_result, 'src'):
                self.emitter.show_tooltip.emit(str(google_result), box)
                return

            detected_lang = google_result.src
            google_translation = google_result.text

            # Now, check if we should also fetch from Longdo.
            longdo_data = None
            if TARGET_LANG == 'th' and detected_lang == 'en':
                print(f"Detected English word '{search_word}', fetching from Longdo...")
                soup = fetch_longdo_word(search_word)
                longdo_data = parse_longdo_data(soup) if soup else None
            
            formatted_translation = format_combined_data(
                longdo_data, 
                google_translation, 
                search_word,
                detected_lang, # Use the detected language for display
                TARGET_LANG
            )
            self.translation_cache[cache_key] = formatted_translation
        else:
            print(f"Fetching from cache: {search_word}")
            formatted_translation = self.translation_cache[cache_key]
        
        if self.last_processed_box == box:
            print(f"Showing tooltip for: {search_word}")
            self.emitter.show_tooltip.emit(formatted_translation, box)
