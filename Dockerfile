FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
COPY docker/wheels /wheels

# If local wheels are present, install offline; otherwise use PyPI.
RUN if ls /wheels/*.whl >/dev/null 2>&1; then \
      pip install --no-index --find-links=/wheels -r requirements.txt; \
    else \
      apt-get update && apt-get install -y --no-install-recommends curl \
        && rm -rf /var/lib/apt/lists/* \
        && pip install --upgrade pip && pip install -r requirements.txt; \
    fi

COPY . .
RUN mkdir -p /app/data/models

CMD ["python", "-m", "scripts.entrypoint_pipeline"]