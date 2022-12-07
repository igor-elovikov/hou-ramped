from __future__ import annotations

import math
from typing import Optional, Callable, TYPE_CHECKING
import functools

from enum import Enum, auto

from PySide2.QtCore import QLineF, QPointF, Qt
from PySide2.QtGui import QColor, QPen, QBrush, QPainterPath, QGuiApplication
from PySide2.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsPathItem, QGraphicsView

from .control import PointControl, ControlStyle
from .logger import logger
from .settings import EPSILON, SHAPE_GRADIENT, SHAPE_STEPS, SHAPE_STEP, SHAPE_PEN, SNAPPING_DISTANCE
from .knot import BezierKnot

if TYPE_CHECKING:
    from .editor import RampEditor

import hou

ONE_THIRD = 0.3333333333333
TWO_THIRDS = 0.6666666666666



class BezierCurve:

    def __init__(self, scene: QGraphicsScene) -> None:

        self.editor: RampEditor | None = None

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
             
