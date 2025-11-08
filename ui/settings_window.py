"""
The settings window for the Floating Dictionary application.
Provides UI for managing history, hotkeys, and other configurations.
"""
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QTreeWidget, 
    QTreeWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QHeaderView,
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

        self.history_delete_button = QPushButton("Delete Selected")
        self.history_delete_button.clicked.connect(self.delete_selected_history_items)

        self.history_clear_button = QPushButton("Clear All History")
        self.history_clear_button.setStyleSheet("background-color: #8B0000; color: white;")
        self.history_clear_button.clicked.connect(self.confirm_clear_history)

        controls_layout.addWidget(self.history_search_input)
        controls_layout.addWidget(self.history_delete_button)
        controls_layout.addWidget(self.history_refresh_button)
        controls_layout.addWidget(self.history_clear_button)
        layout.addLayout(controls_layout)

        # --- History Table ---
        self.history_tree = QTreeWidget()
        self.history_tree.setColumnCount(4)
        self.history_tree.setHeaderLabels(["ID", "Word", "To", "Date"])
        self.history_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_tree.setSortingEnabled(True)
        self.history_tree.itemDoubleClicked.connect(self.on_history_item_doubled_clicked)

        header = self.history_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.history_tree)
        return widget

    def populate_history_table(self):
        """Fills the history table with data from the worker."""
        self.history_tree.setSortingEnabled(False)
        self.history_tree.clear()
        dictionary_data = self.worker.dictionary_data
        
        groups = {}
        today = date.today()
        
        # Sort items by timestamp descending to get correct IDs
        sorted_items = sorted(dictionary_data.items(), key=lambda item: item[1]['timestamp'], reverse=True)

        for i, (cache_key, data) in enumerate(sorted_items):
            word, src_lang, dest_lang = cache_key
            
            dt_object = datetime.fromisoformat(data['timestamp'])
            if dt_object.date() == today:
                timestamp_str = f"Today, {dt_object.strftime('%H:%M')}"
            else:
                timestamp_str = dt_object.strftime('%Y-%m-%d %H:%M')

            if src_lang not in groups:
                groups[src_lang] = QTreeWidgetItem(self.history_tree, [f"From: {src_lang.upper()}"])
                groups[src_lang].setExpanded(True)

            child_item = QTreeWidgetItem(groups[src_lang], [str(i + 1), word.capitalize(), dest_lang, timestamp_str])
            child_item.setData(0, Qt.ItemDataRole.UserRole, cache_key) # Store cache_key

        self.history_tree.setSortingEnabled(True)
        self.history_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def filter_history_table(self, text):
        """Hides rows that do not match the search text."""
        root = self.history_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            group_has_visible_child = False
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                word = child_item.text(1) # Word is in column 1
                match = text.lower() in word.lower()
                child_item.setHidden(not match)
                if match:
                    group_has_visible_child = True
            group_item.setHidden(not group_has_visible_child)

    def on_history_item_doubled_clicked(self, item):
        """Handles double-clicking on a history item."""
        # Only act on child items, not group headers
        if item.parent():
            word_to_copy = item.text(1) # Word is in column 1
            QApplication.clipboard().setText(word_to_copy)
            # Optionally, show a notification that text was copied

    def delete_selected_history_items(self):
        """Gathers selected items and emits a signal to request their deletion."""
        selected_items = self.history_tree.selectedItems()
        keys_to_delete = []
        for item in selected_items:
            if item.parent(): # Ensure it's a child item
                cache_key = item.data(0, Qt.ItemDataRole.UserRole)
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