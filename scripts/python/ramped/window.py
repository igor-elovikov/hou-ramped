from __future__ import annotations

from PySide2.QtCore import QLineF, QPointF, QRectF, QSize, Qt, Signal, Slot, QPoint, QRect
from PySide2.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QLabel, QLineEdit
from PySide2.QtCore import QFile
from PySide2.QtGui import QCloseEvent, QMouseEvent, QCursor, QFont, QFocusEvent
from .ui import Ui_RampEditorWindow

import functools

import hou

class BorderLabel(QLabel):

    double_clicked = Signal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.double_clicked.emit(self.mapToGlobal(self.pos()))
        return super().mouseDoubleClickEvent(event)

class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(hou.qt.styleSheet())
        self.ui = Ui_RampEditorWindow()
        self.ui.setupUi(self)
        self.ui.editor.on_borders_changed = self.on_boders_changed
        
        self.top_line_label = BorderLabel()
        self.top_line_label.setText("1.0")
        self.top_line_label.setMinimumSize(50, 0)
        self.top_line_label.double_clicked.connect(functools.partial(self.show_border_input, True))
        self.ui.top_line.setLayout(QHBoxLayout())
        self.ui.top_line.layout().setMargin(0)
        self.ui.top_line.layout().addWidget(self.top_line_label)

        self.bottom_line_label = BorderLabel()
        self.bottom_line_label.setText("1.0")
        self.bottom_line_label.setMinimumSize(50, 0)
        self.bottom_line_label.double_clicked.connect(functools.partial(self.show_border_input, False))
        self.ui.bottom_line.setLayout(QHBoxLayout())
        self.ui.bottom_line.layout().setMargin(0)
        self.ui.bottom_line.layout().addWidget(self.bottom_line_label)

        self.ui.central_widget.setFocusPolicy(Qt.NoFocus)

        self.border_input: QWidget = hou.qt.InputField(hou.qt.InputField.FloatType, 1)        
        self.border_input.setWidth(100)
        self.border_input.editingFinished.connect(self.on_border_input_changed)
        self.border_input.setParent(self)
        self.border_input.setVisible(False)

        self.grid_step_input: QWidget = hou.qt.InputField(hou.qt.InputField.FloatType, 2, "Grid Step")
        self.ui.grid_settings.setLayout(QHBoxLayout())
        self.ui.grid_settings.layout().addWidget(self.grid_step_input)

        self.top_border_edit = False

        self.setWindowTitle("Ramp Editor")

    def show_border_input(self, top: bool, pos: QPoint) -> None:
        pos = self.mapFromGlobal(pos)
        self.top_border_edit = top
        value = self.ui.editor.top_border if top else self.ui.editor.bottom_border
        line_edit: QLineEdit = self.border_input.lineEdits[0]
        line_edit.setText(f"{value}")
        line_edit.selectAll()
        line_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        line_edit.setFocus()

        self.border_input.setVisible(True)
        self.border_input.setGeometry(QRect(pos, QSize(100, 40)))
    
    def set_bottom_line(self, value: float) -> None:
        self.border_input.setVisible(False)
        self.ui.editor.set_borders(value[0], self.ui.editor.top_border)
        self.ui.editor.update()

    def set_top_line(self, value: float) -> None:
        self.border_input.setVisible(False)
        self.ui.editor.set_borders(self.ui.editor.bottom_border, value[0])
        self.ui.editor.update()

    def on_border_input_changed(self, value: float):
        if self.top_border_edit:
            self.set_top_line(value)
        else:
            self.set_bottom_line(value)

    def on_boders_changed(self, bottom: float, top: float) -> None:
        self.bottom_line_label.setText(f"{bottom:.2f}")
        self.top_line_label.setText(f"{top:.2f}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.ui.editor.on_close()
        return super().close()        

