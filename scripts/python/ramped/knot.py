from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING
import functools

from enum import Enum, auto

from PySide2.QtCore import QLineF, QPointF, Qt
from PySide2.QtGui import QColor, QPen, QGuiApplication
from PySide2.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .control import PointControl, ControlStyle
from .logger import logger
from .settings import EPSILON

if TYPE_CHECKING:
    from .curve import BezierCurve


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

        self.limit_horizontally = False
        self.limit_x = 0.0  
        self.is_first = False
        self.is_last = False 

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
            self.in_point_control.on_start_move = self.on_start_move_control
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
            self.out_point_control.on_start_move = self.on_start_move_control
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
            self.curve.export_to_parm()
            return

        if self.type is KnotType.CORNER:
            self.set_type(KnotType.SMOOTH)
            self._on_points_changed()
            self.curve.export_to_parm()
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
        if self.out_point_control is None:
            self.set_out_control_scene_position(self.scene_position)
            return self.scene_position

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
        if desired_position.x() <= left_limit + EPSILON:
            desired_position.setX(left_limit + EPSILON)

        self.set_out_control_scene_position(desired_position)

        return desired_position

    def move_in_control(self, knot_position: QPointF) -> QPointF:
        if self.in_point_control is None:
            self.set_in_control_scene_position(self.scene_position )
            return self.scene_position

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
        if desired_position.x() >= right_limit - EPSILON:
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
            if self.is_last:
                position.setX(right_limit)

        if position.x() <= left_limit:
            out_of_limits = True
            position.setX(left_limit + EPSILON)
            if self.is_first:
                position.setX(left_limit)

        if self.limit_horizontally:
            out_of_limits = True
            position.setX(self.limit_x * self.curve.scene_width)                

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

        if self.curve.editor.looping_enabled and (self.is_first or self.is_last):
            if self.is_first:
                knot = self.curve.knots[-1]
                knot_pos = QPointF(knot.scene_position.x(), position.y())
                knot.move_in_scene(knot_pos)
                knot.knot_point_control.setPos(knot_pos)
                knot.remap_all_from_controls_positions()   
            if self.is_last:
                knot = self.curve.knots[0]
                knot_pos = QPointF(knot.scene_position.x(), position.y())
                knot.move_in_scene(knot_pos)
                knot.knot_point_control.setPos(knot_pos)
                knot.remap_all_from_controls_positions()                             


        self._on_points_changed()

    def on_start_move_control(self, point_control: PointControl) -> None:
        keyboard_modifiers = QGuiApplication.keyboardModifiers()
        if (keyboard_modifiers & Qt.ShiftModifier):
            self.type = KnotType.SMOOTH
        elif (keyboard_modifiers & Qt.ControlModifier):
            self.type = KnotType.BROKEN        
    
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
        

        opposite_point_control = self.get_control(opposite_control)
        opposite_knot = self

        if self.curve.editor.looping_enabled:
            if self.is_last and control is KnotControl.IN:
                opposite_point_control = self.curve.knots[0].get_control(KnotControl.OUT)
                opposite_knot = self.curve.knots[0]

            if self.is_first and control is KnotControl.OUT:
                opposite_point_control = self.curve.knots[-1].get_control(KnotControl.IN)
                opposite_knot = self.curve.knots[-1]  

        opposite_offset = opposite_knot.get_control_scene_offset(opposite_control)                              
                
        if opposite_point_control is None or self.type is not KnotType.SMOOTH:
            self._on_points_changed()
            return

        length = qpoint_length(opposite_offset)
        dir = offset * -1.0
        qpoint_normalize(dir)

        opposite_knot.set_control_scene_offset(opposite_control, dir * length)
        opposite_knot.move_control(opposite_control, opposite_knot.scene_position)

        self._on_points_changed()
        if self is not opposite_knot:
            opposite_knot._on_points_changed()

    def finish_move_in_scene(self, control: PointControl, has_moved: bool) -> None:

        if has_moved:
            for knot in self.curve.selection:
                knot.sync_scene_offsets()
                knot.remap_all_from_scene_positions()
            if self.curve.editor.auto_extend_enabled:
                self.curve.editor.extend_viewport()                
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