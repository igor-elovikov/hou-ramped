from PySide2.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget
from PySide2.QtCore import QFile
from .ui import Ui_RampEditorWindow

import hou


class EditorWindow(QMainWindow):
    def __init__(self, parm: hou.Parm):
        super().__init__()
        self.setStyleSheet(hou.qt.styleSheet())
        self.ui = Ui_RampEditorWindow()
        self.ui.setupUi(self)
        

        self.ui.editor.setup_parm(parm)
        self.ui.editor.on_borders_changed = self.on_boders_changed
        self.top_line = hou.qt.InputField(hou.qt.InputField.FloatType, 1)
        
        self.top_line.setWidth(100)
        self.top_line.editingFinished.connect(self.set_top_line)
        self.ui.top_line.setLayout(QHBoxLayout())
        self.ui.top_line.layout().addWidget(self.top_line)

        self.bottom_line = hou.qt.InputField(hou.qt.InputField.FloatType, 1)
        self.bottom_line.setWidth(100)
        self.bottom_line.editingFinished.connect(self.set_bottom_line)
        self.ui.bottom_line.setLayout(QHBoxLayout())
        self.ui.bottom_line.layout().addWidget(self.bottom_line)

        self.setWindowTitle("Ramp Editor")

    def set_bottom_line(self, value):
        self.ui.editor.set_borders(value[0], self.ui.editor.top_border)
        self.ui.editor.update()

    def set_top_line(self, value):
        self.ui.editor.set_borders(self.ui.editor.bottom_border, value[0])
        self.ui.editor.update()

    def on_boders_changed(self, bottom: float, top: float) -> None:
        self.bottom_line.setValue(bottom)
        self.top_line.setValue(top)

