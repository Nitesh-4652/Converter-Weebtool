"""
Image Module Utilities.
Pillow-based image conversion functions.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from PIL import Image
from django.conf import settings
from apps.core.dependency_guard import CAIROSVG_AVAILABLE, HEIF_AVAILABLE


class ImageConversionError(Exception):
    """Custom exception for image conversion errors."""
    pass


# Format mappings for Pillow
PILLOW_FORMAT_MAP = {
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'png': 'PNG',
    'webp': 'WEBP',
    'gif': 'GIF',
    'bmp': 'BMP',
    'tiff': 'TIFF',
    'tif': 'TIFF',
    'ico': 'ICO',
    'ppm': 'PPM',
    'pgm': 'PPM',
}

# Formats that support transparency
TRANSPARENT_FORMATS = ['png', 'webp', 'gif', 'ico']


def get_pillow_format(extension: str) -> str:
    """Get Pillow format name from extension."""
    return PILLOW_FORMAT_MAP.get(extension.lower(), extension.upper())


def convert_image(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Convert image to specified format using Pillow.
    
    Args:
        input_path: Path to input image
        output_path: Path for output image
        output_format: Target format
        options: Additional options (quality, resize, etc.)
    
    Returns:
        Output file path
    """
    options = options or {}
    
    try:
        # Open image
        with Image.open(input_path) as img:
            # Get target format
            pillow_format = get_pillow_format(output_format)
            
            # Handle transparency for formats that don't support it
            if output_format.lower() in ['jpg', 'jpeg', 'bmp']:
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Convert to RGB, filling transparency with white
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            
            # PERFORMANCE: Handle resize with BILINEAR (faster) for large images
            # Use LANCZOS only for small final sizes where quality matters
            if 'width' in options or 'height' in options:
                width = options.get('width')
                height = options.get('height')
                
                # Calculate target dimensions
                if width and height:
                    new_width, new_height = width, height
                elif width:
                    ratio = width / img.width
                    new_width = width
                    new_height = int(img.height * ratio)
                elif height:
                    ratio = height / img.height
                    new_width = int(img.width * ratio)
                    new_height = height
                else:
                    new_width, new_height = img.width, img.height
                
                # PERFORMANCE: Use BILINEAR for large images (2x faster), LANCZOS for small
                if new_width * new_height < 500000:  # Less than ~700x700
                    resample = Image.Resampling.LANCZOS
                else:
                    resample = Image.Resampling.BILINEAR
                
                img = img.resize((new_width, new_height), resample)
            
            # Build save options
            save_options = {}
            
            # Quality for JPEG/WEBP
            if output_format.lower() in ['jpg', 'jpeg', 'webp']:
                quality = options.get('quality', 85)
                save_options['quality'] = quality
                if output_format.lower() in ['jpg', 'jpeg']:
                    # PERFORMANCE: optimize=False is faster, subsampling affects quality/size
                    save_options['optimize'] = False  # Faster encoding
                    save_options['subsampling'] = '4:2:0'  # Smaller file, faster
            
            # PNG optimization - skip for speed
            if output_format.lower() == 'png':
                # PERFORMANCE: Skip optimize for faster encoding
                save_options['compress_level'] = 6  # Default, balanced
            
            # Save image
            img.save(output_path, format=pillow_format, **save_options)
            
            return output_path
    
    except Exception as e:
        raise ImageConversionError(f'Image conversion failed: {str(e)}')


def convert_svg_to_image(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Convert SVG to raster image using cairosvg.
    
    Args:
        input_path: Path to SVG file
        output_path: Path for output image
        output_format: Target format (png, jpg, etc.)
        options: Additional options (width, height, scale)
    
    Returns:
        Output file path
    """
    options = options or {}
    
    try:
        if not CAIROSVG_AVAILABLE:
            raise ImportError
        import cairosvg
        
        # First convert to PNG
        temp_png = output_path + '.temp.png'
        
        svg_options = {}
        if 'width' in options:
            svg_options['output_width'] = options['width']
        if 'height' in options:
            svg_options['output_height'] = options['height']
        if 'scale' in options:
            svg_options['scale'] = options['scale']
        
        cairosvg.svg2png(url=input_path, write_to=temp_png, **svg_options)
        
        # If target is PNG, we're done
        if output_format.lower() == 'png':
            os.rename(temp_png, output_path)
            return output_path
        
        # Convert PNG to target format
        convert_image(temp_png, output_path, output_format, options)
        
        # Clean up temp file
        if os.path.exists(temp_png):
            os.remove(temp_png)
        
        return output_path
    
    except ImportError:
        raise ImageConversionError('cairosvg is required for SVG conversion')
    except Exception as e:
        raise ImageConversionError(f'SVG conversion failed: {str(e)}')


def convert_heic_to_image(
    input_path: str,
    output_path: str,
    output_format: str,
    options: Dict[str, Any] = None
) -> str:
    """
    Convert HEIC/HEIF to other formats.
    
    Args:
        input_path: Path to HEIC file
        output_path: Path for output image
        output_format: Target format
        options: Additional options
    
    Returns:
        Output file path
    """
    options = options or {}
    
    try:
        if not HEIF_AVAILABLE:
            raise ImportError
        from pillow_heif import register_heif_opener
        register_heif_opener()
        
        return convert_image(input_path, output_path, output_format, options)
    
    except ImportError:
        raise ImageConversionError('pillow-heif is required for HEIC conversion')
    except Exception as e:
        raise ImageConversionError(f'HEIC conversion failed: {str(e)}')


def get_image_info(file_path: str) -> Dict[str, Any]:
    """
    Get image file information.
    
    Args:
        file_path: Path to image file
    
    Returns:
        Dictionary with image metadata
    """
    try:
        with Image.open(file_path) as img:
            return {
                'format': img.format,
                'mode': img.mode,
                'width': img.width,
                'height': img.height,
                'has_transparency': img.mode in ('RGBA', 'LA', 'P'),
                'is_animated': getattr(img, 'is_animated', False),
                'n_frames': getattr(img, 'n_frames', 1),
            }
    except Exception as e:
        raise ImageConversionError(f'Failed to get image info: {str(e)}')
