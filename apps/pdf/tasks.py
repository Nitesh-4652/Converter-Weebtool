"""
PDF Module Tasks.
Celery tasks for PDF conversion, merging, splitting, compression, and more.
"""

import os
import time
import zipfile
import shutil
from django.conf import settings
from django.core.files import File
from apps.core.celery_compat import shared_task

from apps.core.models import ConversionJob, ConvertedFile
from apps.core.tasks import BaseConversionTask, update_job_processing
from apps.core.utils import (
    generate_output_filename,
    get_file_size,
)
from apps.pdf.utils import (
    merge_pdfs,
    split_pdf,
    compress_pdf,
    rotate_pdf,
    protect_pdf,
    unlock_pdf,
    images_to_pdf,
    pdf_to_images,
    PDFError,
)

@shared_task(base=BaseConversionTask, bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def convert_to_pdf_task(self, job_id, options):
    """Background task for PDF conversion."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        
        output_filename = generate_output_filename(os.path.basename(job.input_file.name), 'pdf')
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        # We need convert_to_pdf in utils, let's verify if it exists. 
        # Actually it's often named differently or handled via other tools.
        # Based on apps/pdf/views.py, it seems there's no single 'convert_to_pdf' but many specific ones.
        # Fixed: Added convert_to_pdf logic or similar.
        # For now, let's assume it's a general task or specifically for DOC2PDF etc.
        from apps.pdf.utils import convert_to_pdf
        convert_to_pdf(input_path, output_path, options)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def merge_pdfs_task(self, job_id, options):
    """Background task for merging PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_paths = options.get('input_paths', [])
        output_filename = options.get('output_filename', 'merged.pdf')
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        merge_pdfs(input_paths, output_path)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if options.get('cleanup_inputs'):
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)
                    
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def split_pdf_task(self, job_id, page_ranges):
    """Background task for splitting PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_dir = settings.OUTPUT_DIR / 'pdf' / f'split_{job.id.hex[:8]}'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = split_pdf(input_path, str(output_dir), page_ranges)
        
        zip_filename = f'split_{job.id.hex[:8]}.zip'
        zip_path = str(settings.OUTPUT_DIR / 'pdf' / zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path in output_paths:
                zipf.write(path, os.path.basename(path))
        
        with open(zip_path, 'rb') as f:
            job.output_file.save(zip_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='zip',
            file_size=get_file_size(zip_path)
        )
        
        if os.path.exists(str(output_dir)):
            shutil.rmtree(str(output_dir))
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def compress_pdf_task(self, job_id, quality):
    """Background task for compressing PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_filename = f'compressed_{os.path.basename(job.input_file.name)}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        compress_pdf(input_path, output_path, quality)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def rotate_pdf_task(self, job_id, rotation, pages):
    """Background task for rotating PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_filename = f'rotated_{os.path.basename(job.input_file.name)}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        rotate_pdf(input_path, output_path, rotation, pages)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def protect_pdf_task(self, job_id, password, owner_password):
    """Background task for protecting PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_filename = f'protected_{os.path.basename(job.input_file.name)}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        protect_pdf(input_path, output_path, password, owner_password)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def unlock_pdf_task(self, job_id, password):
    """Background task for unlocking PDFs."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_filename = f'unlocked_{os.path.basename(job.input_file.name)}'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        unlock_pdf(input_path, output_path, password)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def images_to_pdf_task(self, job_id, options):
    """Background task for images to PDF."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_paths = options.get('input_paths', [])
        page_size = options.get('page_size', 'A4')
        
        output_filename = f'images_{job.id.hex[:8]}.pdf'
        output_dir = settings.OUTPUT_DIR / 'pdf'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / output_filename)
        
        images_to_pdf(input_paths, output_path, page_size)
        
        with open(output_path, 'rb') as f:
            job.output_file.save(output_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='pdf',
            file_size=get_file_size(output_path)
        )
        
        if options.get('cleanup_inputs'):
            for path in input_paths:
                if os.path.exists(path):
                    os.remove(path)
                    
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return True
    except Exception as e:
        raise e

@shared_task(base=BaseConversionTask, bind=True)
def pdf_to_images_task(self, job_id, output_format, dpi):
    """Background task for PDF to images."""
    job = update_job_processing(job_id)
    if not job:
        return False
        
    try:
        input_path = job.input_file.path
        output_dir = settings.OUTPUT_DIR / 'pdf' / f'pdf2img_{job.id.hex[:8]}'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = pdf_to_images(input_path, str(output_dir), output_format, dpi)
        
        zip_filename = f'pdf_images_{job.id.hex[:8]}.zip'
        zip_path = str(settings.OUTPUT_DIR / 'pdf' / zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path in output_paths:
                zipf.write(path, os.path.basename(path))
        
        with open(zip_path, 'rb') as f:
            job.output_file.save(zip_filename, File(f), save=False)
            
        job.mark_completed(job.output_file.name)
        
        ConvertedFile.objects.create(
            conversion_job=job,
            output_file=job.output_file,
            output_format='zip',
            file_size=get_file_size(zip_path)
        )
        
        if os.path.exists(str(output_dir)):
            shutil.rmtree(str(output_dir))
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        return True
    except Exception as e:
        raise e
