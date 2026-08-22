# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build dependencies are kept only for the layer that installs Python packages.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements-deploy.txt \
    && apt-get purge -y --auto-remove build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# The API needs read access to the curated catalog and trained model assets.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data /app/models \
    && chown -R appuser:appuser /app

COPY docker/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod 0555 /usr/local/bin/entrypoint

USER appuser

EXPOSE 8000

ENTRYPOINT ["entrypoint"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
