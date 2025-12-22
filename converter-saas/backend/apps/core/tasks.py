"""
Core Tasks for File Converter SaaS.
Shared base task and utilities for background processing.
"""

from celery import shared_task, Task
from django.utils import timezone
from .models import ConversionJob, JobStatus
import logging

logger = logging.getLogger(__name__)

class BaseConversionTask(Task):
    """Base class for all conversion tasks with error handling."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure by updating the ConversionJob."""
        job_id = kwargs.get('job_id')
        if job_id:
            try:
                job = ConversionJob.objects.get(id=job_id)
                job.mark_failed(str(exc))
                logger.error(f"Task {task_id} failed for job {job_id}: {str(exc)}")
            except ConversionJob.DoesNotExist:
                logger.error(f"Task {task_id} failed, but job {job_id} not found.")

def update_job_processing(job_id):
    """Mark job as processing safely."""
    try:
        job = ConversionJob.objects.get(id=job_id)
        job.mark_processing()
        return job
    except ConversionJob.DoesNotExist:
        logger.error(f"Job {job_id} not found during status update.")
        return None
