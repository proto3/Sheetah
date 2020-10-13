from PyQt5.QtCore import QObject, pyqtSignal, QRectF
import fileutils
import pathlib
import numpy as np
import math

class Project(QObject):
    job_update = pyqtSignal()
    # selection_update = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.jobs = list()
        # self._selection = set()
        self.transforming = False
        self.step_transform = self.step_translate

    # @property
    # def selection(self):
    #     return self._selection
    #
    # def set_selection(self, selection):
    #     if not (isinstance(selection, set) or isinstance(selection, list)):
    #         selection = [selection]
    #     self._selection = set(selection)
    #     self.selection_update.emit()

    def load_job(self, filepath):
        try:
            self.jobs += fileutils.load(filepath)
            self.job_update.emit()
        except Exception as e:
            filename = pathlib.Path(filepath).name
            print('Unable to load ' + filename + ', ' + str(e))

    # assuming job exists
    def remove_job(self, job):
        self.jobs.remove(job)
        self.job_update.emit()

    def remove_jobs(self, jobs):
        unwanted_jobs = set(jobs)
        self.jobs = [j for j in self.jobs if j not in unwanted_jobs]
        self.job_update.emit()

    # mode should be either 'translate', 'rotate' or 'scale'
    # def set_transform_mode(self, mode):
    #     if mode == 'translate':
    #         self.step_transform = self.step_translate
    #     elif mode == 'rotate':
    #         self.step_transform = self.step_rotate
    #     elif mode == 'scale':
    #         self.step_transform = self.step_scale

    def end_transform(self):
        self.transforming = False

    def step_translate(self, pos, prev_pos, down_pos):
        dir = pos - prev_pos
        if not self.transforming:
            self.transforming = True
        for job in self._selection:
            job.position += dir

    # def selection_center(self):
    #     if self._selection:
    #         centroids = [job.get_centroid() for job in self._selection]
    #         return np.mean(centroids, axis=0)
    #     else:
    #         return np.zeros(2)

    def step_rotate(self, pos, prev_pos, down_pos):
        if not self.transforming:
            self.transforming = True
            self.center = self.selection_center()
            dir_vect = down_pos - self.center
            self.prev_angle = math.atan2(dir_vect[1], dir_vect[0])
        dir_vect = pos - self.center
        angle = math.atan2(dir_vect[1], dir_vect[0])
        diff_angle = angle - self.prev_angle
        for job in self._selection:
            job.turn_around(self.center, diff_angle)
        self.prev_angle = angle

    def step_scale(self, pos, prev_pos, down_pos):
        if not self.transforming:
            self.transforming = True
            self.center = self.selection_center()
            self.prev_dist = np.linalg.norm(down_pos - self.center)
        dist = np.linalg.norm(pos - self.center)
        scale = (dist + 1) / (self.prev_dist + 1) # just prevent divide by zero
        for job in self._selection:
            job.scale_around(self.center, scale)
        self.prev_dist = dist

    # def generate_tasks(self, post_processor, dry_run):
    #     tasks = []
    #     for job in self.jobs:
    #         for i in job.cut_state_indices(Job.TODO):
    #             tasks.append(post_processor.generate(job, i, dry_run))
    #     if tasks:
    #         tasks.insert(0, post_processor.init_task())
    #     return tasks
