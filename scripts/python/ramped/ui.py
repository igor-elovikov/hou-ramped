# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'window.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from .editor import RampEditor


class Ui_RampEditorWindow(object):
    def setupUi(self, RampEditorWindow):
        if not RampEditorWindow.objectName():
            RampEditorWindow.setObjectName(u"RampEditorWindow")
        RampEditorWindow.resize(741, 701)
        self.central_widget = QWidget(RampEditorWindow)
        self.central_widget.setObjectName(u"central_widget")
        self.verticalLayout = QVBoxLayout(self.central_widget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(self.central_widget)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setBold(False)
        font.setWeight(50)
        self.label.setFont(font)
        self.label.setTextFormat(Qt.AutoText)
        self.label.setMargin(8)

        self.verticalLayout.addWidget(self.label)

        self.editor_layout = QHBoxLayout()
        self.editor_layout.setSpacing(2)
        self.editor_layout.setObjectName(u"editor_layout")
        self.inputs_container = QVBoxLayout()
        self.inputs_container.setSpacing(0)
        self.inputs_container.setObjectName(u"inputs_container")
        self.inputs_container.setSizeConstraint(QLayout.SetFixedSize)
        self.top_line = QWidget(self.central_widget)
        self.top_line.setObjectName(u"top_line")

        self.inputs_container.addWidget(self.top_line)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.inputs_container.addItem(self.verticalSpacer)

        self.bottom_line = QWidget(self.central_widget)
        self.bottom_line.setObjectName(u"bottom_line")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.bottom_line.sizePolicy().hasHeightForWidth())
        self.bottom_line.setSizePolicy(sizePolicy)
        self.bottom_line.setMinimumSize(QSize(0, 0))

        self.inputs_container.addWidget(self.bottom_line)


        self.editor_layout.addLayout(self.inputs_container)

        self.editor = RampEditor(self.central_widget)
        self.editor.setObjectName(u"editor")

        self.editor_layout.addWidget(self.editor)


        self.verticalLayout.addLayout(self.editor_layout)

        self.verticalSpacer_2 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.settings = QGroupBox(self.central_widget)
        self.settings.setObjectName(u"settings")
        self.settings.setFont(font)
        self.settings.setFlat(False)
        self.settings.setCheckable(False)
        self.verticalLayout_2 = QVBoxLayout(self.settings)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.clamp_to_01 = QCheckBox(self.settings)
        self.clamp_to_01.setObjectName(u"clamp_to_01")
        self.clamp_to_01.setFont(font)

        self.horizontalLayout.addWidget(self.clamp_to_01)

        self.looping_ramp = QCheckBox(self.settings)
        self.looping_ramp.setObjectName(u"looping_ramp")

        self.horizontalLayout.addWidget(self.looping_ramp)

        self.grid_snap = QCheckBox(self.settings)
        self.grid_snap.setObjectName(u"grid_snap")

        self.horizontalLayout.addWidget(self.grid_snap)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.grid_settings = QWidget(self.settings)
        self.grid_settings.setObjectName(u"grid_settings")

        self.horizontalLayout_2.addWidget(self.grid_settings)

        self.auto_extend = QCheckBox(self.settings)
        self.auto_extend.setObjectName(u"auto_extend")

        self.horizontalLayout_2.addWidget(self.auto_extend)

        self.fit_button = QPushButton(self.settings)
        self.fit_button.setObjectName(u"fit_button")

        self.horizontalLayout_2.addWidget(self.fit_button)


        self.verticalLayout_2.addLayout(self.horizontalLayout_2)


        self.verticalLayout.addWidget(self.settings)

        RampEditorWindow.setCentralWidget(self.central_widget)

        self.retranslateUi(RampEditorWindow)

        QMetaObject.connectSlotsByName(RampEditorWindow)
    # setupUi

    def retranslateUi(self, RampEditorWindow):
        RampEditorWindow.setWindowTitle(QCoreApplication.translate("RampEditorWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("RampEditorWindow", u"Current Parameter", None))
        self.settings.setTitle(QCoreApplication.translate("RampEditorWindow", u"Settings", None))
        self.clamp_to_01.setText(QCoreApplication.translate("RampEditorWindow", u"Clamp to [0:1]", None))
        self.looping_ramp.setText(QCoreApplication.translate("RampEditorWindow", u"Looping Ramp", None))
        self.grid_snap.setText(QCoreApplication.translate("RampEditorWindow", u"Grid Snapping", None))
        self.auto_extend.setText(QCoreApplication.translate("RampEditorWindow", u"Auto Extend Viewport", None))
        self.fit_button.setText(QCoreApplication.translate("RampEditorWindow", u"Fit Viewport To Curve", None))
    # retranslateUi

