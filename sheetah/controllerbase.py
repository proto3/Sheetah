#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from abc import abstractmethod
import regex as re
import sys, queue

from job import Job, Task

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
    incident = QtCore.pyqtSignal(str)
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

class ControllerBase(QtCore.QObject):
    link_state_update = QtCore.pyqtSignal()
    ST_UNCO = 0
    ST_INAC = 1
    ST_ACTI = 2
    ST_SAFE = 3
    def __init__(self, project, post_processor):
        super().__init__()
        self.project = project
        self.post_processor = post_processor

        self.keep_workers = False
        self.input_thread = GenericThread(self._input_worker)
        self.output_thread = GenericThread(self._output_worker)
        self.send_cond = QtCore.QWaitCondition()
        self.mutex = QtCore.QMutex()

        # NOTE better use SimpleQueue in 3.7
        self.manual_cmd_queue = queue.Queue()
        self.com_logger = CommunicationLogger()
        self.state = self.ST_UNCO

    def __del__(self):
        self.disconnect()

    def run_file(self, filename):
        """Run a raw GCode from file.
        """
        if self.is_inactive():
            with open(filename) as f:
                cmd_list = f.read().splitlines()
            if cmd_list:
                self.mutex.lock()
                self._kickstart(Task(cmd_list))
                self.mutex.unlock()

    def run(self, dry_run):
        """Make post-processor generate project's GCode as a list of tasks and
        start running it.
        """
        self.mutex.lock()
        if self.is_inactive():
            tasks = self.project.generate_tasks(self.post_processor, dry_run)
            self.task_list = tasks
            try:
                task = self.task_list.pop(0)
            except:
                print('No job to run.')
            else:
                self._kickstart(task)
                self.send_cond.wakeOne()
        self.mutex.unlock()

    def stop(self):
        """Discard any tasks and manual commands except the one running.
        """
        self.mutex.lock()
        if self.is_active():
            self.manual_cmd_queue.queue.clear()
            self.task_list = []
        self.mutex.unlock()

    def abort(self):
        """Discard all tasks and commands, setup emergency task instead and
        switch to safe mode to prevent any interruption of the emergency task.
        """
        self.mutex.lock()
        if self.is_active():
            self._enter_safe_mode()
        self.mutex.unlock()

    def _abort_internal(self, message):
        """Internal version of abort with mutex acquired on caller side and
        error logging.
        """
        if self.is_active():
            self._enter_safe_mode()
            self.com_logger.incident.emit(message)

    def _enter_safe_mode(self):
        """Factorization of abort and _abort_internal behaviour.
        """
        self.manual_cmd_queue.queue.clear()
        self.cur_task.fail()
        self.task_list = [self.post_processor.emergency_task()]
        self.state = self.ST_SAFE

    def send_manual_cmd(self, cmd):
        """Push a manual command to waiting queue and eventually kickstart it.
        """
        self.mutex.lock()
        # remove leading/trailing spaces
        cmd = re.sub(r'(^\s*)|(\s*$)', '', cmd)
        if self.is_active():
            self.manual_cmd_queue.put(cmd)
        elif self.is_inactive():
            self._kickstart(Task([cmd]))
        self.mutex.unlock()

    @abstractmethod
    def _link_open(self, *args, **kwargs):
        """Open communication link."""
        pass

    @abstractmethod
    def _link_close(self):
        """Close communication link."""
        pass

    @abstractmethod
    def _link_read(self):
        """Blocking read with timeout. Return complete line or empty string."""
        pass

    @abstractmethod
    def _link_send(self, cmd):
        """Sends a command and eventually adds end characters to it."""
        pass

    @abstractmethod
    def _link_busy(self):
        """Return True when machine controller is ready for next command to be
        sent. Implementation can use self.next_cmd if length information is
        needed.
        """
        pass

    @abstractmethod
    def _process_input(self, input):
        """Parse a line from the machine controller."""
        pass

    def is_unconnected(self):
        return self.state == self.ST_UNCO
    def is_inactive(self):
        return self.state == self.ST_INAC
    def is_active(self):
        return self.state == self.ST_ACTI
    def in_safe_mode(self):
        return self.state == self.ST_SAFE

    def connect(self, *args, **kwargs):
        """Connect to machine controller."""
        if self.is_unconnected():
            try:
                self._link_open(args, kwargs)
            except Exception as e:
                print('Connection failed: ' + str(e), file=sys.stderr)
            else:
                self.task_list = []
                self.cur_task = None
                self.next_cmd = None
                self.keep_workers = True
                self.input_thread.start()
                self.output_thread.start()
                self.state = self.ST_INAC
                self.link_state_update.emit()

    def disconnect(self):
        """Close link with machine controller. It can be called either from
        external thread or its self worker threads.
        """
        if self.is_inactive():
            self.mutex.lock()
            self.keep_workers = False
            self.send_cond.wakeOne()
            self.mutex.unlock()
            if QtCore.QThread.currentThread() != self.input_thread:
                self.input_thread.wait()
            if QtCore.QThread.currentThread() != self.output_thread:
                self.output_thread.wait()
            self._link_close()
            self.state = self.ST_UNCO
            self.link_state_update.emit()

    def _input_worker(self):
        """Input thread working loop."""
        while self.keep_workers:
            line = ''
            while (not line or line[-1] != '\n') and self.keep_workers:
                try:
                    line += self._link_read()
                except Exception as e:
                    print('Link read failed: ' + str(e), file=sys.stderr)
                    self.disconnect()
                    return
            if self.keep_workers:
                line = line.rstrip()
                self.mutex.lock()
                self._process_input(line)
                self.com_logger.log_received_data(line)
                self.mutex.unlock()

    def _output_worker(self):
        """Output thread working loop."""
        while self.keep_workers:
            self.mutex.lock()
            while ((self.next_cmd is None or self._link_busy()) and
                   self.keep_workers):
                self.send_cond.wait(self.mutex)
            if self.keep_workers:
                try:
                    self._link_send(self.next_cmd)
                except Exception as e:
                    self.mutex.unlock()
                    print('Link send failed: ' + str(e), file=sys.stderr)
                    self.disconnect()
                    return
                self.com_logger.log_sent_data(self.next_cmd)
                self.next_cmd = None
            self.mutex.unlock()

    def _kickstart(self, task):
        """Wake up worker thread to run task."""
        self.cur_task = task
        self.next_cmd = self.cur_task.pop()
        self.state = self.ST_ACTI
        self.send_cond.wakeOne()

    def _pop_next_cmd(self):
        """In active mode, return manual command if one is available
        otherwise pop next command from tasks.
        In safe mode, only consider commands from task.
        If no command at all or in another mode, return None.
        """
        if self.is_active():
            try:
                manual_cmd = self.manual_cmd_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                if self.cur_task is None:
                    self.cur_task = Task([manual_cmd])
                else:
                    return manual_cmd
        if self.is_active() or self.in_safe_mode():
            try:
                return self.cur_task.pop()
            except IndexError:
                self.cur_task.close()
                try:
                    self.cur_task = self.task_list.pop(0)
                except IndexError:
                    self.cur_task = None
                    self.state = self.ST_INAC
                else:
                    return self.cur_task.pop()
        return None

    def _complete_cmd(self):
        """Function to be called by input parser when a command is completed.
        """
        self.next_cmd = self._pop_next_cmd()
        self.send_cond.wakeOne()

class JobErrorDialog(QtWidgets.QDialog):
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Job incident')
        std_btns = QtWidgets.QDialogButtonBox.Ok
        self.buttonBox = QtWidgets.QDialogButtonBox(std_btns)
        self.buttonBox.accepted.connect(self.accept)
        name_label = QtWidgets.QLabel(msg, alignment=QtCore.Qt.AlignCenter)
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

    def on_incident(self, msg):
        j = JobErrorDialog(msg[3:], self)
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
        self.controller.send_manual_cmd(text)
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

        self.dry_run_checker = QtWidgets.QCheckBox('DryRun')
        self.run_btn = QtWidgets.QPushButton('Run')
        self.stop_btn = QtWidgets.QPushButton('Stop')
        self.abort_btn = QtWidgets.QPushButton('Abort')
        self.run_file_btn = QtWidgets.QPushButton('Run file')
        self.connect_btn = QtWidgets.QPushButton('Connect')
        self.run_btn.clicked.connect(self.on_run)
        self.stop_btn.clicked.connect(self.on_stop)
        self.abort_btn.clicked.connect(self.on_abort)
        self.run_file_btn.clicked.connect(self.on_run_file)
        self.connect_btn.clicked.connect(self.on_connect)
        self.controller.link_state_update.connect(self.on_link_state_update)

        self.btn_box = QtWidgets.QGroupBox()
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.dry_run_checker)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.abort_btn)
        layout.addWidget(self.run_file_btn)
        layout.addWidget(self.connect_btn)
        self.btn_box.setLayout(layout)

    def on_run_file(self):
        filename, _ = QtGui.QFileDialog.getOpenFileName(self,
                      'Open File', QtCore.QDir.currentPath(),
                      'gcode (*.gcode);; All Files (*)')
        if filename:
            self.controller.run_file(filename)

    def on_run(self):
        self.controller.run(self.dry_run_checker.isChecked())
    def on_stop(self):
        self.controller.stop()
    def on_abort(self):
        self.controller.abort()
    def on_connect(self):
        if self.controller.is_unconnected():
            self.controller.connect()
        else:
            self.controller.disconnect()
    def on_link_state_update(self):
        if self.controller.is_unconnected():
            self.connect_btn.setText('Connect')
        else:
            self.connect_btn.setText('Disconnect')
