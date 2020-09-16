#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import pathlib

import fileutils

class Project(QtCore.QObject):
    update = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.job_list = list()
        self.busy = False
        self.pause_required = False

    # def load_project_file(self, filepath):
    #     pass

    def load_job_file(self, filepath):
        # try:
        jobs = fileutils.load(filepath)
        self.job_list += jobs
        self.update.emit()
        # except Exception as e:
        #     filename = pathlib.Path(filepath).name
        #     print('Unable to load ' + filename + ', ' + str(e))

    def remove_job(self, job):
        if not self.busy:
            self.job_list.remove(job)
            self.update.emit()

    def generate_tasks(self, post_processor, dry_run):
        tasks = []
        for job in self.job_list:
            for i in job.state_indices(Job.TODO):
                tasks.append(post_processor.generate(job, i, dry_run))
        if tasks:
            tasks.insert(0, post_processor.init_task())
        return tasks
