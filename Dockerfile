# MedRisk AI API - production-conscious image for local/Compose use.
# app/services/model_deployment.py imports medrisk_inference unconditionally at startup
# (regardless of MODEL_REQUIRED), which in turn imports torch/torchvision/medrisk_ml at
# module scope - so this image needs the CPU-only inference runtime even when no model
# bundle is configured. No model weights are baked in either way.

FROM python:3.12-slim

# Optional, honest build provenance for GET /version - never fabricated when omitted, see
# app.core.config.Settings.GIT_COMMIT_SHA. Pass with:
#   docker build --build-arg GIT_COMMIT_SHA=$(git rev-parse --short HEAD) ...
ARG GIT_COMMIT_SHA=""
ENV GIT_COMMIT_SHA=${GIT_COMMIT_SHA}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependency layer first, so code-only changes don't invalidate the pip install cache.
# torch/torchvision are installed explicitly from PyTorch's own CPU index first, to
# guarantee a minimal CPU-only install regardless of platform (see Dockerfile.inference).
COPY requirements.txt requirements-inference.txt ./
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -r requirements-inference.txt

COPY app ./app
COPY medrisk_ml ./medrisk_ml
COPY medrisk_inference ./medrisk_inference
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN groupadd --system medrisk && useradd --system --gid medrisk --create-home medrisk \
    && chown -R medrisk:medrisk /app
USER medrisk

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
