#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import shapely.geometry as geo
import numpy as np
import pathlib, math
from dataclasses import dataclass
from dxfloader import DXFLoader

def dist_abc(points):
    a = points[:,:-2]  # left
    b = points[:,2:]   # right
    c = points[:,1:-1] # mid
    ab = b-a
    ca = a-c
    dist = np.abs(np.cross(ab, ca, axis=0)) / np.linalg.norm(ab, axis=0)
    return np.hstack((np.inf, dist, np.inf))

def decimate(points, tol):
    accu = np.zeros(points.shape[1])
    dist = dist_abc(points)
    while True:
        i = np.argmin(dist)
        if dist[i] + accu[i] < tol:
            accu[i-1] += dist[i]
            accu[i+1] += dist[i]
            accu = np.delete(accu, i)
            points = np.delete(points, i, axis=1)
            dist = np.delete(dist, i)
            dist[i-1:i+1] = dist_abc(points[:,i-2:i+2])[1:3]
        else:
            break
    return points

class Task():
    def __init__(self, cmd_list):
        self.cmd_list = cmd_list
        self.cmd_index = 0

    def __str__(self):
        return str(self.cmd_list)

    def pop(self):
        cmd = self.cmd_list[self.cmd_index]
        self.cmd_index += 1
        return cmd

    def close(self):
        self.cmd_list = []

class JobTask(Task):
    def __init__(self, cmd_list, job, id, dry_run):
        super().__init__(cmd_list)
        self.job = job
        self.id = id
        self.dry_run = dry_run

    def pop(self):
        if not self.dry_run and self.cmd_index == 0:
            self.job.set_state(self.id, JobModel.RUNNING)
        return super().pop()

    def close(self):
        if not self.dry_run:
            if self.cmd_index >= len(self.cmd_list):
                self.job.set_state(self.id, JobModel.DONE)
            else:
                self.job.set_state(self.id, JobModel.FAILED)
        super().close()

@dataclass(order=True)
class JobModel(QtCore.QObject):
    index: int # first parameter used for job sorting #TODO only use this one

    shape_update = QtCore.pyqtSignal()
    param_update = QtCore.pyqtSignal()
    state_update = QtCore.pyqtSignal()

    TODO    = 0
    RUNNING = 1
    DONE    = 2
    FAILED  = 3
    IGNORED = 4
    _states = (TODO, RUNNING, DONE, FAILED, IGNORED)

    def __init__(self, name, index, polygon=None, paths=[]):
        super().__init__()
        self._name = name
        self._index = index
        self.need_contour_transform = self.need_affine_transform = False

        #TODO use default params handler to fill these attr
        self._arc_voltage = 150.0
        self._exterior_clockwise = True
        self._feedrate = 5000
        self._kerf_width = 1.5
        self._pierce_delay = 500
        self._position = np.array([10.,10.])
        self._angle = 0.

        self.surf = polygon # surface polygon
        self.surf_bf = None # buffered surface polygon
        self.paths = paths  # open path LineStrings

        # surface numpy representations (origin and affine transformed)
        self.surf_arr = self.surf_tr_arr = []
        self.surf_bf_arr = self.surf_bf_tr_arr = []

        # paths numpy representations (origin and affine transformed)
        self.path_arr = self.path_tr_arr = []

        if self.surf is not None:
            self.contour_count = len(self.paths) + len(self.surf.interiors) + 1
            self.cut_count = 0
            # generate surf_arr
            for ring in list(self.surf.interiors) + [self.surf.exterior]:
                self.surf_arr.append(np.array(ring.coords.xy))
        else:
            self.contour_count = self.cut_count = len(self.paths)
            self.lead_pos = [0.] * self.cut_count
            self.cut_state = [self.TODO] * self.cut_count

        # generate path_arr
        for path in self.paths:
            self.path_arr.append(np.array(path.coords.xy))

        self._contour_transform()
        self._affine_transform()

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, n):
        self._name = n

    @property
    def index(self):
        return self._index
    @index.setter
    def index(self, i):
        self._index = i

    @property
    def position(self):
        return self._position
    @position.setter
    def position(self, p):
        self._position = np.array(p)
        self.need_affine_transform = True
        self.shape_update.emit()

    @property
    def angle(self):
        return self._angle
    @angle.setter
    def angle(self, a):
        """Set job angle in degrees."""
        self._angle = a
        self.need_affine_transform = True
        self.shape_update.emit()

    @property
    def exterior_clockwise(self):
        return self._exterior_clockwise
    @exterior_clockwise.setter
    def exterior_clockwise(self, e):
        self._exterior_clockwise = e
        self.need_contour_transform = True
        self.shape_update.emit()
        self.param_update.emit()

    @property
    def kerf_width(self):
        return self._kerf_width
    @kerf_width.setter
    def kerf_width(self, k):
        self._kerf_width = k
        self.need_contour_transform = True
        self.shape_update.emit()
        self.param_update.emit()

    @property
    def arc_voltage(self):
        return self._arc_voltage
    @arc_voltage.setter
    def arc_voltage(self, v):
        self._arc_voltage = v
        self.param_update.emit()

    @property
    def feedrate(self):
        return self._feedrate
    @feedrate.setter
    def feedrate(self, f):
        self._feedrate = f
        self.param_update.emit()

    @property
    def pierce_delay(self):
        return self._pierce_delay
    @pierce_delay.setter
    def pierce_delay(self, d):
        self._pierce_delay = d
        self.param_update.emit()

    def set_lead_pos(self, index, pos):
        self.lead_pos[index] = pos
        self.shape_update.emit()

    def get_state(self, index):
        return self.cut_state[index]

    def set_state(self, index, state):
        """Set state of a particular cut."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        self.cut_state[index] = state
        self.state_update.emit()
        self.shape_update.emit()

    def state_index(self, state):
        """Return index of the first cut matching state, -1 otherwise."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        try:
            index = self.cut_state.index(state)
        except:
            index = -1
        return index

    def state_indices(self, state):
        """Return indices of cuts matching state."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        return [i for i, s in enumerate(self.cut_state) if s==state]

    def get_bounds(self):
        self._check_transform()
        arr = np.hstack(self.get_cut_arrays())
        return np.concatenate((np.amin(arr, axis=1), np.amax(arr, axis=1)))

    def get_size(self):
        bounds = self.get_bounds()
        return bounds[2:] - bounds[:2]

    def get_cut_count(self):
        return self.cut_count

    def get_part_arrays(self):
        self._check_transform()
        return (self.path_tr_arr + self.surf_tr_arr)

    def get_cut_arrays(self):
        self._check_transform()
        return (self.path_tr_arr + self.surf_bf_tr_arr)

    def _check_transform(self):
        if self.need_contour_transform:
            self._contour_transform()
        if self.need_affine_transform:
            self._affine_transform()

    def _contour_transform(self):
        if self.surf is not None:
            self.surf_bf = self.surf.buffer(self._kerf_width, resolution=32,
                                            cap_style=1, join_style=1)
            sign = -1.0 if self._exterior_clockwise else 1.0
            self.surf_bf = geo.polygon.orient(self.surf_bf, sign=sign)

            self.surf_bf_arr = []
            for ring in list(self.surf_bf.interiors) + [self.surf_bf.exterior]:
                arr = np.array(ring.coords.xy)
                decimated = decimate(arr, 1e-2)
                self.surf_bf_arr.append(decimated)

            cut_count = len(self.surf_bf.interiors) + 1 + len(self.paths)
            if cut_count != self.cut_count:
                self.cut_count = cut_count
                self.lead_pos = [0.] * self.cut_count
                self.cut_state = [self.TODO] * self.cut_count

        self.need_affine_transform = True
        self.need_contour_transform = False

    def _apply_tr_mat(tr_mat, arr):
        return np.dot(tr_mat, np.insert(arr, 2, 1., axis=0))[:-1]

    def _affine_transform(self):
        self.surf_tr_arr = []
        self.surf_bf_tr_arr = []
        self.path_tr_arr = []

        #prepare transform matrix
        r_rad = self._angle / 180 * math.pi
        cos = math.cos(r_rad)
        sin = math.sin(r_rad)
        tr_mat = np.array([[cos,-sin, self._position[0]],
                           [sin, cos, self._position[1]],
                           [  0,   0,                1]])

        for arr in self.surf_arr:
            self.surf_tr_arr.append(JobModel._apply_tr_mat(tr_mat, arr))
        for arr in self.surf_bf_arr:
            self.surf_bf_tr_arr.append(JobModel._apply_tr_mat(tr_mat, arr))
        for arr in self.path_arr:
            self.path_tr_arr.append(JobModel._apply_tr_mat(tr_mat, arr))

        self.need_affine_transform = False

class JobManager(QtCore.QThread):
    update = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.job_list = list()

        self.busy = False
        self.pause_required = False

    def load_job(self, filename):
        path = pathlib.Path(filename)
        name = path.stem.capitalize()

        if self.job_list:
            self.job_list.sort()
            index = self.job_list[-1].index + 1
        else:
            index = 0

        try:
            parts = DXFLoader.load(filename)
        except Exception as e:
            print('Unable to load ' + path.name + ', ' + str(e))
            return

        if len(parts) > 1:
            for i, p in enumerate(parts):
                self.job_list.append(JobModel(name + '_' + str(i), index+i, p[0], p[1]))
        elif parts:
            self.job_list.append(JobModel(name, index, parts[0][0], parts[0][1]))
        self.update.emit()

    def remove_job(self, job):
        if not self.busy:
            self.job_list.remove(job)
            self.update.emit()

    def generate_tasks(self, post_processor, dry_run):
        tasks = []
        for job in self.job_list:
            for i in job.state_indices(JobModel.TODO):
                tasks.append(post_processor.generate(job, i, dry_run))
        if tasks:
            tasks.insert(0, post_processor.init_task())
        return tasks
