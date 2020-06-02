#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import numpy as np
import serial, queue
import regex as re

from controllerinterface import ControllerInterface
from jobmodel import JobModel

class GenericThread(QtCore.QThread):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self, *args):
        self.function(*self.args, **self.kwargs)

class QLogger(QtCore.QObject):
    log_available = QtCore.pyqtSignal()
    thc_update = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.thc_data = np.zeros(1000)
    def log_received_data(self, text):
        self.queue.put((text, True))
        self.log_available.emit()
    def log_sent_data(self, text):
        self.queue.put((text, False))
        self.log_available.emit()
    def empty(self):
        return self.queue.empty()
    def get(self):
        return self.queue.get()
    def log_thc_data(self, val):
        self.thc_data[:-1] = self.thc_data[1:]
        self.thc_data[-1] = val
        self.thc_update.emit()

class KlipperController(ControllerInterface):
    def __init__(self, job_manager, post_processor):
        self.job_manager = job_manager
        self.post_processor = post_processor

        self.serial = serial.Serial()
        self.keep_threads = False
        self.cmd_delimiter = '\n'
        self.input_buffer = ''
        self.klipper_busy = False

        self.input_thread = GenericThread(self._input_worker)
        self.output_thread = GenericThread(self._output_worker)
        self.mutex = QtCore.QMutex()
        self.send_cond = QtCore.QWaitCondition()

        self.state = 'disconnected'
        self.job_list = list()
        self.current_job = None
        self.current_task = -1
        self.cmd_list = list()
        self.manual_cmd_queue = queue.Queue()

        self.logger = QLogger()

    def __del__(self):
        self.disconnect()

    def start(self):
        if self.state == 'connected':
            # TODO lock job_manager state

            self.job_list = self.job_manager.pending_jobs()
            if not self.job_list:
                return

            self.current_job = self.job_list.pop(0)
            self.current_job.activate()
            self.cmd_list = self.post_processor.start_sequence()
            self.klipper_busy = False
            self.state = 'running'
            self.send_cond.wakeOne()

    def stop(self):
        if self.state != 'disconnected':
            self.state = 'connected'
            self.job_list = list()
            self.current_job = None # TODO set state fail?
            self.current_task = -1
            self.cmd_list = list()
            # TODO unlock job_manager state

    def pause(self):
        if self.state == 'running':
            self.state = 'paused'

    def resume(self):
        if self.state == 'paused':
            self.state = 'running'
            self.send_cond.wakeOne()

    def connect(self, port):
        # if not self.serial.is_open:
        if self.state == 'disconnected':
            try:
                self.serial = serial.Serial(port, timeout=0.2)
            except:
                raise Exception('Cannot open port ' + port)
            self.keep_threads = True
            self.input_thread.start()
            self.output_thread.start()
            self.state = 'connected'

    def disconnect(self):
        # if self.serial.is_open:
        if self.state != 'disconnected':
            self.mutex.lock()
            self.keep_threads = False
            self.send_cond.wakeOne()
            self.mutex.unlock()
            self.input_thread.wait()
            self.output_thread.wait()
            self.serial.close()
            self.state = 'disconnected'

    def _input_worker(self):
        while self.keep_threads:
            line = ''
            # TODO use self.cmd_delimiter instead '\n'
            while (not line or line[-1] != '\n') and self.keep_threads:
                line += self.serial.readline().decode('ascii')
            if self.keep_threads:
                self.mutex.lock()
                self._process_input_line(line)
                self.mutex.unlock()

    def _output_worker(self):
        while self.keep_threads:
            self.mutex.lock()
            while not self._send_required() and self.keep_threads:
                self.send_cond.wait(self.mutex)
            if self.keep_threads:
                cmd = self._next_cmd()
                self.serial.write((cmd + self.cmd_delimiter).encode('ascii'))
                self.logger.log_sent_data(cmd)
            self.mutex.unlock()

    def send_manual_cmd(self, cmd):
        if self.state == 'connected' or self.state == 'paused':
            # remove leading/trailing spaces
            cmd = re.sub(r'(^\s*)|(\s*$)', '', cmd)
            self.manual_cmd_queue.put(cmd)
            self.send_cond.wakeOne()
            return True
        return False

    def _process_input_line(self, line):
        line = line.rstrip()
        if line == 'ok':
            self.klipper_busy = False
            self.send_cond.wakeOne()
        # elif line[:2] == '!!':
        #     pass
        elif line[:18] == '// echo: THC_error':
            words = line.split()
            # v1 = float(words[3])
            v2 = float(words[4])
            self.logger.log_thc_data(v2)
            return
        # else:
        #     pass
        self.logger.log_received_data(line)

    def _pull_next_job(self):
        if not self.job_list:
            self.state = 'connected'
        else:
            self.current_job = self.job_list.pop(0)
            self.current_job.activate()

    def _pull_next_task(self):
        self.current_task = self.current_job.state_index(JobModel.TODO)
        if self.current_task < 0:
            self._pull_next_job()
            if self.current_job is not None:
                self.current_task = self.current_job.state_index(JobModel.TODO)

    def _pull_next_cmds(self):
        if self.current_task >= 0:
            self.current_job.set_state(self.current_task, JobModel.DONE)
        self._pull_next_task()
        if self.current_task >= 0:
            self.cmd_list = self.post_processor.generate(self.current_job,
                                                         self.current_task)

    def _send_required(self):
        if self.state == 'running':
            if not self.cmd_list:
                self._pull_next_cmds()

        cmd_available = self.cmd_list or not self.manual_cmd_queue.empty()
        return cmd_available and not self.klipper_busy

    def _next_cmd(self):
        self.klipper_busy = True
        if not self.manual_cmd_queue.empty():
            return self.manual_cmd_queue.get_nowait()
        else:
            return self.cmd_list.pop(0)
