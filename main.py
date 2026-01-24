import sys
from functools import partial
from typing import Optional, Union

from PyQt6.QtCore import QObject, QRect, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
    QWidget,
)

from config import (
    DEFAULT_HOTKEY_EXIT,
    DEFAULT_HOTKEY_SENTENCE,
    DEFAULT_HOTKEY_WORD,
    LANG_CODE_MAP,
    SETTINGS_FILE_PATH,
    SOURCE_LANG,
    TARGET_LANG,
)
from core.hotkey_manager import HotkeyManager
from core.settings_manager import load_settings, save_settings
from core.worker import TranslationWorker
from services.tesseract_setup import initialize_tesseract
from ui.overlay import Overlay
from ui.settings_window import SettingsWindow
from ui.tooltip import PersistentToolTip
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

        # --- Load Settings ---
        self.default_hotkeys = {
            "word": DEFAULT_HOTKEY_WORD,
            "sentence": DEFAULT_HOTKEY_SENTENCE,
            "exit": DEFAULT_HOTKEY_EXIT,
        }
        self.settings = load_settings(SETTINGS_FILE_PATH, self.default_hotkeys)

        self.overlay = Overlay()
        self.tooltip = PersistentToolTip()
        self.worker = TranslationWorker(self.emitter)
        self.settings_window = SettingsWindow(
            self.worker, self.settings, self.default_hotkeys, parent=None
        )
        self.hotkey_manager = self._create_hotkey_manager()
        self.setup_tray_icon()
        self.connect_signals()

    def _create_hotkey_manager(self):
        """Creates a new HotkeyManager instance with the current settings."""
        callbacks = {
            "capture": self.on_capture_hotkey,
            "sentence": self.on_sentence_hotkey,
            "exit": self.on_exit,
        }
        hotkey_config = {
            "word": self.settings["word"],
            "sentence": self.settings["sentence"],
            "exit": self.settings["exit"],
        }
        return HotkeyManager(
            hotkey_config, callbacks, hide_callback=self.cancel_highlight
        )

    def setup_tray_icon(self):
        icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(icon, parent=self.app)
        self.settings_window.setWindowIcon(
            icon
        )  # Set the same icon for the settings window
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
        self.overlay.region_selected.connect(self.on_region_selected)
        self.overlay.translate_all_requested.connect(self.on_translate_all_requested)
        self.overlay.words_selected.connect(self.on_words_selected)
        self.overlay.dismiss_requested.connect(self.cancel_highlight)
        self.tooltip.dismiss_requested.connect(self.cancel_highlight)
        self.settings_window.clear_history_requested.connect(
            self.on_clear_history_requested
        )
        self.settings_window.delete_entries_requested.connect(
            self.on_delete_entries_requested
        )
        self.settings_window.display_translation_requested.connect(
            self.display_cached_translation
        )
        self.settings_window.settings_saved.connect(self.on_settings_saved)

    def run(self):
        self.worker.start()
        self.hotkey_manager.start()
        self.tray_icon.show()
        self.tray_icon.showMessage(
            "Floating Dictionary",
            f"Ready to work!\n- Translate word: {self.settings['word']}\n- Translate sentence: {self.settings['sentence']}",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
        debug_print("Floating Dictionary (Longdo + Google) is ready!")
        debug_print(
            f" - Press [{self.settings['word']}] to translate the word under the cursor"
        )
        debug_print(
            f" - Press [{self.settings['sentence']}] to enter sentence selection mode (drag to select)"
        )
        debug_print(" - Press [Esc] to cancel or hide the window")
        debug_print(f" - Press [{self.settings['exit']}] to exit the program")

    def on_capture_hotkey(self):
        self.worker.add_job(self.source_lang, self.target_lang)

    def on_sentence_hotkey(self):
        self.emitter.enter_sentence_mode_signal.emit()

    def show_settings_window(self):
        """Stops hotkeys, shows the settings window, and restarts them when it closes."""
        debug_print("Disabling hotkeys to open settings window.")
        self.hotkey_manager.stop()

        # The exec() call makes the window modal and blocks until it's closed.
        self.settings_window.exec()

        # After the window is closed (either by 'X' or 'Save'), restart the hotkey manager.
        # The on_settings_saved signal already handles restarting, so this covers the case
        # where the user closes the window without saving.
        self.restart_hotkey_manager()

    def blink_highlight(self, box_to_blink):
        self.overlay.enter_dismiss_mode(box_to_blink)

    def on_show_tooltip(
        self,
        text: str,
        position_hint: Optional[Union[dict, QRect]],
    ) -> None:
        pos = QCursor.pos()
        rect: Optional[QRect] = None

        if isinstance(position_hint, dict):
            rect = QRect(
                position_hint["left"],
                position_hint["top"],
                position_hint["width"],
                position_hint["height"],
            )
            pos = rect.topRight()

        elif isinstance(position_hint, QRect):
            rect = position_hint
            pos = rect.center()

        self.tooltip.show_at(pos, text)

        is_final_result: bool = "<i>" not in text and bool(text)

        if is_final_result and rect is not None:
            self.overlay.enter_dismiss_mode(rect)
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

    def on_delete_entries_requested(self, cache_keys: list):
        """Deletes specific entries from history and cache."""
        self.worker.delete_entries(cache_keys)

    def restart_hotkey_manager(self):
        """Safely stops the current hotkey manager and starts a new one with current settings."""
        debug_print("Restarting hotkey manager...")
        if self.hotkey_manager and self.hotkey_manager.listener.is_alive():
            self.hotkey_manager.stop()
        self.hotkey_manager = self._create_hotkey_manager()
        self.hotkey_manager.start()

    def on_settings_saved(self, new_settings):
        """Applies new settings, especially for hotkeys."""
        self.settings = new_settings
        save_settings(SETTINGS_FILE_PATH, self.settings)
        self.restart_hotkey_manager()  # Restart with the new settings

        QMessageBox.information(
            self.settings_window,
            "Settings Saved",
            "Your new settings have been applied successfully.",
        )
        self.settings_window.close()

    def display_cached_translation(self, cache_key: tuple):
        """Retrieves and displays a cached translation."""
        formatted_translation = self.worker.dictionary_data.get(cache_key, {}).get(
            "html"
        )
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
