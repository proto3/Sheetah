#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import serial
from controllerbase import ControllerBase, ControllerUIBase, InputDecisionTree

import queue

class QTHCLogger(QtCore.QObject):
    thc_update = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.thc_data = np.zeros((1000, 3))
    def log_thc_data(self, z_pos, arc_v, speed):
        self.thc_data[:-1] = self.thc_data[1:]
        self.thc_data[-1] = np.array([z_pos, arc_v, speed])
        self.thc_update.emit()

class KlipperController(ControllerBase):
    def __init__(self, project, post_processor):
        super().__init__(project, post_processor)
        self.serial = serial.Serial()
        self.thc_logger = QTHCLogger()
        self.klipper_busy = False

        self.input_parser = InputDecisionTree()
        self.input_parser.append_node('ok', self._process_ok)
        self.input_parser.append_node('!!', self._process_error)
        self.input_parser.append_node('// echo: THC_error', self._process_thc)

    def _link_open(self, *args, **kwargs):
        self.serial = serial.Serial('/tmp/printer', timeout=0.2)

    def _link_close(self):
        self.serial.close()

    def _link_read(self):
        return self.serial.readline().decode('ascii')

    def _link_send(self, cmd):
        self.serial.write((cmd + '\n').encode('ascii'))
        self.klipper_busy = True

    def _link_busy(self):
        return self.klipper_busy

    def _process_input(self, input):
        self.input_parser.process_input(input)

    def _process_ok(self, input):
        self._complete_cmd()
        self.klipper_busy = False

    def _process_error(self, input):
        self._abort_internal(input)

    def _process_thc(self, input):
        words = input.split()
        z_pos = float(words[3])
        arc_v = float(words[4])
        speed = float(words[5])
        self.thc_logger.log_thc_data(z_pos, arc_v, speed)

class THCWidget(pg.PlotWidget):
    def __init__(self, thc_logger):
        super().__init__()
        self.thc_logger = thc_logger
        self.showGrid(True, True, 0.5)
        self.setRange(yRange=(0, 200), disableAutoRange=True)
        self.hideButtons()

        self.z_pos_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(87, 200, 34), width=2))
        self.arc_v_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255, 87, 34), width=2))
        self.speed_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(34, 120, 255), width=2))
        self.on_thc_data()
        self.addItem(self.z_pos_curve)
        self.addItem(self.arc_v_curve)
        self.addItem(self.speed_curve)
        self.thc_logger.thc_update.connect(self.on_thc_data)

    def on_thc_data(self):
        self.z_pos_curve.setData(self.thc_logger.thc_data[:,0])
        self.arc_v_curve.setData(self.thc_logger.thc_data[:,1])
        self.speed_curve.setData(self.thc_logger.thc_data[:,2])

class KlipperControllerUI(ControllerUIBase):
    def __init__(self, controller):
        super().__init__(controller)
        self.thc_graph = THCWidget(self.controller.thc_logger)
        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.console, 0, 0, 2, 1)
        layout.addWidget(self.btn_box, 0, 1)
        layout.addWidget(self.thc_graph, 1, 1)
        self.setLayout(layout)
