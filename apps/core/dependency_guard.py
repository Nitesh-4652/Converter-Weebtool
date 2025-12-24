"""
Dependency Guard.
Centralized module for checking and safely handling optional dependencies.
Prevents import-time crashes when packages are missing.
"""

import logging
import importlib

logger = logging.getLogger(__name__)

def is_available(module_name: str) -> bool:
    """Check if a module is available without importing it at module level."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception as e:
        # Catching everything (ImportError, ModuleNotFoundError, OSError for DLLs, etc.)
        # so the app doesn't crash during dependency checking.
        logger.debug(f"Optional dependency '{module_name}' is not functional: {str(e)}")
        return False

# Availability Flags
CELERY_AVAILABLE = is_available('celery')
REPORTLAB_AVAILABLE = is_available('reportlab')
PYMUPDF_AVAILABLE = is_available('fitz')
CAIROSVG_AVAILABLE = is_available('cairosvg')
WEASYPRINT_AVAILABLE = is_available('weasyprint')
HEIF_AVAILABLE = is_available('pillow_heif')

# Log availability for debugging
if not CELERY_AVAILABLE:
    logger.info("Optional dependency 'celery' not found. Async tasks will run synchronously.")
if not REPORTLAB_AVAILABLE:
    logger.info("Optional dependency 'reportlab' not found. PDF features using ReportLab will be limited.")

def get_reportlab_canvas():
    """Lazy import for reportlab.pdfgen.canvas"""
    if REPORTLAB_AVAILABLE:
        from reportlab.pdfgen import canvas
        return canvas
    return None

def get_reportlab_pagesizes():
    """Lazy import for reportlab.lib.pagesizes"""
    if REPORTLAB_AVAILABLE:
        from reportlab.lib import pagesizes
        return pagesizes
    return None

def require_dependency(module_name: str, feature_name: str):
    """Raise a clear error if a required optional dependency is missing."""
    if not is_available(module_name):
        raise ImportError(
            f"The '{module_name}' library is required for {feature_name}. "
            f"Please install it (pip install {module_name}) to use this feature."
        )
