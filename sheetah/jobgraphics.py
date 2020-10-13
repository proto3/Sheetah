from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from pyqtgraph import arrayToQPath
import numpy as np

class JobVisual:
    def __init__(self, project, job):
        self.project = project
        self.job = job
        cut_colors = [QtGui.QColor(255, 255, 255),
                      QtGui.QColor(250, 170,   0),
                      QtGui.QColor(  5, 220,  10),
                      QtGui.QColor(255,   0,   0),
                      QtGui.QColor(100, 100, 100)]
        self.cut_item = GraphicsCutPathsItem(cut_colors)
        self.part_item = GraphicsCutPartItem(project, job)
        self.job.shape_update.connect(self.on_job_shape_update)
        self.on_job_shape_update()

    def items(self):
        return [self.part_item, self.cut_item]

    def on_job_shape_update(self):
        self.part_item.setData(self.job.get_shape_paths())
        self.cut_item.setData(*self.job.get_cut_paths(), self.job.kerf_width)

class GraphicsCutPathsItem(QtWidgets.QGraphicsPathItem):
    def __init__(self, state_colors):
        super().__init__()
        self.colors = state_colors
        self.painter_paths = [QtGui.QPainterPath()] * len(state_colors)
        self.pen_base = QtGui.QPen(QtGui.QBrush(), 0, Qt.SolidLine, Qt.RoundCap,
                                   Qt.RoundJoin)

    def setWidth(self, width):
        self.pen_base.setWidthF(width)

    # last path should always be the external contour
    def setData(self, paths, states, width=None):
        self.prepareGeometryChange()
        if width is not None:
            self.pen_base.setWidthF(width)
        if paths:
            data = [np.empty((2,0), dtype=np.float) for i in range(5)]
            connect = [np.empty(0, dtype=np.bool) for i in range(5)]
            for i, state in enumerate(states):
                connected = np.ones(paths[i].shape[1], dtype=np.bool)
                connected[-1] = False
                connect[state] = np.concatenate((connect[state], connected))
                data[state] = np.concatenate((data[state], paths[i]), axis=1)
            self.painter_paths = [arrayToQPath(data[i][0], data[i][1], connect[i])
                                  for i in range(len(self.painter_paths))]
            # last path is used to keep shape and boundingRect up to date
            self.setPath(self.painter_paths[states[-1]])
        else:
            self.setPath(QtGui.QPainterPath())
        self.update()

    def paint(self, painter, option, widget):
        for i, color in enumerate(self.colors):
            self.pen_base.setColor(color)
            painter.setPen(self.pen_base)
            painter.drawPath(self.painter_paths[i])

class GraphicsCutPartItem(QtWidgets.QGraphicsPathItem):
    def __init__(self, project, job):
        super().__init__()
        self.project = project
        self.job = job
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.press = False
        self.drag = False

        self.selectBrush = QtGui.QBrush(QtGui.QColor(65, 220, 10, 95))
        self.unselectBrush = QtGui.QBrush(QtGui.QColor(4, 150, 255, 95))
        self.setBrush(self.unselectBrush)
        self.setPen(QtGui.QPen(Qt.NoPen))

        self.menu = QtGui.QMenu()
        self.action = QtGui.QAction('Job settings')
        self.action.triggered.connect(self.on_job_settings)
        self.menu.addAction(self.action)

        self.params_dialog = JobParamDialog(self.job)

    def setData(self, paths):
        data = np.empty((2,0), dtype=np.float)
        connect = np.empty(0, dtype=np.bool)
        for path in paths:
            connected = np.ones(path.shape[1], dtype=np.bool)
            connected[-1] = False
            connect = np.concatenate((connect, connected))
            data = np.concatenate((data, path), axis=1)
        self.setPath(arrayToQPath(data[0], data[1], connect))

    def on_job_settings(self):
        self.params_dialog.move(self.menu.pos())
        self.params_dialog.reset_params()
        self.params_dialog.exec_()

    def _select_toggle(self):
        self.setSelected(not self.isSelected())
        self.project.set_selection([i.job for i in self.scene().selectedItems()])

    def _select_exclusive(self):
        self.scene().clearSelection()
        self.setSelected(True)
        self.project.set_selection(self.job)

    def leftPressHandler(self, ev):
        if ev.modifiers() & Qt.ShiftModifier:
            self._select_toggle()
        elif not self.isSelected():
            self._select_exclusive()

        if self.isSelected():
            self.press = True
            self.down_pos = self.prev_pos = ev.pos()

    def leftReleaseHandler(self, ev):
        if (not ev.modifiers() & Qt.ShiftModifier
            and {self.job} != self.project.selection):
            self._select_exclusive()

    def rightPressHandler(self, ev):
        if not self.isSelected():
            self._select_exclusive()

    def rightReleaseHandler(self, ev):
        pass

    def contextMenuEvent(self, ev):
        self.menu.popup(ev.screenPos())
        ev.accept()

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            if value:
                self.setBrush(self.selectBrush)
            else:
                self.setBrush(self.unselectBrush)
        return QtWidgets.QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.leftPressHandler(ev)
            ev.accept()
        elif ev.button() & Qt.RightButton:
            self.rightPressHandler(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            if self.drag:
                self.project.end_transform()
            else:
                self.leftReleaseHandler(ev)
            self.press = self.drag = False
        elif ev.button() & Qt.RightButton:
            self.rightReleaseHandler(ev)

    def mouseMoveEvent(self, ev):
        if self.press:
            self.drag = True
        if self.drag:
            if ev.pos() != self.prev_pos:
                self.project.step_transform(
                    np.array([ev.pos().x(), ev.pos().y()]),
                    np.array([self.prev_pos.x(), self.prev_pos.y()]),
                    np.array([self.down_pos.x(), self.down_pos.y()]))
                self.prev_pos = ev.pos()
            ev.accept()

    def paint(self, painter, option, widget):
        # override paint to hide default selection style
        option.state = option.state & ~QtWidgets.QStyle.State_Selected
        QtWidgets.QGraphicsPathItem.paint(self, painter, option, widget)

class JobParamDialog(QtWidgets.QDialog):
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle('Job settings')

        std_btns = (QtWidgets.QDialogButtonBox.Ok |
                   QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox = QtWidgets.QDialogButtonBox(std_btns)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        name_label = QtGui.QLabel(self.job.name,
                                  font=QtGui.QFont('SansSerif', 12),
                                  alignment=QtCore.Qt.AlignCenter)

        form = QtGui.QFormLayout()

        self.cut_direction_checkbox = QtGui.QCheckBox('(exterior clockwise)')
        self.cut_direction_checkbox.setTristate(False)
        form.addRow("Cut direction",self.cut_direction_checkbox)

        self.feedrate_spbox = QtGui.QSpinBox()
        self.feedrate_spbox.setRange(100, 20000)
        self.feedrate_spbox.setValue(self.job.feedrate)
        self.feedrate_spbox.setSingleStep(50)
        self.feedrate_spbox.setSuffix("mm/min")
        form.addRow("Feedrate",self.feedrate_spbox)

        self.arc_voltage_spbox = QtGui.QDoubleSpinBox()
        self.arc_voltage_spbox.setRange(0, 500)
        self.arc_voltage_spbox.setValue(self.job.arc_voltage)
        self.arc_voltage_spbox.setSingleStep(0.1)
        self.arc_voltage_spbox.setSuffix("V")
        form.addRow("Arc voltage",self.arc_voltage_spbox)

        self.pierce_delay_spbox = QtGui.QSpinBox()
        self.pierce_delay_spbox.setRange(0, 10000)
        self.pierce_delay_spbox.setValue(self.job.pierce_delay)
        self.pierce_delay_spbox.setSingleStep(50)
        self.pierce_delay_spbox.setSuffix("ms")
        form.addRow("Pierce delay",self.pierce_delay_spbox)

        self.kerf_width_spbox = QtGui.QDoubleSpinBox()
        self.kerf_width_spbox.setRange(0, 50)
        self.kerf_width_spbox.setValue(self.job.kerf_width)
        self.kerf_width_spbox.setSingleStep(0.1)
        self.kerf_width_spbox.setSuffix("mm")
        form.addRow("Kerf width",self.kerf_width_spbox)

        self.loop_radius_spbox = QtGui.QDoubleSpinBox()
        self.loop_radius_spbox.setRange(0, 50)
        self.loop_radius_spbox.setValue(self.job.loop_radius)
        self.loop_radius_spbox.setSingleStep(0.1)
        self.loop_radius_spbox.setSuffix("mm")
        form.addRow("Loop radius",self.loop_radius_spbox)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(name_label)
        layout.addLayout(form)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    def reset_params(self):
        self.cut_direction_checkbox.setChecked(self.job.exterior_clockwise)
        self.feedrate_spbox.setValue(self.job.feedrate)
        self.arc_voltage_spbox.setValue(self.job.arc_voltage)
        self.pierce_delay_spbox.setValue(self.job.pierce_delay)
        self.kerf_width_spbox.setValue(self.job.kerf_width)
        self.loop_radius_spbox.setValue(self.job.loop_radius)

    def accept(self):
        # TODO ugly way to avoid multiple signals (break encapsulation)
        self.job.blockSignals(True)

        self.job.exterior_clockwise = self.cut_direction_checkbox.isChecked()
        self.job.feedrate = self.feedrate_spbox.value()
        self.job.arc_voltage = self.arc_voltage_spbox.value()
        self.job.pierce_delay = self.pierce_delay_spbox.value()
        self.job.kerf_width = self.kerf_width_spbox.value()
        self.job.loop_radius = self.loop_radius_spbox.value()

        self.job.blockSignals(False)
        self.job.shape_update.emit()
        self.job.param_update.emit()

        super().accept()
