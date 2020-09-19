#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import fileutils
import pathlib

# class Project(QtCore.QObject):
#     update = QtCore.pyqtSignal()
#
#     def __init__(self):
#         super().__init__()
#         self.job_list = list()
#         self.busy = False
#         self.pause_required = False
#
#     # def load_project_file(self, filepath):
#     #     pass
#
#     def load_job_file(self, filepath):
#         # try:
#         jobs = fileutils.load(filepath)
#         self.job_list += jobs
#         self.update.emit()
#         # except Exception as e:
#         #     filename = pathlib.Path(filepath).name
#         #     print('Unable to load ' + filename + ', ' + str(e))
#
#     def remove_job(self, job):
#         if not self.busy:
#             self.job_list.remove(job)
#             self.update.emit()
#
#     def generate_tasks(self, post_processor, dry_run):
#         tasks = []
#         for job in self.job_list:
#             for i in job.state_indices(Job.TODO):
#                 tasks.append(post_processor.generate(job, i, dry_run))
#         if tasks:
#             tasks.insert(0, post_processor.init_task())
#         return tasks
#
#




class Project(QtCore.QObject):
    job_update = QtCore.pyqtSignal()
    selection_update = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.jobs = list()
        self._selection = set()
        self.dragging = False

    @property
    def selection(self):
        return self._selection
    @selection.setter
    def selection(self, s):
        #TODO store selection in history
        self._selection = s
        self.selection_update.emit()

    def load_job(self, filepath):
        try:
            #TODO store self.jobs in history
            self.jobs += fileutils.load(filepath)
            self.job_update.emit()
        except Exception as e:
            filename = pathlib.Path(filepath).name
            print('Unable to load ' + filename + ', ' + str(e))

    # assuming job exists
    def remove_job(self, job):
        #TODO store self.jobs in history
        self.jobs.remove(job)
        self.job_update.emit()

    def step_mov_selection(self, m):
        if not self.dragging:
            self.dragging = True
            #TODO store selected jobs position in history
        for job in self._selection:
            job.position += m

    def step_rot_selection(self, r):
        if not self.dragging:
            self.dragging = True
            #TODO store selected jobs angle in history
        for job in self._selection:
            job.rotate(r)

    def finish_drag_selection(self):
        self.dragging = False




    # def generate_tasks(self, post_processor, dry_run):
    #     tasks = []
    #     for job in self.jobs:
    #         for i in job.state_indices(Job.TODO):
    #             tasks.append(post_processor.generate(job, i, dry_run))
    #     if tasks:
    #         tasks.insert(0, post_processor.init_task())
    #     return tasks
