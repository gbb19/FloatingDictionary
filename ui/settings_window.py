"""
The settings window for the Floating Dictionary application.
Provides UI for managing history, hotkeys, and other configurations.
"""
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QTableWidget, QListWidget,
    QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QHeaderView,
    QAbstractItemView, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsWindow(QDialog):
    # Signals to communicate back to the main application
    clear_history_requested = pyqtSignal()
    delete_entries_requested = pyqtSignal(list)
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
        
        # Main layout with a left-side group list and a right-side content area
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left side (Language Group List) ---
        self.language_list = QListWidget()
        self.language_list.setMaximumWidth(150)
        self.language_list.setStyleSheet("""
            QListWidget {
                font-size: 11pt;
                background-color: #2c2c2c;
                border: none;
                padding-top: 5px;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background-color: #0078d7; }
        """)
        self.language_list.currentItemChanged.connect(self.update_history_view)

        # --- Right side (Controls and Table) ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # --- Controls (Search and Buttons) ---
        controls_layout = QHBoxLayout()
        self.history_search_input = QLineEdit()
        self.history_search_input.setPlaceholderText("Search for a word...")
        self.history_search_input.textChanged.connect(self.update_history_view)
        
        self.history_refresh_button = QPushButton("Refresh")
        self.history_refresh_button.clicked.connect(self.populate_history_table)

        self.history_delete_button = QPushButton("Delete Selected")
        self.history_delete_button.clicked.connect(self.delete_selected_history_items)

        self.history_clear_button = QPushButton("Clear All History")
        self.history_clear_button.setStyleSheet("background-color: #8B0000; color: white;")
        self.history_clear_button.clicked.connect(self.confirm_clear_history)

        controls_layout.addWidget(self.history_search_input)
        controls_layout.addWidget(self.history_delete_button)
        controls_layout.addWidget(self.history_refresh_button)
        controls_layout.addWidget(self.history_clear_button)
        content_layout.addLayout(controls_layout)

        # --- History Table ---
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setStyleSheet("font-size: 11pt;")
        self.history_table.setHorizontalHeaderLabels(["ID", "Word", "To", "Date"])
        self.history_table.setColumnHidden(0, True)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_table.setSortingEnabled(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.itemDoubleClicked.connect(self.on_history_item_doubled_clicked)

        header = self.history_table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section { font-size: 10pt; font-weight: bold; padding: 4px; }
        """)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        content_layout.addWidget(self.history_table)
        
        main_layout.addWidget(self.language_list)
        main_layout.addWidget(content_widget)

        return widget

    def populate_history_table(self):
        """Fills the history table with data from the worker."""
        dictionary_data = self.worker.dictionary_data
        
        today = date.today()
        
        # Sort items by timestamp descending to get correct IDs
        sorted_items = sorted(dictionary_data.items(), key=lambda item: item[1]['timestamp'], reverse=True)

        # --- Populate Language List (Left Panel) ---
        self.language_list.blockSignals(True) # Block signals while we modify it
        self.language_list.clear()
        self.language_list.addItem("All Languages")
        
        # Get unique source languages and sort them
        src_languages = sorted(list(set(key[1] for key, data in sorted_items)))
        for lang in src_languages:
            self.language_list.addItem(lang.upper())
        
        self.language_list.setCurrentRow(0) # Select "All Languages" by default
        self.language_list.blockSignals(False)

        # --- Populate Table (Right Panel) ---
        self.update_history_view()

    def update_history_view(self):
        """Central method to update the table based on selected language and search text."""
        self.history_table.setSortingEnabled(False)
        self.history_table.setRowCount(0)
        dictionary_data = self.worker.dictionary_data
        today = date.today()
        
        search_text = self.history_search_input.text().lower()
        selected_lang_item = self.language_list.currentItem()
        selected_lang = selected_lang_item.text().lower() if selected_lang_item else "all languages"

        # Sort items by timestamp descending to get correct IDs
        sorted_items = sorted(dictionary_data.items(), key=lambda item: item[1]['timestamp'], reverse=True)

        for i, (cache_key, data) in enumerate(sorted_items):
            word, src_lang, dest_lang = cache_key

            # Filter by selected language
            if selected_lang != "all languages" and src_lang != selected_lang:
                continue
            
            # Filter by search text
            if search_text and search_text not in word.lower():
                continue

            dt_object = datetime.fromisoformat(data['timestamp'])
            if dt_object.date() == today:
                timestamp_str = f"Today, {dt_object.strftime('%H:%M')}"
            else:
                timestamp_str = dt_object.strftime('%Y-%m-%d %H:%M')

            row_position = self.history_table.rowCount()
            self.history_table.insertRow(row_position)
            
            # Create items for each column
            id_item = QTableWidgetItem(str(i + 1))
            word_item = QTableWidgetItem(word.capitalize())
            to_item = QTableWidgetItem(dest_lang)
            date_item = QTableWidgetItem(timestamp_str)

            # Store the cache_key in the word item for later retrieval
            word_item.setData(Qt.ItemDataRole.UserRole, cache_key)

            self.history_table.setItem(row_position, 0, id_item)
            self.history_table.setItem(row_position, 1, word_item)
            self.history_table.setItem(row_position, 2, to_item)
            self.history_table.setItem(row_position, 3, date_item)

        self.history_table.setSortingEnabled(True)
        self.history_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def on_history_item_doubled_clicked(self, item):
        """Handles double-clicking on a history item."""
        # The item clicked is in some column, but we want the data from the 'Word' column (col 1)
        word_item = self.history_table.item(item.row(), 1)
        word_to_copy = word_item.text()
        QApplication.clipboard().setText(word_to_copy)

    def delete_selected_history_items(self):
        """Gathers selected items and emits a signal to request their deletion."""
        selected_rows = sorted(list(set(index.row() for index in self.history_table.selectedIndexes())), reverse=True)
        keys_to_delete = []
        for row in selected_rows:
            word_item = self.history_table.item(row, 1) # Get item from the 'Word' column
            cache_key = word_item.data(Qt.ItemDataRole.UserRole)
            if cache_key:
                keys_to_delete.append(cache_key)
        
        if keys_to_delete:
            self.delete_entries_requested.emit(keys_to_delete)
            self.populate_history_table() # Refresh view immediately

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