#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

from klippercontroller import KlipperController

class THCWidget(pg.PlotWidget):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        grid_levels = [(1000, 0), (100, 0),(10, 0),(1, 0)]
        # self.setAspectLocked()
        self.showGrid(True, True, 0.5)
        self.getAxis("bottom").setTickSpacing(levels=grid_levels)
        self.getAxis("left").setTickSpacing(levels=grid_levels)

        self.setRange(yRange=(-30, 30), disableAutoRange=True)

        self.curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255, 87, 34), width=2))
        self.on_thc_data()
        self.addItem(self.curve)
        self.logger.thc_update.connect(self.on_thc_data)

    def on_thc_data(self):
        self.curve.setData(self.logger.thc_data)

class ConsoleWidget(QtWidgets.QWidget):
    hist_filename = '.history'
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.serial_data_w = QtWidgets.QTextBrowser()
        self.user_input_w = QtWidgets.QLineEdit()
        try:
            with open(self.hist_filename, 'r') as file:
                self.hist = file.read().splitlines()
        except:
            self.hist = []
        self.hist_fd = open(self.hist_filename, 'a+')
        self.hist_tmp = self.hist.copy() + ['']
        self.hist_cursor = len(self.hist_tmp) - 1
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.serial_data_w)
        layout.addWidget(self.user_input_w)
        layout.setStretch(0, 2)
        layout.setStretch(1, 1)
        self.setLayout(layout)

        self.controller.logger.log_available.connect(self.on_log)
        self.user_input_w.returnPressed.connect(self.on_user_input)

        QtWidgets.QShortcut(QtCore.Qt.Key_Up, self.user_input_w, self.key_up)
        QtWidgets.QShortcut(QtCore.Qt.Key_Down, self.user_input_w, self.key_down)

    def on_log(self):
        while not self.controller.logger.empty():
            log = self.controller.logger.get()
            if log[1]:
                text = log[0]
            else:
                text = '<span style=\" color:#888888;\" >' + log[0] + '</span>'
            self.serial_data_w.append(text)

    def on_user_input(self):
        text = self.user_input_w.text()
        if self.controller.send_manual_cmd(text):
            self.hist_fd.write(text + '\n')
            self.hist_fd.flush()
            self.user_input_w.clear()
            self.hist.append(text)
            self.hist_tmp = self.hist.copy() + ['']
            self.hist_cursor = len(self.hist_tmp) - 1

    def key_up(self):
        if self.user_input_w.hasFocus():
            self.hist_tmp[self.hist_cursor] = self.user_input_w.text()
            if self.hist_cursor > 0:
                self.hist_cursor -= 1
                self.user_input_w.setText(self.hist_tmp[self.hist_cursor])

    def key_down(self):
        if self.user_input_w.hasFocus():
            self.hist_tmp[self.hist_cursor] = self.user_input_w.text()
            if self.hist_cursor < len(self.hist_tmp) - 1:
                self.hist_cursor += 1
                self.user_input_w.setText(self.hist_tmp[self.hist_cursor])

class KlipperControllerWidget(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.console = ConsoleWidget(self.controller)
        self.thc_graph = THCWidget(self.controller.logger)

        self.start_btn = QtWidgets.QPushButton('Start')
        self.stop_btn = QtWidgets.QPushButton('Stop')
        self.pause_btn = QtWidgets.QPushButton('Pause')
        self.resume_btn = QtWidgets.QPushButton('Resume')
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.pause_btn.clicked.connect(self.on_pause)
        self.resume_btn.clicked.connect(self.on_resume)

        self.btn_box = QtWidgets.QGroupBox()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.resume_btn)
        self.btn_box.setLayout(layout)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.console)
        layout.addWidget(self.btn_box)
        layout.addWidget(self.thc_graph)
        self.setLayout(layout)

    def on_start(self):
        self.controller.start()
    def on_stop(self):
        self.controller.stop()
    def on_pause(self):
        self.controller.pause()
    def on_resume(self):
        self.controller.resume()

# class JobIncidentDialog(QtWidgets.QDialog):
#     def __init__(self, msg, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle('Job incident')
#         std_btns = (QtWidgets.QDialogButtonBox.Ok |
#                    QtWidgets.QDialogButtonBox.Cancel)
#         self.buttonBox = QtWidgets.QDialogButtonBox(std_btns)
#         self.buttonBox.accepted.connect(self.accept)
#         self.buttonBox.rejected.connect(self.reject)
#
#         name_label = QtWidgets.QLabel(msg, alignment=QtCore.Qt.AlignCenter)
#         layout = QtWidgets.QVBoxLayout()
#         layout.addWidget(name_label)
#         layout.addWidget(self.buttonBox)
#         self.setLayout(layout)
