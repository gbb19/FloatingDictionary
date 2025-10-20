import sys
import os
import pyautogui
import pytesseract
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QScrollArea, QSystemTrayIcon, QMenu, QAction, QStyle
from PyQt5.QtCore import Qt, QRect, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import QCursor, QPainter, QPen, QIcon, QColor, QLinearGradient
import threading
import requests
from queue import Queue
from bs4 import BeautifulSoup
import re
import asyncio
from googletrans import Translator 
import ctypes # สำหรับเรียกใช้ Windows API
from pynput import keyboard as pynput_keyboard

# -------------------------------------------------------------------
# 1. ส่วน Tesseract
# -------------------------------------------------------------------
def get_executable_path(name):
    """
    หา Path ของไฟล์ที่ถูกรวมเข้ามากับโปรแกรม (สำหรับ PyInstaller)
    """
    if getattr(sys, 'frozen', False):
        # ถ้ากำลังรันจากไฟล์ .exe ที่ build แล้ว
        base_path = sys._MEIPASS
    else:
        # ถ้ารันจากสคริปต์ .py ปกติ
        base_path = os.path.abspath(".")
    return os.path.join(base_path, name)

def setup_tessdata_env():
    """
    ตั้ง TESSDATA_PREFIX environment variable ให้ถูกต้อง
    """
    tessdata_dir = get_executable_path(os.path.join("Tesseract-OCR", "tessdata"))
    tessdata_dir_forward = tessdata_dir.replace('\\', '/')
    
    os.environ['TESSDATA_PREFIX'] = tessdata_dir_forward
    print(f"✓ ตั้ง TESSDATA_PREFIX = {tessdata_dir_forward}")

# เรียกใช้ก่อนสั่ง pytesseract
setup_tessdata_env()

# ตอนนี้ส่วน Tesseract initialization จะทำงานสำเร็จ
try:
    tesseract_path = get_executable_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    pytesseract.get_tesseract_version() 
    print("✓ Tesseract เตรียมพร้อมแล้ว")
except Exception as e:
    print("="*50)
    print("!!! Tesseract OCR ไม่ถูกต้อง !!!")
    print(f"Error: {e}")
    print("="*50)
    sys.exit(1)

# -------------------------------------------------------------------
# 2. ส่วน Google Translate (แก้ไขแล้ว)
# -------------------------------------------------------------------
async def async_translate(text):
    """
    ฟังก์ชัน async สำหรับ Google Translate
    """
    # --- ⬇️⬇️⬇️ [แก้ไขจุดที่ 1] ⬇️⬇️⬇️ ---
    # ลบ 'service_urls' ออก เพราะอาจทำให้บางเครื่องมีปัญหา
    # ใช้แบบเดียวกับโค้ดตัวอย่างของคุณที่ทำงานได้
    translator = Translator()
    # --- ⬆️⬆️⬆️ [แก้ไขจุดที่ 1] ⬆️⬆️⬆️ ---
    
    try:
        # translator.translate() เป็น async (coroutine) อยู่แล้ว
        result = await translator.translate(text, src='en', dest='th')
        return result.text
    except Exception as e:
        print(f"Google Translate Error: {e}")
        return f"Google Error: {e}"

def get_translation_sync(text):
    """
    ฟังก์ชันสำหรับรัน async_translate ใน Thread
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_translate(text))
        return result
    except Exception as e:
        print(f"Sync/Async Loop Error: {e}")
        return f"Sync Error: {e}"
    finally:
        if loop:
            loop.close()


# -------------------------------------------------------------------
# 3. ส่วน Longdo Scraper (เหมือนเดิม)
# -------------------------------------------------------------------
def fetch_word(word: str) -> BeautifulSoup | None:
    url = f"https://dict.longdo.com/mobile.php?search={word}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Longdo: {e}")
        return None

def parse_data(soup: BeautifulSoup) -> dict:
    results = { "translations": [], "examples": [] }
    target_dict_names = [
        'NECTEC Lexitron Dictionary EN-TH',
        'Nontri Dictionary'
    ]
    
    for dict_name in target_dict_names:
        header = soup.find('b', string=dict_name)
        if header:
            table = header.find_next_sibling('table', class_='result-table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        
                        # [แก้ไขแล้ว] เซลล์คำศัพท์ (cells[0])
                        word = cells[0].get_text(strip=True)
                        
                        # [คงเดิม] เซลล์คำแปล (cells[1])
                        definition_raw = cells[1].get_text(strip=True, separator=' ')
                        
                        pos = "N/A"
                        translation = definition_raw
                        match = re.match(r'\s*\((.*?)\)\s*(.*)', definition_raw, re.DOTALL)
                        
                        if match:
                            pos = match.group(1).strip()
                            translation = match.group(2).strip()
                            translation_match = re.match(r'^(pron|adj|det|n|v|adv|int|conj)\.?(.*)', translation, re.IGNORECASE | re.DOTALL)
                            if translation_match:
                                pos = translation_match.group(1).strip('.')
                                translation = translation_match.group(2).strip()
                        
                        # --- ⬇️⬇️⬇️ [เพิ่ม 2 บรรทัดนี้] ⬇️⬇️⬇️ ---
                        # ซ่อมแซมคำที่ถูก 'separator' แยก
                        translation = translation.replace("your self", "yourself")
                        translation = translation.replace("your selves", "yourselves")
                        # --- ⬆️⬆️⬆️ [เพิ่ม 2 บรรทัดนี้] ⬆️⬆️⬆️ ---

                        results["translations"].append({
                            "dictionary": dict_name.replace("NECTEC Lexitron Dictionary EN-TH", "NECTEC"),
                            "word": word,
                            "pos": pos,
                            "translation": translation
                        })

    # --- ส่วนค้นหาตัวอย่างประโยค (เหมือนเดิม) ---
    string_element = soup.find(string=re.compile(r'^\s*ตัวอย่างประโยคจาก Open Subtitles'))
    table = None
    if string_element:
        header = string_element.parent
        if hasattr(header, 'find_next_sibling'):
            table = header.find_next_sibling('table', class_='result-table')

    if table:
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            sentence_parts = row.find_all('font', color='black')
            if len(sentence_parts) == 2:
                eng_sentence = sentence_parts[0].get_text(strip=True, separator=' ')
                thai_sentence = sentence_parts[1].get_text(strip=True, separator=' ')
                results["examples"].append({"en": eng_sentence, "th": thai_sentence})

    return results

# -------------------------------------------------------------------
# 4. ส่วนจัดรูปแบบ Tooltip
# -------------------------------------------------------------------
def format_combined_data(longdo_data: dict | None, google_translation: str, search_word: str) -> str:
    output_lines = []

    # --- 1. Search Term (หัวข้อใหญ่) ---
    output_lines.append(f"<p style='font-size: 20pt; font-weight: bold; color: #ffffff; margin-bottom: 0px;'>{search_word}</p><hr style='margin: 2px 0 4px 0; border-color: #666;'>")
    
    # --- 2. Google Translate Section ---
    output_lines.append("<p style='font-size: 16pt; margin: 5px 0 2px 0;'><u><b>Google Translate:</b></u></p>")
    if google_translation and "Error" not in google_translation and google_translation.lower() != search_word.lower():
        output_lines.append(f"<p style='margin: 0;'>&#8226; {google_translation}</p>")
    else:
        output_lines.append(f"<p style='margin: 0;'><i>(ไม่สามารถแปลได้)</i></p>")
    
    # --- 3. Longdo Dict Section ---
    output_lines.append("<p style='font-size: 16pt; margin: 8px 0 2px 0;'><u><b>Longdo Dict:</b></u></p>")
    
    if longdo_data and longdo_data['translations']:
        for item in longdo_data['translations']:
            line = f"<p style='margin: 0 0 4px 0;'>&#8226; <b>{item['word']}</b> [{item['pos']}] {item['translation']} ({item['dictionary']})</p>"
            output_lines.append(line)
    elif longdo_data:
        output_lines.append("<p style='margin: 0;'><i>(ไม่พบคำแปล)</i></p>")
    else:
        output_lines.append("<p style='margin: 0;'><i>(เชื่อมต่อล้มเหลว)</i></p>")
    
    # --- 4. Examples Section ---
    if longdo_data and longdo_data['examples']:
        output_lines.append("<p style='font-size: 16pt; margin: 8px 0 2px 0;'><u><b>ตัวอย่างประโยค (Longdo):</b></u></p>")
        for ex in longdo_data['examples'][:2]: 
            output_lines.append(f"<p style='margin: 0 0 4px 0;'>&#8226; <i>EN:</i> {ex['en']}<br>  <i>&#8594; TH:</i> {ex['th']}</p>")
    
    return f"<div style='font-family: Segoe UI, Arial; font-size: 14pt; line-height: 1.4;'>{''.join(output_lines)}</div>"

# -------------------------------------------------------------------
# 5. ส่วน PyQt5 Application (เหมือนเดิม)
# -------------------------------------------------------------------

def force_set_focus(hwnd):
    """
    [เพิ่มใหม่] ฟังก์ชันสำหรับบังคับให้ Focus ไปยังหน้าต่างที่ระบุ (hwnd)
    โดยใช้เทคนิค AttachThreadInput เพื่อให้มั่นใจว่าสำเร็จ
    """
    if not hwnd:
        return
    try:
        our_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        target_thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)

        if our_thread_id != target_thread_id:
            ctypes.windll.user32.AttachThreadInput(our_thread_id, target_thread_id, True)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)
            ctypes.windll.user32.AttachThreadInput(our_thread_id, target_thread_id, False)
        else:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)

        # [แก้ไข] เทคนิค "ปลุก" หน้าต่างโดยการจำลองการกด Alt
        # สิ่งนี้จะทำให้หน้าต่างพร้อมรับ Keyboard Input ทันที
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0) # Press Alt
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0) # Release Alt

    except Exception as e:
        print(f"Force set focus error: {e}")

# Global variables
text_boxes = []
current_hovered_box = None
translation_cache = {} 
last_processed_box = None # [เพิ่มใหม่] เก็บ box ล่าสุดที่ส่งไปแปล
translation_queue = Queue()

class SignalEmitter(QObject):
    show_tooltip = pyqtSignal(str)

emitter = SignalEmitter()

from PyQt5.QtCore import QPropertyAnimation
from PyQt5.QtCore import QTimer # [เพิ่ม] Import QTimer

class CustomScrollArea(QScrollArea):
    """
    [เพิ่มใหม่] QScrollArea ที่ปรับปรุงให้รับ Event ของเมาส์ได้ถูกต้อง
    เมื่อใช้กับหน้าต่างแบบโปร่งใส เพื่อแก้ปัญหา Scroll ทะลุ
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # ทำให้ ScrollArea ไม่รับ Event เมาส์โดยตรง แต่ให้ Widget ลูกรับแทน
        self.setFocusPolicy(Qt.NoFocus)

    def viewportEvent(self, event):
        # ส่งต่อ Event ทั้งหมดให้ viewport จัดการ
        return super().viewportEvent(event)

class PersistentToolTip(QWidget):
    """
    วิดเจ็ตที่ทำหน้าที่เป็น Tooltip แบบถาวร สามารถควบคุมการแสดง/ซ่อนได้เอง
    """
    def __init__(self):
        super().__init__()
        # [แก้ไข] เพิ่ม Qt.Popup เพื่อให้รับ Focus ได้ และเอา Qt.Tool ออก
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # [แก้ไข] ใช้ QScrollArea เพื่อรองรับเนื้อหาที่ยาวเกิน
        self.scroll_area = CustomScrollArea(self) # [แก้ไข] เปลี่ยนมาใช้ CustomScrollArea
        self.scroll_area.setWidgetResizable(True) # สำคัญมาก
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # สไตล์ของ ScrollArea และ Scrollbar
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #333;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                min-height: 20px;
                border-radius: 4px;
            }
        """)

        self.label = QLabel(self)
        self.label.setStyleSheet(
            """
            background-color: transparent;
            color: #f7f7f7;
            padding-right: 4px; /* กันข้อความติด scrollbar */
            """
        )
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.label)

        # [แก้ไข] ปรับโครงสร้าง Layout และ Padding
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12) # [แก้ไข] เพิ่ม Padding รอบๆ
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        # [เพิ่มใหม่] สร้าง Animation สำหรับ Fade-in
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(150) # 150 มิลลิวินาที
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        
        # [เพิ่มใหม่] สร้าง Animation สำหรับ Fade-out
        self.hide_animation = QPropertyAnimation(self, b"windowOpacity")
        self.hide_animation.setDuration(150)
        self.hide_animation.setStartValue(1.0)
        self.hide_animation.setEndValue(0.0)
        self.hide_animation.finished.connect(self.hide) # เมื่อ animation จบ ให้ซ่อน widget จริงๆ
        
        self.previous_focus_hwnd = None # [เพิ่มใหม่] สำหรับเก็บหน้าต่างที่ focus อยู่ก่อนหน้า
        self.hide()

    def keyPressEvent(self, event):
        """
        [เพิ่มใหม่] จัดการการกดปุ่มเมื่อ Widget นี้มี Focus
        """
        if event.key() == Qt.Key_Escape:
            # ถ้ากด Esc ให้เริ่ม animation การซ่อน
            self.hide_animation.start()
            event.accept()

    def paintEvent(self, event):
        """
        [เพิ่มใหม่] วาดพื้นหลังด้วยตัวเองเพื่อแก้ปัญหาความโปร่งใส
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # [แก้ไข] เปลี่ยนเป็นสีทึบ #222222
        painter.setBrush(QColor("#222222"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

    def on_hide_finished(self):
        """
        [เพิ่มใหม่] Slot ที่จะถูกเรียกเมื่อ animation การซ่อนสิ้นสุดลง
        """
        self.hide()
        force_set_focus(self.previous_focus_hwnd)

    def show_at(self, position, text):
        if not text:
            # [แก้ไข] ถ้ามีข้อความว่าง ให้เริ่ม animation การซ่อน
            if self.isVisible():
                self.animation.stop()
                self.hide_animation.start()
            return
        
        # [แก้ไข] ปรับปรุงการคำนวณขนาดทั้งหมด
        # 1. กำหนดขนาดสูงสุดของ Tooltip โดยอิงจากขนาดหน้าจอ
        screen_geo = QApplication.desktop().availableGeometry(position)
        max_width = int(screen_geo.width() * 0.35)  # 35% ของความกว้างหน้าจอ
        max_height = int(screen_geo.height() * 0.5) # 50% ของความสูงหน้าจอ

        # 2. ตั้งค่าข้อความและคำนวณขนาดที่เหมาะสม (ปรับปรุงใหม่)
        self.label.setText(text)
        
        # ปลดการล็อคขนาดของ label ก่อน
        self.label.setMinimumSize(0, 0)
        self.label.setMaximumSize(16777215, 16777215)

        # คำนวณขนาดที่เหมาะสมโดยไม่มีการจำกัดความกว้าง
        unconstrained_size = self.label.sizeHint()

        if unconstrained_size.width() > max_width:
            # ถ้าข้อความยาวกว่า max_width ให้คำนวณความสูงใหม่แบบมีการตัดคำ
            self.label.setFixedWidth(max_width - 24 - 8) # max_width - (padding*2) - scrollbar
            ideal_height = self.label.sizeHint().height()
            final_width = max_width
            final_height = min(ideal_height + 24, max_height) # +24 สำหรับ padding บน-ล่าง
        else:
            # ถ้าข้อความสั้น (เช่น Loading...) ให้ใช้ขนาดที่พอดี
            final_width = unconstrained_size.width() + 24 # +24 สำหรับ padding ซ้าย-ขวา
            final_height = unconstrained_size.height() + 24 # +24 สำหรับ padding บน-ล่าง

        self.setFixedSize(final_width, final_height)

        # 3. จัดตำแหน่ง Tooltip ไม่ให้ตกขอบ (ปรับปรุงใหม่)
        final_pos = QPoint(position.x() + 15, position.y() + 20) # ตำแหน่งเริ่มต้น: ขวาล่างของเคอร์เซอร์

        # เช็คขอบขวา
        if final_pos.x() + final_width > screen_geo.right():
            final_pos.setX(position.x() - final_width - 15) # ย้ายไปด้านซ้ายของเคอร์เซอร์

        # เช็คขอบล่าง
        if final_pos.y() + final_height > screen_geo.bottom():
            final_pos.setY(position.y() - final_height - 15) # ย้ายไปด้านบนของเคอร์เซอร์

        # เช็คขอบซ้าย (หลังจากอาจจะย้ายมาซ้ายแล้ว)
        if final_pos.x() < screen_geo.left():
            final_pos.setX(screen_geo.left())

        # เช็คขอบบน (หลังจากอาจจะย้ายมาบนแล้ว)
        if final_pos.y() < screen_geo.top():
            final_pos.setY(screen_geo.top())

        self.move(final_pos)
        
        # [แก้ไข] เริ่มเล่น Animation แทนการ show() ตรงๆ
        self.animation.stop() # หยุด animation เก่า (ถ้ามี)
        self.show() # [เพิ่ม] ทำให้ Widget แสดงผลก่อนเริ่ม Animation
        self.animation.start()

        # [แก้ไข] ย้ายการเชื่อมต่อสัญญาณมาไว้ที่นี่ และเชื่อมต่อ on_hide_finished
        self.hide_animation.finished.disconnect() # ตัดการเชื่อมต่อเก่าก่อน
        self.hide_animation.finished.connect(self.on_hide_finished)

        # [แก้ไขใหม่] ใช้เทคนิค AttachThreadInput เพื่อขโมย Focus มาที่ Tooltip
        # ซึ่งเป็นวิธีที่น่าเชื่อถือที่สุดในการแก้ปัญหา Focus
        try:
            our_hwnd = int(self.winId())
            # [แก้ไข] เก็บ handle ของหน้าต่างเดิมไว้ใน instance variable
            self.previous_focus_hwnd = ctypes.windll.user32.GetForegroundWindow()
            
            if self.previous_focus_hwnd and our_hwnd != self.previous_focus_hwnd:
                our_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
                foreground_thread_id = ctypes.windll.user32.GetWindowThreadProcessId(self.previous_focus_hwnd, None)
                
                ctypes.windll.user32.AttachThreadInput(foreground_thread_id, our_thread_id, True)
                ctypes.windll.user32.SetForegroundWindow(our_hwnd)
                ctypes.windll.user32.AttachThreadInput(foreground_thread_id, our_thread_id, False)
        except Exception as e:
            print(f"Focus stealing error: {e}")

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, pyautogui.size().width, pyautogui.size().height)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(Qt.red, 2)
        painter.setPen(pen)
        if current_hovered_box:
            rect = QRect(
                current_hovered_box['left'],
                current_hovered_box['top'],
                current_hovered_box['width'],
                current_hovered_box['height']
            )
            painter.drawRect(rect)

def on_exit():
    print("กำลังปิดโปรแกรม...")
    # Worker thread อาจจะยังไม่ได้ถูกสร้างถ้าโปรแกรมปิดเร็ว
    if 'worker_thread' in globals() and worker_thread.is_alive():
        translation_queue.put(None)
        worker_thread.join()
    tray_icon.hide() # ซ่อนไอคอนก่อนปิด
    app.quit() # สั่งให้ QApplication ปิดตัวลง

# --- [แก้ไข] ย้าย app และ overlay มาสร้างก่อน ---
app = QApplication(sys.argv)

# [เพิ่มใหม่] ป้องกันไม่ให้โปรแกรมปิดเมื่อหน้าต่างที่มองไม่เห็นถูกปิด
app.setQuitOnLastWindowClosed(False)

overlay = Overlay()
overlay.show()

# สร้าง Instance ของ Tooltip ที่เราทำขึ้นเอง
persistent_tooltip = PersistentToolTip()

# --- [เพิ่มใหม่] ส่วน System Tray Icon ---
# [แก้ไข] ใช้ไอคอนมาตรฐานของระบบแทนการใช้ไฟล์ icon.png
icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
tray_icon = QSystemTrayIcon(icon, parent=app) # ทำให้ tray_icon เป็น global
tray_icon.setToolTip("TranslateDictionary")

tray_menu = QMenu()
exit_action = QAction("Exit")
exit_action.triggered.connect(on_exit)
tray_menu.addAction(exit_action)

tray_icon.setContextMenu(tray_menu)
tray_icon.show()
# เชื่อมสัญญาณเข้ากับเมธอดของ Tooltip ใหม่
emitter.show_tooltip.connect(lambda text: persistent_tooltip.show_at(QCursor.pos(), text))

def blink_highlight(box_to_blink):
    """
    ฟังก์ชันสำหรับทำให้กรอบไฮไลท์กระพริบ 2 ครั้งแล้วหายไป
    ใช้ threading.Timer เพื่อไม่ให้ block การทำงานหลัก
    """
    global current_hovered_box

    def set_box(box):
        global current_hovered_box
        current_hovered_box = box
        overlay.update()

    # กระพริบครั้งที่ 1
    set_box(box_to_blink)
    threading.Timer(0.15, lambda: set_box(None)).start()
    # กระพริบครั้งที่ 2
    threading.Timer(0.30, lambda: set_box(box_to_blink)).start()
    # ซ่อนถาวร
    threading.Timer(0.45, lambda: set_box(None)).start()

def find_tessdata_path():
    """
    ค้นหา tessdata path ที่ถูกต้อง
    """
    import subprocess
    
    # วิธีที่ 1: ค้นหาจากเส้นทางของโปรแกรม / ตัวแปรสภาพแวดล้อม / ตำแหน่งมาตรฐาน
    local_paths = []
    
    # 1) เส้นทางที่อาจถูกรวมมากับโปรแกรม (PyInstaller)
    local_paths.append(get_executable_path(os.path.join("Tesseract-OCR", "tessdata")))
    
    # 2) ถ้ามีการตั้ง TESSDATA_PREFIX ไว้แล้ว ให้ลองใช้
    tess_env = os.environ.get('TESSDATA_PREFIX')
    if tess_env:
        local_paths.append(tess_env)
        # ถ้า env ชี้ไปที่โฟลเดอร์หลัก ให้ลองต่อ 'tessdata'
        local_paths.append(os.path.join(tess_env, "tessdata"))
    
    # 3) ลองจากตำแหน่งของ tesseract.exe (ถ้ามี)
    try:
        tesseract_exec = get_executable_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
        local_paths.append(os.path.join(os.path.dirname(tesseract_exec), "tessdata"))
    except Exception:
        pass
    
    # 4) ตำแหน่งมาตรฐานบน Windows (ถ้ามี)
    program_files = os.environ.get('ProgramFiles')
    if program_files:
        local_paths.append(os.path.join(program_files, "Tesseract-OCR", "tessdata"))
    
    # ลองทุกเส้นทางที่รวบรวมมา
    for path in local_paths:
        if not path:
            continue
        eng_file = os.path.join(path, "eng.traineddata")
        print(f"DEBUG: ตรวจสอบ {path}")
        if os.path.exists(eng_file):
            print(f"DEBUG: พบ eng.traineddata ที่ {path}")
            return path
    
    # วิธีที่ 2: ค้นหาจาก registry (Windows)
    try:
        import winreg
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        try:
            key = winreg.OpenKey(reg, r"Software\Tesseract-OCR")
            value, _ = winreg.QueryValueEx(key, "InstallPath")
            registry_tessdata = os.path.join(value, "tessdata")
            if os.path.exists(os.path.join(registry_tessdata, "eng.traineddata")):
                print(f"DEBUG: พบ tessdata จาก registry: {registry_tessdata}")
                return registry_tessdata
        except:
            pass
    except:
        pass
    
    print("DEBUG: ไม่พบ tessdata path ที่ถูกต้อง!")
    return None

def capture_and_highlight():
    global text_boxes, current_hovered_box
    
    capture_width = 400
    capture_height = 300
    x, y = pyautogui.position()
    left = max(0, x - capture_width // 2)
    top = max(0, y - capture_height // 2)
    right = min(pyautogui.size().width, left + capture_width)
    bottom = min(pyautogui.size().height, top + capture_height)
    
    screenshot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
    
    # ซ่อน Tooltip เก่า
    persistent_tooltip.hide()
    
    try:
        # TESSDATA_PREFIX ตั้งไว้ที่เริ่มต้นแล้ว ดังนั้นสามารถใช้ได้เลย
        data = pytesseract.image_to_data(screenshot, lang='eng', output_type=pytesseract.Output.DICT)
    except pytesseract.pytesseract.TesseractError as e:
        print(f"Tesseract Error: {e}")
        emitter.show_tooltip.emit("<i>Tesseract Error</i>")
        return

    text_boxes = []
    n_boxes = len(data['text'])
    
    for i in range(n_boxes):
        if data['text'][i].strip() != '':
            text_boxes.append({
                'text': data['text'][i],
                'left': int(data['left'][i]) + left,
                'top': int(data['top'][i]) + top,
                'width': int(data['width'][i]),
                'height': int(data['height'][i])
            })
    
    found_box = None
    cursor_x, cursor_y = x, y
    for box in text_boxes:
        if (box['left'] <= cursor_x <= box['left'] + box['width'] and
            box['top'] <= cursor_y <= box['top'] + box['height']):
            found_box = box
            break
    
    if found_box:
        emitter.show_tooltip.emit("<i>Loading...</i>")
        blink_highlight(found_box)
        translation_queue.put(found_box)
    else:
        cancel_highlight()

def translation_worker():
    """
    เธรดที่ทำงานตลอดเวลาเพื่อรอรับงานแปลจาก Queue
    """
    while True:
        box_to_translate = translation_queue.get() # รอจนกว่าจะมีงานเข้ามา
        if box_to_translate is None: # ถ้าได้รับ None คือสัญญาณให้ออกจาก loop
            break
        
        translate_and_show(box_to_translate)

def translate_and_show(box):
    global last_processed_box
    last_processed_box = box # อัปเดตว่ากำลังประมวลผล box นี้

    search_word = box['text'].strip(".,;:?!'\"-").lower()
    
    if not search_word:
        return

    if search_word not in translation_cache:
        print(f"กำลังค้นหา (Longdo & Google): {search_word}")
        
        # --- 3. Get Longdo Data ---
        soup = fetch_word(search_word)
        longdo_data = None
        if soup:
            longdo_data = parse_data(soup)
        
        # --- 4. Get Google Translate Data ---
        google_translation = get_translation_sync(search_word)
        
        # --- 5. Format Combined Data ---
        formatted_translation = format_combined_data(longdo_data, google_translation, search_word)
        
        translation_cache[search_word] = formatted_translation
    else:
        print(f"ดึงจาก Cache: {search_word}")
        formatted_translation = translation_cache[search_word]
    
    # ตรวจสอบว่า box ที่แปลเสร็จแล้ว ยังเป็น box ล่าสุดที่ผู้ใช้ต้องการหรือไม่
    # เพื่อป้องกันกรณีผู้ใช้กด Ctrl+D รัวๆ แล้วผลแปลของคำเก่ามาแสดงทับคำใหม่
    if last_processed_box == box:
        print(f"กำลังแสดง Tooltip สำหรับ: {search_word}")
        emitter.show_tooltip.emit(formatted_translation)

def cancel_highlight():
    global current_hovered_box
    current_hovered_box = None
    overlay.update()
    emitter.show_tooltip.emit("") # ส่งสัญญาณให้ซ่อน Tooltip ที่แสดงอยู่

print("โปรแกรมแปลภาษา (Longdo + Google) พร้อมทำงาน!")
print(" - กด [Ctrl + D] เพื่อจับภาพและแปลคำใต้เมาส์")
print(" - กด [Esc] เพื่อซ่อนกรอบและคำแปล")
print(" - กด [Ctrl + Q] เพื่อปิดโปรแกรม (หรือปิดหน้าต่าง Terminal)")

# สร้างและเริ่ม Worker Thread เพียงครั้งเดียว
worker_thread = threading.Thread(target=translation_worker, daemon=True)
worker_thread.start()

# -------------------------------------------------------------------
# 6. ส่วน Hotkeys และการรัน (แก้ไขมาใช้ pynput)
# -------------------------------------------------------------------

# [แก้ไขใหม่] กลับมาใช้ Listener แบบ on_press/on_release เพื่อความเสถียร
current_keys = set()

def on_press(key):
    """ฟังก์ชันที่จะถูกเรียกเมื่อมีการกดปุ่ม"""
    try:
        # เก็บ Ctrl ลงใน set
        if key == pynput_keyboard.Key.ctrl_l or key == pynput_keyboard.Key.ctrl_r:
            current_keys.add('ctrl')
        
        # ตรวจสอบ Ctrl+D (char code '\x04' = Ctrl+D)
        if hasattr(key, 'char') and key.char == '\x04':
            if 'ctrl' in current_keys:
                print("Hotkey 'Ctrl+D' pressed.")
                capture_and_highlight()
                return
        
        # ตรวจสอบ Ctrl+Q (char code '\x11' = Ctrl+Q)
        if hasattr(key, 'char') and key.char == '\x11':
            if 'ctrl' in current_keys:
                print("Hotkey 'Ctrl+Q' pressed. Exiting...")
                on_exit()
                return
            
    except AttributeError:
        pass

def on_release(key):
    """ฟังก์ชันที่จะถูกเรียกเมื่อมีการปล่อยปุ่ม"""
    try:
        if key == pynput_keyboard.Key.ctrl_l or key == pynput_keyboard.Key.ctrl_r:
            current_keys.discard('ctrl')
            
    except (AttributeError, KeyError):
        pass

def start_hotkey_listener():
    with pynput_keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

# เริ่ม Listener ใน Thread แยก
hotkey_thread = threading.Thread(target=start_hotkey_listener, daemon=True)
hotkey_thread.start()

try:
    sys.exit(app.exec_())
except KeyboardInterrupt:
    on_exit()