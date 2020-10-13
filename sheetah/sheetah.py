#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
import pyqtgraph as pg


from project import Project
from klippercontroller import KlipperController, KlipperControllerUI
from postprocessor import PostProcessor

from workspacegraphics import WorkspaceView, ProjectBar

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, graphicview, sidebar, console):
        super().__init__()
        self.graphicview = graphicview
        self.setWindowTitle("Sheetah")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(graphicview, 0, 0, 1, 2)
        layout.setRowStretch(0,2)
        layout.setRowStretch(1,1)
        # layout.setColumnStretch(0,2)
        layout.addWidget(console, 1, 0)
        layout.addWidget(sidebar, 1, 1)
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.i = 0

    def keyPressEvent(self, ev):
        # Ctrl + A
        if ev.key() == Qt.Key_A and ev.modifiers() == Qt.ControlModifier:
            print('Select All')
            for i in self.graphicview.scene().items():
                i.setSelected(True)
        # Ctrl + Z
        if ev.key() == Qt.Key_Z and ev.modifiers() == Qt.ControlModifier:
            print('Undo')
        # Ctrl + Shift + Z
        if (ev.key() == Qt.Key_Z and
            ev.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier)):
            print('Redo')
        # Ctrl + S
        elif ev.key() == Qt.Key_S and ev.modifiers() == Qt.ControlModifier:
            print('Save')
        else:
            self.graphicview.keyPressEvent(ev)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    pg.setConfigOption('background', 'w')

    app.setStyleSheet(open('style/darkorange.stylesheet').read())

    pg.setConfigOption('antialias', True)
    pg.setConfigOption('background', 0.1)
    pg.setConfigOption('foreground', 'w')

    project = Project()
    project_bar = ProjectBar(project)
    workspace_view = WorkspaceView(project) #, machine)

    post_processor = PostProcessor()
    controller = KlipperController(project, post_processor)
    controller_ui = KlipperControllerUI(controller)
    controller.connect('/tmp/printer')

    main_window = MainWindow(workspace_view,
                             project_bar,
                             controller_ui)
    main_window.show()
    controller_ui.console.user_input_w.setFocus()

    app.exec_()
