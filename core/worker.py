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

    def add_sentence_job(self, sentence, bounding_rect):
        """Captures a screenshot of a specific region and adds it as a sentence job."""
        self.queue.put({
            'text': sentence, 
            'is_sentence': True,
            'bounding_rect': bounding_rect
        })

    def add_pre_ocr_job(self, region):
        """Captures a user-defined region for pre-OCR to find all word boxes for selection."""
        # --- [แก้ไข] รับ region ที่ผู้ใช้เลือกมาโดยตรง ---
        rect = region.getRect() # (x, y, width, height)
        screenshot = pyautogui.screenshot(region=rect)
        self.queue.put({
            'screenshot': screenshot, 
            'region_top_left': (rect[0], rect[1]), # The top-left corner of the selected region
            'is_pre_ocr': True,
            'original_region': region # --- [เพิ่ม] ส่ง region ต้นฉบับไปด้วย ---
        })

    def add_ocr_and_translate_job(self, region, bounding_rect):
        """Performs OCR and then immediately translates the entire result."""
        rect = region.getRect()
        self.queue.put({
            'screenshot': pyautogui.screenshot(region=rect), 
            'is_ocr_and_translate': True,
            'bounding_rect': bounding_rect
        })

    def stop(self):
        """Signals the worker thread to stop."""
        self.queue.put(None)

    def _process_job(self, job):
        """Handles OCR, word finding, and initiates translation for a job."""
        screenshot = job.get('screenshot') # Use .get() to avoid KeyError
        
        if job.get('is_ocr_and_translate', False):
            # --- [เพิ่ม] จัดการ Job ประเภท "แปลทั้งหมด" ---
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
            data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            self.emitter.show_tooltip.emit("<i>Tesseract Error</i>", None)
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
            self.emitter.blink_box.emit(found_box) # --- [แก้ไข] เปลี่ยนมาใช้การส่ง Signal ---
            self._translate_and_show(found_box)
        else:
            self.emitter.show_tooltip.emit("", None) # Just hide the tooltip

    def _process_sentence(self, source, bounding_rect=None):
        """Processes an entire image as a single sentence for translation."""
        self.emitter.show_tooltip.emit("<i>Reading sentence...</i>", bounding_rect)
        sentence = ""
        if isinstance(source, str):
            sentence = source
        else: # It's a screenshot
            try:
                # OCR the entire image as a single block of text
                sentence = pytesseract.image_to_string(source, lang='eng')
                sentence = sentence.replace('\n', ' ').replace('-\n', '').strip()
            except pytesseract.pytesseract.TesseractError as e:
                self.emitter.show_tooltip.emit(f"<i>Tesseract Error: {e}</i>", bounding_rect)
                return

        if not sentence:
            self.emitter.show_tooltip.emit("", bounding_rect) # Just hide the tooltip
            return

        self.emitter.show_tooltip.emit("<i>Translating sentence...</i>", bounding_rect)
        google_translation = get_google_translation_sync(sentence)
        formatted_text = f"<p style='font-size: 14pt;'><b>EN:</b> {sentence}</p><hr><p style='font-size: 14pt;'><b>TH:</b> {google_translation}</p>"
        self.emitter.show_tooltip.emit(formatted_text, bounding_rect)

    def _process_pre_ocr(self, screenshot, region_top_left, job):
        """Performs OCR and emits the found word boxes along with the original region."""
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
            self.emitter.pre_ocr_ready.emit(text_boxes, job['original_region'])
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Pre-OCR Tesseract Error: {e}")
            self.emitter.pre_ocr_ready.emit([], job.get('original_region')) # Emit empty list on error

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
            self.emitter.show_tooltip.emit(formatted_translation, box)