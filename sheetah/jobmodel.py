#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import numpy as np
import pathlib, math
from dataclasses import dataclass
from dxfloader import DXFLoader
from shapely import affinity
import shapely

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

    def __init__(self, name, index, polygon):
        super().__init__()
        self._name = name
        self._index = index

        #TODO use default params handler to fill these attr
        self._arc_voltage = 110.0
        self._exterior_clockwise = False
        self._feedrate = 10000
        self._kerf_width = 2.0
        self._pierce_delay = 500
        self._position = np.array([10.,10.])
        self._angle = 0.

        sign = -1.0 if self._exterior_clockwise else 1.0
        polygon = shapely.geometry.polygon.orient(polygon, sign=sign)
        self.part_shape = polygon
        self.cut_shape = self.part_shape_mov = self.cut_shape_mov = None

        self.contour_count = len(self.part_shape.interiors) + 1
        self.cut_count = 0
        self.lead_pos = self.cut_state = list()

        self.need_contour_transform = False
        self.need_affine_transform = False

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
        if self.need_affine_transform:
            self._affine_transform()
        return np.array(self.cut_shape_mov.bounds)
    def get_size(self):
        if self.need_affine_transform:
            self._affine_transform()
        rel_bounds = np.array(self.cut_shape.bounds)
        return rel_bounds[2:] - rel_bounds[:2]
    def get_cut_count(self):
        return self.cut_count
    def get_part_array(self, index):
        if self.need_contour_transform:
            self._contour_transform()
        if self.need_affine_transform:
            self._affine_transform()
        return self.part_arrays[index]
    def get_cut_array(self, index):
        if self.need_contour_transform:
            self._contour_transform()
        if self.need_affine_transform:
            self._affine_transform()
        return self.cut_arrays[index]
    def _contour_transform(self):
        self.cut_shape = self.part_shape.buffer(self._kerf_width,
                                                resolution=32,
                                                cap_style=1,
                                                join_style=1)
        sign = -1.0 if self._exterior_clockwise else 1.0
        self.cut_shape = shapely.geometry.polygon.orient(self.cut_shape, sign=sign)
        updated_cut_count = len(self.cut_shape.interiors) + 1
        if updated_cut_count != self.cut_count:
            self.cut_count = updated_cut_count
            self.lead_pos = [0.] * self.cut_count
            self.cut_state = [self.TODO] * self.cut_count
        self.need_contour_transform = False
        self.need_affine_transform = True
    def _affine_transform(self):
        r_rad = self._angle / 180 * math.pi
        a = math.cos(r_rad)
        b = math.sin(r_rad)
        coeffs = [a,-b, b, a] + list(self._position)
        self.part_shape_mov = affinity.affine_transform(self.part_shape, coeffs)
        self.cut_shape_mov = affinity.affine_transform(self.cut_shape, coeffs)
        self.part_arrays = list()
        rings = list(self.part_shape_mov.interiors) + [self.part_shape_mov.exterior]
        for ring in rings:
            self.part_arrays.append(np.array(ring.coords.xy))
        self.cut_arrays = list()
        rings = list(self.cut_shape_mov.interiors) + [self.cut_shape_mov.exterior]
        for ring in rings:
            self.cut_arrays.append(np.array(ring.coords.xy))
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
            polygons = DXFLoader.load(filename)
        except Exception as e:
            print('Unable to load ' + path.name + ', ' + str(e))
            return

        if len(polygons) > 1:
            for i, polygon in enumerate(polygons):
                self.job_list.append(JobModel(name + '_' + str(i), index+i, polygon))
        elif polygons:
            self.job_list.append(JobModel(name, index, polygons[0]))
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
