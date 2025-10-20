"""
The main worker thread for handling OCR and translation tasks.
"""
import pyautogui
import pytesseract
from queue import Queue
import threading

from config import CAPTURE_WIDTH, CAPTURE_HEIGHT


from services.translation import fetch_longdo_word, parse_longdo_data, get_google_translation_sync
from ui.formatter import format_combined_data

class TranslationWorker(threading.Thread):
    def __init__(self, emitter):
        super().__init__(daemon=True)
        self.queue = Queue()
        self.emitter = emitter
        self.translation_cache = {}
        self.last_processed_box = None

    def run(self):
        """The main loop of the worker thread."""
        while True:
            job = self.queue.get()
            # A None job is a signal to stop the thread.
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
        rect = region.getRect() # (x, y, width, height)
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put({
            'screenshot': screenshot, 
            'region_top_left': (rect[0], rect[1]), # The top-left corner of the selected region
            'is_pre_ocr': True,
            'original_region': region # Pass the original region for the UI to use
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
        screenshot = job.get('screenshot') # Use .get() to safely access the key
        
        # Route the job to the correct processing method based on its type
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

        # Default job: Find word under cursor from a screenshot
        cursor_x, cursor_y = job['cursor_pos']
        left, top = job['region_top_left']

        try:
            data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            self.emitter.show_tooltip.emit("<i>Tesseract Error</i>", None)
            return

        text_boxes = []
        for i in range(len(data['text'])):
            if data['text'][i].strip():
                # Adjust box coordinates to be screen-absolute
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
            self.emitter.show_tooltip.emit("", None) # Hide tooltip if no word is found

    def _process_sentence(self, source, bounding_rect=None):
        """Processes an entire image or a string as a single sentence for translation."""
        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>", bounding_rect)
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else: # The source is a screenshot
            try:
                # OCR the entire image as a single block of text
                sentence = pytesseract.image_to_string(source, lang='eng')
                # Clean up OCR results by replacing newlines
                sentence = sentence.replace('\n', ' ').replace('-\n', '').strip()
            except pytesseract.pytesseract.TesseractError as e:
                self.emitter.show_tooltip.emit(f"<i>Tesseract Error: {e}</i>", bounding_rect)
                return

        if not sentence:
            self.emitter.show_tooltip.emit("", bounding_rect)
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>", bounding_rect)
        google_translation = get_google_translation_sync(sentence)
        formatted_text = f"<p style='font-size: 14pt;'><b>EN:</b> {sentence}</p><hr><p style='font-size: 14pt;'><b>TH:</b> {google_translation}</p>"
        self.emitter.show_tooltip.emit(formatted_text, bounding_rect)

    def _process_pre_ocr(self, screenshot, region_top_left, job):
        """Performs OCR on a region and emits the found word boxes for the UI to handle."""
        left, top = region_top_left
        try:
            data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
            
            text_boxes = []
            for i in range(len(data['text'])):
                # No confidence filter is applied here to ensure all potential words
                # are available for the user to select in the UI.
                if data['text'][i].strip():
                    text_boxes.append({
                        'text': data['text'][i],
                        'left': int(data['left'][i]) + left, 'top': int(data['top'][i]) + top,
                        'width': int(data['width'][i]), 'height': int(data['height'][i])
                    })
            # Emit the list of found boxes to the main thread for the overlay to display
            self.emitter.pre_ocr_ready.emit(text_boxes, job['original_region'])
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Pre-OCR Tesseract Error: {e}")
            self.emitter.pre_ocr_ready.emit([], job.get('original_region')) # Emit empty list on error

    def _translate_and_show(self, box):
        """Fetches translations, formats, and emits a signal to show them."""
        self.last_processed_box = box
        # Sanitize the word before searching
        search_word = box['text'].strip(".,;:?!'\"-").lower()
        
        if not search_word:
            return

        if search_word not in self.translation_cache:
            print(f"Searching (Longdo & Google): {search_word}")
            soup = fetch_longdo_word(search_word)
            longdo_data = parse_longdo_data(soup) if soup else None
            google_translation = get_google_translation_sync(search_word)
            formatted_translation = format_combined_data(longdo_data, google_translation, search_word)
            self.translation_cache[search_word] = formatted_translation
        else:
            print(f"Fetching from cache: {search_word}")
            formatted_translation = self.translation_cache[search_word]
        
        # Ensure the tooltip corresponds to the most recently processed word
        if self.last_processed_box == box:
            print(f"Showing tooltip for: {search_word}")
            self.emitter.show_tooltip.emit(formatted_translation, box)