"""
Celery Compatibility Layer.
Provides fallback decorators when Celery is not installed.
This allows the app to work with or without Celery.

Usage:
    from apps.core.celery_compat import shared_task, Task, CELERY_AVAILABLE
    
    @shared_task
    def my_task():
        pass
"""

import logging
import functools

logger = logging.getLogger(__name__)

# Try to import Celery
try:
    from celery import shared_task as celery_shared_task, Task as CeleryTask
    CELERY_AVAILABLE = True
    logger.info("Celery is available - async tasks enabled")
except ImportError:
    CELERY_AVAILABLE = False
    logger.info("Celery not installed - tasks will run synchronously")
    celery_shared_task = None
    CeleryTask = None


class SyncTask:
    """
    Fallback base task class when Celery is not available.
    Mimics Celery Task interface for compatibility.
    """
    
    # Task name (set by decorator)
    name = None
    
    # Retry configuration (ignored in sync mode)
    autoretry_for = ()
    retry_backoff = False
    max_retries = 3
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure - override in subclass."""
        pass
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success - override in subclass."""
        pass
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry - override in subclass."""
        pass


def make_sync_task(func, base_class=None):
    """
    Create a synchronous task wrapper that mimics Celery task behavior.
    """
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # If first arg is 'self' (bind=True), create a mock task instance
        if base_class:
            task_instance = base_class()
            task_instance.request = type('Request', (), {'id': 'sync-task'})()
            try:
                result = func(task_instance, *args, **kwargs)
                task_instance.on_success(result, 'sync-task', args, kwargs)
                return result
            except Exception as e:
                task_instance.on_failure(e, 'sync-task', args, kwargs, None)
                raise
        else:
            return func(*args, **kwargs)
    
    # Add .delay() method for compatibility
    def delay(*args, **kwargs):
        """Synchronous execution when Celery not available."""
        logger.debug(f"Running {func.__name__} synchronously (Celery not available)")
        return wrapper(*args, **kwargs)
    
    def apply_async(*args, **kwargs):
        """Synchronous execution when Celery not available."""
        return delay(*args, **kwargs)
    
    wrapper.delay = delay
    wrapper.apply_async = apply_async
    wrapper.name = f'{func.__module__}.{func.__name__}'
    
    return wrapper


def shared_task(*args, **kwargs):
    """
    Drop-in replacement for celery.shared_task.
    Uses real Celery if available, otherwise runs synchronously.
    
    Supports all common Celery task options:
    - bind=True
    - base=BaseClass
    - autoretry_for=(Exception,)
    - retry_backoff=True
    - max_retries=3
    """
    
    def decorator(func):
        if CELERY_AVAILABLE:
            # Use real Celery shared_task
            return celery_shared_task(*args, **kwargs)(func)
        else:
            # Use sync wrapper
            base_class = kwargs.get('base')
            bind = kwargs.get('bind', False)
            
            if bind and base_class:
                return make_sync_task(func, base_class)
            elif bind:
                return make_sync_task(func, SyncTask)
            else:
                return make_sync_task(func)
    
    # Check if called as @shared_task (no parentheses, direct function)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        func = args[0]
        return make_sync_task(func)
    
    return decorator


# Export Task class - use Celery's if available, otherwise use SyncTask
if CELERY_AVAILABLE:
    Task = CeleryTask
else:
    Task = SyncTask
