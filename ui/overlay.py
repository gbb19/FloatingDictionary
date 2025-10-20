"""
The overlay widget for highlighting text boxes.
"""
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QCursor, QFont

class Overlay(QWidget):
    # Signal to be emitted when a region is selected
    translate_all_requested = pyqtSignal(QRect)
    region_selected = pyqtSignal(QRect)
    words_selected = pyqtSignal(list)
    dismiss_requested = pyqtSignal()

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
        self.is_dismiss_mode = False # --- [เพิ่ม] สถานะใหม่สำหรับรอคลิกเพื่อปิด ---
        self.is_selection_mode = False
        
        # For region selection mode
        # --- [เพิ่ม] สถานะใหม่สำหรับรอการเลือก action ---
        self.is_awaiting_action = False
        self.button_translate_all_rect = QRect()
        self.button_select_words_rect = QRect()
        self.hovered_button = None

        self.is_region_selection_mode = False
        self.selection_rect = QRect()
        self.origin_point = None

        # For word selection mode
        self.all_word_boxes = []
        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False
        self.selection_anchor_box = None # --- [เพิ่ม] สำหรับ Shift+Click ---

    def set_box(self, box_data):
        """Sets the bounding box to be drawn on the overlay."""
        if box_data:
            if isinstance(box_data, QRect):
                self.box_to_draw = box_data
            elif isinstance(box_data, dict):
                self.box_to_draw = QRect(box_data['left'], box_data['top'], box_data['width'], box_data['height'])
        else:
            self.box_to_draw = None
        self.update()

    def paintEvent(self, event):
        """Draws the highlight box."""
        if not self.box_to_draw and not self.is_selection_mode and not self.is_region_selection_mode and not self.is_awaiting_action and not self.is_dismiss_mode:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # --- [แก้ไข] กำหนดสีพื้นหลังที่โปร่งใสมากขึ้น และใช้ร่วมกันในทุกโหมด ---
        # --- [แก้ไข] ใช้ค่า Alpha=1 เพื่อให้ยังรับการคลิกเมาส์ได้ แต่ดูโปร่งใส ---
        overlay_background_color = QColor(0, 0, 0, 1)

        if self.is_region_selection_mode or self.is_dismiss_mode:
            # Draw a semi-transparent overlay
            painter.fillRect(self.rect(), overlay_background_color)
            # Draw the selection rectangle
            painter.setPen(QPen(QColor("#33AFFF"), 1, Qt.SolidLine))
            painter.setBrush(QColor(0, 0, 0, 0)) # Transparent brush
            painter.drawRect(self.selection_rect)
        elif self.is_awaiting_action:
            # --- [เพิ่ม] วาดปุ่ม "แปลทั้งหมด" และ "เลือกคำ" ---
            painter.fillRect(self.rect(), overlay_background_color)
            painter.setPen(QPen(QColor("#33AFFF"), 1, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
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
            painter.drawText(self.button_translate_all_rect, Qt.AlignCenter, "Translate All")

            # Draw "Select Words" button
            bg_color_select = QColor("#555") if self.hovered_button == 'select' else QColor("#333")
            painter.setBrush(bg_color_select)
            painter.setPen(QPen(QColor("#888")))
            painter.drawRoundedRect(self.button_select_words_rect, 5, 5)
            painter.setPen(QPen(QColor("#f0f0f0")))
            painter.drawText(self.button_select_words_rect, Qt.AlignCenter, "Select Words")
        elif self.is_selection_mode:
            # --- [แก้ไข] รวมโค้ดวาดพื้นหลังที่ซ้ำซ้อน และใช้สีใหม่ ---
            painter.fillRect(self.rect(), overlay_background_color)
            
            # --- [เพิ่ม] วาดกรอบของพื้นที่ที่เลือกไว้แต่แรก เพื่อให้ผู้ใช้เห็นขอบเขต ---
            pen = QPen(QColor("#33AFFF"), 1, Qt.DashLine) # สีฟ้า, เส้นประ
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.selection_rect)

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
            # --- [แก้ไข] เปลี่ยนจากการวาดเส้นขอบเป็นการเติมสีให้เหมือนโหมดเลือกประโยค ---
            painter.setPen(Qt.NoPen) # ไม่ต้องมีเส้นขอบ
            painter.setBrush(QColor(60, 179, 113, 120)) # SeaGreen, semi-transparent
            painter.drawRect(self.box_to_draw)

    def enter_region_selection_mode(self):
        """Activates the overlay for the first step: region selection."""
        # --- [แก้ไข] รีเซ็ตสถานะทั้งหมดก่อนเริ่มโหมดเลือกพื้นที่ใหม่เสมอ ---
        self.exit_selection_mode()
        self.is_region_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()

    def enter_dismiss_mode(self, box_to_draw):
        """Activates a mode where any click will dismiss the overlay and tooltip."""
        self.exit_selection_mode() # Reset everything first
        self.is_dismiss_mode = True
        self.set_box(box_to_draw)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()

    def enter_word_selection_mode(self, boxes, selection_rect):
        """Activates the overlay for word-by-word selection."""
        self.exit_selection_mode() # Reset first
        self.all_word_boxes = boxes
        self.selection_rect = selection_rect # --- [เพิ่ม] รับค่า selection_rect มาเก็บไว้ ---
        self.is_selection_mode = True
        self.set_box(None)
        self.setCursor(QCursor(Qt.IBeamCursor)) # --- [แก้ไข] เปลี่ยน Cursor เป็นแบบเลือกข้อความ (I-Beam) ---
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()
        self.activateWindow()
        self.setMouseTracking(True) # Important for hover effects

    def exit_selection_mode(self):
        """Deactivates the selection mode."""
        self.is_dismiss_mode = False
        self.is_selection_mode = False
        self.all_word_boxes = []

        self.is_awaiting_action = False
        self.hovered_button = None

        self.is_region_selection_mode = False
        self.selection_rect = QRect()
        self.origin_point = None

        self.hovered_word_box = None
        self.selected_word_boxes = []
        self.is_mouse_pressed = False
        self.selection_anchor_box = None
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self.hide()
        self.update()

    def mousePressEvent(self, event):
        # --- [แก้ไข] ปรับปรุงเงื่อนไขให้รองรับทั้งสองโหมดการเลือก ---
        if event.button() != Qt.LeftButton:
            return

        # --- [เพิ่ม] ถ้าอยู่ในโหมดรอคลิกเพื่อปิด ให้ทำการยกเลิกทันที ---
        if self.is_dismiss_mode:
            self.dismiss_requested.emit()
            return

        if self.is_region_selection_mode:
            self.origin_point = event.pos()
            self.selection_rect = QRect(self.origin_point, self.origin_point)
            self.update()
            return

        if self.is_awaiting_action:
            # --- [เพิ่ม] ตรวจสอบการคลิกปุ่ม ---
            if self.button_translate_all_rect.contains(event.pos()):
                self.translate_all_requested.emit(self.selection_rect)
                self.exit_selection_mode()
            elif self.button_select_words_rect.contains(event.pos()):
                self.region_selected.emit(self.selection_rect)
                self.exit_selection_mode()
            # Allow clicking outside to cancel
            # self.exit_selection_mode()
            return

        # --- [แก้ไข] ปรับปรุง Logic การเลือกคำศัพท์ทั้งหมด ---
        clicked_box = self.get_box_at(event.pos())
        if not clicked_box:
            return

        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.ShiftModifier and self.selection_anchor_box:
            # --- Shift + Click: เลือกเป็นช่วง ---
            try:
                start_index = self.all_word_boxes.index(self.selection_anchor_box)
                end_index = self.all_word_boxes.index(clicked_box)
                if start_index > end_index:
                    start_index, end_index = end_index, start_index
                
                self.selected_word_boxes = self.all_word_boxes[start_index : end_index + 1]
            except ValueError:
                # กรณีที่ anchor หายไป (ไม่น่าเกิด)
                self.selected_word_boxes = [clicked_box]
                self.selection_anchor_box = clicked_box

        elif modifiers == Qt.ControlModifier:
            # --- Ctrl + Click: เลือก/ยกเลิกทีละคำ ---
            if clicked_box in self.selected_word_boxes:
                self.selected_word_boxes.remove(clicked_box)
            else:
                self.selected_word_boxes.append(clicked_box)
            self.selection_anchor_box = clicked_box # ตั้ง anchor ใหม่

        else:
            # --- คลิกธรรมดา: เริ่มการเลือกใหม่ หรือเริ่มลาก ---
            self.selected_word_boxes = [clicked_box]
            self.selection_anchor_box = clicked_box
            self.is_mouse_pressed = True

        self.update()

    def mouseMoveEvent(self, event):
        if self.is_region_selection_mode and self.origin_point:
            self.selection_rect = QRect(self.origin_point, event.pos()).normalized()
            self.update()
        elif self.is_selection_mode:
            # --- [แก้ไข] กลับมาใช้ Logic การเลือกทีละคำ ---
            new_hovered_box = self.get_box_at(event.pos())
            
            if self.hovered_word_box != new_hovered_box:
                self.hovered_word_box = new_hovered_box
                self.update()

            # --- [แก้ไข] ใช้ Logic การเลือกแบบ Text Editor (ลากแล้วเลือก) เพียงอย่างเดียว ---
            if self.is_mouse_pressed and new_hovered_box and self.selection_anchor_box:
                try:
                    start_index = self.all_word_boxes.index(self.selection_anchor_box)
                    end_index = self.all_word_boxes.index(new_hovered_box)

                    # เรียง index ให้ถูกต้องเสมอ
                    if start_index > end_index:
                        start_index, end_index = end_index, start_index
                    
                    # เลือกคำทั้งหมดที่อยู่ระหว่าง start และ end
                    self.selected_word_boxes = self.all_word_boxes[start_index : end_index + 1]
                except (ValueError, IndexError):
                    # ป้องกันข้อผิดพลาดหากไม่เจอคำใน list
                    pass
                self.update()

    def mouseReleaseEvent(self, event):
        # --- [แก้ไข] หยุดการลากเลือกเมื่อปล่อยเมาส์ ---
        self.is_mouse_pressed = False

        if event.button() != Qt.LeftButton:
            return

        if self.is_region_selection_mode:
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                # --- [แก้ไข] เปลี่ยนไปสู่โหมดรอการเลือก action แทน ---
                self.is_region_selection_mode = False
                self.is_awaiting_action = True
                self.setMouseTracking(True) # เปิดการติดตามเมาส์เพื่อ hover
                
                # --- [แก้ไข] คำนวณตำแหน่งปุ่มให้อยู่ที่มุมขวาล่างของพื้นที่ที่เลือก ---
                button_width = 100
                button_height = 30
                button_spacing = 5
                button_y = self.selection_rect.bottom() + 5
                self.button_select_words_rect = QRect(self.selection_rect.right() - button_width, button_y, button_width, button_height)
                self.button_translate_all_rect = QRect(self.selection_rect.right() - (button_width * 2) - button_spacing, button_y, button_width, button_height)
                
                self.update()
            else:
                self.exit_selection_mode()

        elif self.is_selection_mode:
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

    def get_box_at(self, pos):
        """Helper function to find which word box is at a given position."""
        for box in self.all_word_boxes:
            if QRect(box['left'], box['top'], box['width'], box['height']).contains(pos):
                return box
        return None