from __future__ import annotations

import math
from typing import Optional
import functools

from enum import Enum, auto

from PySide2.QtCore import QLineF, QPointF, Qt
from PySide2.QtGui import QColor, QPen, QBrush, QPainterPath
from PySide2.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsPathItem, QGraphicsView

from .control import PointControl, ControlStyle
from .logger import logger
from .settings import EPSILON, SHAPE_GRADIENT, SHAPE_STEPS, SHAPE_STEP, SHAPE_PEN

import hou

class KnotType(Enum):
    SMOOTH = auto()
    BROKEN = auto()
    CORNER = auto()

class KnotControl(Enum):
    IN = 0
    OUT = 1

def qpoint_length(point: QPointF) -> float:
    return math.sqrt(QPointF.dotProduct(point, point))

def qpoint_normalize(point: QPointF) -> None:
    length: float = qpoint_length(point)
    point.setX(point.x() / length)
    point.setY(point.y() / length)

class BezierKnot:

    def __init__(self, curve: BezierCurve, index: int, position: QPointF, in_offset: Optional[QPointF], out_offset: Optional[QPointF]) -> None:

        self.type: KnotType = KnotType.SMOOTH
        self.curve: BezierCurve = curve
        self.scene: QGraphicsScene = curve.scene

        self.limit_horizontally: bool = False
        self.limit_x: float = 0.0   

        self.handles_pen: QPen = QPen(QColor(218, 218, 217), 2)
        self.handles_pen.setStyle(Qt.DashLine)  
        self.handles_pen.setDashPattern([5, 4])   

        self.knot_point_control: PointControl = PointControl(position, 6, ControlStyle.SQUARE)
        self.knot_point_control.on_move = self.on_move_knot
        self.knot_point_control.on_mouse_release = self.finish_move_in_scene
        self.knot_point_control.on_hovered = self.on_hovered

        if in_offset is not None:
            self.in_point_control: PointControl = PointControl(position + in_offset, 5)
            self.in_point_control.on_move = functools.partial(self.on_move_control, KnotControl.IN)
            self.in_point_control.on_mouse_release = self.finish_move_in_scene
            self.in_point_control.on_hovered = self.on_hovered
            self.in_handle = QGraphicsLineItem(QLineF(position, in_offset))
            self.in_handle.setPen(self.handles_pen)  
            self.scene.addItem(self.in_handle)          
        else:
            self.in_point_control: PointControl = None
            self.in_handle: QGraphicsLineItem = None

        if out_offset is not None:
            self.out_point_control: PointControl = PointControl(position + out_offset, 5)
            self.out_point_control.on_move = functools.partial(self.on_move_control, KnotControl.OUT)
            self.out_point_control.on_mouse_release = self.finish_move_in_scene
            self.out_point_control.on_hovered = self.on_hovered
            self.out_handle = QGraphicsLineItem(QLineF(position, out_offset))
            self.out_handle.setPen(self.handles_pen)  
            self.scene.addItem(self.out_handle)          
        else:
            self.out_point_control: PointControl = None
            self.out_handle: QGraphicsLineItem = None
        
        self.scene.addItem(self.knot_point_control)
        self.scene.addItem(self.in_point_control)
        self.scene.addItem(self.out_point_control)
        
        self.index: int = index

        self.position: QPointF = position
        self.in_offset: QPointF = QPointF(0, 0) if in_offset is None else in_offset
        self.out_offset: QPointF = QPointF(0, 0) if out_offset is None else out_offset
        
        self.in_scene_position: QPointF = QPointF(0, 0)
        self.out_scene_position: QPointF = QPointF(0, 0)
        self.in_scene_offset: QPointF = QPointF(0, 0)
        self.out_scene_offset: QPointF = QPointF(0, 0)        
        self.scene_position: QPointF = QPointF(0, 0)

        self.clamp_by_line: bool = True

        self.set_scene_positions()

    @staticmethod
    def get_opposite_control(control: KnotControl) -> KnotControl:
        return KnotControl.IN if control is KnotControl.OUT else KnotControl.OUT

    def on_hovered(self, point_control: PointControl, state: bool) -> None:
        self.curve.hovered_control = point_control if state else None

    def map_to_scene(self, position: QPointF) -> QPointF:
        return self.curve.map_to_scene(position)

    def map_to_curve_space(self, position: QPointF) -> QPointF:
        return self.curve.map_to_curve_space(position)        

    def get_control(self, control: KnotControl) -> PointControl:
        return self.in_point_control if control is KnotControl.IN else self.out_point_control

    def get_control_scene_position(self, control: KnotControl) -> QPointF:
        control = self.get_control(control)
        return self.knot_point_control.scenePos() if control is None else control.scenePos()     

    def get_control_offset(self, control: KnotControl) -> QPointF:
        return self.in_offset if control is KnotControl.IN else self.out_offset

    def get_control_scene_offset(self, control: KnotControl) -> QPointF:
        return self.in_scene_offset if control is KnotControl.IN else self.out_scene_offset        

    def set_knot_scene_position(self, position: QPointF) -> None:
        self.knot_point_control.setPos(position)
        self.scene_position = position

    def set_in_control_scene_position(self, position: QPointF, sync_point_control: bool = True) -> None:
        if self.in_point_control is None: 
            self.in_scene_position = self.position
            return
        if sync_point_control:
            self.in_point_control.set_pos_notification(False)
            self.in_point_control.setPos(position)
            self.scene.update()
            self.in_point_control.restore_pos_notifications()
        self.in_scene_position = position
        
        if self.in_handle is not None:
            self.in_handle.setLine(QLineF(self.scene_position, self.in_scene_position))

    def set_out_control_scene_position(self, position: QPointF, sync_point_control: bool = True) -> None:
        if self.out_point_control is None:
            self.out_scene_position = self.position
            return
        if sync_point_control:
            self.out_point_control.set_pos_notification(False)
            self.out_point_control.setPos(position)
            self.out_point_control.restore_pos_notifications()
        self.out_scene_position = position

        if self.out_handle is not None:
            self.out_handle.setLine(QLineF(self.scene_position, self.out_scene_position))

    def set_control_scene_position(self, control: KnotControl, position: QPointF, sync_point_control: bool = True) -> None:
        if control is KnotControl.IN:
            self.set_in_control_scene_position(position, sync_point_control)
        else:
            self.set_out_control_scene_position(position, sync_point_control)

    def map_knot_scene_position(self) -> None:
        self.set_knot_scene_position(self.map_to_scene(self.position))

    def map_in_control_scene_position(self) -> None:
        self.set_in_control_scene_position(self.map_to_scene(self.position + self.in_offset))

    def map_out_control_scene_position(self) -> None:
        self.set_out_control_scene_position(self.map_to_scene(self.position + self.out_offset))

    def remap_all_from_scene_positions(self) -> None:
        self.position = self.map_to_curve_space(self.scene_position)
        self.in_offset = self.map_to_curve_space(self.in_scene_offset)
        self.out_offset = self.map_to_curve_space(self.out_scene_offset)

    def remap_all_from_controls_positions(self) -> None:
        knot_position = self.scene_position
        self.position = self.map_to_curve_space(knot_position)
        self.in_offset = self.map_to_curve_space(self.in_scene_position - knot_position)
        self.out_offset = self.map_to_curve_space(self.out_scene_position - knot_position)        

    def sync_scene_positions(self) -> None:
        self.scene_position = self.knot_point_control.scenePos()
        self.in_scene_position = self.in_point_control.scenePos() if self.in_point_control is not None else self.scene_position
        self.out_scene_position = self.out_point_control.scenePos() if self.out_point_control is not None else self.scene_position

    def sync_scene_offsets(self) -> None:
        self.in_scene_offset = self.in_scene_position - self.scene_position
        self.out_scene_offset = self.out_scene_position - self.scene_position

    def set_control_scene_offset(self, control: KnotControl, offset: QPointF) -> None:
        if control is KnotControl.IN:
            self.in_scene_offset = offset
        else:
            self.out_scene_offset = offset


    def sync_control_scene_offset(self, control: KnotControl) -> None:
        if control is KnotControl.IN:
            self.in_scene_offset = self.in_scene_position - self.scene_position
        else:
            self.out_scene_offset = self.out_scene_position - self.scene_position
    
    def set_scene_positions(self) -> None:
        self.map_knot_scene_position()
        self.map_in_control_scene_position()
        self.map_out_control_scene_position()
        self.sync_scene_offsets()
       
    def move_out_control(self, knot_position: QPointF) -> QPointF:
        next_knot = self.curve.next_knot(self)

        right_limit = self.curve.scene_width
        if next_knot is not None and next_knot.in_point_control is not None:
            right_limit = next_knot.in_point_control.scenePos().x()

        factor: float = 1.0
        desired_position: QPointF = knot_position + self.out_scene_offset

        if desired_position.x() > right_limit:
            if self.clamp_by_line:
                factor = (right_limit - knot_position.x()) / self.out_scene_offset.x()
                desired_position = knot_position + self.out_scene_offset * factor
                desired_position.setX(desired_position.x() - EPSILON)
            else:
                desired_position.setX(right_limit - EPSILON)

        left_limit = self.scene_position.x()
        if desired_position.x() < left_limit:
            desired_position.setX(left_limit + EPSILON)

        self.set_out_control_scene_position(desired_position)

        return desired_position

    def move_in_control(self, knot_position: QPointF) -> QPointF:
        prev_knot = self.curve.prev_knot(self)
        left_limit = 0.0
        if prev_knot is not None and prev_knot.out_point_control is not None:
            left_limit = prev_knot.out_point_control.scenePos().x()

        factor = 1.0
        desired_position: QPointF = knot_position + self.in_scene_offset

        if desired_position.x() < left_limit:
            if self.clamp_by_line:
                factor = -(knot_position.x() - left_limit) / self.in_scene_offset.x()
                desired_position = knot_position + self.in_scene_offset * factor
                desired_position.setX(desired_position.x() + EPSILON)
            else:
                desired_position.setX(left_limit + EPSILON)

        right_limit = self.scene_position.x()
        if desired_position.x() > right_limit:
            desired_position.setX(right_limit - EPSILON)                

        self.set_in_control_scene_position(desired_position)   

        return desired_position

    def move_control(self, control: KnotControl, knot_position: QPointF) -> QPointF:
        if control is KnotControl.IN:
            return self.move_in_control(knot_position)
        else:
            return self.move_out_control(knot_position)

    def on_move_knot(self, control: PointControl, offset: QPointF, position: QPointF) -> None:
        self.scene_position = position

        next_knot = self.curve.next_knot(self)
        right_limit = self.curve.scene_width
        
        if next_knot is not None and next_knot.in_point_control is not None:
            right_limit = next_knot.in_point_control.scenePos().x()

        prev_knot = self.curve.prev_knot(self)
        left_limit = 0.0

        if prev_knot is not None and prev_knot.out_point_control is not None:
            left_limit = prev_knot.out_point_control.scenePos().x()

        out_of_limits = False

        if position.x() > right_limit:
            out_of_limits = True
            position.setX(right_limit - EPSILON)

        if position.x() < left_limit:
            out_of_limits = True
            position.setX(left_limit + EPSILON)

        if out_of_limits:
            self.knot_point_control.set_pos_notification(False)
            self.set_knot_scene_position(position)
            self.knot_point_control.set_pos_notification(True)

        self.move_out_control(position)
        self.move_in_control(position)

        self._on_points_changed()
    
    def on_move_control(self, control: KnotControl, point_control: PointControl, offset: QPointF, position: QPointF) -> None:

        self.set_control_scene_position(control, position, sync_point_control=False)
        self.sync_control_scene_offset(control)
        moved_position = self.move_control(control, self.scene_position)
        self.sync_control_scene_offset(control)

        position.setX(moved_position.x())
        position.setY(moved_position.y())

        opposite_control = self.get_opposite_control(control)
        offset = self.get_control_scene_offset(control)
        opposite_offset = self.get_control_scene_offset(opposite_control)

        opposite_point_control = self.get_control(opposite_control)

        if opposite_point_control is None or self.type is not KnotType.SMOOTH:
            self._on_points_changed()
            return

        length = qpoint_length(opposite_offset)
        dir = offset * -1.0
        qpoint_normalize(dir)

        self.set_control_scene_offset(opposite_control, dir * length)
        self.move_control(opposite_control, self.scene_position)

        self._on_points_changed()

    def finish_move_in_scene(self, control: PointControl, has_moved: bool) -> None:

        if has_moved:
            self.sync_scene_offsets()
            self.remap_all_from_scene_positions()
            self.curve.export_to_parm()
            logger.debug("Finish moving")

        if control is self.out_point_control or control is self.in_point_control:
            logger.debug("Finish moving handle")


    def _on_points_changed(self):
        self.remap_all_from_controls_positions()
        self.curve.sync_ramp()
        self.curve.set_ramp_shape()


class BezierCurve:

    def __init__(self, scene: QGraphicsScene) -> None:

        self.knots: list[BezierKnot] = []
        self.bottom_border = 0.0
        self.top_border = 1.0
        self.vertical_ratio = 1.0

        self.parm: hou.Parm = None
        self.ramp: hou.Ramp = None
        self.scene: QGraphicsScene = scene

        self.ramp_shape: QGraphicsPathItem = QGraphicsPathItem()
        self.ramp_shape.setBrush(QBrush(SHAPE_GRADIENT))
        self.ramp_shape.setPath(QPainterPath())
        self.ramp_shape.setPen(SHAPE_PEN)
        
        self.scene.addItem(self.ramp_shape)

        self.scene_width = 0
        self.scene_height = 0

        self.min_y = 0.0
        self.max_y = 1.0

        self.hovered_control: PointControl = None

    def _get_ramp(self) -> hou.Ramp:
        num_keys = len(self.knots) * 3 - 2

        basis = [hou.rampBasis.Bezier] * num_keys
        keys = []
        values = []

        self.min_y = 0.0
        self.max_y = 1.0

        for knot in self.knots:
            if knot.in_point_control is not None:
                pos = knot.position + knot.in_offset
                keys.append(pos.x())
                values.append(pos.y())
                if pos.y() < self.min_y:
                    self.min_y = pos.y()
                if pos.y() > self.max_y:
                    self.max_y = pos.y()

            keys.append(knot.position.x())
            values.append(knot.position.y())
            if knot.position.y() < self.min_y:
                self.min_y = knot.position.y()
            if knot.position.y() > self.max_y:
                self.max_y = knot.position.y()            

            if knot.out_point_control is not None:
                pos = knot.position + knot.out_offset
                keys.append(pos.x())
                values.append(pos.y())
                if pos.y() < self.min_y:
                    self.min_y = pos.y()
                if pos.y() > self.max_y:
                    self.max_y = pos.y()                

        return hou.Ramp(basis, keys, values)

    def map_to_scene(self, position: QPointF) -> QPointF:
        return QPointF(position.x() * self.scene_width, position.y() * self.scene_height / self.vertical_ratio )

    def map_to_curve_space(self, position: QPointF) -> QPointF:
        return QPointF(position.x() / self.scene_width, position.y() / self.scene_height * self.vertical_ratio)         

    def set_borders(self, bottom: float, top: float):
        self.bottom_border = bottom
        self.top_border = top
        self.vertical_ratio = top - bottom
        logger.debug(f"Set curve borders: {bottom}->{top} ratio: {self.vertical_ratio}")

    def next_knot(self, knot: BezierKnot) -> Optional[BezierKnot]:
        if (knot.index < (len(self.knots) - 1)):
            return self.knots[knot.index + 1]
        return None

    def prev_knot(self, knot: BezierKnot) -> Optional[BezierKnot]:
        if (knot.index > 0):
            return self.knots[knot.index - 1]
        return None

    def add_knot(self, position: QPointF, in_offset: Optional[QPointF], out_offset: Optional[QPointF], insert_index: int = -1) -> None:
        index = len(self.knots)
        logger.debug(f"Add knot: {position} in: {in_offset} out: {out_offset} index: {index}")
        knot = BezierKnot(self, index, position, in_offset, out_offset)
        if insert_index < 0:
            self.knots.append(knot)
        else:
            self.knots.insert(insert_index, knot)
            self.reindex_knots()

    def reindex_knots(self) -> None:
        for i, knot in enumerate(self.knots):
            knot.index = i
        
    def reset_scene_positions(self) -> None:
        for knot in self.knots:
            knot.set_scene_positions()

    def ramp_scene_position(self, pos: float) -> QPointF:
        return self.map_to_scene(QPointF(pos, self.ramp.lookup(pos)))

    def sync_ramp(self):
        self.ramp = self._get_ramp()

    def set_ramp_shape(self, ramp: Optional[hou.Ramp] = None) -> None:

        if ramp is None: 
            ramp = self.ramp

        self.ramp_shape.prepareGeometryChange()
        
        path: QPainterPath = QPainterPath()
        path.moveTo(-100.0, 0)

        for i in range(SHAPE_STEPS + 1):
            pos = i * SHAPE_STEP
            value = ramp.lookup(pos)
            path_position = self.map_to_scene(QPointF(pos, value))
            path.lineTo(path_position)

        path.lineTo(self.scene_width + 100.0, 0)

        gradient_limit = max(math.fabs(self.min_y), math.fabs(self.max_y))

        SHAPE_GRADIENT.setStart(QPointF(0, 0))
        SHAPE_GRADIENT.setFinalStop(QPointF(0, gradient_limit * self.scene_height / self.vertical_ratio))
        self.ramp_shape.setPath(path)
        self.ramp_shape.setBrush(QBrush(SHAPE_GRADIENT))

        self.ramp_shape.update()

        self.scene.update()

    def knot_indicies_from_pos(self, pos: float) -> tuple[int, int]:
        for i in range(len(self.knots) - 1):
            left = self.knots[i].position.x()
            right = self.knots[i+1].position.x()
            print(f"i: {i} left: {left} right: {right}")
            if left <= pos and right > pos:
                return (i, i+1)
        return (-1, -1)

    def add_knot_to_curve(self, pos: float) -> None:
        left, right = self.knot_indicies_from_pos(pos)
        print(f"lr: {left} {right}")
        if left < 0:
            return

        left_knot = self.knots[left]
        right_knot = self.knots[right]

        ratio = (pos - left_knot.position.x())/(right_knot.position.x() - left_knot.position.x())

        knot_pos = QPointF(pos, self.ramp.lookup(pos))

        left_knot.out_offset *= ratio
        right_knot.in_offset *= (1.0 - ratio)

        left_control_pos = left_knot.position + left_knot.out_offset
        right_control_pos = right_knot.position + right_knot.in_offset

        gradient = right_control_pos - left_control_pos

        knot_in = gradient * (-ratio) * 0.5
        knot_out = gradient * (1.0 - ratio) * 0.5

        self.add_knot(knot_pos, knot_in, knot_out, right)

        self.reset_scene_positions()
        self.sync_ramp()
        self.set_ramp_shape()
        


    def export_to_parm(self):
        self.parm.set(self.ramp)
        #self.set_ramp_shape(ramp)             
