FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY web/backend/requirements.txt /build/web-requirements.txt

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install \
        "audioop-lts>=0.2.2" \
        "celery>=5.5.3" \
        "ffmpeg-python>=0.2.0" \
        "imageio-ffmpeg>=0.6.0" \
        "moviepy>=2.2.1" \
        "numpy>=2.2.6" \
        "opencv-python-headless>=4.12.0.88" \
        "pillow>=11.3.0" \
        "proglog>=0.1.12" \
        "pydantic>=2.0" \
        "pydantic-settings>=2.0" \
        "python-dotenv>=1.0" \
        "pytesseract>=0.3.13" \
        "pyyaml>=6.0.3" \
        "redis>=6.0.0" \
        "requests>=2.32.5" \
        "yandex-speechkit>=1.5.0" \
 && /opt/venv/bin/pip install -r /build/web-requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    AAVB_WORK_DIR=/data \
    AAVB_MAX_CONCURRENT=2

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 aavb \
 && useradd --system --uid 1001 --gid 1001 --create-home --home-dir /home/aavb aavb

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY --chown=aavb:aavb core /app/core
COPY --chown=aavb:aavb engines /app/engines
COPY --chown=aavb:aavb web /app/web
COPY --chown=aavb:aavb main.py /app/main.py
COPY --chown=aavb:aavb pyproject.toml /app/pyproject.toml

RUN mkdir -p /data/assets /data/scripts /data/outputs \
 && chown -R aavb:aavb /data /app

USER aavb

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "web.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
