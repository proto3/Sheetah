#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from jobmodel import Task, JobTask

class PostProcessor:
    def __init__(self):
        self._init_seq = ['G90', 'G28 Z', 'G28 X Y']
        self._abort_seq = ['M7', 'M5', 'M8']

    def init_task(self):
        return Task(self._init_seq)

    def abort_task(self):
        return Task(self._abort_seq)

    def generate(self, job, task_id):
        cut_path = job.get_cut_array(task_id)
        gcode = list()
        gcode += ['G90',
                  'G1 Z20']
        gcode += ['G1 F6000 X' + '{:.3f}'.format(cut_path[0][0]) + ' Y' + '{:.3f}'.format(cut_path[1][0]),
                  'PROBE',
                  'G91',
                  'G1 Z3.8',
                  'M3',
                  'G4 P' + str(job.pierce_delay),
                  'G1 Z-2.3',
                  'G90',
                  'M6 V' + '{:.2f}'.format(job.arc_voltage),
                  'G1 F' + str(job.feedrate)]
        for x,y in cut_path.transpose()[1:]:
            gcode += ['G1 X' + '{:.3f}'.format(x) + ' Y' + '{:.3f}'.format(y)]
        gcode += ['M7',
                  'M5',
                  'M8']
        return JobTask(gcode, job, task_id, 6)

class GcodeExporter:
    def export(filename, job_manager, post_processor):
        jobs = job_manager.jobs_to_do()
        if jobs:
            # create/clear file
            file.writelines(post_processor.start_sequence())
            for job in jobs:
                file.writelines(post_processor.job2gcode(job))
            # close file
        else:
            raise Exception('Empty program')
