#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from job import Task, JobTask
import numpy as np
import math

class PostProcessor:
    def __init__(self):
        self._init_seq = ['G90', 'G28 Z', 'G28 X Y']
        self._abort_seq = ['M7', 'M5', 'M8']

    def init_task(self):
        return Task(self._init_seq)

    def emergency_task(self):
        return Task(self._abort_seq)

    def generate(self, job, task_id, dry_run=False):
        cut_pline = job.get_cut_plines()[task_id]
        gcode = list()
        gcode = ['G90',
                 'G1 F6000 X' + '{:.3f}'.format(cut_pline.start[0]) +
                         ' Y' + '{:.3f}'.format(cut_pline.start[1]), 'PROBE']
        if dry_run:
            gcode += ['G91', 'G1 F3000 Z20', 'G90', 'M6 V0 T-1']
        else:
            gcode += ['G91', 'G1 Z3.8', 'M3', 'G4 P' + str(job.pierce_delay),
            'G1 Z-2.3', 'G90',
            'M6 V' + '{:.2f}'.format(job.arc_voltage) + ' T' + '{:.0f}'.format(job.feedrate * 0.9)]
        gcode += ['G1 F' + str(job.feedrate)]

        data = cut_pline.raw
        points = []
        n = data.shape[0]
        for i in range(n - int(not cut_pline.is_closed())):
            a = data[i,:2]
            b = data[(i+1)%n,:2]
            bulge = data[i,2]
            if points:
                points.pop(-1)

            x, y = b
            if math.isclose(bulge, 0) or np.linalg.norm(b-a) < 1e0:
                gcode += ['G1 X' + '{:.3f}'.format(x) + ' Y' + '{:.3f}'.format(y)]
            else:
                rot = np.array([[0,-1],
                                [1, 0]])
                on_right = bulge >= 0
                if not on_right:
                    rot = -rot
                bulge = abs(bulge)
                ab = b-a
                chord = np.linalg.norm(ab)
                radius = chord * (bulge + 1. / bulge) / 4
                center_offset = radius - chord * bulge / 2
                center = a + ab/2 + center_offset / chord * rot.dot(ab)
                i_val, j_val = center - a
                cmd = 'G3' if on_right else 'G2'
                gcode += [cmd + ' X' + '{:.3f}'.format(x) +
                                ' Y' + '{:.3f}'.format(y) +
                                ' I' + '{:.3f}'.format(i_val) +
                                ' J' + '{:.3f}'.format(j_val)]

        if dry_run:
            gcode += ['M7', 'M8']
        else:
            gcode += ['M7', 'M5', 'M8', 'G91', 'G1 F3000 Z10', 'G90']
        return JobTask(gcode, job, task_id, dry_run)
