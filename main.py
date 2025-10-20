import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QStyle, QWidget
from PyQt5.QtCore import pyqtSignal, QObject, QPoint, QRect
from PyQt5.QtGui import QCursor

from services.tesseract_setup import initialize_tesseract
from ui.overlay import Overlay
from ui.tooltip import PersistentToolTip
from core.worker import TranslationWorker
from core.hotkey_manager import HotkeyManager

class SignalEmitter(QObject):
    """Emits signals to communicate between threads and components."""
    show_tooltip = pyqtSignal(str, 'PyQt_PyObject')
    pre_ocr_ready = pyqtSignal(list, 'PyQt_PyObject')
    blink_box = pyqtSignal(dict)
    enter_sentence_mode_signal = pyqtSignal()
    
class MainApplication:
    """The main application class that orchestrates all components."""
    def __init__(self, app):
        self.app = app
        self.emitter = SignalEmitter()
        
        # A dummy widget is used as a stable parent for the QMenu.
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
        """Initializes the system tray icon and its context menu."""
        icon = self.app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(icon, parent=self.app)
        self.tray_icon.setToolTip("FloatingDictionary")
        
        self.tray_menu = QMenu(self.dummy_parent_widget)
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
        self.exit_action = QAction("Exit", triggered=self.on_exit)
        self.tray_menu.addAction(self.exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

    def connect_signals(self):
        """Connects signals from various components to the appropriate slots."""
        self.emitter.show_tooltip.connect(self.on_show_tooltip)
        self.emitter.pre_ocr_ready.connect(self.on_pre_ocr_ready)
        self.emitter.blink_box.connect(self.blink_highlight)
        self.emitter.enter_sentence_mode_signal.connect(self.enter_sentence_mode)
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.translate_all_requested.connect(self.on_translate_all_requested)
        self.overlay.words_selected.connect(self.on_words_selected)
        self.overlay.dismiss_requested.connect(self.cancel_highlight)

    def run(self):
        """Starts the application components and shows the initial notification."""
        self.worker.start()
        self.hotkey_manager.start()
        self.tray_icon.show()
        self.tray_icon.showMessage(
            "Floating Dictionary",
            "Ready to work!\n- Press Ctrl+Alt+D to translate a word\n- Press Ctrl+Alt+S to translate a sentence",
            QSystemTrayIcon.Information,
            2000
        )
        print("Floating Dictionary (Longdo + Google) is ready!")
        print(" - Press [Ctrl + Alt + D] to translate the word under the cursor")
        print(" - Press [Ctrl + Alt + S] to enter sentence selection mode (drag to select)")
        print(" - Press [Esc] to cancel or hide the window")
        print(" - Press [Ctrl + Alt + Q] to exit the program")

    def blink_highlight(self, box_to_blink):
        """Enters the overlay's dismiss mode, highlighting the target box."""
        self.overlay.enter_dismiss_mode(box_to_blink)

    def on_show_tooltip(self, text, position_hint):
        """Calculates the best position and shows the tooltip."""
        pos = QCursor.pos() # Default to cursor position
        if isinstance(position_hint, dict):
            # Position hint for a single word is a dictionary
            rect = QRect(position_hint['left'], position_hint['top'], position_hint['width'], position_hint['height'])
            pos = rect.topRight()
        elif isinstance(position_hint, QRect):
            # Position hint for a sentence region is a QRect
            pos = position_hint.center()
        
        self.tooltip.show_at(pos, text)

        # If this is the final translation result, highlight the area and bring the tooltip to the front.
        is_final_result = "<i>" not in text and text
        if is_final_result and position_hint:
            self.overlay.enter_dismiss_mode(position_hint)
            self.tooltip.raise_()

    def cancel_highlight(self):
        """Hides the overlay and the tooltip, canceling any selection mode."""
        self.overlay.exit_selection_mode()
        self.tooltip.start_hide_animation()

    def enter_sentence_mode(self):
        """Enters the region selection mode on the.overlay."""
        self.overlay.enter_region_selection_mode()

    def on_pre_ocr_ready(self, boxes, region):
        """Once the worker has identified all words in a region, show them in the overlay."""
        self.overlay.enter_word_selection_mode(boxes, region)

    def on_region_selected(self, region):
        """When the user selects a region, send it to the worker for pre-OCR."""
        self.worker.add_pre_ocr_job(region)

    def on_translate_all_requested(self, region):
        """When the user wants to translate the whole region, send it to the worker."""
        self.worker.add_ocr_and_translate_job(region, region)

    def on_words_selected(self, words):
        """When the user finishes selecting words, join them and send to the worker."""
        if not words:
            return
        
        # Calculate the bounding box that contains all selected words.
        min_x = min(w['left'] for w in words)
        min_y = min(w['top'] for w in words)
        max_x = max(w['left'] + w['width'] for w in words)
        max_y = max(w['top'] + w['height'] for w in words)
        bounding_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

        sentence = ' '.join([word['text'] for word in words])
        if sentence:
            self.worker.add_sentence_job(sentence, bounding_rect)

    def on_exit(self):
        """Cleans up resources and exits the application."""
        print("Exiting program...")
        self.worker.stop()
        self.worker.join()
        self.tray_icon.hide()
        self.app.quit()

def main():
    # Ensure Tesseract is available before starting the application.
    if not initialize_tesseract():
        sys.exit(1)

    app = QApplication(sys.argv)
    # Don't quit the app when the last window is closed, only when explicitly told to.
    app.setQuitOnLastWindowClosed(False)

    main_app = MainApplication(app)
    main_app.run()

    try:
        sys.exit(app.exec_())
    except (KeyboardInterrupt, SystemExit):
        main_app.on_exit()

if __name__ == "__main__":
    main()
