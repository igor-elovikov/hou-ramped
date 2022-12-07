from __future__ import annotations

import math
from typing import Optional, Callable
import functools

from enum import Enum, auto

from PySide2.QtCore import QLineF, QPointF, Qt
from PySide2.QtGui import QColor, QPen, QBrush, QPainterPath, QGuiApplication
from PySide2.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsPathItem, QGraphicsView

from .control import PointControl, ControlStyle
from .logger import logger
from .settings import EPSILON, SHAPE_GRADIENT, SHAPE_STEPS, SHAPE_STEP, SHAPE_PEN, SNAPPING_DISTANCE

import hou

ONE_THIRD = 0.3333333333333
TWO_THIRDS = 0.6666666666666

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

def qpoint_normalized(point: QPointF) -> QPointF:
    length: float = qpoint_length(point)
    return point / length 

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
        self.knot_point_control.on_double_click = self.on_double_click
        self.knot_point_control.on_selected = self.on_selected
        self.knot_point_control.is_selectable = True

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
        
        self.scene.addItem(self.in_point_control)
        self.scene.addItem(self.out_point_control)
        self.scene.addItem(self.knot_point_control)
        
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

        self.is_selected = False
        self.is_clicked_while_selected = False

        self.set_scene_positions()

    @staticmethod
    def get_opposite_control(control: KnotControl) -> KnotControl:
        return KnotControl.IN if control is KnotControl.OUT else KnotControl.OUT

    def set_all_handles_visibility(self, visible: bool) -> None:
        if self.in_handle is not None:
            self.in_handle.setVisible(visible)
        if self.out_handle is not None:
            self.out_handle.setVisible(visible)
        if self.in_point_control is not None:
            self.in_point_control.setVisible(visible)
        if self.out_point_control is not None:
            self.out_point_control.setVisible(visible)

    def set_type(self, knot_type: KnotType) -> None:
        if knot_type is KnotType.SMOOTH and self.type is not KnotType.SMOOTH:
            prev_knot = self.curve.prev_knot(self)
            next_knot = self.curve.next_knot(self)

            prev_knot_pos = prev_knot.position if prev_knot is not None else self.position
            next_knot_pos = next_knot.position if next_knot is not None else self.position

            gradient = next_knot_pos - prev_knot_pos
            gradient = gradient / gradient.x()
            
            #FIXME: can be improved
            if prev_knot is not None:
                prev_out_pos = prev_knot.position + prev_knot.out_offset
                ratio = (0.5 * (self.position.x() - prev_out_pos.x()) ) 
                self.in_offset = -gradient * ratio 

            if next_knot is not None:
                next_in_pos = next_knot.position + next_knot.in_offset
                ratio = ((0.5 * (next_in_pos.x() - self.position.x()) ))
                self.out_offset = gradient * ratio

            self.set_all_handles_visibility(True)
            self.set_scene_positions()

            self.type = KnotType.SMOOTH

            return

        if knot_type is KnotType.CORNER:
            self.set_all_handles_visibility(False)
            self.in_offset = QPointF(0.0, 0.0)
            self.out_offset = QPointF(0.0, 0.0)
            self.set_scene_positions()

            self.type = KnotType.CORNER

            return

    def on_selected(self, point_control: PointControl) -> None:
        self.is_clicked_while_selected = False
        keyboard_modifiers = QGuiApplication.keyboardModifiers()
        if (keyboard_modifiers & Qt.ShiftModifier):
            if not self.is_selected:
                self.curve.add_to_selection(self)
            elif len(self.curve.selection) > 1:
                self.curve.remove_from_selection(self)
        else:
            if not self.is_selected:
                self.curve.select_knot(self)
            else:
                self.is_clicked_while_selected = True


    def on_double_click(self, point_control: PointControl) -> None:
        if self.type is KnotType.SMOOTH or self.type is KnotType.BROKEN:
            self.set_type(KnotType.CORNER)
            self._on_points_changed()
            return

        if self.type is KnotType.CORNER:
            self.set_type(KnotType.SMOOTH)
            self._on_points_changed()
            return

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

        if desired_position.x() >= right_limit:
            if self.clamp_by_line:
                factor = (right_limit - knot_position.x()) / self.out_scene_offset.x()
                desired_position = knot_position + self.out_scene_offset * factor
                desired_position.setX(desired_position.x() - EPSILON)
            else:
                desired_position.setX(right_limit - EPSILON)

        left_limit = self.scene_position.x()
        if desired_position.x() <= left_limit:
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

        if desired_position.x() <= left_limit:
            if self.clamp_by_line:
                factor = -(knot_position.x() - left_limit) / self.in_scene_offset.x()
                desired_position = knot_position + self.in_scene_offset * factor
                desired_position.setX(desired_position.x() + EPSILON)
            else:
                desired_position.setX(left_limit + EPSILON)

        right_limit = self.scene_position.x()
        if desired_position.x() >= right_limit:
            logger.debug("Exceed right limit")
            desired_position.setX(right_limit - EPSILON)                

        self.set_in_control_scene_position(desired_position)   

        return desired_position

    def move_control(self, control: KnotControl, knot_position: QPointF) -> QPointF:
        if control is KnotControl.IN:
            return self.move_in_control(knot_position)
        else:
            return self.move_out_control(knot_position)

    def move_in_scene(self, position: QPointF) -> None:

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

        if position.x() >= right_limit:
            out_of_limits = True
            position.setX(right_limit - EPSILON)

        if position.x() <= left_limit:
            out_of_limits = True
            position.setX(left_limit + EPSILON)

        if out_of_limits:
            self.knot_point_control.set_pos_notification(False)
            self.set_knot_scene_position(position)
            self.knot_point_control.restore_pos_notifications()

        self.move_out_control(position)
        self.move_in_control(position)        

    def on_move_knot(self, control: PointControl, offset: QPointF, position: QPointF) -> None:
        self.curve.snap_position(position)
        prev_position = self.scene_position
        self.move_in_scene(position)
        offset = position - prev_position
        if len(self.curve.selection) > 1:
            for knot in self.curve.selection:
                if knot is not self:
                    knot_pos = knot.scene_position + offset
                    knot.move_in_scene(knot.scene_position + offset)
                    knot.knot_point_control.setPos(knot_pos)
                    knot.remap_all_from_controls_positions()

        self._on_points_changed()
    
    def on_move_control(self, control: KnotControl, point_control: PointControl, offset: QPointF, position: QPointF) -> None:

        self.curve.snap_position(position)

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
            for knot in self.curve.selection:
                knot.sync_scene_offsets()
                knot.remap_all_from_scene_positions()
            self.curve.export_to_parm()
            logger.debug("Finish moving knot")
        elif self.is_clicked_while_selected:
            self.curve.select_knot(self)

        if control is self.out_point_control or control is self.in_point_control:
            logger.debug("Finish moving handle")

    
    def remove_from_scene(self):
        self.scene.removeItem(self.knot_point_control)
        if self.in_point_control is not None:
            self.scene.removeItem(self.in_point_control)
        if self.out_point_control is not None:
            self.scene.removeItem(self.out_point_control)
        if self.in_handle is not None:
            self.scene.removeItem(self.in_handle)
        if self.out_handle is not None:
            self.scene.removeItem(self.out_handle)

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

        self.hovered_control: PointControl | None = None
        self.selection: list[BezierKnot] = []

        self.snap_position: Callable[[QPointF], None] = lambda _: None

        self.parm_set_by_curve = False

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

    def select_knot(self, knot: BezierKnot) -> None:
        for other_knot in self.knots:
            if other_knot is not knot:
                other_knot.is_selected = False
                other_knot.knot_point_control.set_selected(False)

        knot.is_selected = True
        self.selection = [knot]

    def add_to_selection(self, knot: BezierKnot) -> None:
        if knot not in self.selection:
            self.selection.append(knot)
            knot.is_selected = True

    def remove_from_selection(self, knot: BezierKnot) -> None:
        if knot in self.selection:
            self.selection.remove(knot)
            knot.is_selected = False
            knot.knot_point_control.set_selected(False)

    def clear_selection(self) -> None:
        for knot in self.knots:
            knot.is_selected = False
            knot.knot_point_control.set_selected(False)        

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

    def clear(self):
        for knot in self.knots:
            knot.remove_from_scene()
        self.knots.clear()

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

        next_knot_pos = self.knots[1].position.x()
        next_knot_index = 1

        for i in range(SHAPE_STEPS + 1):
            pos = i * SHAPE_STEP
            value = ramp.lookup(pos)
            path_position = self.map_to_scene(QPointF(pos, value))
            path.lineTo(path_position)

            while next_knot_index >= 0 and next_knot_pos > pos and next_knot_pos <= (pos + SHAPE_STEP):
                value = ramp.lookup(next_knot_pos)
                path_position = self.map_to_scene(QPointF(next_knot_pos, value))
                path.lineTo(path_position)                
                path.lineTo(path_position)

                if next_knot_index < len(self.knots) - 1:
                    next_knot_index += 1
                    next_knot_pos = self.knots[next_knot_index].position.x()
                else:
                    next_knot_index = -1
                    break

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
            if left <= pos and right > pos:
                return (i, i+1)
        return (-1, -1)

    def add_knot_to_curve(self, pos: float) -> None:
        left, right = self.knot_indicies_from_pos(pos)

        if left < 0:
            return

        left_knot = self.knots[left]
        right_knot = self.knots[right]

        left_out_pos = left_knot.position + left_knot.out_offset
        right_in_pos = right_knot.position + right_knot.in_offset


        ratio = (pos - left_knot.position.x())/(right_knot.position.x() - left_knot.position.x())
        knot_pos = QPointF(pos, self.ramp.lookup(pos))

        out_length = QPointF(0.0, 0.0)
        current_point = QPointF(knot_pos)

        SAMPLING_RATE = 50

        current_pos = QPointF(left_knot.position)

        for x in range(1, SAMPLING_RATE + 1):
            ratio = x * 1.0 / SAMPLING_RATE
            lk_out_offset = left_knot.out_offset * ratio
            rk_in_offset =  right_knot.in_offset * (1.0 - ratio)

            left_control_pos = left_knot.position + lk_out_offset
            right_control_pos = right_knot.position + rk_in_offset

            middle = left_out_pos + (right_in_pos - left_out_pos) * ratio
            middle_out = left_control_pos + (middle - left_control_pos) * ratio
            middle_in = middle + (right_control_pos - middle) * ratio

            gradient = middle_in - middle_out
            sampled_pos = middle_out + gradient * ratio

            logger.debug(f"ratio: {ratio} current: {current_pos} sampled: {sampled_pos} knot: {knot_pos}")

            if knot_pos.x() <= sampled_pos.x() and knot_pos.x() >= current_pos.x():
                logger.debug(f"Found U: {ratio}")
                break

            current_pos = sampled_pos


        left_knot.out_offset *= ratio
        if left_knot.out_offset.x() < EPSILON:
            left_knot.out_offset.setX(EPSILON)
        right_knot.in_offset *= (1.0 - ratio)
        if right_knot.in_offset.x() > -EPSILON:
            right_knot.in_offset.setX(-EPSILON)


        #ratio = (knot_pos.x() - left_control_pos.x()) / gradient_len

        knot_in = gradient * (-ratio) 
        knot_out = gradient * (1.0 - ratio) 

        self.add_knot(knot_pos, knot_in, knot_out, right)

        self.reset_scene_positions()
        self.sync_ramp()
        self.set_ramp_shape()
        
    def export_to_parm(self):
        self.parm_set_by_curve = True
        self.parm.set(self.ramp)
        self.parm_set_by_curve = False
        #self.set_ramp_shape(ramp)

    def load_from_ramp(self, ramp: hou.Ramp) -> None:

        self.clear()

        keys: list[float] = ramp.keys()
        values: list[float] = ramp.values()

        num_keys = len(keys)
        num_knots = 2 + (num_keys - 4) // 3

        logger.debug(f"Ramp num knots: {num_knots}")

        for i in range(num_knots):

            if i == 0:
                knot_pos = QPointF(keys[0], values[0])
                out_pos = QPointF(keys[1], values[1])
                self.add_knot(knot_pos, None, out_pos - knot_pos)
                continue

            if i == (num_knots - 1):
                index = (num_knots - 1) * 3
                knot_pos = QPointF(keys[index], values[index])
                in_pos = QPointF(keys[index-1], values[index-1])
                self.add_knot(knot_pos, in_pos - knot_pos, None)
                continue

            index = i * 3
            knot_pos = QPointF(keys[index], values[index])
            in_pos = QPointF(keys[index-1], values[index-1])
            out_pos = QPointF(keys[index+1], values[index+1])
            self.add_knot(knot_pos, in_pos - knot_pos, out_pos - knot_pos)

        self.sync_ramp()  
        
    def on_parm_changed(self):
        if not self.parm_set_by_curve:
            logger.debug("Sync changes from parm")
            self.load_from_ramp(self.parm.evalAsRamp())
            self.set_ramp_shape()
             
