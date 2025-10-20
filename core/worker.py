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
    def __init__(self, emitter, blink_callback, cancel_callback):
        super().__init__(daemon=True)
        self.queue = Queue()
        self.emitter = emitter
        self.blink_callback = blink_callback
        self.cancel_callback = cancel_callback
        self.translation_cache = {}
        self.last_processed_box = None

    def run(self):
        """The main loop of the worker thread."""
        while True:
            job = self.queue.get()
            if job is None:
                break
            
            self._process_job(job)

    def add_job(self):
        """Captures a screenshot and adds it as a job to the queue."""
        x, y = pyautogui.position()
        left = max(0, x - CAPTURE_WIDTH // 2)
        top = max(0, y - CAPTURE_HEIGHT // 2)
        
        screenshot = pyautogui.screenshot(region=(left, top, CAPTURE_WIDTH, CAPTURE_HEIGHT))
        self.queue.put({'screenshot': screenshot, 'cursor_pos': (x, y), 'region_top_left': (left, top)})

    def stop(self):
        """Signals the worker thread to stop."""
        self.queue.put(None)

    def _process_job(self, job):
        """Handles OCR, word finding, and initiates translation for a job."""
        screenshot = job['screenshot']
        cursor_x, cursor_y = job['cursor_pos']
        left, top = job['region_top_left']

        try:
            data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            self.emitter.show_tooltip.emit("<i>Tesseract Error</i>")
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
            self.emitter.show_tooltip.emit("<i>Loading...</i>")
            self.blink_callback(found_box)
            self._translate_and_show(found_box)
        else:
            self.cancel_callback()

    def _translate_and_show(self, box):
        """Fetches translations, formats, and displays them."""
        self.last_processed_box = box
        search_word = box['text'].strip(".,;:?!'\"-").lower()
        
        if not search_word:
            return

        if search_word not in self.translation_cache:
            print(f"กำลังค้นหา (Longdo & Google): {search_word}")
            soup = fetch_longdo_word(search_word)
            longdo_data = parse_longdo_data(soup) if soup else None
            google_translation = get_google_translation_sync(search_word)
            formatted_translation = format_combined_data(longdo_data, google_translation, search_word)
            self.translation_cache[search_word] = formatted_translation
        else:
            print(f"ดึงจาก Cache: {search_word}")
            formatted_translation = self.translation_cache[search_word]
        
        if self.last_processed_box == box:
            print(f"กำลังแสดง Tooltip สำหรับ: {search_word}")
            self.emitter.show_tooltip.emit(formatted_translation)