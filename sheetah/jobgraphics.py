from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from pyqtgraph import arrayToQPath
import numpy as np

class JobVisual(QtWidgets.QGraphicsPathItem):
    def __init__(self, controller, job):
        super().__init__()
        self.controller = controller
        self.job = job
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)

        self.cut_colors = [QtGui.QColor(255, 255, 255),
                           QtGui.QColor(250, 170,   0),
                           QtGui.QColor(  5, 220,  10),
                           QtGui.QColor(255,   0,   0),
                           QtGui.QColor(100, 100, 100)]
        self.cut_paths = [QtGui.QPainterPath()] * len(self.cut_colors)
        self.pen_base = QtGui.QPen(QtGui.QBrush(), 0,
                                   Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

        self.select_brush = QtGui.QBrush(QtGui.QColor(4, 200, 255, 200))
        self.unselect_brush = QtGui.QBrush(QtGui.QColor(4, 150, 255, 150))

        self.job.shape_update.connect(self.on_job_shape_update)
        self.on_job_shape_update()

        self.menu = QtGui.QMenu()
        self.action = QtGui.QAction('Job settings')
        self.action.triggered.connect(self.on_job_settings)
        self.menu.addAction(self.action)
        self.params_dialog = JobParamDialog(self.job)

    def _select_toggle(self):
        self.setSelected(not self.isSelected())

    def _select_exclusive(self):
        self.scene().clearSelection()
        self.setSelected(True)

    def contextMenuEvent(self, ev):
        self.menu.popup(ev.screenPos())
        ev.accept()

    def mousePressEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            self.down_pos = ev.scenePos()
            if ev.modifiers() & Qt.ShiftModifier:
                self._select_toggle()
            elif not self.isSelected():
                self._select_exclusive()
            ev.accept()
        elif ev.button() & Qt.RightButton and not self.isSelected():
            self._select_exclusive()

    def mouseReleaseEvent(self, ev):
        if ev.button() & Qt.LeftButton:
            if self.controller.grabbing():
                self.controller.end_grab()
            elif not ev.modifiers() & Qt.ShiftModifier:
                self._select_exclusive()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self.isSelected() and not self.controller.grabbing():
            self.controller.start_grab(self.down_pos)
        if self.controller.grabbing():
            self.controller.step_grab(ev.scenePos(),
                                      bool(ev.modifiers() & Qt.ControlModifier))
            ev.accept()

    def on_job_shape_update(self):
        data = np.empty((2,0), dtype=np.float)
        connect = np.empty(0, dtype=np.bool)
        for path in self.job.get_shape_paths():
            connected = np.ones(path.shape[1], dtype=np.bool)
            connected[-1] = False
            connect = np.concatenate((connect, connected))
            data = np.concatenate((data, path), axis=1)
        self.fill_path = arrayToQPath(data[0], data[1], connect)

        paths, states = self.job.get_cut_paths()
        self.pen_base.setWidthF(self.job.kerf_width)
        # set pen for boundingRect to take it into account
        self.setPen(self.pen_base)
        data = [np.empty((2,0), dtype=np.float) for i in range(5)]
        connect = [np.empty(0, dtype=np.bool) for i in range(5)]
        for i, state in enumerate(states):
            connected = np.ones(paths[i].shape[1], dtype=np.bool)
            connected[-1] = False
            connect[state] = np.concatenate((connect[state], connected))
            data[state] = np.concatenate((data[state], paths[i]), axis=1)
        self.cut_paths = [arrayToQPath(data[i][0], data[i][1], connect[i])
                              for i in range(len(self.cut_colors))]
        # last path is used to keep shape and boundingRect up to date
        self.setPath(self.cut_paths[states[-1]]) # TODO should take ALL paths

        # TODO breaking encapsulation to refresh handle on kerf with update
        self.controller.handle.update()

    def on_job_settings(self):
        self.params_dialog.move(self.menu.pos())
        self.params_dialog.reset_params()
        self.params_dialog.exec_()

    def paint(self, painter, option, widget):
        if self.job.is_closed():
            if self.isSelected():
                painter.fillPath(self.fill_path, self.select_brush)
            else:
                painter.fillPath(self.fill_path, self.unselect_brush)

        for i, color in enumerate(self.cut_colors):
            self.pen_base.setColor(color)
            painter.setPen(self.pen_base)
            painter.drawPath(self.cut_paths[i])

class JobVisualProxy(QtWidgets.QGraphicsPathItem):
    def paint(self, painter, option, widget):
        brush = QtGui.QBrush(QtGui.QColor(50, 200, 255, 100))
        painter.fillPath(self.parentItem().fill_path, brush)

        pen = self.parentItem().pen_base
        pen.setColor(QtGui.QColor(0, 0, 0))
        painter.setPen(pen)
        for path in self.parentItem().cut_paths:
            painter.drawPath(path)

    def boundingRect(self):
        return self.parentItem().boundingRect()

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
