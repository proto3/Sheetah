#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore
import pyqtgraph as pg
import numpy as np
import cv2, math

from shapely.geometry import Point

class JobVisual:
    def __init__(self, job):
        self.job = job
        # self.part_curve = pg.PlotCurveItem([], [], fillLevel=0, pen=pg.mkPen(color=(150, 210, 50), width=2), brush=pg.mkBrush(color=(110, 230, 20, 80)))
        self.part_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(4, 150, 255), width=2))

        self.todo_curve    = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255, 255, 255), width=2))
        self.running_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(250, 170,   0), width=2))
        self.done_curve    = pg.PlotCurveItem([], [], pen=pg.mkPen(color=( 65, 220,  10), width=2))
        self.failed_curve  = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(255,   0,   0), width=2))
        self.ignored_curve = pg.PlotCurveItem([], [], pen=pg.mkPen(color=(100, 100, 100), width=2))

        pos = self.job.position
        size = self.job.get_size()
        self.roi = pg.ROI(pos=pos, size=size, pen=pg.mkPen(color=(255,255,255,20)))
        self.roi.addRotateHandle([0, 0], [0.5, 0.5])
        self.job.shape_update.connect(self.on_job_shape_update)
        self.roi.sigRegionChanged.connect(self.on_roi_update)
        self.roi.sigHoverEvent.connect(self.on_roi_hover)
        # hoverLeaveEvent
        self.on_job_shape_update()

    def on_roi_hover(self):
        self.job.get_bounds() # just to regen if needed
        self.job.cut_shape_mov

    def on_job_shape_update(self):
        connect = np.empty(0, dtype=np.bool)
        data = np.empty((2,0), dtype=np.float)
        for i in range(self.job.contour_count):
            c = self.job.get_part_array(i)
            connected = np.repeat(True, c.shape[1])
            connected[-1] = False
            connect = np.concatenate((connect, connected))
            data = np.concatenate((data, c), axis=1)
        self.part_curve.setData(data[0], data[1], connect=connect)

        connect = [np.empty(0, dtype=np.bool) for i in range(5)]
        data = [np.empty((2,0), dtype=np.float) for i in range(5)]
        for i in range(self.job.get_cut_count()):
            cut = self.job.get_cut_array(i)
            state = self.job.get_state(i)
            connected = np.repeat(True, cut.shape[1])
            connected[-1] = False
            connect[state] = np.concatenate((connect[state], connected))
            data[state] = np.concatenate((data[state], cut), axis=1)

        self.todo_curve.setData(data[0][0], data[0][1], connect=connect[0])
        self.running_curve.setData(data[1][0], data[1][1], connect=connect[1])
        self.done_curve.setData(data[2][0], data[2][1], connect=connect[2])
        self.failed_curve.setData(data[3][0], data[3][1], connect=connect[3])
        self.ignored_curve.setData(data[4][0], data[4][1], connect=connect[4])

    def on_roi_update(self):
        self.job.angle = self.roi.angle()
        self.job.position = self.roi.pos()

class VideoThread(QtCore.QThread):
    frame_available = QtCore.pyqtSignal()
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
                # frame[:,:,2] = 2  #VAL
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

class WorkspaceViewWidget(pg.PlotWidget): #GraphicsView
    def __init__(self):
        super().__init__()
        self.video_thread = VideoThread()
        self.video_thread.frame_available.connect(self.on_frame)
        self.bg_image = pg.ImageItem()
        self.addItem(self.bg_image)
        self.video_thread.start()

        self.setAspectLocked()
        self.msize = (900, 1320)
        self.workspace = pg.PlotCurveItem([0, self.msize[0], self.msize[0], 0, 0],
                                      [0, 0, self.msize[1], self.msize[1], 0],
                                      pen=pg.mkPen(color=(239, 67, 15), width=1))
        self.addItem(self.workspace)

    def on_frame(self):
        self.bg_image.setImage(self.video_thread.frame, autoLevels=False)

    def add_job_visual(self, visual):
        self.addItem(visual.todo_curve)
        self.addItem(visual.running_curve)
        self.addItem(visual.done_curve)
        self.addItem(visual.failed_curve)
        self.addItem(visual.ignored_curve)
        self.addItem(visual.part_curve)
        self.addItem(visual.roi)

    def remove_job_visual(self, visual):
        self.removeItem(visual.todo_curve)
        self.removeItem(visual.running_curve)
        self.removeItem(visual.done_curve)
        self.removeItem(visual.failed_curve)
        self.removeItem(visual.ignored_curve)
        self.removeItem(visual.part_curve)
        self.removeItem(visual.roi)
