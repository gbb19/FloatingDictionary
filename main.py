import sys
from functools import partial
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QActionGroup, QStyle, QWidget
from PyQt5.QtCore import pyqtSignal, QObject, QPoint, QRect
from PyQt5.QtGui import QCursor

from services.tesseract_setup import initialize_tesseract
from ui.overlay import Overlay
from ui.tooltip import PersistentToolTip
from core.worker import TranslationWorker
from core.hotkey_manager import HotkeyManager
from config import SOURCE_LANG, TARGET_LANG, LANG_CODE_MAP

class SignalEmitter(QObject):
    show_tooltip = pyqtSignal(str, 'PyQt_PyObject')
    pre_ocr_ready = pyqtSignal(list, 'PyQt_PyObject')
    blink_box = pyqtSignal(dict)
    enter_sentence_mode_signal = pyqtSignal()
    
class MainApplication:
    def __init__(self, app):
        self.app = app
        self.emitter = SignalEmitter()
        self.dummy_parent_widget = QWidget()

        # --- Language State ---
        self.source_lang = SOURCE_LANG
        self.target_lang = TARGET_LANG
        
        self.overlay = Overlay()
        self.tooltip = PersistentToolTip()
        self.worker = TranslationWorker(self.emitter)
        self.hotkey_manager = HotkeyManager(
            capture_callback=self.on_capture_hotkey,
            sentence_callback=self.on_sentence_hotkey,
            exit_callback=self.on_exit,
            hide_callback=self.cancel_highlight
        )
        self.setup_tray_icon()
        self.connect_signals()

    def setup_tray_icon(self):
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

        # --- Source Language Menu ---
        self.source_menu = QMenu("Source Language", self.tray_menu)
        self.source_action_group = QActionGroup(self.source_menu)
        self.source_action_group.setExclusive(True)

        auto_action = self.source_menu.addAction("Auto")
        auto_action.setCheckable(True)
        auto_action.triggered.connect(partial(self.set_source_lang, 'auto'))
        self.source_action_group.addAction(auto_action)
        if self.source_lang == 'auto':
            auto_action.setChecked(True)

        for code, tesseract_code in LANG_CODE_MAP.items():
            action = self.source_menu.addAction(f"{code} ({tesseract_code})")
            action.setCheckable(True)
            action.triggered.connect(partial(self.set_source_lang, code))
            self.source_action_group.addAction(action)
            if self.source_lang == code:
                action.setChecked(True)
        
        self.tray_menu.addMenu(self.source_menu)

        # --- Target Language Menu ---
        self.target_menu = QMenu("Target Language", self.tray_menu)
        self.target_action_group = QActionGroup(self.target_menu)
        self.target_action_group.setExclusive(True)

        for code, tesseract_code in LANG_CODE_MAP.items():
            action = self.target_menu.addAction(f"{code} ({tesseract_code})")
            action.setCheckable(True)
            action.triggered.connect(partial(self.set_target_lang, code))
            self.target_action_group.addAction(action)
            if self.target_lang == code:
                action.setChecked(True)

        self.tray_menu.addMenu(self.target_menu)
        self.tray_menu.addSeparator()

        self.exit_action = QAction("Exit", triggered=self.on_exit)
        self.tray_menu.addAction(self.exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

    def set_source_lang(self, lang_code):
        self.source_lang = lang_code
        print(f"Source language set to: {lang_code}")

    def set_target_lang(self, lang_code):
        self.target_lang = lang_code
        print(f"Target language set to: {lang_code}")

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
            "Ready to work!\n- Press Ctrl+Alt+D to translate a word\n- Press Ctrl+Alt+S to translate a sentence",
            QSystemTrayIcon.Information,
            2000
        )
        print("Floating Dictionary (Longdo + Google) is ready!")
        print(" - Press [Ctrl + Alt + D] to translate the word under the cursor")
        print(" - Press [Ctrl + Alt + S] to enter sentence selection mode (drag to select)")
        print(" - Press [Esc] to cancel or hide the window")
        print(" - Press [Ctrl + Alt + Q] to exit the program")

    def on_capture_hotkey(self):
        self.worker.add_job(self.source_lang, self.target_lang)

    def on_sentence_hotkey(self):
        self.emitter.enter_sentence_mode_signal.emit()

    def blink_highlight(self, box_to_blink):
        self.overlay.enter_dismiss_mode(box_to_blink)

    def on_show_tooltip(self, text, position_hint):
        pos = QCursor.pos()
        if isinstance(position_hint, dict):
            rect = QRect(position_hint['left'], position_hint['top'], position_hint['width'], position_hint['height'])
            pos = rect.topRight()
        elif isinstance(position_hint, QRect):
            pos = position_hint.center()
        
        self.tooltip.show_at(pos, text)

        is_final_result = "<i>" not in text and text
        if is_final_result and position_hint:
            self.overlay.enter_dismiss_mode(position_hint)
            self.tooltip.raise_()

    def cancel_highlight(self):
        self.overlay.exit_selection_mode()
        self.tooltip.start_hide_animation()

    def enter_sentence_mode(self):
        self.overlay.enter_region_selection_mode()

    def on_pre_ocr_ready(self, boxes, region):
        self.overlay.enter_word_selection_mode(boxes, region)

    def on_region_selected(self, region):
        self.worker.add_pre_ocr_job(region, self.source_lang, self.target_lang)

    def on_translate_all_requested(self, region):
        self.worker.add_ocr_and_translate_job(region, region, self.source_lang, self.target_lang)

    def on_words_selected(self, words):
        if not words:
            return
        
        min_x = min(w['left'] for w in words)
        min_y = min(w['top'] for w in words)
        max_x = max(w['left'] + w['width'] for w in words)
        max_y = max(w['top'] + w['height'] for w in words)
        bounding_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

        sentence = ' '.join([word['text'] for word in words])
        if sentence:
            self.worker.add_sentence_job(sentence, bounding_rect, self.source_lang, self.target_lang)

    def on_exit(self):
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
