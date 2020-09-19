#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt5.QtWidgets import QGraphicsPathItem, QOpenGLWidget
from PyQt5.QtGui import QPainter, QPen, QSurfaceFormat, QGraphicsRectItem
import pyqtgraph as pg
import numpy as np
import cv2, math

class DragQGraphicsPathItem(QGraphicsPathItem):
    def __init__(self, drag_cb):
        super().__init__()
        self.drag_cb = drag_cb

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() & Qt.LeftButton:
            self.drag_cb(ev)
            ev.accept()

class JobVisual:
    def __init__(self, job, job_drag_cb):
        self.job = job
        self.job_drag_cb = job_drag_cb

        self.part_poly = DragQGraphicsPathItem(self.drag_cb)
        self.part_poly.setPen(QPen(Qt.green, 0, Qt.NoPen))
        self.part_poly.setBrush(pg.mkBrush(color=(4, 150, 255, 95)))
        # self.part_poly.setBrush(pg.mkBrush(color=(65, 220, 10, 95)))

        self.cut_pen = QPen(Qt.white, job.kerf_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.todo_curve = QGraphicsPathItem()
        self.todo_curve.setPen(self.cut_pen)

        self.running_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(250, 170,   0), width=2))
        self.done_curve    = pg.PlotCurveItem([], [], pen=pg.mkPen(color=( 65, 220,  10), width=2))
        self.failed_curve  = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255,   0,   0), width=2))
        self.ignored_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(100, 100, 100), width=2))

        self.job.shape_update.connect(self.on_job_shape_update)
        self.on_job_shape_update()

    def drag_cb(self, ev):
        self.job_drag_cb(self.job, ev)

    def set_selected(self, selected):
        if selected:
            self.part_poly.setBrush(pg.mkBrush(color=(200, 200, 0, 95)))
        else:
            self.part_poly.setBrush(pg.mkBrush(color=(4, 150, 255, 95)))
            # self.part_poly.setBrush(pg.mkBrush(color=(65, 220, 10, 95)))

    def on_job_shape_update(self):
        connect = np.empty(0, dtype=np.bool)
        data = np.empty((2,0), dtype=np.float)

        for arr in self.job.get_part_arrays():
            connected = np.repeat(True, arr.shape[1])
            connected[-1] = False
            connect = np.concatenate((connect, connected))
            data = np.concatenate((data, arr), axis=1)

        self.part_poly.setPath(pg.arrayToQPath(data[0], data[1], connect))

        connect = [np.empty(0, dtype=np.bool) for i in range(5)]
        data = [np.empty((2,0), dtype=np.float) for i in range(5)]
        for i, arr in enumerate(self.job.get_cut_arrays()):
            state = self.job.get_state(i)
            connected = np.repeat(True, arr.shape[1])
            connected[-1] = False
            connect[state] = np.concatenate((connect[state], connected))
            data[state] = np.concatenate((data[state], arr), axis=1)

        self.cut_pen.setWidthF(self.job.kerf_width)
        self.todo_curve.setPen(self.cut_pen)
        self.todo_curve.setPath(pg.arrayToQPath(data[0][0], data[0][1], connect[0]))

        self.running_curve.setData(data[1][0], data[1][1], connect=connect[1])
        self.done_curve.setData(data[2][0], data[2][1], connect=connect[2])
        self.failed_curve.setData(data[3][0], data[3][1], connect=connect[3])
        self.ignored_curve.setData(data[4][0], data[4][1], connect=connect[4])

class VideoThread(QThread):
    frame_available = pyqtSignal()
    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 5)
        counter = -1
        while True:
            ret, frame = cap.read()
            counter = (counter + 1)%(5./0.2)
            if ret and not counter:
                colored = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                colored[:,:,0] = 20   #HUE
                colored[:,:,1] = 120  #SAT
                # frame[:,:,2] *= 5  #VAL
                colored = cv2.cvtColor(colored, cv2.COLOR_HSV2RGB, cv2.CV_8U)
                colored = cv2.convertScaleAbs(colored, alpha=0.35, beta=20)


                blurred = cv2.bilateralFilter(frame, 7, 50, 50)
                aaa = cv2.Canny(blurred, 20, 60)
                canny = cv2.cvtColor(aaa, cv2.COLOR_GRAY2RGB)
                canny = cv2.convertScaleAbs(canny, alpha=0.05, beta=0)
                frame = colored + canny
                frame = cv2.resize(frame, (1320, 900))

                # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                # blurred = cv2.GaussianBlur(src, (3,3), 0)
                # blurred = cv2.medianBlur(src, 5)
                # laplace = cv2.Laplacian(blurred, cv2.CV_16S)
                # res = cv2.convertScaleAbs(laplace)
                # self.frame = cv2.stylization(frame, sigma_s=60, sigma_r=0.45)
                # blurred = cv2.blur(src, (3,3))
                # blurred = cv2.medianBlur(src, 5)
                # blurred = cv2.bilateralFilter(src, 7, 50, 50)
                self.frame = frame

                self.frame_available.emit()

class MyViewBox(pg.ViewBox):
    def __init__(self, press_cb, **kwargs):
        super().__init__(**kwargs)
        ## Make select box that is shown when dragging on the view
        self.rbSelectBox = QGraphicsRectItem(0, 0, 1, 1)
        self.rbSelectBox.setPen(pg.mkPen((49,154,255), width=1))
        self.rbSelectBox.setBrush(pg.mkBrush(173, 207, 239,50))
        self.rbSelectBox.setZValue(1e9)
        self.rbSelectBox.hide()
        self.addItem(self.rbSelectBox, ignoreBounds=True)

        self.press_cb = press_cb

    def updateSelectBox(self, p1, p2):
        r = QRectF(p1, p2)
        r = self.childGroup.mapRectFromParent(r)
        self.rbSelectBox.setPos(r.topLeft())
        self.rbSelectBox.resetTransform()
        self.rbSelectBox.scale(r.width(), r.height())
        self.rbSelectBox.show()

    def mousePressEvent(self, ev, axis=None):
        self.press_cb(ev.button(), self.mapToView(ev.pos()))
        ev.ignore()

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() & Qt.LeftButton:
            ev.accept()
            if ev.isFinish(): # apply selection
                self.rbSelectBox.hide()
                pos = ev.pos()
                ax = QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                ax = self.childGroup.mapRectFromParent(ax)
                self.selection_ballback(ax)
            else: ## update shape of select box
                self.updateSelectBox(ev.buttonDownPos(), ev.pos())
        elif ev.button() & Qt.MidButton:
            pg.ViewBox.mouseDragEvent(self, ev, axis)

    def set_selection_cb(self, cb):
        self.selection_ballback = cb

class WorkspaceView(pg.PlotWidget):
    def __init__(self, project):
        super().__init__(plotItem=pg.PlotItem(viewBox=MyViewBox(self.press_cb)))
        self.plotItem.hideAxis('left')
        self.plotItem.hideAxis('bottom')

        self.project = project

        self.getPlotItem().getViewBox().set_selection_cb(self.rect_selection)

        use_opengl = True
        enable_antialiasing = True
        if use_opengl:
            gl = QOpenGLWidget()
            if enable_antialiasing:
                format = QSurfaceFormat()
                format.setSamples(32) # nothing happens under 16 samples, but why ???
                gl.setFormat(format)
            self.setViewport(gl)
        else:
            self.setAntialiasing(enable_antialiasing)
            # if enable_antialiasing:
            #     self.setRenderHints(QPainter.Antialiasing)
            # else:
            #     pass

        # flip view vertically
        self.scale(1, -1)

        self.video_thread = VideoThread()
        self.video_thread.frame_available.connect(self.on_frame)
        self.bg_image = pg.ImageItem()
        self.addItem(self.bg_image)
        self.video_thread.start()

        self.setAspectLocked()
        self.machine = QGraphicsRectItem(0,0, 900, 1320)
        self.machine.setPen(pg.mkPen(color=(239, 67, 15)))
        self.addItem(self.machine)

        self.project.job_update.connect(self.on_job_update)
        self.project.selection_update.connect(self.on_selection_update)

        self.jobs = [[],[]]

        self.dragging = False

    def press_cb(self, button, pos):
        if button & (Qt.RightButton | Qt.LeftButton):
            for i, jobvis in enumerate(self.jobs[1]):
                if jobvis.part_poly.path().contains(pos):
                    job = self.jobs[0][i]
                    if not job in self.project.selection:
                        self.project.selection = set([job])
                    if button & Qt.RightButton:
                        print('menu')

                    return
            self.project.selection = set()

    def rect_selection(self, rect):
        selection = set()
        for i, jv in enumerate(self.jobs[1]):
            if rect.contains(jv.part_poly.boundingRect()):
                selection.add(self.jobs[0][i])
        self.project.selection = selection

    def selection_center(self):
        centroids = []
        for job in self.project.selection:
            centroids.append(job.get_centroid())
        centroids = np.array(centroids).T
        return np.mean(centroids, axis=1)

    def job_drag_cb(self, job, ev):
        mode = 'translate'
        if mode == 'translate':
            if ev.isFinish(): # end drag
                self.dragging = False
                self.project.finish_drag_selection()
            elif not self.dragging: # start drag
                self.prev_pos = ev.buttonDownPos(ev.button())
                self.dragging = True
            mov = ev.pos() - self.prev_pos
            self.prev_pos = ev.pos()
            if not mov.isNull():
                self.project.step_mov_selection(mov)
        elif mode == 'rotate':
            if ev.isFinish(): # end drag
                self.dragging = False
                self.project.finish_drag_selection()
            elif not self.dragging: # start drag
                self.dragging = True
                self.center = self.selection_center()
                dir_ini = ev.buttonDownPos(ev.button()) - self.center
                self.prev_angle = math.atan2(dir_ini.y(), dir_ini.x())
            dir = ev.pos() - self.center
            angle = math.atan2(dir.y(), dir.x())
            angle_diff = angle - self.prev_angle
            if angle_diff != 0.:
                self.project.step_rot_selection(self.center, angle_diff * 180 / math.pi)
                self.prev_angle = angle
        else: # if mode == 'scale':
            pass
            # if ev.isFinish(): # end drag
            #     self.dragging = False
            #     self.project.finish_drag_selection()
            # elif not self.dragging: # start drag
            #     self.prev_pos = ev.buttonDownPos(ev.button())
            #     self.dragging = True
            # mov = ev.pos() - self.prev_pos
            # self.prev_pos = ev.pos()
            # if not mov.isNull():
            #     self.project.step_mov_selection(mov)

    def on_job_update(self):
        for i, job in enumerate(self.jobs[0]):
            if job not in self.project.jobs:
                self.remove_job_visual(self.jobs[1][i])
                for l in self.jobs:
                    l.pop(i)
        for job in self.project.jobs:
            if job not in self.jobs[0]:
                jobvisual = JobVisual(job, self.job_drag_cb)
                self.jobs[0].append(job)
                self.jobs[1].append(jobvisual)
                self.add_job_visual(jobvisual)

    def on_selection_update(self):
        for i, job in enumerate(self.jobs[0]):
            self.jobs[1][i].set_selected(job in self.project.selection)

    def on_frame(self):
        self.bg_image.setImage(self.video_thread.frame, autoLevels=False)

    def add_job_visual(self, visual):
        self.addItem(visual.todo_curve)
        # self.addItem(visual.running_curve)
        # self.addItem(visual.done_curve)
        # self.addItem(visual.failed_curve)
        # self.addItem(visual.ignored_curve)
        self.addItem(visual.part_poly)
        # self.scene.addItem(visual.roi)

    def remove_job_visual(self, visual):
        self.removeItem(visual.todo_curve)
        # self.scene.removeItem(visual.running_curve)
        # self.scene.removeItem(visual.done_curve)
        # self.scene.removeItem(visual.failed_curve)
        # self.scene.removeItem(visual.ignored_curve)
        self.removeItem(visual.part_poly)
        # self.scene.removeItem(visual.roi)
