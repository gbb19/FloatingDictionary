"""
The overlay widget for highlighting text boxes, selecting regions, and selecting words.
This widget is a transparent, full-screen window that can be in one of several modes
to handle user interaction without interfering with other applications.
"""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QCursor, QFont, QGuiApplication

class Overlay(QWidget):
    """
    Manages different interaction modes:
    - Region Selection: User draws a rectangle on the screen.
    - Word Selection: After OCR, user selects individual word boxes.
    - Awaiting Action: After region selection, user chooses to translate all or select words.
    - Dismiss Mode: A simple highlight is shown, and any click dismisses it.
    """
    # Signal emitted when the user wants to translate the entire selected region.
    translate_all_requested = pyqtSignal(QRect)
    # Signal emitted when the user wants to proceed to word selection for the region.
    region_selected = pyqtSignal(QRect)
    # Signal emitted with the final list of selected words.
    words_selected = pyqtSignal(list)
    # Signal emitted when the overlay should be hidden (e.g., by clicking or pressing Esc).
    dismiss_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Set window flags to be a frameless, always-on-top tool window.
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        # Make the window background transparent and initially ignore mouse events.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Unify geometry across all available screens for multi-monitor support.
        screens = QApplication.screens()
        total_geometry = QRect()
        for screen in screens:
            total_geometry = total_geometry.united(screen.geometry())
        self.setGeometry(total_geometry)

        # --- State variables ---
        self.box_to_draw = None
        self.is_dismiss_mode = False
        self.is_selection_mode = False
        self.is_region_selection_mode = False
        self.is_awaiting_action = False
        
        # For region selection
        self.selection_rect = QRect()
        self.origin_point = None

        # For the action choice after region selection
        self.button_translate_all_rect = QRect()
        self.button_select_words_rect = QRect()
        self.hovered_button = None

        # For word selection
        self.all_word_boxes = []
        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False
        self.selection_anchor_box = None # Used for Shift+Click range selection

    def set_box(self, box_data):
        """Sets the bounding box to be drawn on the overlay for dismiss mode."""
        if box_data:
            if isinstance(box_data, QRect):
                self.box_to_draw = box_data
            elif isinstance(box_data, dict):
                self.box_to_draw = QRect(box_data['left'], box_data['top'], box_data['width'], box_data['height'])
        else:
            self.box_to_draw = None
        self.update()

    def paintEvent(self, event):
        """Draws the overlay content based on the current mode."""
        if not self.box_to_draw and not self.is_selection_mode and not self.is_region_selection_mode and not self.is_awaiting_action and not self.is_dismiss_mode:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Use a near-transparent background to capture mouse events in active modes.
        overlay_background_color = QColor(0, 0, 0, 1)

        if self.is_region_selection_mode or self.is_dismiss_mode:
            painter.fillRect(self.rect(), overlay_background_color)
            painter.setPen(QPen(QColor("#33AFFF"), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selection_rect)

        elif self.is_awaiting_action:
            # Draw the two choice buttons ("Translate All", "Select Words")
            painter.fillRect(self.rect(), overlay_background_color)
            painter.setPen(QPen(QColor("#33AFFF"), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selection_rect)

            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)

            # Draw "Translate All" button
            bg_color_all = QColor("#555") if self.hovered_button == 'all' else QColor("#333")
            painter.setBrush(bg_color_all)
            painter.setPen(QPen(QColor("#888")))
            painter.drawRoundedRect(self.button_translate_all_rect, 5, 5)
            painter.setPen(QPen(QColor("#f0f0f0")))
            painter.drawText(self.button_translate_all_rect, Qt.AlignmentFlag.AlignCenter, "Translate All")

            # Draw "Select Words" button
            bg_color_select = QColor("#555") if self.hovered_button == 'select' else QColor("#333")
            painter.setBrush(bg_color_select)
            painter.setPen(QPen(QColor("#888")))
            painter.drawRoundedRect(self.button_select_words_rect, 5, 5)
            painter.setPen(QPen(QColor("#f0f0f0")))
            painter.drawText(self.button_select_words_rect, Qt.AlignmentFlag.AlignCenter, "Select Words")

        elif self.is_selection_mode:
            painter.fillRect(self.rect(), overlay_background_color)
            
            # Draw a dashed border around the original selection area for context.
            pen = QPen(QColor("#33AFFF"), 1, Qt.PenStyle.DashLine) # Blue, dashed line
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selection_rect)

            # Highlight already selected boxes in green.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(60, 179, 113, 120)) # SeaGreen
            for box in self.selected_word_boxes:
                painter.drawRect(QRect(box['left'], box['top'], box['width'], box['height']))
            
            # Highlight the box currently under the cursor in blue.
            if self.hovered_word_box and self.hovered_word_box not in self.selected_word_boxes:
                painter.setBrush(QColor(51, 175, 255, 120)) # Light Blue
                box = self.hovered_word_box
                painter.drawRect(QRect(box['left'], box['top'], box['width'], box['height']))

        if self.box_to_draw:
            # In dismiss mode, draw a solid highlight over the translated word/phrase.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(60, 179, 113, 120)) # SeaGreen, semi-transparent
            painter.drawRect(self.box_to_draw)

    def enter_region_selection_mode(self):
        """Activates the overlay for the user to draw a selection rectangle."""
        self.exit_selection_mode() # Reset all states first
        self.is_region_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()

    def enter_dismiss_mode(self, box_to_draw):
        """Activates a mode where a box is highlighted and any click dismisses the overlay."""
        self.exit_selection_mode() # Reset all states first
        self.is_dismiss_mode = True
        self.set_box(box_to_draw)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()

    def enter_word_selection_mode(self, boxes, selection_rect):
        """Activates the overlay for word-by-word selection after pre-OCR."""
        self.exit_selection_mode() # Reset all states first
        self.all_word_boxes = boxes
        self.selection_rect = selection_rect
        self.is_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()
        self.setMouseTracking(True) # Required for hover effects

    def exit_selection_mode(self):
        """Deactivates any active mode and resets all state variables."""
        self.is_dismiss_mode = False
        self.is_selection_mode = False
        self.is_awaiting_action = False
        self.is_region_selection_mode = False
        
        self.all_word_boxes = []
        self.hovered_button = None
        self.selection_rect = QRect()
        self.origin_point = None
        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False
        self.selection_anchor_box = None
        
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self.hide()
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.is_dismiss_mode:
            self.dismiss_requested.emit()
            return

        if self.is_region_selection_mode:
            self.origin_point = event.pos()
            self.selection_rect = QRect(self.origin_point, self.origin_point)
            self.update()
            return

        if self.is_awaiting_action:
            if self.button_translate_all_rect.contains(event.pos()):
                self.translate_all_requested.emit(self.selection_rect)
                self.exit_selection_mode()
            elif self.button_select_words_rect.contains(event.pos()):
                self.region_selected.emit(self.selection_rect)
                self.exit_selection_mode()
            return

        if self.is_selection_mode:
            clicked_box = self.get_box_at(event.pos())
            if not clicked_box:
                return

            modifiers = QGuiApplication.keyboardModifiers()

            if modifiers == Qt.KeyboardModifier.ShiftModifier and self.selection_anchor_box:
                # Shift+Click: Select a range of words.
                try:
                    start_index = self.all_word_boxes.index(self.selection_anchor_box)
                    end_index = self.all_word_boxes.index(clicked_box)
                    if start_index > end_index:
                        start_index, end_index = end_index, start_index
                    
                    self.selected_word_boxes = self.all_word_boxes[start_index : end_index + 1]
                except ValueError:
                    # Fallback if the anchor box is not found (should not happen)
                    self.selected_word_boxes = [clicked_box]
                    self.selection_anchor_box = clicked_box

            elif modifiers == Qt.KeyboardModifier.ControlModifier:
                # Ctrl+Click: Add or remove a single word from the selection.
                if clicked_box in self.selected_word_boxes:
                    self.selected_word_boxes.remove(clicked_box)
                else:
                    self.selected_word_boxes.append(clicked_box)
                self.selection_anchor_box = clicked_box # Set new anchor for potential shift-clicks

            else:
                # Plain Click: Start a new selection or begin a drag-selection.
                self.selected_word_boxes = [clicked_box]
                self.selection_anchor_box = clicked_box
                self.is_mouse_pressed = True

            self.update()

    def mouseMoveEvent(self, event):
        if self.is_region_selection_mode and self.origin_point:
            self.selection_rect = QRect(self.origin_point, event.pos()).normalized()
            self.update()
        elif self.is_awaiting_action:
            pos = event.pos()
            new_hovered_button = None
            if self.button_translate_all_rect.contains(pos):
                new_hovered_button = 'all'
            elif self.button_select_words_rect.contains(pos):
                new_hovered_button = 'select'
            
            if self.hovered_button != new_hovered_button:
                self.hovered_button = new_hovered_button
                self.update()
        elif self.is_selection_mode:
            new_hovered_box = self.get_box_at(event.pos())
            
            if self.hovered_word_box != new_hovered_box:
                self.hovered_word_box = new_hovered_box
                self.update()

            # Handle drag-to-select logic (like a text editor)
            if self.is_mouse_pressed and new_hovered_box and self.selection_anchor_box:
                try:
                    start_index = self.all_word_boxes.index(self.selection_anchor_box)
                    end_index = self.all_word_boxes.index(new_hovered_box)

                    if start_index > end_index:
                        start_index, end_index = end_index, start_index
                    
                    self.selected_word_boxes = self.all_word_boxes[start_index : end_index + 1]
                except (ValueError, IndexError):
                    # Ignore if a box is not found in the list
                    pass
                self.update()

    def mouseReleaseEvent(self, event):
        self.is_mouse_pressed = False

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.is_region_selection_mode:
            # If the selection is reasonably sized, transition to the action-awaiting state.
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                self.is_region_selection_mode = False
                self.is_awaiting_action = True
                self.setMouseTracking(True) # Enable mouse tracking for button hovering
                
                # Calculate positions for the action buttons below the selection rectangle.
                button_width = 100
                button_height = 30
                button_spacing = 5
                button_y = self.selection_rect.bottom() + 5
                self.button_select_words_rect = QRect(self.selection_rect.right() - button_width, button_y, button_width, button_height)
                self.button_translate_all_rect = QRect(self.selection_rect.right() - (button_width * 2) - button_spacing, button_y, button_width, button_height)
                
                self.update()
            else:
                # If selection is too small, just cancel the operation.
                self.exit_selection_mode()

        elif self.is_selection_mode:
            # When selection is finished, sort the words logically and emit the result.
            if self.selected_word_boxes:
                # This logic sorts words first by line, then by horizontal position.
                sorted_by_y = sorted(self.selected_word_boxes, key=lambda b: b['top'])
                
                lines = []
                if not sorted_by_y:
                    self.words_selected.emit([])
                    self.exit_selection_mode()
                    return

                current_line = [sorted_by_y[0]]
                
                for i in range(1, len(sorted_by_y)):
                    prev_box = current_line[-1]
                    current_box = sorted_by_y[i]
                    
                    # Check if the vertical center of the current box is within the previous box's height to group words into lines.
                    if (current_box['top'] + current_box['height'] / 2) < (prev_box['top'] + prev_box['height']):
                        current_line.append(current_box)
                    else:
                        lines.append(sorted(current_line, key=lambda b: b['left']))
                        current_line = [current_box]
                lines.append(sorted(current_line, key=lambda b: b['left']))
                
                self.selected_word_boxes = [box for line in lines for box in line]

            self.words_selected.emit(self.selected_word_boxes)
            self.exit_selection_mode()

    def get_box_at(self, pos):
        """Helper function to find which word box is at a given QPoint position."""
        for box in self.all_word_boxes:
            if QRect(box['left'], box['top'], box['width'], box['height']).contains(pos):
                return box
        return None
