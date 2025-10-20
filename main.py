import sys
import threading
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QStyle, QWidget
from PyQt5.QtCore import pyqtSignal, QObject, QPoint, QRect
from PyQt5.QtGui import QCursor

from services.tesseract_setup import initialize_tesseract
from ui.overlay import Overlay
from ui.tooltip import PersistentToolTip
from core.worker import TranslationWorker
from core.hotkey_manager import HotkeyManager

# -------------------------------------------------------------------
# 1. Application Setup
# -------------------------------------------------------------------
class SignalEmitter(QObject):
    show_tooltip = pyqtSignal(str, 'PyQt_PyObject')
    pre_ocr_ready = pyqtSignal(list, 'PyQt_PyObject') # --- [แก้ไข] เพิ่ม Argument สำหรับ region ---
    blink_box = pyqtSignal(dict)
    enter_sentence_mode_signal = pyqtSignal()
    
class MainApplication:
    def __init__(self, app):
        self.app = app
        self.emitter = SignalEmitter()
        # --- [เพิ่ม] สร้าง Widget ที่มองไม่เห็นเพื่อเป็น Parent ที่ถูกต้องสำหรับ QMenu ---
        self.dummy_parent_widget = QWidget()
        self.overlay = Overlay()
        self.tooltip = PersistentToolTip()
        self.worker = TranslationWorker(self.emitter)        
        self.hotkey_manager = HotkeyManager(
            capture_callback=self.worker.add_job,
            sentence_callback=self.emitter.enter_sentence_mode_signal.emit,
            exit_callback=self.on_exit,
            hide_callback=self.cancel_highlight
        )
        self.setup_tray_icon()
        self.connect_signals()

    def setup_tray_icon(self):
        icon = self.app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(icon, parent=self.app)
        self.tray_icon.setToolTip("FloatingDictionary")
        
        # --- [แก้ไข] สร้าง QMenu โดยมี Parent ที่เป็น QWidget เพื่อความเสถียร ---
        self.tray_menu = QMenu(self.dummy_parent_widget)
        # --- [เพิ่ม] กำหนดสไตล์ให้เมนูดูสวยงามและทันสมัยขึ้น ---
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #333;
                color: #f0f0f0;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 25px 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #555;
            }
        """)
        self.exit_action = QAction("Exit", triggered=self.on_exit) # --- [แก้ไข] ทำให้เป็น instance variable ---
        self.tray_menu.addAction(self.exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

    def connect_signals(self):
        self.emitter.show_tooltip.connect(self.on_show_tooltip)
        self.emitter.pre_ocr_ready.connect(self.on_pre_ocr_ready)
        self.emitter.blink_box.connect(self.blink_highlight)
        self.emitter.enter_sentence_mode_signal.connect(self.enter_sentence_mode)
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.translate_all_requested.connect(self.on_translate_all_requested)
        self.overlay.words_selected.connect(self.on_words_selected)
        self.overlay.dismiss_requested.connect(self.cancel_highlight)

    def run(self):
        self.worker.start()
        self.hotkey_manager.start()
        self.tray_icon.show()
        self.tray_icon.showMessage(
            "Floating Dictionary",
            "โปรแกรมพร้อมทำงานแล้ว!\n- กด Ctrl+Alt+D เพื่อแปลคำ\n- กด Ctrl+Alt+S เพื่อแปลประโยค",
            QSystemTrayIcon.Information,
            2000
        )
        print("โปรแกรมแปลภาษา (Longdo + Google) พร้อมทำงาน!")
        print(" - กด [Ctrl + Alt + D] เพื่อแปลคำศัพท์ใต้เมาส์")
        print(" - กด [Ctrl + Alt + S] เพื่อเข้าโหมดเลือกประโยค (ลากเมาส์เพื่อเลือก)")
        print(" - กด [Esc] เพื่อยกเลิก/ซ่อนหน้าต่าง")
        print(" - กด [Ctrl + Alt + Q] เพื่อปิดโปรแกรม")

    def blink_highlight(self, box_to_blink):
        # --- [แก้ไข] เปลี่ยนมาใช้ dismiss_mode ของ Overlay ---
        self.overlay.enter_dismiss_mode(box_to_blink)

    def on_show_tooltip(self, text, position_hint):
        """Calculates the best position and shows the tooltip."""
        pos = QCursor.pos() # Default to cursor position
        if isinstance(position_hint, dict):
            # For single word from Ctrl+Alt+D
            rect = QRect(position_hint['left'], position_hint['top'], position_hint['width'], position_hint['height'])
            pos = rect.topRight()
        elif isinstance(position_hint, QRect):
            # For sentence region from Ctrl+Alt+S
            pos = position_hint.center()
        
        self.tooltip.show_at(pos, text)

        # --- [เพิ่ม] เมื่อแสดงผลลัพธ์สุดท้าย ให้ทำการไฮไลท์พื้นที่นั้นๆ ด้วย ---
        is_final_result = "<i>" not in text and text
        if is_final_result and position_hint:
            self.overlay.enter_dismiss_mode(position_hint)
            # --- [แก้ไข] ดึง Tooltip กลับขึ้นมาอยู่บนสุดเสมอ ---
            self.tooltip.raise_()

    def cancel_highlight(self):
        # --- [แก้ไข] รวมการยกเลิกทั้งหมดไว้ในที่เดียว ---
        self.overlay.exit_selection_mode()
        self.tooltip.start_hide_animation()

    def enter_sentence_mode(self):
        self.overlay.enter_region_selection_mode()

    def on_pre_ocr_ready(self, boxes, region):
        # --- [แก้ไข] รับ region และส่งต่อไปยัง Overlay ---
        self.overlay.enter_word_selection_mode(boxes, region)

    def on_region_selected(self, region):
        self.worker.add_pre_ocr_job(region)

    def on_translate_all_requested(self, region):
        self.worker.add_ocr_and_translate_job(region, region)

    def on_words_selected(self, words):
        if not words:
            return
        
        # Calculate the bounding box of all selected words
        min_x = min(w['left'] for w in words)
        min_y = min(w['top'] for w in words)
        max_x = max(w['left'] + w['width'] for w in words)
        max_y = max(w['top'] + w['height'] for w in words)
        bounding_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

        sentence = ' '.join([word['text'] for word in words])
        if sentence:
            self.worker.add_sentence_job(sentence, bounding_rect)

    def on_exit(self):
        print("กำลังปิดโปรแกรม...")
        self.worker.stop()
        self.worker.join()
        self.tray_icon.hide()
        self.app.quit()

def main():
    if not initialize_tesseract():
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    main_app = MainApplication(app)
    main_app.run()

    try:
        sys.exit(app.exec_())
    except (KeyboardInterrupt, SystemExit):
        main_app.on_exit()

if __name__ == "__main__":
    main()