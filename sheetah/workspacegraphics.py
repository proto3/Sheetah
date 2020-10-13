from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from videothread import VideoThread

class ProjectBar(QtGui.QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project

        self.load_btn = QtGui.QPushButton('load')
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.load_btn)
        self.setLayout(layout)

        self.load_btn.clicked.connect(self.on_load)

    def on_load(self):
        filepath, _ = QtGui.QFileDialog.getOpenFileName(self,
                      'Open File', QtCore.QDir.currentPath(),
                      'DXF (*.dxf);; All Files (*)')
        if filepath:
            self.project.load_job(filepath)

class WorkspaceView(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__(QtWidgets.QGraphicsScene())
        self.controller = None

        self.video_thread = VideoThread()
        self.video_thread.frame_available.connect(self.on_frame)
        self.bg_image = QtWidgets.QGraphicsPixmapItem()
        self.scene().addItem(self.bg_image)
        self.bg_image.setTransform(QtGui.QTransform().scale(1,-1))
        self.video_thread.start()

        self.machine = QtWidgets.QGraphicsRectItem(0,0, 900, 1320)
        machinePen = QtGui.QPen(QtGui.QColor(239, 67, 15))
        machinePen.setCosmetic(True)
        self.machine.setPen(machinePen)
        self.machine.setBrush(QtGui.QBrush(QtGui.QColor(50, 60, 70)))
        self.scene().addItem(self.machine)
        self.fitInView(self.machine.rect(), Qt.KeepAspectRatio)

        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(44, 48, 55)))

        # View params
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)

        # OpenGL
        opengl = True
        antialias = True
        if opengl:
            gl_viewport = QtWidgets.QOpenGLWidget()
            if antialias:
                format = QtGui.QSurfaceFormat()
                format.setSamples(32) # nothing happens under 16 samples, but why ???
                gl_viewport.setFormat(format)
            self.setViewport(gl_viewport)
        else:
            if antialias:
                self.setRenderHints(QtGui.QPainter.Antialiasing)

        # flip view vertically
        self.scale(1, -1)

        # Select box
        self.selectBox = QtWidgets.QGraphicsRectItem()
        self.selectBox.setPen(QtGui.QPen(QtGui.QBrush(QtGui.QColor(49, 154, 255)), 0))
        self.selectBox.setBrush(QtGui.QBrush(QtGui.QColor(173, 207, 239, 50)))
        self.selectBox.setZValue(1)
        self.selectBox.hide()
        self.scene().addItem(self.selectBox)

        self.dragging = False
        self.selecting = False

        # Avoid Qt bug occuring when the view is clicked after a focus loss, the
        # event position is not updated. We generate a fake moveEvent after a
        # focus loss to prevent that.
        self.lastScenePosOutdated = False

    def on_frame(self):
        cvImg = self.video_thread.frame
        height, width, channel = cvImg.shape
        bytesPerLine = 3 * width
        qImg = QtGui.QImage(cvImg.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
        self.bg_image.setPixmap(QtGui.QPixmap(qImg))

    def focusOutEvent(self, ev):
        QtWidgets.QGraphicsView.focusOutEvent(self, ev)
        self.lastScenePosOutdated = True

    def posSyncCheck(self, ev):
        if self.lastScenePosOutdated:
            moveEvent = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, ev.pos(),
            QtCore.Qt.NoButton,
            QtCore.Qt.MouseButtons(QtCore.Qt.NoButton),
            QtCore.Qt.NoModifier)
            self.mouseMoveEvent(moveEvent)
            self.lastScenePosOutdated = False

    def wheelEvent(self, ev):
        QtWidgets.QGraphicsView.wheelEvent(self, ev)
        degrees = ev.angleDelta().y() / 8
        sc = 1.01 ** degrees
        mouse_to_center = self.sceneRect().center() - self.mapToScene(ev.pos())
        new_center = self.mapToScene(ev.pos()) + mouse_to_center/sc
        self.scale(sc,sc)
        r = QtCore.QRectF(self.rect())
        viewport = self.viewportTransform().inverted()[0].mapRect(r)
        viewport.translate(new_center - viewport.center())
        self.setSceneRect(viewport)
        self.selecting = False

    def mouseDoubleClickEvent(self, ev):
        self.posSyncCheck(ev)
        QtWidgets.QGraphicsView.mouseDoubleClickEvent(self, ev)

    def mousePressEvent(self, ev):
        self.posSyncCheck(ev)

        if ev.button() & Qt.MidButton:
            self.prev_pos = ev.pos()
            self.dragging = True
        else:
            QtWidgets.QGraphicsView.mousePressEvent(self, ev)
            if not ev.isAccepted():
                if ev.button() & Qt.LeftButton:
                    self.scene().clearSelection()
                    self.downPos = self.mapToScene(ev.pos())
                    ini_rect = QtCore.QRectF(self.downPos, self.downPos)
                    self.selectBox.setRect(ini_rect)
                    self.selectBox.show()
                    self.selecting = True

    def mouseReleaseEvent(self, ev):
        if self.dragging:
            self.dragging = False
        elif self.selecting:
            self.selecting = False
            self.selectBox.hide()
            self.scene().setSelectionArea(self.selectBox.shape())
        else:
            QtWidgets.QGraphicsView.mouseReleaseEvent(self, ev)

    def mouseMoveEvent(self, ev):
        if self.dragging:
            pos_diff = self.prev_pos - ev.pos()
            if not pos_diff.isNull():
                sf = self.transform().inverted()[0] # scale factor
                diff = sf.map(QtCore.QPointF(pos_diff))
                new_rect = self.sceneRect().translated(diff)
                self.setSceneRect(new_rect)
                self.prev_pos = ev.pos()
        elif self.selecting:
            scene_pos = self.mapToScene(ev.pos())
            rect = QtCore.QRectF(self.downPos, scene_pos).normalized()
            self.selectBox.setRect(rect)
        else:
            QtWidgets.QGraphicsView.mouseMoveEvent(self, ev)

    def resizeEvent(self, ev):
        # create new rect of center self.sceneRect().center() and of size self.rect() in scene units
        r = QtCore.QRectF(self.rect())
        viewport = self.viewportTransform().inverted()[0].mapRect(r)
        viewport.translate(self.sceneRect().center() - viewport.center())
        self.setSceneRect(viewport)
