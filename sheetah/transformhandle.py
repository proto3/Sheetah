from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

class RotateHandle(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, parent, controller):
        super().__init__(-5,-5,10,10, parent)
        self.controller = controller
        self.setPen(QtGui.QPen(Qt.NoPen))
        self.setBrush(QtGui.QBrush(QtGui.QColor(50,180,255)))

    def mousePressEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.controller.start_rot(ev.scenePos())
            ev.accept()

    def mouseReleaseEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.controller.end_rot()
            ev.accept()

    def mouseMoveEvent(self, ev):
        self.controller.step_rot(ev.scenePos(),
                                 bool(ev.modifiers() & Qt.ControlModifier))
        ev.accept()

class ScaleHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent, controller):
        super().__init__(-5,-5,10,10, parent)
        self.controller = controller
        self.setPen(QtGui.QPen(Qt.NoPen))
        self.setBrush(QtGui.QBrush(QtGui.QColor(255,150,0)))
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, ev):
        #TODO change cursor
        pass

    def hoverLeaveEvent(self, ev):
        #TODO change cursor
        pass

    def mousePressEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.controller.start_scale(ev.scenePos())
            ev.accept()

    def mouseReleaseEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.controller.end_scale()
            ev.accept()

    def mouseMoveEvent(self, ev):
        self.controller.step_scale(ev.scenePos(),
                                   bool(ev.modifiers() & Qt.ControlModifier))
        ev.accept()

class TransformHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        pen = QtGui.QPen(QtGui.QColor(0,150,255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(2)
        self.rotate = RotateHandle(self, controller)
        self.scale = ScaleHandle(self, controller)
        self.hide()

    def update(self):
        # TODO handle error scene == None ?
        if self.scene().selectedItems():
            group = self.scene().createItemGroup(self.scene().selectedItems())
            b_rect = group.boundingRect()
            self.setRect(b_rect)
            self.scene().destroyItemGroup(group)
            self.rotate.setPos(b_rect.bottomRight())
            self.scale.setPos(b_rect.topRight())
            self.show()
        else:
            self.hide()
