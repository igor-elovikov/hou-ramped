from PySide2.QtGui import QColor, QLinearGradient, QPen, QBrush, QFont

HOVERED_SCALE = 1.2
EPSILON = 0.0001
SHAPE_STEPS = 100

ADD_MARKER_RADIUS = 7.0
ADD_MARKER_COLOR = (166, 210, 121)
SNAPPING_DISTANCE = 8.0

SHAPE_GRADIENT = QLinearGradient()
SHAPE_GRADIENT.setColorAt(0, QColor(165, 165, 165, 15))
SHAPE_GRADIENT.setColorAt(1, QColor(241, 241, 241, 100))
SHAPE_GRADIENT.setSpread(QLinearGradient.Spread.ReflectSpread)

SHAPE_PEN = QPen(QBrush(QColor(239, 239, 239)), 3)

SHAPE_STEP = 1.0 / SHAPE_STEPS

GRID_FONT = QFont("Source Code Pro", 8.0)