#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import numpy as np
import pathlib, math
from dataclasses import dataclass
from dxfloader import DXFLoader
from shapely import affinity
import shapely

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
    SKIPPED = 4
    DRYRUN  = 5
    _states = (TODO, RUNNING, DONE, FAILED, SKIPPED, DRYRUN)

    def __init__(self, name, index, polygon):
        super().__init__()
        self._name = name
        self._index = index
        self._activated = False

        #TODO use default params handler to fill these attr
        self._arc_voltage = 110.0
        self._exterior_clockwise = False
        self._feedrate = 2000
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
        if not self._activated:
            self._position = np.array(p)
            self.need_affine_transform = True
            self.shape_update.emit()

    @property
    def angle(self):
        return self._angle
    @angle.setter
    def angle(self, a):
        """Set job angle in degrees."""
        if not self._activated:
            self._angle = a
            self.need_affine_transform = True
            self.shape_update.emit()

    @property
    def exterior_clockwise(self):
        return self._exterior_clockwise
    @exterior_clockwise.setter
    def exterior_clockwise(self, e):
        if not self._activated:
            self._exterior_clockwise = e
            self.need_contour_transform = True
            self.shape_update.emit()
            self.param_update.emit()

    @property
    def kerf_width(self):
        return self._kerf_width
    @kerf_width.setter
    def kerf_width(self, k):
        if not self._activated:
            self._kerf_width = k
            self.need_contour_transform = True
            self.shape_update.emit()
            self.param_update.emit()

    @property
    def arc_voltage(self):
        return self._arc_voltage
    @arc_voltage.setter
    def arc_voltage(self, v):
        if not self._activated:
            self._arc_voltage = v
            self.param_update.emit()

    @property
    def feedrate(self):
        return self._feedrate
    @feedrate.setter
    def feedrate(self, f):
        if not self._activated:
            self._feedrate = f
            self.param_update.emit()

    @property
    def pierce_delay(self):
        return self._pierce_delay
    @pierce_delay.setter
    def pierce_delay(self, d):
        if not self._activated:
            self._pierce_delay = d
            self.param_update.emit()

    def set_lead_pos(self, index, pos):
        if not self._activated:
            self.lead_pos[index] = pos
            self.shape_update.emit()

    def activate(self):
        """Definitely freeze all job parameters to avoid modifications during
        cut.
        """
        if not self._activated:
            self._activated = True
            self.state_update.emit()
    def set_state(self, index, state):
        """Set state of a particular cut."""
        if not self._activated:
            raise Exception('Updating state before activation is forbidden.')
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        self.cut_state[index] = state
        self.state_update.emit()
    def state_indices(self, state):
        """Return indices of cuts that match state."""
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
    def get_cut_gcode(self, index, dryrun=False):
        cut_path = self.get_cut_array(index)
        gcode = list()
        gcode += ['G90',
                  'G1 Z20']
        gcode += ['G1 F6000 X' + '{:.3f}'.format(cut_path[0][0]) + ' Y' + '{:.3f}'.format(cut_path[1][0]),
                  'PROBE',
                  'G91',
                  'G1 Z3.8',
                  'M3',
                  'G4 P' + str(self._pierce_delay),
                  'G1 Z-2.3',
                  'G90',
                  'M6 V' + '{:.2f}'.format(self._arc_voltage),
                  'G1 F' + str(self._feedrate)]
        for x,y in cut_path.transpose()[1:]:
            gcode += ['G1 X' + '{:.3f}'.format(x) + ' Y' + '{:.3f}'.format(y)]
        gcode += ['M7',
                  'M5',
                  'M8']
        return gcode
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
                                                resolution=8,
                                                cap_style=1,
                                                join_style=1,
                                                mitre_limit=5.0) #TODO
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

class JobModelCollection(QtCore.QThread):
    update = QtCore.pyqtSignal()

    def __init__(self, serialmanager):
        super().__init__()
        self._sm = serialmanager
        self.job_list = list()

        self.busy = False
        self.pause_required = False

    def loadJob(self, filename):
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

    def removeJob(self, job):
        if not self.busy:
            self.job_list.remove(job)
            self.update.emit()

    def job_todo(self):
        for job in self.job_list:
            if job.has_cut_todo():
                return True
        return False

    def run(self):
        # THREAD
        self.job_list.sort()
        for job in self.job_list:
            if self.pause_required:
                #TODO do the pause
                pass
            cut_ids = job.state_indices(JobModel.TODO)
            for index in cut_ids:
                job.activate()
                contour = job.get_cut_gcode(index)
                job.set_state(index, JobModel.RUNNING)
                if self._sm.send_job(contour): #blocking
                    job.set_state(index, JobModel.DONE)
                else:
                    # TODO handle user decision to skip or retry
                    job.set_state(index, JobModel.FAILED)
        self.busy = False

    def play(self):
        self.job_list.sort()
        self.busy = True
        self.pause_required = False
        self.start()

    def stop(self):
        self.pause()
        self._sm.abort_job()

    def pause(self):
        self.pause_required = True

    def __iter__(self):
        return iter(self.job_list)
