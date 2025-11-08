"""
The settings window for the Floating Dictionary application.
Provides UI for managing history, hotkeys, and other configurations.
"""
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QTableWidget, 
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QHeaderView,
    QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsWindow(QDialog):
    # Signals to communicate back to the main application
    clear_history_requested = pyqtSignal()
    display_translation_requested = pyqtSignal(tuple)

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Floating Dictionary - Settings")
        self.setMinimumSize(700, 500)
        self.worker = worker

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        
        # --- Tab Widget ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 20px;
                font-size: 10pt;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                border-top: none;
            }
        """)
        main_layout.addWidget(self.tab_widget)

        # --- Create Tabs ---
        self.history_tab = self._create_history_tab()
        self.settings_tab = self._create_settings_tab()
        self.about_tab = self._create_about_tab()

        self.tab_widget.addTab(self.history_tab, "History")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        self.tab_widget.addTab(self.about_tab, "About")

    def _create_history_tab(self):
        """Creates the UI for the History tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Controls (Search and Buttons) ---
        controls_layout = QHBoxLayout()
        self.history_search_input = QLineEdit()
        self.history_search_input.setPlaceholderText("Search for a word...")
        self.history_search_input.textChanged.connect(self.filter_history_table)
        
        self.history_refresh_button = QPushButton("Refresh")
        self.history_refresh_button.clicked.connect(self.populate_history_table)

        self.history_clear_button = QPushButton("Clear All History")
        self.history_clear_button.setStyleSheet("background-color: #8B0000; color: white;")
        self.history_clear_button.clicked.connect(self.confirm_clear_history)

        controls_layout.addWidget(self.history_search_input)
        controls_layout.addWidget(self.history_refresh_button)
        controls_layout.addWidget(self.history_clear_button)
        layout.addLayout(controls_layout)

        # --- History Table ---
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Word", "From", "To", "Date"])
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSortingEnabled(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.itemDoubleClicked.connect(self.on_history_item_doubled_clicked)

        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.history_table)
        return widget

    def populate_history_table(self):
        """Fills the history table with data from the worker."""
        self.history_table.setSortingEnabled(False) # Disable sorting during population
        self.history_table.setRowCount(0)
        dictionary_data = self.worker.dictionary_data

        # Convert dict to list of tuples for easier handling
        history_items = dictionary_data.items()

        for cache_key, data in history_items:
            word, src_lang, dest_lang = cache_key
            timestamp = datetime.fromisoformat(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            row_position = self.history_table.rowCount()
            self.history_table.insertRow(row_position)
            self.history_table.setItem(row_position, 0, QTableWidgetItem(word.capitalize()))
            self.history_table.setItem(row_position, 1, QTableWidgetItem(src_lang))
            self.history_table.setItem(row_position, 2, QTableWidgetItem(dest_lang))
            self.history_table.setItem(row_position, 3, QTableWidgetItem(timestamp))
            # Store the cache_key in the first item for later retrieval
            self.history_table.item(row_position, 0).setData(Qt.ItemDataRole.UserRole, cache_key)

        self.history_table.setSortingEnabled(True)
        self.history_table.sortByColumn(3, Qt.SortOrder.DescendingOrder) # Sort by date descending

    def filter_history_table(self, text):
        """Hides rows that do not match the search text."""
        for i in range(self.history_table.rowCount()):
            word_item = self.history_table.item(i, 0)
            if word_item:
                match = text.lower() in word_item.text().lower()
                self.history_table.setRowHidden(i, not match)

    def on_history_item_doubled_clicked(self, item):
        """Handles double-clicking on a history item to re-display the translation."""
        cache_key = item.data(Qt.ItemDataRole.UserRole)
        if cache_key:
            self.display_translation_requested.emit(cache_key)
            self.hide() # Hide settings window after showing translation

    def confirm_clear_history(self):
        """Shows a confirmation dialog before clearing history."""
        reply = QMessageBox.question(self, 'Confirm Clear', 
                                     "Are you sure you want to delete all translation history and cache?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.clear_history_requested.emit()
            self.populate_history_table() # Refresh the table view

    def showEvent(self, event):
        """Override showEvent to populate history when the window is shown."""
        super().showEvent(event)
        if self.tab_widget.currentWidget() == self.history_tab:
            self.populate_history_table()

    def _create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Hotkey and language settings will be implemented here."))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        return widget

    def _create_about_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Application information will be shown here."))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        return widget