from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt

import jobgraphics
class ScaleHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent):
        super().__init__(-5,-5,10,10, parent)
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
            ev.accept()
            print("scale")

    def mouseMoveEvent(self, ev):
        ev.accept()
        print("do scale")

class RotateHandle(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, parent):
        super().__init__(-5,-5,10,10, parent)
        self.setPen(QtGui.QPen(Qt.NoPen))
        self.setBrush(QtGui.QBrush(QtGui.QColor(50,180,255)))

    def mousePressEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            ev.accept()
            print("rotate")

class TransformHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, project, scene):
        super().__init__(0,0,0,0)
        self.project = project

        pen = QtGui.QPen(QtGui.QColor(0,150,255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(2)

        self.scale = ScaleHandle(self)
        self.rotate = RotateHandle(self)

        scene.selectionChanged.connect(self.on_selection)
        self.hide()

    def on_selection(self):
        if self.scene().selectedItems():
            group = self.scene().createItemGroup(self.scene().selectedItems())
            b_rect = group.boundingRect()
            self.setRect(b_rect)
            self.scene().destroyItemGroup(group)
            self.scale.setPos(b_rect.bottomRight())
            self.rotate.setPos(b_rect.topRight())
            self.show()
        else:
            self.hide()
