from PyQt5.QtCore import QObject, pyqtSignal
import fileutils
import pathlib
from job import Job

class Project(QObject):
    job_update = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.jobs = list()

    def load_job(self, filepath):
        try:
            self.jobs += fileutils.load(filepath)
            self.job_update.emit()
        except Exception as e:
            filename = pathlib.Path(filepath).name
            print('Unable to load ' + filename + ', ' + str(e))

    def remove_jobs(self, jobs):
        unwanted_jobs = set(jobs)
        self.jobs = [j for j in self.jobs if j not in unwanted_jobs]
        self.job_update.emit()

    def generate_tasks(self, post_processor, dry_run):
        tasks = []
        for job in self.jobs:
            for i in job.cut_state_indices(Job.TODO):
                tasks.append(post_processor.generate(job, i, dry_run))
        if tasks:
            tasks.insert(0, post_processor.init_task())

        # for t in tasks:
        #     for i in t.cmd_list:
        #         print(i)
        return tasks
