"""
PDF Module Utilities.
PDF manipulation functions using PyPDF2, ReportLab, etc.
"""

import os
import io
from pathlib import Path
from typing import Optional, Dict, Any, List

from PIL import Image
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4


class PDFError(Exception):
    """Custom exception for PDF errors."""
    pass


def merge_pdfs(input_paths: List[str], output_path: str) -> str:
    """
    Merge multiple PDF files into one.
    
    Args:
        input_paths: List of paths to PDF files
        output_path: Path for output PDF
    
    Returns:
        Output file path
    """
    try:
        merger = PdfMerger()
        
        for path in input_paths:
            merger.append(path)
        
        merger.write(output_path)
        merger.close()
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF merge failed: {str(e)}')


def split_pdf(
    input_path: str,
    output_dir: str,
    page_ranges: List[tuple] = None
) -> List[str]:
    """
    Split PDF into multiple files.
    
    Args:
        input_path: Path to input PDF
        output_dir: Directory for output files
        page_ranges: List of (start, end) tuples. If None, split into individual pages.
    
    Returns:
        List of output file paths
    """
    try:
        reader = PdfReader(input_path)
        output_paths = []
        
        if page_ranges is None:
            # Split into individual pages
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                
                output_path = os.path.join(output_dir, f'page_{i+1}.pdf')
                with open(output_path, 'wb') as f:
                    writer.write(f)
                output_paths.append(output_path)
        else:
            # Split by page ranges
            for i, (start, end) in enumerate(page_ranges):
                writer = PdfWriter()
                
                for page_num in range(start - 1, min(end, len(reader.pages))):
                    writer.add_page(reader.pages[page_num])
                
                output_path = os.path.join(output_dir, f'split_{i+1}.pdf')
                with open(output_path, 'wb') as f:
                    writer.write(f)
                output_paths.append(output_path)
        
        return output_paths
    except Exception as e:
        raise PDFError(f'PDF split failed: {str(e)}')


def compress_pdf(input_path: str, output_path: str, quality: str = 'medium') -> str:
    """
    Compress PDF file by reducing image quality using PyMuPDF.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        quality: Compression level ('low', 'medium', 'high')
    
    Returns:
        Output file path
    """
    try:
        import fitz  # PyMuPDF
        
        # Quality settings - COMPRESSION level (not quality level)
        # 'low' compression = best quality, larger file
        # 'high' compression = lowest quality, smallest file
        quality_settings = {
            'high': {'dpi': 72, 'jpeg_quality': 40},    # Maximum compression, smallest file
            'medium': {'dpi': 100, 'jpeg_quality': 60}, # Balanced
            'low': {'dpi': 150, 'jpeg_quality': 80}     # Minimum compression, best quality
        }
        
        settings = quality_settings.get(quality, quality_settings['medium'])
        
        # Open source PDF
        src_doc = fitz.open(input_path)
        
        # Create new PDF for output
        dst_doc = fitz.open()
        
        for page_num in range(len(src_doc)):
            page = src_doc[page_num]
            
            # Get page as pixmap at reduced resolution
            zoom = settings['dpi'] / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
            
            # Convert to JPEG bytes with compression
            img_bytes = pix.tobytes("jpeg", jpg_quality=settings['jpeg_quality'])
            
            # Create new page with same dimensions as original
            rect = page.rect
            new_page = dst_doc.new_page(width=rect.width, height=rect.height)
            
            # Insert compressed image
            new_page.insert_image(rect, stream=img_bytes)
        
        # Save with compression options
        dst_doc.save(
            output_path,
            garbage=4,  # Maximum garbage collection
            deflate=True,  # Compress streams
            clean=True,  # Clean redundant data
        )
        
        dst_doc.close()
        src_doc.close()
        
        return output_path
    except ImportError:
        raise PDFError('PyMuPDF is required for compression. Install with: pip install PyMuPDF')
    except Exception as e:
        raise PDFError(f'PDF compression failed: {str(e)}')


def rotate_pdf(
    input_path: str,
    output_path: str,
    rotation: int,
    pages: List[int] = None
) -> str:
    """
    Rotate PDF pages.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        rotation: Rotation angle (90, 180, 270)
        pages: List of page numbers to rotate (1-indexed). None for all pages.
    
    Returns:
        Output file path
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        for i, page in enumerate(reader.pages):
            if pages is None or (i + 1) in pages:
                page.rotate(rotation)
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF rotation failed: {str(e)}')


def delete_pages(
    input_path: str,
    output_path: str,
    pages_to_delete: List[int]
) -> str:
    """
    Delete specific pages from PDF.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        pages_to_delete: List of page numbers to delete (1-indexed)
    
    Returns:
        Output file path
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        for i, page in enumerate(reader.pages):
            if (i + 1) not in pages_to_delete:
                writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF page deletion failed: {str(e)}')


def reorder_pages(
    input_path: str,
    output_path: str,
    new_order: List[int]
) -> str:
    """
    Reorder PDF pages.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        new_order: List of page numbers in new order (1-indexed)
    
    Returns:
        Output file path
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        for page_num in new_order:
            if 1 <= page_num <= len(reader.pages):
                writer.add_page(reader.pages[page_num - 1])
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF reorder failed: {str(e)}')


def protect_pdf(
    input_path: str,
    output_path: str,
    password: str,
    owner_password: str = None
) -> str:
    """
    Add password protection to PDF.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        password: User password (required to open)
        owner_password: Owner password (required to edit)
    
    Returns:
        Output file path
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        writer.encrypt(
            user_password=password,
            owner_password=owner_password or password
        )
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF protection failed: {str(e)}')


def unlock_pdf(
    input_path: str,
    output_path: str,
    password: str
) -> str:
    """
    Remove password protection from PDF.
    
    Args:
        input_path: Path to input PDF
        output_path: Path for output PDF
        password: Password to unlock
    
    Returns:
        Output file path
    """
    try:
        reader = PdfReader(input_path)
        
        if reader.is_encrypted:
            reader.decrypt(password)
        
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
    except Exception as e:
        raise PDFError(f'PDF unlock failed: {str(e)}')


def images_to_pdf(
    image_paths: List[str],
    output_path: str,
    page_size: str = 'A4'
) -> str:
    """
    Convert images to PDF.
    
    Args:
        image_paths: List of image file paths
        output_path: Path for output PDF
        page_size: Page size ('A4' or 'Letter')
    
    Returns:
        Output file path
    """
    try:
        # Get page size
        size = A4 if page_size == 'A4' else letter
        
        images = []
        for path in image_paths:
            img = Image.open(path)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            images.append(img)
        
        if images:
            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:] if len(images) > 1 else [],
                format='PDF'
            )
        
        return output_path
    except Exception as e:
        raise PDFError(f'Image to PDF conversion failed: {str(e)}')


def pdf_to_images(
    input_path: str,
    output_dir: str,
    output_format: str = 'png',
    dpi: int = 200
) -> List[str]:
    """
    Convert PDF pages to images using PyMuPDF.
    
    Args:
        input_path: Path to input PDF
        output_dir: Directory for output images
        output_format: Output image format
        dpi: Resolution in DPI
    
    Returns:
        List of output image paths
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(input_path)
        output_paths = []
        
        # Calculate zoom factor from DPI (default PDF is 72 DPI)
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        for i, page in enumerate(doc):
            # Determine file extension
            ext = 'jpg' if output_format.lower() in ['jpg', 'jpeg'] else output_format.lower()
            output_path = os.path.join(output_dir, f'page_{i+1}.{ext}')
            
            if output_format.lower() == 'png':
                # PNG: Direct save from pixmap
                pix = page.get_pixmap(matrix=matrix)
                pix.save(output_path)
            else:
                # JPEG: Use RGB colorspace (no alpha), convert via PIL
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.save(output_path, "JPEG", quality=95)
            
            output_paths.append(output_path)
        
        doc.close()
        return output_paths
        
    except ImportError:
        raise PDFError('PyMuPDF is required for PDF to image conversion. Install with: pip install PyMuPDF')
    except Exception as e:
        raise PDFError(f'PDF to image conversion failed: {str(e)}')


def get_pdf_info(file_path: str) -> Dict[str, Any]:
    """
    Get PDF file information.
    
    Args:
        file_path: Path to PDF file
    
    Returns:
        Dictionary with PDF metadata
    """
    try:
        reader = PdfReader(file_path)
        
        return {
            'num_pages': len(reader.pages),
            'is_encrypted': reader.is_encrypted,
            'metadata': {
                'title': reader.metadata.title if reader.metadata else None,
                'author': reader.metadata.author if reader.metadata else None,
                'subject': reader.metadata.subject if reader.metadata else None,
                'creator': reader.metadata.creator if reader.metadata else None,
            }
        }
    except Exception as e:
        raise PDFError(f'Failed to get PDF info: {str(e)}')
