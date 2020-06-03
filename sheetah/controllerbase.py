#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
from abc import ABC, abstractmethod
import regex as re
import queue
from jobmodel import JobModel

class InputDecisionTree:
    def __init__(self, default_function=None):
        self._prefix = ''
        self._function = default_function
        self._children = []

    def _node_create(prefix, function):
        node = InputDecisionTree.__new__(InputDecisionTree)
        node._prefix = prefix
        node._function = function
        node._children = []
        return node

    def append_node(self, prefix, function):
        node = InputDecisionTree._node_create(prefix, function)
        pos = self
        pos_changed = True
        while pos_changed:
            pos_changed = False
            for child in pos._children:
                if node._prefix.startswith(child._prefix):
                    pos = child
                    pos_changed = True
                    break
        node_children = [index for index, child in enumerate(pos._children)
                         if child._prefix.startswith(node._prefix)]
        for index in sorted(node_children, reverse=True):
            node._children.append(pos._children.pop(index))
        pos._children.append(node)

    def process_input(self, input):
        pos = self
        pos_changed = True
        while pos_changed:
            pos_changed = False
            for child in pos._children:
                if input.startswith(child._prefix):
                    pos = child
                    pos_changed = True
                    break
        if pos._function is not None:
            pos._function(input)

class CommunicationLogger(QtCore.QObject):
    log_available = QtCore.pyqtSignal()
    incident = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
    def log_received_data(self, text):
        if not text.startswith('// echo: THC_error'):
            self.queue.put((text, True))
            self.log_available.emit()
    def log_sent_data(self, text):
        self.queue.put((text, False))
        self.log_available.emit()
    def empty(self):
        return self.queue.empty()
    def get(self):
        return self.queue.get()

class GenericThread(QtCore.QThread):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self, *args):
        self.function(*self.args, **self.kwargs)

class ControllerBase(ABC):
    NONE  = 0
    START = 1
    STOP  = 2
    ABORT = 3
    def __init__(self, job_manager, post_processor):
        self.job_manager = job_manager
        self.post_processor = post_processor
        self.input_parser = InputDecisionTree()
        self.cmd_it = None

        self.keep_threads = False
        self.input_thread = GenericThread(self._input_worker)
        self.output_thread = GenericThread(self._output_worker)
        self.send_cond = QtCore.QWaitCondition()
        self.mutex = QtCore.QMutex()

        self.connected = False
        self.active = False
        self.action = self.NONE

        self.manual_cmd_queue = queue.Queue()
        self.com_logger = CommunicationLogger()

    def __del__(self):
        self.disconnect()

    def start(self):
        if not self.active and self.action == self.NONE:
            self.action = self.START
            self.send_cond.wakeOne()

    def stop(self):
        if self.active and self.action != self.ABORT:
            self.action = self.STOP

    def abort(self):
        if self.active:
            self.action = self.ABORT

    def send_manual_cmd(self, cmd):
        if self.connected and not self.active:
            # remove leading/trailing spaces
            cmd = re.sub(r'(^\s*)|(\s*$)', '', cmd)
            self.manual_cmd_queue.put(cmd)
            self.send_cond.wakeOne()
            return True
        return False

    @abstractmethod
    def connect(self, *args, **kwargs):
        pass
    @abstractmethod
    def disconnect(self):
        pass
    @abstractmethod
    def _input_worker(self):
        pass
    @abstractmethod
    def _output_worker(self):
        pass

class JobErrorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Job incident')
        std_btns = QtWidgets.QDialogButtonBox.Ok
        self.buttonBox = QtWidgets.QDialogButtonBox(std_btns)
        self.buttonBox.accepted.connect(self.accept)
        name_label = QtWidgets.QLabel('message', alignment=QtCore.Qt.AlignCenter)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(name_label)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

class ConsoleWidget(QtWidgets.QWidget):
    hist_filename = '.cmd_history'
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
        self.setLayout(layout)

        self.controller.com_logger.log_available.connect(self.on_log)
        self.user_input_w.returnPressed.connect(self.on_user_input)

        self.controller.com_logger.incident.connect(self.on_incident)

        QtWidgets.QShortcut(QtCore.Qt.Key_Up, self.user_input_w, self.key_up)
        QtWidgets.QShortcut(QtCore.Qt.Key_Down, self.user_input_w, self.key_down)

    def on_incident(self):
        j = JobErrorDialog(self)
        j.exec_()

    def on_log(self):
        while not self.controller.com_logger.empty():
            log = self.controller.com_logger.get()
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

class ControllerUIBase(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.console = ConsoleWidget(self.controller)

        self.start_btn = QtWidgets.QPushButton('Start')
        self.stop_btn = QtWidgets.QPushButton('Abort')
        self.pause_btn = QtWidgets.QPushButton('Stop')
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.pause_btn.clicked.connect(self.on_pause)

        self.btn_box = QtWidgets.QGroupBox()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.pause_btn)
        self.btn_box.setLayout(layout)

    def on_start(self):
        self.controller.start()
    def on_stop(self):
        self.controller.abort()
    def on_pause(self):
        self.controller.stop()
