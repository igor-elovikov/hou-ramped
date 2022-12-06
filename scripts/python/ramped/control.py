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
from enum import Enum, auto

class ControlStyle(Enum):
    CIRCLE = auto()
    SQUARE = auto() 


class PointControl(QGraphicsItem):

    def __init__(self, position: QPointF, radius: float, style: ControlStyle = ControlStyle.CIRCLE) -> None:
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
        self.is_selected = False
        self.is_selectable = False

        self.current_brush = self.brush
        self.current_pen = self.pen
        self.current_radius = self.radius
        self.last_pos = position
        self.move_offset = QPointF(0, 0)
        self.setPos(self.last_pos)
        self.style = style

        self.has_moved = False
        self.last_flags: QGraphicsItem.GraphicsItemFlags = self.flags()
        
        self.on_move: Callable[[PointControl, QPointF, QPointF], None] = lambda control, offset, pos: None
        self.on_start_move: Callable[[PointControl], None] = lambda control: None
        self.on_mouse_release: Callable[[PointControl, bool], None] = lambda control, has_moved: None 
        self.on_hovered: Callable[[PointControl, bool], None] = lambda control, state: None
        self.on_double_click: Callable[[PointControl], None] = lambda control: None
        self.on_selected: Callable[[PointControl], None] = lambda control: None

    def _set_active_paint(self) -> None:
        self.current_brush = self.hovered_brush
        self.current_pen = self.hovered_pen
        self.current_radius = self.radius * HOVERED_SCALE

    def _set_normal_paint(self) -> None:
        self.current_brush = self.brush
        self.current_pen = self.pen
        self.current_radius = self.radius             


    def _set_hovered(self, is_hovered: bool) -> None:
        self.is_hovered = is_hovered
        if is_hovered:
            self._set_active_paint()
        elif not self.is_selected:
            self._set_normal_paint()

        self.on_hovered(self, is_hovered)
        self.update()

    def set_selected(self, is_selected: bool) -> None:
        if not self.is_selectable:
            self.is_selected = False
            return
        self.is_selected = is_selected
        if is_selected:
            self._set_active_paint()
        elif not self.is_hovered:
            self._set_normal_paint()
            self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:

        painter.setBrush(self.current_brush)
        painter.setPen(self.current_pen)
        if self.style is ControlStyle.CIRCLE:
            painter.drawEllipse(QPointF(0, 0), self.current_radius, self.current_radius)
        else:
            rect_size = self.current_radius * 2
            painter.drawRect(-self.current_radius, -self.current_radius, rect_size, rect_size)

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
        if not self.is_selected:
            self.set_selected(True)
        self.on_selected(self)
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

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.on_double_click(self)
        return super().mouseDoubleClickEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionChange):
            if not self.has_moved:
                self.on_start_move(self)
            self.on_move(self, self.move_offset, value)
            self.has_moved = True
        return super().itemChange(change, value)