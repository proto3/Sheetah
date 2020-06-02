#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

from jobmodel import JobManager
from jobui import JobGUI
from klippercontroller import KlipperController
from klippercontrollerui import KlipperControllerWidget
from postprocessor import PostProcessor

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, graphicview, sidebar, console, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("Sheetah")
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.addWidget(graphicview, 0, 0)
        layout.addWidget(console, 1, 0, 1, 2)
        layout.addWidget(sidebar, 0, 1)
        layout.setRowStretch(0, 2)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    pg.setConfigOption('antialias', True)

    # pg.setConfigOption('background', 0.1)
    # pg.setConfigOption('foreground', 'w')
    # app.setStyleSheet(open('style/darkorange.stylesheet').read())

    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')

    job_manager = JobManager()
    job_gui = JobGUI(job_manager)

    post_processor = PostProcessor()
    kc = KlipperController(job_manager, post_processor)
    kcw = KlipperControllerWidget(kc)
    kc.connect('/tmp/printer')

    mw = MainWindow(job_gui.graphic_w, job_gui.sidebar_w, kcw)
    mw.show()
    kcw.console.user_input_w.setFocus()

    app.exec_()
