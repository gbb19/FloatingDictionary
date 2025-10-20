"""
The overlay widget for highlighting text boxes.
"""
import pyautogui
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QCursor

class Overlay(QWidget):
    # Signal to be emitted when a region is selected
    region_selected = pyqtSignal(QRect)
    words_selected = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        # Start as a tool window that doesn't interfere with mouse
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Get total screen size for multi-monitor setups
        # --- [แก้ไข] เปลี่ยนไปใช้วิธีที่ทันสมัยกว่าในการหาขนาดหน้าจอทั้งหมด ---
        screens = QApplication.screens()
        total_geometry = QRect()
        for screen in screens:
            total_geometry = total_geometry.united(screen.geometry())
        self.setGeometry(total_geometry)

        self.box_to_draw = None
        self.is_selection_mode = False
        
        # For region selection mode
        self.is_region_selection_mode = False
        self.selection_rect = QRect()
        self.origin_point = None

        # For word selection mode
        self.all_word_boxes = []
        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False

    def set_box(self, box_data):
        """Sets the bounding box to be drawn on the overlay."""
        if box_data:
            self.box_to_draw = QRect(box_data['left'], box_data['top'], box_data['width'], box_data['height'])
        else:
            self.box_to_draw = None
        self.update()

    def paintEvent(self, event):
        """Draws the highlight box."""
        if not self.box_to_draw and not self.is_selection_mode and not self.is_region_selection_mode:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.is_region_selection_mode:
            # Draw a semi-transparent overlay
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
            # Draw the selection rectangle
            painter.setPen(QPen(QColor("#33AFFF"), 1, Qt.SolidLine))
            painter.setBrush(QColor(0, 0, 0, 0)) # Transparent brush
            painter.drawRect(self.selection_rect)

        if self.is_selection_mode:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
            
            # Draw selected boxes
            painter.setPen(QPen(QColor(0, 0, 0, 0))) # No border
            painter.setBrush(QColor(60, 179, 113, 120)) # SeaGreen
            for box in self.selected_word_boxes:
                painter.drawRect(QRect(box['left'], box['top'], box['width'], box['height']))
            
            # --- [แก้ไข] กลับมาวาดกรอบสีฟ้าที่คำที่กำลังชี้ ---
            if self.hovered_word_box and self.hovered_word_box not in self.selected_word_boxes:
                painter.setBrush(QColor(51, 175, 255, 120)) # Light Blue
                box = self.hovered_word_box
                painter.drawRect(QRect(box['left'], box['top'], box['width'], box['height']))

        if self.box_to_draw:
            pen = QPen(Qt.red, 2)
            painter.setPen(pen)
            painter.drawRect(self.box_to_draw)

    def enter_region_selection_mode(self):
        """Activates the overlay for the first step: region selection."""
        self.is_region_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()

    def enter_word_selection_mode(self, boxes):
        """Activates the overlay for word-by-word selection."""
        self.all_word_boxes = boxes
        self.is_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()
        self.setMouseTracking(True) # Important for hover effects

    def exit_selection_mode(self):
        """Deactivates the selection mode."""
        self.is_selection_mode = False
        self.all_word_boxes = []

        self.is_region_selection_mode = False
        self.selection_rect = QRect()
        self.origin_point = None

        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self.hide()
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self.is_region_selection_mode:
            self.origin_point = event.pos()
            self.selection_rect = QRect(self.origin_point, self.origin_point)
            self.update()
        elif self.is_selection_mode:
            self.is_mouse_pressed = True
            self.selected_word_boxes = [] # --- [แก้ไข] รีเซ็ตรายการคำที่เลือก ---
            self.mouseMoveEvent(event) # --- [เพิ่ม] เรียกใช้ทันทีเพื่อเลือกคำแรกที่คลิก ---
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_region_selection_mode and self.origin_point:
            self.selection_rect = QRect(self.origin_point, event.pos()).normalized()
            self.update()
        elif self.is_selection_mode:
            # --- [แก้ไข] กลับมาใช้ Logic การเลือกทีละคำ ---
            current_pos = event.pos()
            new_hovered_box = None
            for box in self.all_word_boxes:
                if QRect(box['left'], box['top'], box['width'], box['height']).contains(current_pos):
                    new_hovered_box = box
                    if self.is_mouse_pressed and box not in self.selected_word_boxes:
                        self.selected_word_boxes.append(box)
                    break # --- [สำคัญ] หยุดเมื่อเจอคำแรก ---
            
            if self.hovered_word_box != new_hovered_box:
                self.hovered_word_box = new_hovered_box
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self.is_region_selection_mode:
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                self.region_selected.emit(self.selection_rect)
            self.exit_selection_mode()
        elif self.is_selection_mode:
            self.is_mouse_pressed = False
            
            # --- [แก้ไข] นำการจัดเรียงคำศัพท์กลับมา แต่ใช้ Algorithm ที่ดีกว่าเดิม ---
            # This new logic correctly sorts words into lines and then sorts each line.
            if self.selected_word_boxes:
                # Sort by vertical position first to group lines
                sorted_by_y = sorted(self.selected_word_boxes, key=lambda b: b['top'])
                
                lines = []
                current_line = [sorted_by_y[0]]
                
                for i in range(1, len(sorted_by_y)):
                    prev_box = current_line[-1]
                    current_box = sorted_by_y[i]
                    
                    # Check if the vertical center of the current box is within the previous box's height
                    if (current_box['top'] + current_box['height'] / 2) < (prev_box['top'] + prev_box['height']):
                        current_line.append(current_box)
                    else:
                        lines.append(sorted(current_line, key=lambda b: b['left']))
                        current_line = [current_box]
                lines.append(sorted(current_line, key=lambda b: b['left']))
                
                self.selected_word_boxes = [box for line in lines for box in line]

            self.words_selected.emit(self.selected_word_boxes)
            self.exit_selection_mode()