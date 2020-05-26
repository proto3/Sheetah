#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
from dataclasses import dataclass, field
from typing import Any
import regex as re
import os, queue

HIGH_PRIORITY   = 0
MEDIUM_PRIORITY = 1
LOW_PRIORITY    = 2

class FifoPriorityQueue(queue.PriorityQueue):
    def __init__(self):
        super().__init__()
        self.insert_count = 0
    def put(self, item):
        super(FifoPriorityQueue, self).put((item, self.insert_count))
        self.insert_count += 1
    def get(self):
        return super(FifoPriorityQueue, self).get()[0]
    def get_nowait(self):
        return super(FifoPriorityQueue, self).get(block=False)[0]

@dataclass(order=True)
class CommandItem:
    _priority: int
    _cmd: Any=field(compare=False)
    _rsp: Any=field(compare=False)
    _need_rsp: Any=field(compare=False)
    _over: Any=field(compare=False)
    _aborted: Any=field(compare=False)
    def __init__(self, command, priority, need_response=False):
        self._priority = priority
        self._cmd = command
        self._rsp = list()
        self._need_rsp = need_response
        self._over = False
        self._aborted = False
    def get_command(self):
        return self._cmd
    def get_response(self):
        if self._over:
            return self._rsp
        else:
            raise Exception('Get response from incomplete command.')
    def need_response(self):
        return self._need_rsp
    def response_append(self, text):
        self._rsp.append(text)
    def is_over(self):
        return self._over
    def is_aborted(self):
        return self._aborted
    def complete(self):
        self._over = True
    def abort(self):
        self._over = True
        self._aborted = True

class GenericThread(QtCore.QThread):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def __del__(self):
        self.wait()

    def run(self, *args):
        self.function(*self.args, **self.kwargs)

class SerialManager(QtCore.QObject):
    log_available = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.command_queue = FifoPriorityQueue()
        self.logging_queue = queue.Queue()

        self.input_thread = GenericThread(self._input_worker)
        self.output_thread = GenericThread(self._output_worker)
        self.mutex = QtCore.QMutex()
        self.send_cond = QtCore.QWaitCondition()
        self.recv_cond = QtCore.QWaitCondition()

        self.running = False
        self.ongoing_cmd = False
        self.abort_pending = False

        self.endline = '\n'
        self.plasma_on = False
        self.thc_on = False

    def open(self, port):
        try:
            self.ser_fd = os.open(port, os.O_RDWR)
        except:
            raise Exception('Error: Cannot open port ' + port)

        # clear command_queue
        try:
            while True:
                self.command_queue.get_nowait()
        except queue.Empty:
            pass
        self.cur_cmd_item = None

        self.running = True
        self.ongoing_cmd = False
        self.input_thread.start()
        self.output_thread.start()

    def close(self):
        self.running = False
        self.input_thread.wait()
        self.output_thread.wait()
        self.ser_fd.close()

    def send_user_cmd(self, cmd):
        cmd = SerialManager._filter_cmd(cmd)
        if cmd:
            self.mutex.lock()
            self.command_queue.put(CommandItem(cmd, MEDIUM_PRIORITY))
            self.send_cond.wakeOne()
            self.mutex.unlock()

    def send_cmd_with_reponse(self, cmd): # BLOCKING
        cmd = SerialManager._filter_cmd(cmd)
        if not cmd:
            raise Exception('Invalid command won\'t get any response.')

        self.mutex.lock()
        cmd_item = CommandItem(cmd, LOW_PRIORITY, need_response=True)
        self.command_queue.put(cmd_item)
        self.send_cond.wakeOne()
        while not cmd_item.is_over():
            self.recv_cond.wait(self.mutex)
        self.mutex.unlock()
        return cmd_item.get_response()

    def send_job(self, cmds): # BLOCKING
        cmds = [SerialManager._filter_cmd(cmd) for cmd in cmds if cmd]
        if not cmds:
            return True
        self.mutex.lock()
        for cmd in cmds[:-1]:
            self.command_queue.put(CommandItem(cmd, LOW_PRIORITY))
        last_cmd_item = CommandItem(cmds[-1], LOW_PRIORITY, need_response=True)
        self.command_queue.put(last_cmd_item)
        self.send_cond.wakeOne()
        while not last_cmd_item.is_over():
            self.recv_cond.wait(self.mutex)
        self.mutex.unlock()
        return not last_cmd_item.is_aborted()

    def job_abort(self):
        self.abort_pending = True

    def _abort(self): # To be ran by output thread only
        cleared_command_queue = FifoPriorityQueue()
        while not self.command_queue.empty():
            cmd_item = self.command_queue.get()
            if cmd_item._priority != LOW_PRIORITY:
                cleared_command_queue.put(cmd_item)
            else:
                cmd_item.abort()
        self.command_queue = cleared_command_queue
        self.abort_pending = False
        self.recv_cond.wakeAll()
        self._log_received('JOB ABORTED')

    def _filter_cmd(cmd):
        # remove leading/trailing spaces
        cmd = re.sub(r'(^\s*)|(\s*$)', '', cmd)
        # clear command if comment
        if re.match(r'^;', cmd):
            cmd = ''
        return cmd

    def _log_received(self, text):
        self.logging_queue.put((text, True))
        self.log_available.emit()

    def _log_sent(self, text):
        self.logging_queue.put((text, False))
        self.log_available.emit()

    def _input_worker(self):
        while self.running:
            line = ''
            try:
                # TODO need a way to timeout read
                # blocking read
                line = os.read(self.ser_fd, 4096).decode('utf-8').rstrip()
            except:
                raise Exception('Error: Unable to read serial input')

            self.mutex.lock()

            if line[:2] == '!!':
                ############################
                self.job_abort()
                if self.thc_on:
                    self.command_queue.put(CommandItem('M7', HIGH_PRIORITY))
                if self.plasma_on:
                    self.command_queue.put(CommandItem('M5', HIGH_PRIORITY))
                if self.thc_on:
                    self.command_queue.put(CommandItem('M8', HIGH_PRIORITY))
                ############################
            if self.ongoing_cmd:
                if self.cur_cmd_item.need_response():
                    self.cur_cmd_item.response_append(line)
                if line == 'ok':
                    self.ongoing_cmd = False
                    self.cur_cmd_item.complete()
                    self.send_cond.wakeOne()
                    self.recv_cond.wakeAll()
            self._log_received(line)
            self.mutex.unlock()

    def _output_worker(self):
        while self.running:
            self.mutex.lock()
            if self.abort_pending:
                self._abort()

            # wait for a command and green light to send
            while self.command_queue.empty() or self.ongoing_cmd:
                self.send_cond.wait(self.mutex)
                if self.abort_pending:
                    self._abort()
            self.cur_cmd_item = self.command_queue.get_nowait()

            # send command
            self.ongoing_cmd = True
            cmd = self.cur_cmd_item.get_command()
            os.write(self.ser_fd, (cmd + self.endline).encode('utf-8'))
            self._log_sent(cmd)
            ############################
            if cmd[:2] == 'M3':
                self.plasma_on = True
            elif cmd[:2] == 'M5':
                self.plasma_on = False
            if cmd[:2] == 'M6':
                self.thc_on = True
            elif cmd[:2] == 'M7':
                self.thc_on = False
            ############################
            self.mutex.unlock()
