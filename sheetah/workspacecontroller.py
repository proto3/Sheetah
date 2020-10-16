from PyQt5.QtCore import Qt
import numpy as np
import math

from transformhandle import TransformHandle
from jobgraphics import JobVisual, JobVisualProxy

class WorkspaceController:
    def __init__(self, project, view):
        self.project = project
        self.job_visuals = []
        self.view = view
        self.scene = self.view.scene()
        self.view.controller = self

        self._grab = False
        self.items = []
        self.proxy_items = []

        self.handle = TransformHandle(self)
        self.scene.addItem(self.handle)

        self.project.job_update.connect(self.on_job_update)
        self.scene.selectionChanged.connect(self.on_selection)

    def delete_selection(self):
        self.project.remove_jobs([item.job
                                  for item in self.scene.selectedItems()])

    def grabbing(self):
        return self._grab

    def _create_proxy_items(self):
        self.items = self.scene.selectedItems()
        self.proxy_items = [JobVisualProxy(item) for item in self.items]

    def _delete_proxy_items(self):
        for item in self.proxy_items:
            self.scene.removeItem(item)
        self.proxy_items = []

    def start_grab(self, down_pos):
        self._grab = True
        self._create_proxy_items()
        self.down_pos = np.array([down_pos.x(), down_pos.y()])

    def step_grab(self, pos, step_mode):
        pos = np.array([pos.x(), pos.y()])
        self.pos = pos - self.down_pos
        if step_mode:
            incr = 10
            self.pos = np.round(self.pos / incr) * incr
        for item in self.proxy_items:
            item.setPos(self.pos[0], self.pos[1])
        self.prev_pos = pos

    def end_grab(self):
        self._delete_proxy_items()
        for item in self.items:
            item.job.position += self.pos
        self.items = []
        self.handle.update()
        self._grab = False

    def start_rot(self, down_pos):
        self._create_proxy_items()
        centroids = [item.job.get_centroid() for item in self.scene.selectedItems()]
        self.center = np.mean(centroids, axis=0)
        for item in self.proxy_items:
            item.setTransformOriginPoint(self.center[0], self.center[1])

        down_pos = np.array([down_pos.x(), down_pos.y()])
        dir_vect = down_pos - self.center
        self.down_angle = math.atan2(dir_vect[1], dir_vect[0])

    def step_rot(self, pos, step_mode):
        pos = np.array([pos.x(), pos.y()])
        dir_vect = pos - self.center
        cur_angle = math.atan2(dir_vect[1], dir_vect[0])

        self.angle = cur_angle - self.down_angle
        if step_mode:
            incr = math.pi / 12
            self.angle = round(self.angle / incr) * incr
        for item in self.proxy_items:
            item.setRotation(math.degrees(self.angle))

    def end_rot(self):
        self._delete_proxy_items()
        for item in self.items:
            item.job.turn_around(self.center, self.angle)
        self.items = []
        self.handle.update()

    def start_scale(self, down_pos):
        self._create_proxy_items()
        centroids = [item.job.get_centroid() for item in self.scene.selectedItems()]
        self.center = np.mean(centroids, axis=0)
        for item in self.proxy_items:
            item.setTransformOriginPoint(self.center[0], self.center[1])

        down_pos = np.array([down_pos.x(), down_pos.y()])
        self.down_dist = self.prev_dist = np.linalg.norm(down_pos - self.center)
        if math.isclose(self.down_dist, 0):
            self.down_dist = 1

    def step_scale(self, pos, step_mode):
        pos = np.array([pos.x(), pos.y()])
        dist = np.linalg.norm(pos - self.center)
        self.scale = dist / self.down_dist
        if step_mode:
            incr = 0.1
            self.scale = round(self.scale / incr) * incr
        for item in self.proxy_items:
            item.setScale(self.scale)

    def end_scale(self):
        self._delete_proxy_items()
        for item in self.items:
            item.job.scale_around(self.center, self.scale)
        self.items = []
        self.handle.update()

    def on_job_update(self):
        jobs = self.project.jobs.copy()
        job_visuals = self.job_visuals.copy()
        for jvi, jv in reversed(list(enumerate(job_visuals))):
            try:
                ji = jobs.index(jv.job)
                jobs.pop(ji)
                job_visuals.pop(jvi)
            except ValueError:
                pass
        for jv in job_visuals:
            self.job_visuals.remove(jv)
            self.scene.removeItem(jv)
        for j in jobs:
            jv = JobVisual(self, j)
            self.job_visuals.append(jv)
            self.scene.addItem(jv)

    def on_selection(self):
        self.handle.update()

    def keyPressEvent(self, ev):
        if ev.modifiers() == Qt.NoModifier:
            if ev.key() == Qt.Key_Delete:
                # DEL
                self.delete_selection()
            # elif ev.key() == Qt.Key_Escape:
            #     # ESC
            #     print('Esc')
        elif ev.modifiers() == Qt.ControlModifier:
            if ev.key() == Qt.Key_A:
                # Ctrl + A
                for item in self.scene.items():
                    item.setSelected(True)
            if ev.key() == Qt.Key_Z:
                # Ctrl + Z
                print('Undo')
            elif ev.key() == Qt.Key_S:
                # Ctrl + S
                print('Save')
        elif ev.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            if ev.key() == Qt.Key_Z:
                # Ctrl + Shift + Z
                print('Redo')
