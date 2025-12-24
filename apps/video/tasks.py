"""
Video Module Tasks.
Celery tasks for video conversion and trimming.
"""

import os
import time
from django.conf import settings
from django.core.files import File
from celery import shared_task

from apps.core.models import ConversionJob, ConvertedFile
from apps.core.tasks import BaseConversionTask, update_job_processing
from apps.core.utils import (
    convert_video,
    trim_video,
    get_duration,
    generate_output_filename,
    get_file_size,
)

@shared_task(base=BaseConversionTask, bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def convert_video_task(self, job_id, output_format, options):
    """Background task for video conversion."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        
        if not job.duration:
            job.duration = get_duration(input_path)
            job.save(update_fields=['duration'])
            
        output_filename = generate_output_filename(os.path.basename(job.input_file.name), output_format)
        output_dir = settings.OUTPUT_DIR / 'video'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        convert_video(input_path, output_path, output_format, options)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format=output_format,
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def trim_video_task(self, job_id, trim_start, trim_end, copy_mode, output_format):
    """Background task for video trimming."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        
        output_filename = generate_output_filename(os.path.basename(job.input_file.name), output_format)
        output_dir = settings.OUTPUT_DIR / 'video'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        trim_video(input_path, output_path, trim_start, trim_end, copy_mode)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format=output_format,
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e
