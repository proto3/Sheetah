#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from workspaceview import WorkspaceViewWidget, JobVisual

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

    def accept(self):
        self.job.exterior_clockwise = self.cut_direction_checkbox.isChecked()
        self.job.feedrate = self.feedrate_spbox.value()
        self.job.arc_voltage = self.arc_voltage_spbox.value()
        self.job.pierce_delay = self.pierce_delay_spbox.value()
        self.job.kerf_width = self.kerf_width_spbox.value()
        super().accept()

class JobItemWidget(QtGui.QGroupBox):
    def __init__(self, job_manager, job):
        super().__init__()
        self.job_manager = job_manager
        self.job = job

        self.name_label = QtGui.QLabel(job.name, alignment=QtCore.Qt.AlignCenter)
        self.params_label = QtGui.QLabel(font=QtGui.QFont('SansSerif', 10))
        self.state_label = QtGui.QLabel('')

        self.del_btn = QtGui.QPushButton()
        self.del_btn.setIcon(QtGui.QIcon.fromTheme('list-remove'))

        self.param_btn = QtGui.QPushButton()
        self.param_btn.setIcon(QtGui.QIcon.fromTheme('applications-system'))

        self.params_dialog = JobParamDialog(self.job, self)

        layout = QtGui.QGridLayout()
        layout.addWidget(self.name_label, 0, 0, 1, 2)
        layout.addWidget(self.params_label, 1, 0, 2, 1)
        layout.addWidget(self.param_btn, 1, 1)
        layout.addWidget(self.del_btn, 2, 1)
        layout.setColumnStretch(0, 1)
        # layout.addWidget(self.state_label)
        self.setLayout(layout)

        self.del_btn.clicked.connect(self.on_delete)
        self.param_btn.clicked.connect(self.on_param_open)
        # self.params_dialog.rejected.connect(self.on_param_canceled)
        # self.params_dialog.finished.connect(self.on_param_closed)

        self.job.state_update.connect(self.on_state_update)
        self.job.param_update.connect(self.on_param_update)
        self.on_param_update()
        self._item = None

    def on_param_update(self):
        s = str()
        s += 'Feedrate: ' + str(self.job.feedrate) + 'mm/min\n'
        s += 'Kerf width: ' + '{:.2f}'.format(self.job.kerf_width) + 'mm\n'
        s += 'Arc voltage: ' + '{:.1f}'.format(self.job.arc_voltage) + 'V\n'
        s += 'Pierce delay: ' + str(self.job.pierce_delay) + 'ms\n'
        self.params_label.setText(s)

    def on_param_open(self):
        self.params_dialog.reset_params()
        self.params_dialog.exec_()

    def on_delete(self):
        self.job_manager.remove_job(self.job)

    def on_kerf(self):
        self.job.kerf_width = self.kerf_width_spbox.value()

    def on_state_update(self):
        self.state_label.setText(str(self.job.cut_state))

class JobListWidget(QtGui.QListWidget):
    mov = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)

    def dropEvent(self, e):
        super().dropEvent(e)
        for i in range(self.count()):
            self.itemWidget(self.item(i)).job.index = i

    def append(self, widget):
        widget._item = QtGui.QListWidgetItem()
        widget._item.setSizeHint(widget.minimumSizeHint())
        self.addItem(widget._item)
        self.setItemWidget(widget._item, widget)

    def remove(self, widget):
        row = self.row(widget._item)
        self.takeItem(row)

class JobGUI():
    def __init__(self, job_manager):
        super().__init__()
        self.job_manager = job_manager
        self.jobs = [[], [], []]

        self.graphic_w = WorkspaceViewWidget()

        self.sidebar_w = QtGui.QWidget()
        self.list_w = JobListWidget()
        self.load_btn = QtGui.QPushButton('load')

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.list_w)
        layout.addWidget(self.load_btn)
        self.sidebar_w.setLayout(layout)

        self.load_btn.clicked.connect(self.on_load)
        self.job_manager.update.connect(self.on_job_list_update)

    def on_load(self):
        filename, _ = QtGui.QFileDialog.getOpenFileName(self.sidebar_w,
                      'Open File', QtCore.QDir.currentPath(),
                      'DXF (*.dxf);; All Files (*)')
        if filename:
            self.job_manager.load_job(filename)

    def on_job_list_update(self):
        for idx, job in enumerate(self.jobs[0]):
            if job not in self.job_manager.job_list:
                self.list_w.remove(self.jobs[1][idx])
                self.graphic_w.remove_job_visual(self.jobs[2][idx])
                for l in self.jobs:
                    l.pop(idx)
        for job in self.job_manager.job_list:
            if job not in self.jobs[0]:
                jobitem = JobItemWidget(self.job_manager, job)
                jobvisual = JobVisual(job)

                self.jobs[0].append(job)
                self.jobs[1].append(jobitem)
                self.jobs[2].append(jobvisual)

                self.list_w.append(jobitem)
                self.graphic_w.add_job_visual(jobvisual)
