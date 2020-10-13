#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
import pyqtgraph as pg


from project import Project
from klippercontroller import KlipperController, KlipperControllerUI
from postprocessor import PostProcessor

from workspacegraphics import WorkspaceView, ProjectBar
from workspacecontroller import WorkspaceController

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, ws_view, ws_controller, sidebar, console):
        super().__init__()
        self.ws_controller = ws_controller
        self.setWindowTitle("Sheetah")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(ws_view, 0, 0, 1, 2)
        layout.addWidget(console, 1, 0)
        layout.addWidget(sidebar, 1, 1)
        layout.setRowStretch(0,2)
        layout.setRowStretch(1,1)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def keyPressEvent(self, ev):
        self.ws_controller.keyPressEvent(ev)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    pg.setConfigOption('background', 'w')

    app.setStyleSheet(open('style/darkorange.stylesheet').read())

    pg.setConfigOption('antialias', True)
    pg.setConfigOption('background', 0.1)
    pg.setConfigOption('foreground', 'w')

    project = Project()
    project_bar = ProjectBar(project)
    ws_view = WorkspaceView()
    ws_controller = WorkspaceController(project, ws_view)

    post_processor = PostProcessor()
    controller = KlipperController(project, post_processor)
    controller_ui = KlipperControllerUI(controller)
    controller.connect('/tmp/printer')

    main_window = MainWindow(ws_view,
                             ws_controller,
                             project_bar,
                             controller_ui)
    main_window.show()
    controller_ui.console.user_input_w.setFocus()

    app.exec_()
