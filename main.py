import sys
from functools import partial
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QStyle,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, QObject, QPoint, QRect
from PyQt6.QtGui import QCursor, QGuiApplication, QAction, QActionGroup

from services.tesseract_setup import initialize_tesseract
from ui.overlay import Overlay
from ui.tooltip import PersistentToolTip
from ui.settings_window import SettingsWindow
from core.worker import TranslationWorker
from core.hotkey_manager import HotkeyManager
from config import SOURCE_LANG, TARGET_LANG, LANG_CODE_MAP
from utils.app_logger import debug_print


class SignalEmitter(QObject):
    show_tooltip = pyqtSignal(str, "PyQt_PyObject")
    pre_ocr_ready = pyqtSignal(list, "PyQt_PyObject")
    blink_box = pyqtSignal(dict)
    enter_sentence_mode_signal = pyqtSignal()
    history_updated = pyqtSignal(dict)


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
        self.history_menu = None # Will be initialized in setup_tray_icon
        self.worker = TranslationWorker(self.emitter)
        self.settings_window = SettingsWindow(self.worker, self.dummy_parent_widget)
        self.hotkey_manager = HotkeyManager(
            capture_callback=self.on_capture_hotkey,
            sentence_callback=self.on_sentence_hotkey,
            exit_callback=self.on_exit,
            hide_callback=self.cancel_highlight,
        )
        self.setup_tray_icon()
        self.connect_signals()

    def setup_tray_icon(self):
        icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
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

        auto_action = QAction("Auto", self.source_menu)
        self.source_menu.addAction(auto_action)
        auto_action.setCheckable(True)
        auto_action.triggered.connect(partial(self.set_source_lang, "auto"))
        self.source_action_group.addAction(auto_action)
        if self.source_lang == "auto":
            auto_action.setChecked(True)

        for code, tesseract_code in LANG_CODE_MAP.items():
            action = QAction(f"{code} ({tesseract_code})", self.source_menu)
            self.source_menu.addAction(action)
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
            action = QAction(f"{code} ({tesseract_code})", self.target_menu)
            self.target_menu.addAction(action)
            action.setCheckable(True)
            action.triggered.connect(partial(self.set_target_lang, code))
            self.target_action_group.addAction(action)
            if self.target_lang == code:
                action.setChecked(True)

        self.tray_menu.addMenu(self.target_menu)
        self.tray_menu.addSeparator()

        self.history_menu = QMenu("Translation History", self.tray_menu)
        self.tray_menu.addMenu(self.history_menu)
        self.tray_menu.addSeparator()

        self.settings_action = QAction("Settings...", self.tray_menu)
        self.settings_action.triggered.connect(self.show_settings_window)
        self.tray_menu.addAction(self.settings_action)
        self.tray_menu.addSeparator()

        self.exit_action = QAction("Exit", self.tray_menu)
        self.exit_action.triggered.connect(self.on_exit)
        self.tray_menu.addAction(self.exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

    def set_source_lang(self, lang_code):
        self.source_lang = lang_code
        debug_print(f"Source language set to: {lang_code}")

    def set_target_lang(self, lang_code):
        self.target_lang = lang_code
        debug_print(f"Target language set to: {lang_code}")

    def connect_signals(self):
        self.emitter.show_tooltip.connect(self.on_show_tooltip)
        self.emitter.pre_ocr_ready.connect(self.on_pre_ocr_ready)
        self.emitter.blink_box.connect(self.blink_highlight)
        self.emitter.enter_sentence_mode_signal.connect(self.enter_sentence_mode)
        self.emitter.history_updated.connect(self.update_history_menu)
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.translate_all_requested.connect(self.on_translate_all_requested)
        self.overlay.words_selected.connect(self.on_words_selected)
        self.overlay.dismiss_requested.connect(self.cancel_highlight)
        self.tooltip.dismiss_requested.connect(self.cancel_highlight)
        self.settings_window.clear_history_requested.connect(self.on_clear_history_requested)
        self.settings_window.display_translation_requested.connect(self.display_cached_translation)

    def run(self):
        self.update_history_menu(self.worker.dictionary_data) # Populate history menu on startup
        self.worker.start()
        self.hotkey_manager.start()
        self.tray_icon.show()
        self.tray_icon.showMessage(
            "Floating Dictionary",
            "Ready to work!\n- Press Ctrl+Alt+D to translate a word\n- Press Ctrl+Alt+S to translate a sentence",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
        debug_print("Floating Dictionary (Longdo + Google) is ready!")
        debug_print(" - Press [Ctrl + Alt + D] to translate the word under the cursor")
        debug_print(
            " - Press [Ctrl + Alt + S] to enter sentence selection mode (drag to select)"
        )
        debug_print(" - Press [Esc] to cancel or hide the window")
        debug_print(" - Press [Ctrl + Alt + Q] to exit the program")

    def on_capture_hotkey(self):
        self.worker.add_job(self.source_lang, self.target_lang)

    def on_sentence_hotkey(self):
        self.emitter.enter_sentence_mode_signal.emit()

    def show_settings_window(self):
        self.settings_window.show()
        self.settings_window.activateWindow()

    def blink_highlight(self, box_to_blink):
        self.overlay.enter_dismiss_mode(box_to_blink)

    def on_show_tooltip(self, text, position_hint):
        pos = QCursor.pos()
        if isinstance(position_hint, dict):
            rect = QRect(
                position_hint["left"],
                position_hint["top"],
                position_hint["width"],
                position_hint["height"],
            )
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

    def update_history_menu(self, dictionary_data: dict):
        """
        Updates the 'Translation History' menu with recent translations.
        """
        if not self.history_menu:
            return

        self.history_menu.clear()

        if not dictionary_data:
            self.history_menu.addAction("No history yet").setEnabled(False)
            return

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        today_menu = QMenu("Today", self.history_menu)
        yesterday_menu = QMenu("Yesterday", self.history_menu)
        older_menu = QMenu("Older", self.history_menu)

        # Sort history by timestamp in descending order (most recent first)
        # Convert dict to list of tuples (cache_key, data) for sorting
        sorted_history = sorted(dictionary_data.items(), key=lambda item: item[1]['timestamp'], reverse=True)

        for entry in sorted_history:
            cache_key = entry[0]
            timestamp_str = entry[1]['timestamp']
            translated_word = cache_key[0] # The search_word
            
            try:
                entry_date = datetime.fromisoformat(timestamp_str).date()
            except ValueError:
                entry_date = today # Fallback for malformed timestamp

            action = QAction(translated_word.capitalize(), self.history_menu)
            action.triggered.connect(partial(self.display_cached_translation, cache_key))

            if entry_date == today:
                today_menu.addAction(action)
            elif entry_date == yesterday:
                yesterday_menu.addAction(action)
            else:
                older_menu.addAction(action)
        
        if today_menu.actions(): self.history_menu.addMenu(today_menu)
        if yesterday_menu.actions(): self.history_menu.addMenu(yesterday_menu)
        if older_menu.actions(): self.history_menu.addMenu(older_menu)
        if not (today_menu.actions() or yesterday_menu.actions() or older_menu.actions()):
            self.history_menu.addAction("No history yet").setEnabled(False)

    def on_pre_ocr_ready(self, boxes, region):
        self.overlay.enter_word_selection_mode(boxes, region)

    def on_region_selected(self, region):
        self.worker.add_pre_ocr_job(region, self.source_lang, self.target_lang)

    def on_translate_all_requested(self, region):
        self.worker.add_ocr_and_translate_job(
            region, region, self.source_lang, self.target_lang
        )

    def on_words_selected(self, words):
        if not words:
            return

        min_x = min(w["left"] for w in words)
        min_y = min(w["top"] for w in words)
        max_x = max(w["left"] + w["width"] for w in words)
        max_y = max(w["top"] + w["height"] for w in words)
        bounding_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

        sentence = " ".join([word["text"] for word in words])
        if sentence:
            self.worker.add_sentence_job(
                sentence, bounding_rect, self.source_lang, self.target_lang
            )

    def on_clear_history_requested(self):
        """Clears history and cache when requested from the settings window."""
        self.worker.clear_history_and_cache()
    
    def display_cached_translation(self, cache_key: tuple):
        """Retrieves and displays a cached translation."""
        formatted_translation = self.worker.dictionary_data.get(cache_key, {}).get('html')
        if formatted_translation:
            # Display at current cursor position, as there's no specific box for history recall
            current_pos = QCursor.pos()
            self.tooltip.show_at(current_pos, formatted_translation)

    def on_exit(self):
        debug_print("Exiting program...")
        self.hotkey_manager.stop()
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
        sys.exit(app.exec())
    except (KeyboardInterrupt, SystemExit):
        main_app.on_exit()


if __name__ == "__main__":
    main()
