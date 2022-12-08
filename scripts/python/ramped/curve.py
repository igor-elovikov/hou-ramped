from __future__ import annotations

import math
from typing import Optional, Callable, TYPE_CHECKING

from PySide2.QtCore import QPointF
from PySide2.QtGui import QBrush, QPainterPath
from PySide2.QtWidgets import QGraphicsScene, QGraphicsPathItem

from .control import PointControl
from .logger import logger
from .settings import EPSILON, SHAPE_GRADIENT, SHAPE_STEPS, SHAPE_STEP, SHAPE_PEN
from .knot import BezierKnot, KnotControl, KnotType, qpoint_length

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

        self.scene_width = 1000
        self.scene_height = 1000

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
        path = QPainterPath()
        self.ramp_shape.setPath(path)
        self.ramp_shape.update()
        self.ramp = None

    def add_knot(self, position: QPointF, in_offset: Optional[QPointF], out_offset: Optional[QPointF], insert_index: int = -1) -> None:
        index = len(self.knots)
        logger.debug(f"Add knot: {position} in: {in_offset} out: {out_offset} index: {index}")
        knot = BezierKnot(self, index, position, in_offset, out_offset)
        if insert_index < 0:
            if index == 0:
                knot.is_first = True
            else:
                knot.is_last = True
            self.knots.append(knot)
        else:
            self.knots.insert(insert_index, knot)
        self.reindex_knots()

    def reindex_knots(self) -> None:
        for i, knot in enumerate(self.knots):
            knot.index = i
            knot.is_first = False
            knot.is_last = False
        self.knots[0].is_first = True
        self.knots[-1].is_last = True
        
    def reset_scene_positions(self) -> None:
        for knot in self.knots:
            knot.set_scene_positions()

    def ramp_scene_position(self, pos: float) -> QPointF:
        return self.map_to_scene(QPointF(pos, self.ramp.lookup(pos)))

    def sync_ramp(self):
        self.ramp = self._get_ramp()

    def set_ramp_shape(self, ramp: Optional[hou.Ramp] = None) -> None:
        if not self.knots:
            return

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


        knot_in = gradient * (-ratio) 
        knot_out = gradient * (1.0 - ratio) 

        self.add_knot(knot_pos, knot_in, knot_out, right)

        self.on_knots_changed()

    def on_knots_changed(self) -> None:
        self.reset_scene_positions()
        self.sync_ramp()
        self.set_ramp_shape()
        self.export_to_parm()

    def set_clamped(self, is_clamped: bool) -> None:
        self.editor.clamping_enabled = is_clamped
        logger.debug(f"Set curve clamped: {is_clamped}")

        if not self.knots:
            return

        if is_clamped:
            self.knots[0].limit_horizontally = True
            self.knots[0].limit_x = 0.0
            self.knots[0].position.setX(0.0)
            self.knots[-1].limit_horizontally = True
            self.knots[-1].limit_x = 1.0
            self.knots[-1].position.setX(1.0)
            self.on_knots_changed()
        else:
            self.knots[0].limit_horizontally = False
            self.knots[-1].limit_horizontally = False

            if self.editor.looping_enabled:
                self.set_looped(False)
                self.editor.window.sync_settings_state()

    def set_looped(self, is_looped: bool) -> None:
        self.editor.looping_enabled = is_looped
        if is_looped:
            self.set_clamped(True)
            if not self.knots:
                return
            self.knots[0].on_move_control(KnotControl.OUT, 
                            self.knots[0].out_point_control, 
                            QPointF(0, 0), 
                            self.knots[0].get_control_scene_position(KnotControl.OUT))
            self.knots[-1].position.setY(self.knots[0].position.y())                            
            self.on_knots_changed()
                 
    def export_to_parm(self):
        self.parm_set_by_curve = True
        self.parm.set(self.ramp)
        self.parm_set_by_curve = False
        #self.set_ramp_shape(ramp)

    def create_default(self) -> None:
        self.clear()
        self.add_knot(QPointF(0.0, 0.0), None, QPointF(ONE_THIRD, ONE_THIRD))
        self.add_knot(QPointF(1.0, 1.0), QPointF(-ONE_THIRD, -ONE_THIRD), None)
        self.set_clamped(True)
        self.set_looped(False)
        self.sync_ramp()
        self.editor.update_scene_rect()
        self.editor.fit_viewport()

    def load_from_ramp(self, ramp: hou.Ramp) -> None:

        self.clear()

        keys: list[float] = ramp.keys()
        values: list[float] = ramp.values()
        basis: list[hou.rampBasis] = ramp.basis()

        num_keys = len(keys)
        num_knots = 2 + (num_keys - 4) // 3

        logger.debug(f"Ramp num knots: {num_knots}")

        if all((b == hou.rampBasis.Bezier for b in basis)):

            logger.debug("Load bezier ramp")

            is_supported = True
            is_supported &= ((num_keys - 4) % 3 == 0)
            is_supported &= (num_knots >= 2)

            if not is_supported:
                self.editor.show_default_ramp_message("Can't load ramp. <br>\
                    Bezier ramp doesn't have all control points. <br>\
                    You need two points for first and last knots and three points for every knot in between. <br> \
                    Create default ramp?")
                return
        
            for i in range(num_knots):

                if i == 0:
                    knot_pos = QPointF(keys[0], values[0])
                    out_pos = QPointF(keys[1], values[1])
                    self.add_knot(knot_pos, None, out_pos - knot_pos)
                    if ((out_pos - knot_pos).manhattanLength() < EPSILON):
                        self.knots[-1].set_type(KnotType.CORNER)
                    continue

                if i == (num_knots - 1):
                    index = (num_knots - 1) * 3
                    knot_pos = QPointF(keys[index], values[index])
                    in_pos = QPointF(keys[index-1], values[index-1])
                    self.add_knot(knot_pos, in_pos - knot_pos, None)
                    if ((in_pos - knot_pos).manhattanLength() < EPSILON):
                        self.knots[-1].set_type(KnotType.CORNER)
                    continue

                index = i * 3
                knot_pos = QPointF(keys[index], values[index])
                in_pos = QPointF(keys[index-1], values[index-1])
                out_pos = QPointF(keys[index+1], values[index+1])
                in_offset = in_pos - knot_pos
                out_offset = out_pos - knot_pos
                self.add_knot(knot_pos, in_pos - knot_pos, out_offset)
                if (in_offset.manhattanLength() < EPSILON and out_offset.manhattanLength() < EPSILON):
                    self.knots[-1].set_type(KnotType.CORNER)
                elif in_offset.manhattanLength() >= EPSILON and out_offset.manhattanLength() >= EPSILON:
                    in_length = qpoint_length(in_offset)
                    out_length = qpoint_length(out_offset)
                    if math.fabs(in_length * out_length + QPointF.dotProduct(in_offset, out_offset)) > EPSILON:
                        self.knots[-1].type = KnotType.BROKEN
                    

            self.sync_ramp()

            if self.knots[0].position.x() == 0.0 and self.knots[-1].position.x() == 1.0:
                self.set_clamped(True)
            else:
                self.set_clamped(False)

            self.editor.window.sync_settings_state()


            return

        if all((b == hou.rampBasis.Linear for b in basis)):
            logger.debug("Load linear ramp")
            for index, (value, key) in enumerate(zip(values, keys)):

                out_pos = QPointF(0.0, 0.0)
                in_pos = QPointF(0.0, 0.0)
                if index == 0:
                    in_pos = None
                if index == len(keys) - 1:
                    out_pos = None

                self.add_knot(QPointF(key, value), in_pos, out_pos)
                self.knots[-1].set_type(KnotType.CORNER)

            self.sync_ramp()

            return

        self.editor.show_default_ramp_message("Can't load ramp. <br>\
            Editor supports only Linear or Bezier ramps (without mixing). <br> \
            Create default ramp?")
        
    def on_parm_changed(self):
        if not self.parm_set_by_curve:
            logger.debug("Sync changes from parm")
            self.load_from_ramp(self.parm.evalAsRamp())
            self.set_ramp_shape()
             
