#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui
import pyqtgraph as pg
import numpy as np
import sys

from serialmanager import SerialManager
from jobmodel import JobModelCollection
from jobui import JobGUI

class ConsoleWidget(QtGui.QWidget):
    hist_filename = '.history'
    curve_data_updated = QtCore.pyqtSignal()

    def __init__(self, serialmanager):
        super().__init__()
        self._sm = serialmanager
        self.serial_data_w = QtGui.QTextBrowser()
        self.user_input_w = QtGui.QLineEdit()

        self.graph = pg.PlotWidget()
        grid_levels = [(1000, 0), (100, 0),(10, 0),(1, 0)]
        self.graph.setAspectLocked()
        self.graph.showGrid(True, True, 0.5)
        self.graph.getAxis("bottom").setTickSpacing(levels=grid_levels)
        self.graph.getAxis("left").setTickSpacing(levels=grid_levels)

        self.graph.setRange(yRange=(-30, 30), disableAutoRange=True)

        self.curve1 = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255, 87, 34), width=2))
        self.curve2 = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(62, 152, 255), width=2))
        self.curve1_data = np.zeros(1000)
        self.curve2_data = np.zeros(1000)
        self.update_curve()
        self.curve_data_updated.connect(self.update_curve)

        self.graph.addItem(self.curve1)
        self.graph.addItem(self.curve2)
        try:
            with open(self.hist_filename, 'r') as file:
                self.hist = file.read().splitlines()
        except:
            self.hist = []
        self.hist_fd = open(self.hist_filename, 'a+')
        self.hist_tmp = self.hist.copy() + ['']
        self.hist_cursor = len(self.hist_tmp) - 1

        self.serial_data_w.setMinimumWidth(480)
        self.graph.setMinimumSize(320, 320)
        layout = QtGui.QGridLayout()
        layout.addWidget(self.serial_data_w, 0, 0)
        layout.addWidget(self.user_input_w, 1, 0)
        layout.addWidget(self.graph, 0, 1, 2, 1)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)

        self._sm.log_available.connect(self.on_log)
        self.user_input_w.returnPressed.connect(self.on_user_input)

        QtGui.QShortcut(QtCore.Qt.Key_Up, self.user_input_w, self.key_up)
        QtGui.QShortcut(QtCore.Qt.Key_Down, self.user_input_w, self.key_down)

    def sizeHint(self):
        width = self.serial_data_w.minimumWidth() + self.graph.minimumWidth()
        return QtCore.QSize(width, self.graph.minimumHeight())

    def on_log(self):
        while not self._sm.logging_queue.empty():
            log = self._sm.logging_queue.get()

            if log[0][:12] == '// echo: THC':
                try:
                    tmp = log[0].split()
                    v1 = float(tmp[3])
                    v2 = float(tmp[4])
                    self.curve1_data[:-1] = self.curve1_data[1:]
                    self.curve1_data[-1] = v1
                    self.curve2_data[:-1] = self.curve2_data[1:]
                    self.curve2_data[-1] = v2
                    self.curve_data_updated.emit()
                except:
                    pass
                continue

            if log[1]:
                text = log[0]
            else:
                text = '<span style=\" color:#888888;\" >' + log[0] + '</span>'
            self.serial_data_w.append(text)

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

    def on_user_input(self):
        text = self.user_input_w.text()
        self._sm.send_user_cmd(text)
        self.hist_fd.write(text + '\n')
        self.hist_fd.flush()
        self.user_input_w.clear()
        self.hist.append(text)
        self.hist_tmp = self.hist.copy() + ['']
        self.hist_cursor = len(self.hist_tmp) - 1

    def update_curve(self):
        self.curve1.setData(self.curve1_data)
        self.curve2.setData(self.curve2_data)

class MainWindow(QtGui.QMainWindow):
    def __init__(self, graphicview, sidebar, console, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("Sheetah")
        widget = QtGui.QWidget()
        layout = QtGui.QGridLayout()
        layout.addWidget(graphicview, 0, 0)
        layout.addWidget(console, 1, 0, 1, 2)
        layout.addWidget(sidebar, 0, 1)
        layout.setRowStretch(0, 2)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

if __name__ == '__main__':
    app = QtGui.QApplication([])
    pg.setConfigOption('antialias', True)

    # pg.setConfigOption('background', 0.1)
    # pg.setConfigOption('foreground', 'w')
    # app.setStyleSheet(open('darkorange.stylesheet').read())

    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')

    # functional modules
    serial_manager = SerialManager()
    jobs = JobModelCollection(serial_manager)

    # widgets
    console_w = ConsoleWidget(serial_manager)
    job_gui = JobGUI(jobs)

    mainw = MainWindow(job_gui.graphic_w, job_gui.sidebar_w, console_w)
    mainw.show()
    console_w.user_input_w.setFocus()
    serial_manager.open('/tmp/printer')
    sys.exit(app.exec_())
