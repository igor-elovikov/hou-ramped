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
        RampEditorWindow.resize(676, 679)
        self.central_widget = QWidget(RampEditorWindow)
        self.central_widget.setObjectName(u"central_widget")
        self.verticalLayout = QVBoxLayout(self.central_widget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(self.central_widget)
        self.label.setObjectName(u"label")
        self.label.setMargin(4)

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

        self.settings = QHBoxLayout()
        self.settings.setObjectName(u"settings")
        self.checkBox_3 = QCheckBox(self.central_widget)
        self.checkBox_3.setObjectName(u"checkBox_3")

        self.settings.addWidget(self.checkBox_3)

        self.checkBox_2 = QCheckBox(self.central_widget)
        self.checkBox_2.setObjectName(u"checkBox_2")

        self.settings.addWidget(self.checkBox_2)

        self.checkBox = QCheckBox(self.central_widget)
        self.checkBox.setObjectName(u"checkBox")

        self.settings.addWidget(self.checkBox)


        self.verticalLayout.addLayout(self.settings)

        RampEditorWindow.setCentralWidget(self.central_widget)

        self.retranslateUi(RampEditorWindow)

        QMetaObject.connectSlotsByName(RampEditorWindow)
    # setupUi

    def retranslateUi(self, RampEditorWindow):
        RampEditorWindow.setWindowTitle(QCoreApplication.translate("RampEditorWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("RampEditorWindow", u"TextLabel", None))
        self.checkBox_3.setText(QCoreApplication.translate("RampEditorWindow", u"CheckBox", None))
        self.checkBox_2.setText(QCoreApplication.translate("RampEditorWindow", u"CheckBox", None))
        self.checkBox.setText(QCoreApplication.translate("RampEditorWindow", u"CheckBox", None))
    # retranslateUi

