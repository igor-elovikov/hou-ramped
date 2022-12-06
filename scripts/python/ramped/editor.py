from __future__ import annotations

from typing import Callable

import hou
import hdefereval

from PySide2.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PySide2.QtGui import (QBrush, QColor, QContextMenuEvent, QMouseEvent,
                           QPainter, QPen, QResizeEvent, QFocusEvent, QKeyEvent)
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

        self.parm: hou.Parm | None = None
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

        self.scene_bottom_border = 0.0
        self.scene_top_border = 0.0

        self.grid_pen = QPen(QColor(72, 72, 73), 0)

        self.on_borders_changed: Callable[[float, float], None] = lambda bottom, top: None
        self.changed_flag = False

    def attach_parm(self, parm: hou.Parm):
        self.remove_callbacks()
        self.parm = parm
        self.curve.parm = parm
        self.load_from_ramp(parm.evalAsRamp())
        node: hou.Node = self.parm.node()
        node.addEventCallback((hou.nodeEventType.ParmTupleChanged, ), self.on_parm_changed)
        

    def on_parm_changed(self, **kwargs) -> None:
        is_ramp_parm = False
        parm_tuple: hou.ParmTuple = kwargs["parm_tuple"]
        parm: hou.Parm = parm_tuple[0]
        if parm.isMultiParmInstance():
            parent: hou.Parm = parm.parentMultiParm()
            if parent.name() == self.parm.name():
                is_ramp_parm = True
        if parm.isMultiParmParent():
            if parm.name() == self.parm.name():
                is_ramp_parm = True

        if not is_ramp_parm:
            return

        if not self.changed_flag:
            self.changed_flag = True
            hdefereval.execute_deferred(self.reset_changed_flag)
        else:
            return


    
    def reset_changed_flag(self):
        logger.debug("Reset changed flag")
        self.curve.on_parm_changed()
        self.changed_flag = False

    
    def remove_callbacks(self):
        if self.parm is not None:
            logger.debug("Callbacks removed")
            node: hou.Node = self.parm.node()
            try:
                node.removeEventCallback((hou.nodeEventType.ParmTupleChanged, ), self.on_parm_changed)   
            except Exception as e:
                logger.warning(f"Can't remove callback: {e}")

    def on_close(self) -> None:
        logger.debug("Editor closed")
        self.remove_callbacks()

    
    def load_from_ramp(self, ramp: hou.Ramp) -> None:

        self.curve.load_from_ramp(ramp)  
        self.fit_to_viewport()

    def calculate_scene_borders(self) -> None:
        self.scene_bottom_border = self.bottom_border * self.curve.scene_height / self.curve.vertical_ratio
        self.scene_top_border = self.top_border * self.curve.scene_height / self.curve.vertical_ratio

    def set_scene_rect(self) -> None:
        self.setSceneRect(0, self.scene_bottom_border, self.curve.scene_width, self.curve.scene_height)

    
    def update_scene_rect(self) -> None:
        self.calculate_scene_borders()     
        self.set_scene_rect()
        self.curve.reset_scene_positions()
        self.curve.set_ramp_shape()
     
    def resizeEvent(self, event: QResizeEvent):
        
        size: QSize = event.size()
        logger.debug(f"Resize: [{size.width()}x{size.height()}]")
        self.curve.scene_width = size.width()
        self.curve.scene_height = size.height()

        self.update_scene_rect()

        super().resizeEvent(event)

        #self.fitInView(0, 0, size.width(), size.height())

    def set_borders(self, bottom: float, top: float):
        
        self.bottom_border = bottom
        self.top_border = top
        self.curve.set_borders(bottom, top)

        self.update_scene_rect()
        
        self.update()

        self.on_borders_changed(bottom, top)

    def fit_to_viewport(self):
        self.set_borders(self.curve.min_y, self.curve.max_y)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.curve.ramp is not None:
            if self.curve.hovered_control is None:
                scene_pos = self.mapToScene(event.pos())
                curve_pos: QPointF = self.curve.ramp_scene_position(scene_pos.x() / self.curve.scene_width)
                diff = curve_pos - scene_pos
                if diff.manhattanLength() < ADD_MARKER_RADIUS * 2.0:
                    self.add_marker.setVisible(True)
                    self.add_marker.setPos(curve_pos - QPointF(ADD_MARKER_RADIUS, ADD_MARKER_RADIUS))
                else:
                    self.add_marker.setVisible(False)
            else:
                self.add_marker.setVisible(False)
        return super().mouseMoveEvent(event)   

    def mousePressEvent(self, event: QMouseEvent) -> None:
        logger.debug(f"Editor mouse event: {event.source()} {event.isAccepted()} {event.flags()}")
        if event.buttons() == Qt.LeftButton and self.curve.hovered_control is None and self.add_marker.isVisible():
            scene_pos = self.mapToScene(event.pos())
            ramp_pos = scene_pos.x() / self.curve.scene_width
            self.curve.add_knot_to_curve(ramp_pos)

        if self.curve.hovered_control is None:
            self.curve.clear_selection()
            
        return super().mousePressEvent(event)  

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            logger.debug("Perform Houdini Undo")
            hou.undos.performUndo()
        return super().keyPressEvent(event)

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
            lines.append(QLineF(line_x, self.scene_bottom_border, line_x, self.scene_top_border))
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