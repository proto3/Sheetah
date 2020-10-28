#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import serial
from controllerbase import ControllerBase, ControllerUIBase

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
        self.klipper_busy = False
        self.thc_logger = QTHCLogger()
        self.internal_cmd_queue = queue.Queue()
        self.cut_running = False
        self.task_list = []

        self.input_parser.append_node('ok', self._process_ok)
        self.input_parser.append_node('!!', self._process_error)
        self.input_parser.append_node('// echo: THC_error', self._process_thc)
        self.input_parser.append_node('!! Arc transfer timeout', self._process_arc_transfer_timeout)
        self.input_parser.append_node('!! Arc transfer loss', self._process_arc_loss)

    def _process_ok(self, input):
        self.klipper_busy = False
        self.send_cond.wakeOne()

    def _process_error(self, input):
        if self.active:
            self.abort()
            self.com_logger.incident.emit(input)

    def _process_thc(self, input):
        words = input.split()
        z_pos = float(words[3])
        arc_v = float(words[4])
        speed = float(words[5])
        self.thc_logger.log_thc_data(z_pos, arc_v, speed)

    def _process_arc_transfer_timeout(self, input):
        if self.active:
            self.abort()
            self.com_logger.incident.emit(input)

    def _process_arc_loss(self, input):
        if self.active:
            self.abort()
            self.com_logger.incident.emit(input)

    def connect(self, port):
        if not self.connected:
            try:
                self.serial = serial.Serial(port, timeout=0.2)
            except:
                raise Exception('Cannot open port ' + port)
            self.connected = True
            self.keep_threads = True
            self.klipper_busy = False
            self.input_thread.start()
            self.output_thread.start()

    def disconnect(self):
        if self.connected and not self.active:
            self.mutex.lock()
            self.keep_threads = False
            self.send_cond.wakeOne()
            self.mutex.unlock()
            self.input_thread.wait()
            self.output_thread.wait()
            self.serial.close()
            self.connected = False

    def _input_worker(self):
        while self.keep_threads:
            line = ''
            while (not line or line[-1] != '\n') and self.keep_threads:
                line += self.serial.readline().decode('ascii')
            if self.keep_threads:
                self.mutex.lock()
                line = line.rstrip()
                self.input_parser.process_input(line)
                self.com_logger.log_received_data(line)
                self.mutex.unlock()

    def _output_worker(self):
        while self.keep_threads:
            self.mutex.lock()
            cmd = self._get_next_cmd()
            while not cmd and self.keep_threads:
                self.send_cond.wait(self.mutex)
                cmd = self._get_next_cmd()
            if self.keep_threads:
                self.klipper_busy = True
                self.serial.write((cmd + '\n').encode('ascii'))
                self.com_logger.log_sent_data(cmd)
            self.mutex.unlock()

    def _get_next_cmd(self):
        if not self.klipper_busy:
            if self.active:
                if self.action == self.STOP:
                    self.action = self.NONE
                    self.task_list = []
                elif self.action == self.ABORT:
                    self.action = self.NONE
                    self.task_list = []
                    self.current_task.close()
                    self.current_task = self.post_processor.abort_task()
                    self.aborting = True

                try:
                    return self.current_task.pop()
                except:
                    self.current_task.close()
                    try:
                        self.current_task = self.task_list.pop(0)
                    except:
                        self.active = False
                        self.aborting = False
                        return None
                    return self.current_task.pop() # assumed not empty
            else:
                try:
                    return self.manual_cmd_queue.get_nowait()
                except queue.Empty:
                    pass

                if self.action == self.START:
                    self.action = self.NONE
                    self.task_list = self.project.generate_tasks(self.post_processor, self.dry_run)
                    try:
                        self.current_task = self.task_list.pop(0)
                    except:
                        return None
                    self.active = True
                    return self.current_task.pop() # current_task should never be empty here
                else:
                    return None

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
