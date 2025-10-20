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

    def add_sentence_job(self, text_or_region):
        """Captures a screenshot of a specific region and adds it as a sentence job."""
        if isinstance(text_or_region, str):
            # If we already have the text, just translate it
            self.queue.put({'text': text_or_region, 'is_sentence': True})
        else:
            # If we have a region, take a screenshot
            screenshot = pyautogui.screenshot(region=text_or_region)
            self.queue.put({'screenshot': screenshot, 'is_sentence': True})

    def add_pre_ocr_job(self, region):
        """Captures a user-defined region for pre-OCR to find all word boxes for selection."""
        # --- [แก้ไข] รับ region ที่ผู้ใช้เลือกมาโดยตรง ---
        rect = region.getRect() # (x, y, width, height)
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put({
            'screenshot': screenshot, 
            'region_top_left': (rect[0], rect[1]), # The top-left corner of the selected region
            'is_pre_ocr': True
        })

    def stop(self):
        """Signals the worker thread to stop."""
        self.queue.put(None)

    def _process_job(self, job):
        """Handles OCR, word finding, and initiates translation for a job."""
        screenshot = job.get('screenshot') # Use .get() to avoid KeyError
        
        if job.get('is_pre_ocr', False):
            self._process_pre_ocr(screenshot, job['region_top_left'])
            return

        if job.get('is_sentence', False):
            if 'text' in job:
                self._process_sentence(job['text'])
            elif screenshot:
                self._process_sentence(screenshot)
            return

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
            self.emitter.blink_box.emit(found_box) # --- [แก้ไข] เปลี่ยนมาใช้การส่ง Signal ---
            self._translate_and_show(found_box)
        else:
            self.emitter.show_tooltip.emit("") # Just hide the tooltip

    def _process_sentence(self, source):
        """Processes an entire image as a single sentence for translation."""
        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>")
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else: # It's a screenshot
            try:
                # OCR the entire image as a single block of text
                sentence = pytesseract.image_to_string(source, lang='eng')
                sentence = sentence.replace('\n', ' ').replace('-\n', '').strip()
            except pytesseract.pytesseract.TesseractError as e:
                self.emitter.show_tooltip.emit(f"<i>Tesseract Error: {e}</i>")
                return

        if not sentence:
            self.emitter.show_tooltip.emit("") # Just hide the tooltip
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>")
        google_translation = get_google_translation_sync(sentence)
        formatted_text = f"<p style='font-size: 14pt;'><b>EN:</b> {sentence}</p><hr><p style='font-size: 14pt;'><b>TH:</b> {google_translation}</p>"
        self.emitter.show_tooltip.emit(formatted_text)

    def _process_pre_ocr(self, screenshot, region_top_left):
        """Performs OCR and emits the found word boxes."""
        left, top = region_top_left
        try:
            data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
            
            text_boxes = []
            for i in range(len(data['text'])):
                # --- [แก้ไข] นำตัวกรองค่าความมั่นใจ (confidence) ออก ---
                # เพื่อให้เห็นคำศัพท์ทั้งหมด เหมือนกับโหมด Ctrl+D
                if data['text'][i].strip():
                    text_boxes.append({
                        'text': data['text'][i],
                        'left': int(data['left'][i]) + left, 'top': int(data['top'][i]) + top,
                        'width': int(data['width'][i]), 'height': int(data['height'][i])
                    })
            # Emit the list of found boxes to the main thread
            self.emitter.pre_ocr_ready.emit(text_boxes)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Pre-OCR Tesseract Error: {e}")
            self.emitter.pre_ocr_ready.emit([]) # Emit empty list on error

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