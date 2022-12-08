from __future__ import annotations

from typing import Callable, Optional

import hdefereval
import hou
from PySide2.QtCore import QLineF, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide2.QtGui import (QBrush, QColor, QContextMenuEvent, QFocusEvent,
                           QKeyEvent, QMouseEvent, QPainter, QPen,
                           QResizeEvent)
from PySide2.QtWidgets import (QFrame, QGraphicsEllipseItem, QGraphicsScene,
                               QGraphicsView, QLabel, QMenu, QPushButton,
                               QVBoxLayout, QWidget, QSizePolicy)

from .curve import BezierCurve
from .logger import logger
from .settings import (ADD_MARKER_COLOR, ADD_MARKER_RADIUS, GRID_FONT,
                       SNAPPING_DISTANCE)


class ContextMenu(QMenu):

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setAttribute(Qt.WA_NoMouseReplay)
        super().mousePressEvent(event)

class BorderLabel(QLabel):

    double_clicked = Signal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.double_clicked.emit(self.mapToGlobal(self.pos()))
        return super().mouseDoubleClickEvent(event)

class EditorMessage(QFrame):

    def __init__(self, parent: QGraphicsView | None = None) -> None:
        super().__init__(parent)

        self.setStyleSheet("background-color: #131313")

        self.setLayout(QVBoxLayout())
        self.message = QLabel()
        self.message.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.message.setText("Message Text Message Text<br>Message Text")
        #self.message.setFixedWidth(400)

        self.button = QPushButton()
        self.button.setText("Button")
        #self.button.setMaximumWidth(200)

        self.layout().setSpacing(4)
        self.layout().addWidget(self.message)
        self.layout().addWidget(self.button)
        self.layout().setAlignment(self.button, Qt.AlignHCenter)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)