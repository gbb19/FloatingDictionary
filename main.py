import sys
import threading

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QStyle
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

def blink_highlight(box_to_blink):
    """
    ฟังก์ชันสำหรับทำให้กรอบไฮไลท์กระพริบ 2 ครั้งแล้วหายไป
    ใช้ threading.Timer เพื่อไม่ให้ block การทำงานหลัก
    """
    # กระพริบครั้งที่ 1
    overlay.set_box(box_to_blink)
    threading.Timer(0.15, lambda: overlay.set_box(None)).start()
    # กระพริบครั้งที่ 2
    threading.Timer(0.30, lambda: overlay.set_box(box_to_blink)).start()
    # ซ่อนถาวร
    threading.Timer(0.45, lambda: overlay.set_box(None)).start()

def cancel_highlight():
    """Hides the highlight overlay and the tooltip."""
    overlay.set_box(None)
    emitter.show_tooltip.emit("") # ส่งสัญญาณให้ซ่อน Tooltip ที่แสดงอยู่

def on_exit():
    """Gracefully shuts down the application."""
    print("กำลังปิดโปรแกรม...")
    worker.stop()
    worker.join()
    tray_icon.hide()
    app.quit()

if __name__ == "__main__":
    # 1. Initialize Tesseract
    if not initialize_tesseract():
        sys.exit(1)

    # 2. Create the PyQt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 3. Create UI Components
    emitter = SignalEmitter()
    overlay = Overlay()
    tooltip = PersistentToolTip()
    
    overlay.show()
    
    # 4. Setup System Tray Icon
    icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
    tray_icon = QSystemTrayIcon(icon, parent=app)
    tray_icon.setToolTip("FloatingDictionary")
    tray_menu = QMenu()
    exit_action = QAction("Exit", triggered=on_exit)
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # 5. Connect signals and slots
    emitter.show_tooltip.connect(lambda text: tooltip.show_at(QCursor.pos(), text))

    # 6. Initialize and start worker and hotkey manager
    worker = TranslationWorker(emitter, blink_highlight, cancel_highlight)
    worker.start()

    hotkey_manager = HotkeyManager(capture_callback=worker.add_job, exit_callback=on_exit)
    hotkey_manager.start()

    # 7. Start the application
    print("โปรแกรมแปลภาษา (Longdo + Google) พร้อมทำงาน!")
    print(" - กด [Ctrl + D] เพื่อจับภาพและแปลคำใต้เมาส์")
    print(" - กด [Esc] เพื่อซ่อนกรอบและคำแปล")
    print(" - กด [Ctrl + Q] เพื่อปิดโปรแกรม (หรือปิดหน้าต่าง Terminal)")

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        on_exit()