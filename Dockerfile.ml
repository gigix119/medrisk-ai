# MedRisk AI ML pipeline - CPU-only image for running the medrisk_ml CLI (train/evaluate/
# explain/register/verify-bundle). No dataset, no model weights, and no secrets are baked
# into this image - real PCam data and artifacts/ are meant to be mounted at runtime, never
# COPYed in.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# CPU-only PyTorch/torchvision wheels first, from PyTorch's own CPU index - the default
# PyPI wheel bundles CUDA runtime libraries and is roughly 10x larger, which this image
# never needs. The plain `pip install -r requirements-ml.txt` afterwards is then a no-op
# for torch/torchvision (the pinned version is already satisfied) and installs everything
# else. Dependency layer first, so code-only changes don't invalidate the pip install cache.
COPY requirements-ml.txt ./
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-ml.txt

COPY medrisk_ml ./medrisk_ml
COPY configs ./configs
COPY scripts/ml ./scripts/ml

RUN groupadd --system medrisk && useradd --system --gid medrisk --create-home medrisk \
    && mkdir -p /app/artifacts /app/data \
    && chown -R medrisk:medrisk /app
USER medrisk

ENTRYPOINT ["python", "-m", "medrisk_ml.cli"]
CMD ["environment"]
