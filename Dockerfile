# AegisAPI application image — Phase 10, slice 1.
# Packages the FastAPI app so it runs as a container instead of the host venv.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is used by the compose healthcheck to probe /health.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies first so this layer is cached until requirements change.
# The root requirements.txt is the curated, ASCII source of truth.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App code. Copied so imports resolve as `app.*` with WORKDIR /app
# (i.e. /app/app/main.py) — same layout as running from backend/ on the host.
COPY backend/ ./

EXPOSE 8000

# --proxy-headers so the app trusts X-Forwarded-* once it sits behind Nginx.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
