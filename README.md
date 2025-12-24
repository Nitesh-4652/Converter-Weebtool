# File Converter SaaS Backend

Production-ready file converter SaaS using Django + DRF + PostgreSQL.

## Requirements

- Python 3.10+
- PostgreSQL 14+
- FFmpeg (for audio/video)

## Setup

```bash
# Activate virtual environment
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```
