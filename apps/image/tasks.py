"""
Image Module Tasks.
Celery tasks for image conversion using Pillow.
"""

import os
import time
from django.conf import settings
from django.core.files import File
from apps.core.celery_compat import shared_task

from apps.core.models import ConversionJob, ConvertedFile
from apps.core.tasks import BaseConversionTask, update_job_processing
from apps.core.utils import (
    get_file_extension,
    generate_output_filename,
    get_file_size,
)
from apps.image.utils import (
    convert_image,
    convert_svg_to_image,
    convert_heic_to_image,
    ImageConversionError,
)

@shared_task(base=BaseConversionTask, bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def convert_image_task(self, job_id, output_format, options):
    """Background task for image conversion."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        input_format = get_file_extension(job.input_file.name)
        
        output_filename = generate_output_filename(os.path.basename(job.input_file.name), output_format)
        output_dir = settings.OUTPUT_DIR / 'image'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        # Convert based on input format (replicate view logic)
        if input_format.lower() == 'svg':
            convert_svg_to_image(input_path, output_path, output_format, options)
        elif input_format.lower() in ['heic', 'heif']:
            convert_heic_to_image(input_path, output_path, output_format, options)
        else:
            convert_image(input_path, output_path, output_format, options)
            
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
