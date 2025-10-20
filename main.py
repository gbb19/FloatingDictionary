import sys
import threading
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QStyle
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QStyle, QDesktopWidget
from PyQt5.QtCore import pyqtSignal, QObject
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
    show_tooltip = pyqtSignal(str)
    pre_ocr_ready = pyqtSignal(list)
    blink_box = pyqtSignal(dict)
    
class MainApplication:
    def __init__(self, app):
        self.app = app
        self.emitter = SignalEmitter()
        self.overlay = Overlay()
        self.tooltip = PersistentToolTip()
        self.worker = TranslationWorker(self.emitter)
        self.hotkey_manager = HotkeyManager(
            capture_callback=self.worker.add_job,
            sentence_callback=self.enter_sentence_mode,
            exit_callback=self.on_exit,
            hide_callback=self.cancel_highlight
        )
        self.setup_tray_icon()
        self.connect_signals()

    def setup_tray_icon(self):
        icon = self.app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(icon, parent=self.app)
        self.tray_icon.setToolTip("FloatingDictionary")
        tray_menu = QMenu()
        exit_action = QAction("Exit", triggered=self.on_exit)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)

    def connect_signals(self):
        self.emitter.show_tooltip.connect(lambda text: self.tooltip.show_at(QCursor.pos(), text))
        self.emitter.pre_ocr_ready.connect(self.on_pre_ocr_ready)
        self.emitter.blink_box.connect(self.blink_highlight)
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.words_selected.connect(self.on_words_selected)

    def run(self):
        self.worker.start()
        self.hotkey_manager.start()
        self.tray_icon.show()
        self.tray_icon.showMessage(
            "Floating Dictionary",
            "โปรแกรมพร้อมทำงานแล้ว!\n- กด Ctrl+D เพื่อแปลคำ\n- กด Ctrl+S เพื่อแปลประโยค",
            QSystemTrayIcon.Information,
            2000
        )
        print("โปรแกรมแปลภาษา (Longdo + Google) พร้อมทำงาน!")
        print(" - กด [Ctrl + D] เพื่อแปลคำศัพท์ใต้เมาส์")
        print(" - กด [Ctrl + S] เพื่อเข้าโหมดเลือกประโยค (ลากเมาส์เพื่อเลือก)")
        print(" - กด [Esc] เพื่อยกเลิก/ซ่อนหน้าต่าง")
        print(" - กด [Ctrl + Q] เพื่อปิดโปรแกรม")

    def blink_highlight(self, box_to_blink):
        self.overlay.show()
        self.overlay.set_box(box_to_blink)
        threading.Timer(0.15, lambda: self.overlay.set_box(None)).start()
        threading.Timer(0.30, lambda: self.overlay.set_box(box_to_blink)).start()
        threading.Timer(0.45, lambda: self.overlay.hide()).start()

    def cancel_highlight(self):
        if self.overlay.is_selection_mode or self.overlay.is_region_selection_mode:
            self.overlay.exit_selection_mode()
        else:
            self.overlay.hide()
        self.emitter.show_tooltip.emit("")

    def enter_sentence_mode(self):
        self.overlay.enter_region_selection_mode()

    def on_pre_ocr_ready(self, boxes):
        self.overlay.enter_word_selection_mode(boxes)

    def on_region_selected(self, region):
        self.worker.add_pre_ocr_job(region)

    def on_words_selected(self, words):
        sentence = ' '.join([word['text'] for word in words])
        if sentence:
            self.worker.add_sentence_job(sentence)

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