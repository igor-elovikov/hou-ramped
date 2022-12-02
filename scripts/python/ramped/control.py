from __future__ import annotations

from typing import Any, Callable, Optional

from PySide2.QtCore import QPointF, QRectF, Qt
from PySide2.QtGui import QBrush, QColor, QPainter, QPen
from PySide2.QtWidgets import (QGraphicsItem, QGraphicsRectItem,
                               QGraphicsSceneHoverEvent,
                               QGraphicsSceneMouseEvent,
                               QStyleOptionGraphicsItem, QWidget)

from .logger import logger
from .settings import HOVERED_SCALE


class PointControl(QGraphicsItem):

    def __init__(self, position: QPointF, radius: float) -> None:
        super().__init__(None)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True)

        self.radius = radius

        radius *= HOVERED_SCALE

        self.bounding_rect = QRectF(-radius, -radius, radius * 2, radius * 2)
        
        self.brush = QBrush(QColor(0, 0, 0))
        self.pen = QPen(Qt.transparent)

        self.hovered_brush = QBrush(QColor(185, 134, 32))
        self.hovered_pen = QPen(QColor(0, 0, 0), 3)

        self.is_hovered = False

        self.current_brush = self.brush
        self.current_pen = self.pen
        self.current_radius = self.radius
        self.last_pos = position
        self.move_offset = QPointF(0, 0)
        self.setPos(self.last_pos)

        self.has_moved = False
        self.last_flags: QGraphicsItem.GraphicsItemFlags = self.flags()
        
        self.on_move: Callable[[PointControl, QPointF, QPointF], None] = lambda control, offset, pos: None
        self.on_start_move: Callable[[PointControl], None] = lambda control: None
        self.on_mouse_press: Callable[[PointControl], None] = lambda control: None
        self.on_mouse_release: Callable[[PointControl, bool], None] = lambda control, has_moved: None 
        self.on_hovered: Callable[[PointControl, bool], None] = lambda control, state: None
        
    def _set_hovered(self, is_hovered: bool):
        self.is_hovered = is_hovered
        if is_hovered:
            self.current_brush = self.hovered_brush
            self.current_pen = self.hovered_pen
            self.current_radius = self.radius * HOVERED_SCALE
        else:
            self.current_brush = self.brush
            self.current_pen = self.pen
            self.current_radius = self.radius

        self.on_hovered(self, is_hovered)

        self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:

        painter.setBrush(self.current_brush)
        painter.setPen(self.current_pen)
        painter.drawEllipse(QPointF(0, 0), self.current_radius, self.current_radius)

    def boundingRect(self) -> QRectF:
        return self.bounding_rect

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._set_hovered(True)
        logger.debug("Enter hover")

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._set_hovered(False)
        logger.debug("Leave hover")

    def set_pos_notification(self, enable: bool):
        self.last_flags = self.flags()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, enable)

    def restore_pos_notifications(self):
        self.setFlags(self.last_flags)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        logger.debug("Mouse press")
        self.set_pos_notification(True)
        self.on_mouse_press(self)
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        logger.debug("Mouse release")
        self.set_pos_notification(False)
        self.on_mouse_release(self, self.has_moved)
        self.has_moved = False
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.move_offset = event.lastScenePos() - event.scenePos()
        return super().mouseMoveEvent(event)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionChange):
            #logger.debug(f"Position changed: {value}")
            if not self.has_moved:
                self.on_start_move(self)
            self.on_move(self, self.move_offset, value)
            self.has_moved = True
        return super().itemChange(change, value)