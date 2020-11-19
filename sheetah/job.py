#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import numpy as np
import math

class Task():
    def __init__(self, cmd_list):
        if not cmd_list:
            raise Exception('Cannot create empty task.')
        self.cmd_list = cmd_list
        self.cmd_index = 0
        self.failed = False

    def __str__(self):
        return str(self.cmd_list)

    def pop(self):
        cmd = self.cmd_list[self.cmd_index]
        self.cmd_index += 1
        return cmd

    def fail(self):
        self.failed = True
        self.close()

    def close(self):
        self.cmd_list = []

class JobTask(Task):
    def __init__(self, cmd_list, job, task_id, dry_run):
        super().__init__(cmd_list)
        self.job = job
        self.task_id = task_id
        self.dry_run = dry_run

    def pop(self):
        if not self.dry_run and self.cmd_index == 0:
            self.job.set_cut_state(self.task_id, Job.RUNNING)
        return super().pop()

    def close(self):
        super().close()
        if not self.dry_run:
            if self.failed:
                self.job.set_cut_state(self.task_id, Job.FAILED)
            else:
                self.job.set_cut_state(self.task_id, Job.DONE)

class PipelineNode:
    def __init__(self, fun, parent):
        self.fun = fun
        self.parent = parent
        self.up_to_date = False
        self.children = []

        if self.parent is not None:
            self.parent.register(self)

    def register(self, child):
        self.children.append(child)

    @property
    def data(self):
        self._update()
        return self._data

    def notify_change(self):
        self.up_to_date = False
        for child in self.children:
            child.notify_change()

    def _update(self):
        if self.parent is None:
            return False

        if not self.up_to_date:
            self.parent._update()
            self._data = self.fun(self.parent._data)
            self.up_to_date = True

class Job(QtCore.QObject):
    shape_update = QtCore.pyqtSignal()
    param_update = QtCore.pyqtSignal()
    state_update = QtCore.pyqtSignal()

    TODO    = 0
    RUNNING = 1
    DONE    = 2
    FAILED  = 3
    IGNORED = 4
    _states = (TODO, RUNNING, DONE, FAILED, IGNORED)

    def __init__(self, name, polylines):
        if not polylines:
            raise Exception('Empty job')

        super().__init__()
        self._name = name

        #TODO use default params handler to fill these attr
        self._arc_voltage = 150.0
        self._exterior_clockwise = True
        self._feedrate = 5000
        self._kerf_width = 1.5
        self._pierce_delay = 500
        self._position = np.array([0.,0.])
        self._angle = 0.
        self._scale = 1.
        self._loop_radius = 1.5

        self.root_node = PipelineNode(None, None)
        self.root_node._data = polylines

        # vector
        self.dir_node      = PipelineNode(self._apply_direction, self.root_node)
        self.scale_node    = PipelineNode(self._apply_scale, self.dir_node)
        self.offset_node   = PipelineNode(self._apply_offset, self.scale_node)
        self.lead_node     = PipelineNode(self._apply_lead, self.offset_node)
        self.loop_node     = PipelineNode(self._apply_loop, self.lead_node)
        # discrete (display only)
        self.cut_gen_node  = PipelineNode(self._generate, self.loop_node)
        self.part_gen_node = PipelineNode(self._generate_shape, self.scale_node)
        self.cut_aff_node  = PipelineNode(self._apply_affine, self.cut_gen_node)
        self.part_aff_node = PipelineNode(self._apply_affine, self.part_gen_node)

        self.cut_pline_affine_node = PipelineNode(self._apply_pline_affine, self.loop_node)

        self.cut_count = 0
        self.lead_pos = [0.] * self.cut_count
        self.cut_state = [self.TODO] * self.cut_count

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, n):
        self._name = n

    @property
    def position(self):
        return self._position
    @position.setter
    def position(self, p):
        self._position = np.array(p)
        self.cut_aff_node.notify_change()
        self.part_aff_node.notify_change()
        self.cut_pline_affine_node.notify_change()
        self.shape_update.emit()

    @property
    def angle(self):
        return self._angle
    @angle.setter
    def angle(self, a):
        """Set job angle in radians."""
        self._angle = a
        self.cut_aff_node.notify_change()
        self.part_aff_node.notify_change()
        self.cut_pline_affine_node.notify_change()
        self.shape_update.emit()

    def turn_around(self, center, angle):
        """Angle in radians."""
        self._angle += angle
        cos = math.cos(angle)
        sin = math.sin(angle)
        v = self.position - center
        self._position = center + [v[0]*cos - v[1]*sin, v[0]*sin + v[1]*cos]
        self.cut_aff_node.notify_change()
        self.part_aff_node.notify_change()
        self.cut_pline_affine_node.notify_change()
        self.shape_update.emit()

    def pos_rot_matrix(self):
        cos = math.cos(self._angle)
        sin = math.sin(self._angle)
        return np.array([[cos,-sin, self._position[0]],
                         [sin, cos, self._position[1]],
                         [  0,   0,                1]])

    @property
    def scale(self):
        return self._scale
    @scale.setter
    def scale(self, s):
        self._scale = s
        self.scale_node.notify_change()
        self.shape_update.emit()

    def scale_around(self, center, scale):
        self._scale *= scale
        v = self.position - center
        self._position = v * scale + center
        self.scale_node.notify_change()
        self.cut_aff_node.notify_change()
        self.part_aff_node.notify_change()
        self.cut_pline_affine_node.notify_change()
        self.shape_update.emit()

    @property
    def exterior_clockwise(self):
        return self._exterior_clockwise
    @exterior_clockwise.setter
    def exterior_clockwise(self, e):
        self._exterior_clockwise = e
        self.need_contour_transform = True
        self.dir_node.notify_change()
        self.shape_update.emit()
        self.param_update.emit()

    @property
    def kerf_width(self):
        return self._kerf_width
    @kerf_width.setter
    def kerf_width(self, k):
        self._kerf_width = k
        self.offset_node.notify_change()
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

    @property
    def loop_radius(self):
        return self._loop_radius
    @loop_radius.setter
    def loop_radius(self, l):
        self._loop_radius = l
        self.loop_node.notify_change()
        self.shape_update.emit()

    def set_lead_pos(self, index, pos):
        self.lead_pos[index] = pos
        self.shape_update.emit()

    def set_cut_state(self, index, state):
        """Set state of a particular cut."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        self.cut_state[index] = state
        self.state_update.emit()
        self.shape_update.emit()

    def cut_state_index(self, state):
        """Return index of the first cut matching state, -1 otherwise."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        try:
            index = self.cut_state.index(state)
        except:
            index = -1
        return index

    def cut_state_indices(self, state):
        """Return indices of cuts matching state."""
        if state not in self._states:
            raise Exception('Unknown state ' + str(state) + '.')
        return [i for i, s in enumerate(self.cut_state) if s==state]

    def get_bounds(self):
        return self.scale_node.data[-1].bounds

    def get_size(self):
        bounds = self.get_bounds()
        return bounds[1] - bounds[0]

    def get_centroid(self):
        rel_centroid = self.scale_node.data[-1].centroid
        return np.dot(self.pos_rot_matrix(), np.append(rel_centroid, 1.))[:-1]

    def get_cut_count(self):
        return self.cut_count

    def get_shape_paths(self):
        return self.part_aff_node.data

    def get_cut_paths(self):
        return (self.cut_aff_node.data, self.cut_state)

    def get_cut_plines(self):
        return self.cut_pline_affine_node.data

    def _apply_direction(self, polylines):
        directed_polylines = []
        for p in polylines[:-1]:
            if p.is_ccw() != self._exterior_clockwise:
                directed_polylines.append(p.reverse())
            else:
                directed_polylines.append(p)
        exterior = polylines[-1]
        if exterior.is_ccw() == self._exterior_clockwise:
            directed_polylines.append(exterior.reverse())
        else:
            directed_polylines.append(exterior)
        # print(directed_polylines[0].to_lines())
        return directed_polylines

    def _apply_scale(self, polylines):
        return [p.affine([0,0], 0, self._scale) for p in polylines]

    def _apply_offset(self, polylines):
        offset_polylines = []
        for p in polylines:
            if p.is_closed():
                offset_polylines += p.offset(self.kerf_width / 2)
            else:
                offset_polylines.append(p)
        updated_cut_count = len(offset_polylines)
        if updated_cut_count != self.cut_count:
            self.cut_count = updated_cut_count
            self.lead_pos = [0.] * self.cut_count
            self.cut_state = [self.TODO] * self.cut_count
        return offset_polylines

    def _apply_lead(self, polylines):
        return polylines

    def _apply_loop(self, polylines):
        return [p.loop(121*math.pi/180, self.kerf_width / 2, self._loop_radius)
                for p in polylines]

    def _generate(self, polylines):
        return [p.to_lines() for p in polylines]

    def _generate_shape(self, polylines):
        if len(polylines) > 1:
            polylines = [p for p in polylines if p.is_closed()]
        return self._generate(polylines)

    def _apply_affine(self, polylines):
        return [np.dot(self.pos_rot_matrix(), np.insert(p, 2, 1., axis=0))[:-1]
                for p in polylines]

    def _apply_pline_affine(self, polylines):
        return [p.affine(self._position, self._angle, 1.) for p in polylines]

    def is_closed(self):
        polylines = self.root_node._data
        return len(polylines) != 1 or polylines[0].is_closed()
