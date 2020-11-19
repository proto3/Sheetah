from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

class HandleIcon(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, img_path, parent, controller):
        super().__init__(QtGui.QPixmap(img_path), parent)
        self.setOffset(-self.pixmap().rect().center())
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        self.controller = controller

class RotateHandle(HandleIcon):
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

class ScaleHandle(HandleIcon):
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
        self.rotate = RotateHandle('resources/rotate_icon.png', self, controller)
        self.scale = ScaleHandle('resources/scale_icon.png', self, controller)
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
