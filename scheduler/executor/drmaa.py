import logging
import re
import shutil
from os import makedirs

import drmaa
from drmaa.const import JobControlAction
from drmaa.errors import InvalidJobException, InternalException

from scheduler.executor.base import Executor
from scheduler.job import Job, JobSpec

logger = logging.getLogger(__name__)


class DRMAAExecutor(Executor):
    def __init__(self, stop_on_first_error: bool = False, max_jobs: int = None, skip_already_done=False):
        super().__init__(stop_on_first_error, max_jobs, skip_already_done)
        self._session = drmaa.Session()
        self._session.initialize()

    def _job_status(self, job: Job) -> Executor.JobStatus:
        has_exited = False
        exit_status = None
        try:
            res = self._session.wait(job.job_id,
                                     drmaa.Session.TIMEOUT_NO_WAIT)
            if res.hasExited:
                has_exited = True
                exit_status = res.exitStatus
        except drmaa.ExitTimeoutException:
            # job still active
            pass
        except Exception as e:
            # Dirty hack allowing to catch cancelled job in "queued" status
            if 'code 24' in str(e):
                logger.error("Cancelled job in 'queued' status: {}".format(e))
            else:
                logger.error('Unknown exception: {}: {}'.format(type(e), e))
            exit_status = 42
            has_exited = True
        return Executor.JobStatus(
            exit_status=exit_status,
            has_exited=has_exited,
            job=job
        )

    def _cancel_job(self, job: Job):
        try:
            self._session.control(job.job_id, JobControlAction.TERMINATE)
        except (InvalidJobException, InternalException) as e:
            # FIXME: This is common - logging a warning would probably confuse the user.
            logger.error('DRMAA exception: {}: {}'.format(type(e), e))

    def _create_template(self, spec: JobSpec)->drmaa.JobTemplate:
        jt = self._session.createJobTemplate()
        jt.remoteCommand = shutil.which(spec.command)
        jt.args = spec.args

        if spec.num_slots > 1:
            logger.debug('Job {name} requested {n} slots'.format(
                name=spec.name,
                n=spec.num_slots,
            ))
            # TODO: add support non SGE engines
            jt.nativeSpecification = "-pe make {}".format(spec.num_slots)

        if spec.log_path:
            jt.outputPath = ':'+spec.log_path
            jt.joinFiles = True
        if spec.name:
            if re.match(r'^\d+', spec.name):
                jt.jobName = 'j'+spec.name
            else:
                jt.jobName = spec.name
        if spec.work_dir:
            jt.workingDirectory = spec.work_dir

        return jt

    def _submit(self, job_spec: JobSpec)->Job:
        try:
            jt = self._create_template(job_spec)

            job_id = self._session.runJob(jt)
            job = Job(spec=job_spec, job_id=job_id)
            self._session.deleteJobTemplate(jt)
            return job
        except (drmaa.InternalException,
                drmaa.InvalidAttributeValueException) as e:
            logger.error('drmaa exception in _submit: {}'.format(e))
            # FIXME handle drmaa exceptions
            raise e

    def shutdown(self):
        self._session.exit()
