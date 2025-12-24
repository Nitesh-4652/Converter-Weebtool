"""
Gunicorn Configuration for Converter SaaS Production Server

Optimized for handling large file uploads/downloads and video conversion.
"""
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
# Use CPU count * 2 + 1 for optimal performance
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"  # Thread-based workers for better I/O handling
threads = 4  # 4 threads per worker for concurrent request handling
worker_connections = 1000

# Timeouts
timeout = 300  # 5 minutes - allows large file uploads and video processing
graceful_timeout = 30  # 30 seconds for graceful worker restart
keepalive = 5  # Keep connections alive for 5 seconds

# Request limits
# Increased to handle large video files (up to 500MB)
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Logging
accesslog = "-"  # Log to stdout (Railway captures this)
errorlog = "-"   # Log errors to stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "converter_saas"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Preload app for faster worker spawning (optional)
preload_app = False

# Worker restart settings
max_requests = 1000  # Restart workers after 1000 requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to avoid all workers restarting at once
