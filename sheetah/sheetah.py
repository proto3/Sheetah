#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
import pyqtgraph as pg

from project import Project
from projectui import ProjectUI
from klippercontroller import KlipperController, KlipperControllerUI
from postprocessor import PostProcessor

from workspaceview import WorkspaceView

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, graphicview, sidebar, console):
        super().__init__()
        self.setWindowTitle("Sheetah")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(graphicview, 0, 0, 2, 1)
        layout.addWidget(console, 1, 1)
        layout.addWidget(sidebar, 0, 1)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    # pg.setConfigOption('background', 'w')

    app.setStyleSheet(open('style/darkorange.stylesheet').read())

    pg.setConfigOption('antialias', True)
    pg.setConfigOption('background', 0.1)
    pg.setConfigOption('foreground', 'w')

    project = Project()
    project_ui = ProjectUI(project)
    workspace_view = WorkspaceView(project) #, machine)

    post_processor = PostProcessor()
    controller = KlipperController(project, post_processor)
    controller_ui = KlipperControllerUI(controller)
    controller.connect('/tmp/printer')

    main_window = MainWindow(workspace_view,
                             # project_ui.graphic_w,
                             project_ui.sidebar_w,
                             controller_ui)
    main_window.show()
    controller_ui.console.user_input_w.setFocus()

    app.exec_()
