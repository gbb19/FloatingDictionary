"""
The custom PersistentToolTip widget with scrolling, animations, and focus management.
"""

from PyQt6.QtCore import QEvent, QPoint, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget


class CustomScrollArea(QScrollArea):
    """
    A QScrollArea subclass that sets the focus policy to NoFocus to prevent
    it from stealing focus from the user's active window.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def viewportEvent(self, a0: QEvent | None) -> bool:
        if a0 is None:
            return False
        return super().viewportEvent(a0)


class PersistentToolTip(QWidget):
    """
    A custom tooltip widget that can be controlled programmatically,
    supports scrolling, animations, and does not steal focus.
    """

    # Signal emitted when the tooltip is clicked, requesting dismissal.
    dismiss_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Set window flags to be a frameless, always-on-top popup.
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.scroll_area = CustomScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { border: none; background: #333; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #666; min-height: 20px; border-radius: 4px; }
        """)

        self.label = QLabel(self)
        self.label.setStyleSheet(
            "background-color: transparent; color: #f7f7f7; padding-right: 4px;"
        )
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop)

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

        self.hide()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        """Custom paint event to draw the rounded-corner background."""
        if a0 is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#222222"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

    def on_hide_finished(self):
        """Slot called when the hide animation finishes to hide the widget completely."""
        self.hide()

    def start_hide_animation(self):
        """Starts the fade-out animation if the widget is visible."""
        if self.isVisible():
            self.animation.stop()
            self.hide_animation.start()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        """When the tooltip is clicked, emit a signal to dismiss everything."""
        if a0 is None:
            return

        if a0.button() == Qt.MouseButton.LeftButton:
            self.dismiss_requested.emit()

    def show_at(self, position, text):
        """
        Calculates size, positions the tooltip, and shows it with a fade-in animation.
        """
        if not text:
            self.start_hide_animation()
            return

        # Step 1: Determine max size based on the available screen geometry.
        screen = QApplication.screenAt(position)
        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is None:
            return  # หรือ fallback geometry ที่คุณต้องการ

        screen_geo = screen.availableGeometry()

        max_width = int(screen_geo.width() * 0.35)
        max_height = int(screen_geo.height() * 0.6)  # Increased max height slightly

        # Step 2: Set text and calculate the ideal size for the content.
        self.label.setText(text)
        # Reset fixed width/height to allow sizeHint to calculate correctly
        self.label.setFixedWidth(0)
        self.label.setMinimumSize(0, 0)

        # Determine the width of the content label
        content_width = self.label.sizeHint().width()
        label_width = min(
            content_width, max_width - 24 - 8
        )  # max_width - h_padding - scrollbar
        self.label.setFixedWidth(label_width)

        # Determine the final size of the tooltip widget
        ideal_height = self.label.sizeHint().height()
        final_height = min(
            ideal_height + 24, max_height
        )  # Add vertical padding and cap at max_height

        final_width = (
            label_width + 24 + (8 if ideal_height > final_height else 0)
        )  # Add padding and scrollbar width if needed

        self.setFixedSize(final_width, final_height)

        # Step 3: Position the tooltip to avoid going off-screen.
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

        # Step 4: Start fade-in animation.
        self.animation.stop()
        self.show()
        self.animation.start()

        # Ensure the hide animation is connected to its slot.
        try:
            self.hide_animation.finished.disconnect()
        except TypeError:
            pass  # Was not connected
        self.hide_animation.finished.connect(self.on_hide_finished)
