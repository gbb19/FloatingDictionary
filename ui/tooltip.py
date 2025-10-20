"""
The custom PersistentToolTip widget with scrolling, animations, and focus management.
"""
from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation
from PyQt5.QtGui import QPainter, QColor

from utils.windows import force_set_focus

class CustomScrollArea(QScrollArea):
    """
    A QScrollArea subclass that correctly handles mouse events for transparent windows.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)

    def viewportEvent(self, event):
        return super().viewportEvent(event)

class PersistentToolTip(QWidget):
    """
    A custom tooltip widget that can be controlled programmatically,
    supports scrolling, animations, and proper focus handling.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.scroll_area = CustomScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { border: none; background: #333; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #666; min-height: 20px; border-radius: 4px; }
        """)

        self.label = QLabel(self)
        self.label.setStyleSheet("background-color: transparent; color: #f7f7f7; padding-right: 4px;")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        # Fade-in animation
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(150)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        
        # Fade-out animation
        self.hide_animation = QPropertyAnimation(self, b"windowOpacity")
        self.hide_animation.setDuration(150)
        self.hide_animation.setStartValue(1.0)
        self.hide_animation.setEndValue(0.0)
        
        self.previous_focus_hwnd = None
        self.hide()

    def paintEvent(self, event):
        """Custom paint event to draw the rounded-corner background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#222222"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

    def on_hide_finished(self):
        """Slot called when the hide animation finishes."""
        self.hide()
        # --- [ลบออก] ไม่จำเป็นต้องคืน Focus แล้ว เพราะเราไม่ได้ขโมยมาตั้งแต่แรก ---
        # force_set_focus(self.previous_focus_hwnd)

    def start_hide_animation(self):
        """Starts the fade-out animation."""
        if self.isVisible():
            self.animation.stop()
            self.hide_animation.start()

    def show_at(self, position, text):
        """
        Calculates size, positions the tooltip, and shows it with a fade-in animation.
        """
        if not text:
            self.start_hide_animation()
            return
        
        # 1. Determine max size based on screen geometry
        screen_geo = QApplication.desktop().availableGeometry(position)
        max_width = int(screen_geo.width() * 0.35)
        max_height = int(screen_geo.height() * 0.5)

        # 2. Set text and calculate ideal size
        self.label.setText(text)
        self.label.setMinimumSize(0, 0)
        self.label.setMaximumSize(16777215, 16777215)

        unconstrained_size = self.label.sizeHint()

        if unconstrained_size.width() > max_width:
            # If text is wider than max_width, constrain width and recalculate height
            self.label.setFixedWidth(max_width - 24 - 8) # max_width - (padding*2) - scrollbar
            ideal_height = self.label.sizeHint().height()
            final_width = max_width
            final_height = min(ideal_height + 24, max_height) # +24 for padding
        else:
            # If text is narrow, use its ideal size
            final_width = unconstrained_size.width() + 24
            final_height = unconstrained_size.height() + 24

        self.setFixedSize(final_width, final_height)

        # 3. Position the tooltip to avoid going off-screen
        final_pos = QPoint(position.x() + 15, position.y() + 20)

        if final_pos.x() + final_width > screen_geo.right():
            final_pos.setX(position.x() - final_width - 15)

        if final_pos.y() + final_height > screen_geo.bottom():
            final_pos.setY(position.y() - final_height - 15)

        if final_pos.x() < screen_geo.left():
            final_pos.setX(screen_geo.left())

        if final_pos.y() < screen_geo.top():
            final_pos.setY(screen_geo.top())

        self.move(final_pos)
        
        # 4. Start fade-in animation and manage focus
        self.animation.stop()
        self.show()
        self.animation.start()

        # Connect hide animation finished signal
        try:
            self.hide_animation.finished.disconnect()
        except TypeError:
            pass # Was not connected
        self.hide_animation.finished.connect(self.on_hide_finished)

        # --- [ลบออก] ไม่ต้องขโมย Focus อีกต่อไป ---