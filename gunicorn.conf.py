"""Gunicorn configuration for FastAPI/ASGI runtime."""

import os

# Ensure ASGI worker is used even when start command is `gunicorn app:app`.
worker_class = "uvicorn.workers.UvicornWorker"

# Respect Render's dynamic port.
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"

# Conservative defaults for small instances.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
