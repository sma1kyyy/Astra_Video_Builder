# Astra Video Builder

Production-oriented automation pipeline for generating demonstration videos from YAML scenarios.

Astra Video Builder automates browser recording, screenshot-based capture, OCR, TTS narration, subtitles, annotations and rendering. It also includes a FastAPI web service and an optional LLM-powered YAML scenario generator.

## Why this project matters

- Reduces repetitive demo-video preparation from hours to minutes.
- Supports two capture modes: Live Recording and Screenshot Mode.
- Combines browser automation, OCR, audio generation and video rendering in one CLI/web workflow.
- Can run synchronously or through Celery + Redis for background processing.
- Documents deployment for Linux, macOS and Windows.

## Architecture

`YAML scenario → capture engine → OCR / TTS / annotations → MoviePy + FFmpeg → MP4/WAV output`

The web layer exposes the screenshot workflow through FastAPI. The queue mode uses Celery and Redis. The optional AI generator turns a natural-language description into a validated YAML scenario and can use OCR context.

## Stack

Python 3.13+, FastAPI, Selenium, FFmpeg, MoviePy, Pillow, Tesseract, TTS API, Celery, Redis, Docker Compose, UV.

## Quick start

Requirements:

- Python 3.13+
- UV
- FFmpeg
- Tesseract OCR; add `tesseract-ocr-rus` for Russian text
- Optional `LLM_API_KEY` for the AI generator

```bash
uv sync
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

For the web service and background rendering:

```bash
docker compose up --build
```

See the [Getting Started Guide](docs/Getting_Started_Guide.md), [API Reference](docs/API_Reference.md) and [Deployment Guide](docs/Deployment_Guide.md).

## Repository map

- `cli/`, `core/`, `engines/` — application and capture pipeline
- `web/` — FastAPI service and browser UI
- `docs/` — usage, architecture, deployment and troubleshooting
- `examples/` — ready YAML scenarios
- `tests/` — automated checks

## Platform notes

For macOS Live Recording, grant Screen Recording permission to the terminal or IDE. For Linux Wayland, the project can use `gpu-screen-recorder`.

## Project status

The repository contains the working CLI, web service, queue mode, examples and documentation. Configuration is supplied through `.env`; secrets should never be committed.

## Author

Kirill Kulikov — [GitHub profile](https://github.com/sma1kyyy)
