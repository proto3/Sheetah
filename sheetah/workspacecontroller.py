from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
import numpy as np

from transformhandle import TransformHandle
from jobgraphics import JobVisual, GraphicsProxyItem

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

    def add_job_visual(self, job_visual):
        self.job_visuals.append(job_visual)
        for item in job_visual.items():
            self.scene.addItem(item)

    def remove_job_visual(self, job_visual):
        self.job_visuals.remove(job_visual)
        for item in job_visual.items():
            self.scene.removeItem(item)

    def delete_selection(self):
        self.project.remove_jobs([item.job
                                  for item in self.scene.selectedItems()])

    def grabbing(self):
        return self._grab

    def start_grab(self, down_pos):
        self.down_pos = self.prev_pos = down_pos
        self._grab = True
        self.items = self.scene.selectedItems()
        self.proxy_items = [GraphicsProxyItem(item) for item in self.items]

    def step_grab(self, pos):
        if pos != self.prev_pos:
            diff = pos - self.prev_pos
            for item in self.proxy_items:
                item.setPos(item.pos() + diff)
            self.prev_pos = pos

    def end_grab(self):
        for item in self.proxy_items:
            self.scene.removeItem(item)
        full_move = self.prev_pos - self.down_pos
        full_move = np.array([full_move.x(), full_move.y()])
        for item in self.items:
            item.job.position += full_move
        self.items = self.proxy_items = []
        self.handle.update()
        self._grab = False

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
            self.remove_job_visual(jv)
        for j in jobs:
            self.add_job_visual(JobVisual(self, j))

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
