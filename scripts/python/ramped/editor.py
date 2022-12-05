from __future__ import annotations

from typing import Callable

import hou
from PySide2.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PySide2.QtGui import (QBrush, QColor, QContextMenuEvent, QMouseEvent,
                           QPainter, QPen, QResizeEvent, QFocusEvent)
from PySide2.QtWidgets import QGraphicsScene, QGraphicsView, QWidget, QMenu, QGraphicsEllipseItem

from .curve import BezierCurve
from .logger import logger
from .settings import ADD_MARKER_RADIUS, ADD_MARKER_COLOR


class ContextMenu(QMenu):

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setAttribute(Qt.WA_NoMouseReplay)
        super().mousePressEvent(event)
                
    

class RampEditor(QGraphicsView):

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.setRenderHint(QPainter.Antialiasing)

        self.parm: hou.Parm = None
        self.editor_scene = QGraphicsScene(self)
        self.curve = BezierCurve(self.editor_scene)
        
        self.setBackgroundBrush(QBrush(QColor(55, 54, 54)))
        self.setScene(self.editor_scene)
        self.setSceneRect(0, 0, parent.width(), parent.height())
        self.scale(1, -1)

        self.add_marker = QGraphicsEllipseItem(0, 0, ADD_MARKER_RADIUS * 2, ADD_MARKER_RADIUS * 2)
        self.add_marker.setBrush(QBrush(QColor(*ADD_MARKER_COLOR)))
        self.add_marker.setPen(QPen(Qt.transparent))
        self.editor_scene.addItem(self.add_marker)

        self.grid_horizontal_step = 0.1
        self.grid_vertical_step = 0.1

        self.bottom_border = 0.0
        self.top_border = 1.0

        self.grid_pen = QPen(QColor(72, 72, 73), 0)

        self.on_borders_changed: Callable[[float, float], None] = lambda bottom, top: None

    def setup_parm(self, parm: hou.Parm):
        self.parm = parm
        self.curve.parm = parm
    
    def load_from_ramp(self, ramp: hou.Ramp) -> None:

        keys: list[float] = ramp.keys()
        values: list[float] = ramp.values()

        num_keys = len(keys)
        num_knots = 2 + (num_keys - 4) // 3

        logger.debug(f"Ramp num knots: {num_knots}")

        for i in range(num_knots):

            if i == 0:
                knot_pos = QPointF(keys[0], values[0])
                out_pos = QPointF(keys[1], values[1])
                self.curve.add_knot(knot_pos, None, out_pos - knot_pos)
                continue

            if i == (num_knots - 1):
                index = (num_knots - 1) * 3
                knot_pos = QPointF(keys[index], values[index])
                in_pos = QPointF(keys[index-1], values[index-1])
                self.curve.add_knot(knot_pos, in_pos - knot_pos, None)
                continue

            index = i * 3
            knot_pos = QPointF(keys[index], values[index])
            in_pos = QPointF(keys[index-1], values[index-1])
            out_pos = QPointF(keys[index+1], values[index+1])
            self.curve.add_knot(knot_pos, in_pos - knot_pos, out_pos - knot_pos)

        self.curve.sync_ramp()  
        self.fit_to_viewport()       
     
    def resizeEvent(self, event: QResizeEvent):
        
        size: QSize = event.size()
        logger.debug(f"Resize: [{size.width()}x{size.height()}]")
        self.curve.scene_width = size.width()
        self.curve.scene_height = size.height()        

        self.setSceneRect(0, self.bottom_border * self.curve.scene_height / self.curve.vertical_ratio, self.curve.scene_width, self.curve.scene_height)

        self.curve.reset_scene_positions()
        self.curve.set_ramp_shape()

        super().resizeEvent(event)

        #self.fitInView(0, 0, size.width(), size.height())

    def set_borders(self, bottom: float, top: float):
        
        self.bottom_border = bottom
        self.top_border = top
        self.curve.set_borders(bottom, top)        
        
        self.setSceneRect(0, self.bottom_border * self.curve.scene_height / self.curve.vertical_ratio, self.curve.scene_width, self.curve.scene_height)

        self.curve.reset_scene_positions()
        self.curve.set_ramp_shape()
        self.update()

        self.on_borders_changed(bottom, top)

    def fit_to_viewport(self):
        self.set_borders(self.curve.min_y, self.curve.max_y)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.curve.ramp is not None:
            if self.curve.hovered_control is None:
                self.add_marker.setVisible(True)
                scene_pos = self.mapToScene(event.pos())
                self.add_marker.setPos(self.curve.ramp_scene_position(scene_pos.x() / self.curve.scene_width) - QPointF(ADD_MARKER_RADIUS, ADD_MARKER_RADIUS))
            else:
                self.add_marker.setVisible(False)
        return super().mouseMoveEvent(event)   

    def mousePressEvent(self, event: QMouseEvent) -> None:
        logger.debug(f"Editor mouse event: {event.source()} {event.isAccepted()} {event.flags()}")
        if event.buttons() == Qt.LeftButton and self.curve.hovered_control is None:
            scene_pos = self.mapToScene(event.pos())
            ramp_pos = scene_pos.x() / self.curve.scene_width
            self.curve.add_knot_to_curve(ramp_pos)
            
        return super().mousePressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        logger.debug("Focus In")
        return super().focusInEvent(event)     

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = ContextMenu(self)
        menu.setStyleSheet(hou.qt.styleSheet())
        
        menu.addAction("Set")
        menu.addAction("Get")
        menu.addSeparator()
        menu.addAction("Test")
        menu.popup(event.globalPos())
        


    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)

        x = 0.0
        y = 0.0

        width = self.width()
        height = self.height()

        lines = []

        while x < 1.0:
            line_x = x * width
            lines.append(QLineF(line_x, 0.0, line_x, height))
            x += self.grid_horizontal_step

        while y < self.top_border:
            line_y = y * height
            lines.append(QLineF(0.0, line_y, width, line_y))
            y += self.grid_vertical_step 

        y = -self.grid_vertical_step

        while y > self.bottom_border:           
            line_y = y * height
            lines.append(QLineF(0.0, line_y, width, line_y))
            y -= self.grid_vertical_step 

        painter.setPen(self.grid_pen)
        painter.drawLines(lines)      