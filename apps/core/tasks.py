"""
Core Tasks for File Converter SaaS.
Shared base task and utilities for background processing.
"""

from apps.core.celery_compat import shared_task, Task, CELERY_AVAILABLE
from django.utils import timezone
from .models import ConversionJob, ConvertedFile, JobStatus
import logging
import os

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


@shared_task
def cleanup_expired_files():
    """
    Cleanup expired files that weren't downloaded.
    This task should be scheduled to run periodically (e.g., every 30 minutes).
    """
    from django.conf import settings
    
    expiry_hours = getattr(settings, 'CONVERTED_FILE_EXPIRY_HOURS', 1)
    expiry_time = timezone.now() - timezone.timedelta(hours=expiry_hours)
    
    # Find expired ConvertedFile records
    expired_files = ConvertedFile.objects.filter(created_at__lt=expiry_time)
    deleted_count = 0
    
    for converted_file in expired_files:
        try:
            # Delete output file
            if converted_file.output_file:
                file_path = converted_file.output_file.path
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # Delete input file from conversion job
            if converted_file.conversion_job:
                job = converted_file.conversion_job
                if job.input_file:
                    try:
                        if os.path.exists(job.input_file.path):
                            os.remove(job.input_file.path)
                    except Exception:
                        pass
                if job.output_file:
                    try:
                        if os.path.exists(job.output_file.path):
                            os.remove(job.output_file.path)
                    except Exception:
                        pass
            
            # Delete database record
            converted_file.delete()
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Error cleaning up file {converted_file.id}: {str(e)}")
    
    logger.info(f"Cleanup task completed. Deleted {deleted_count} expired files.")
    return deleted_count

