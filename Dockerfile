FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ✅ STEP 1 — WORKDIR FIRST (MOST IMPORTANT)
WORKDIR /app

# ✅ STEP 2 — system deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libpq-dev \
    gcc \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ✅ STEP 3 — requirements AFTER workdir
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ✅ STEP 4 — rest of project
COPY . .

RUN python manage.py collectstatic --noinput || true

# ✅ STEP 5 — migration & startup
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
