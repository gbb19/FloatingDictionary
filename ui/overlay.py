"""
The Overlay widget for drawing highlight boxes on the screen.
"""
import pyautogui
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QPen

class Overlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, pyautogui.size().width, pyautogui.size().height)
        self.current_hovered_box = None

    def set_box(self, box):
        self.current_hovered_box = box
        self.update()

    def paintEvent(self, event):
        if not self.current_hovered_box:
            return
            
        painter = QPainter(self)
        pen = QPen(Qt.red, 2)
        painter.setPen(pen)
        rect = QRect(self.current_hovered_box['left'], self.current_hovered_box['top'], self.current_hovered_box['width'], self.current_hovered_box['height'])
        painter.drawRect(rect)