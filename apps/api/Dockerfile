# ─── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy only the dependency manifests first so this layer is cached
# as long as dependencies don't change.
COPY pyproject.toml ./
COPY src/ ./src/
COPY workers/ ./workers/

# Install into /build/.venv (no-system-python keeps it isolated)
RUN uv sync --extra asr --no-dev --no-editable

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# ffmpeg for rendering + fonts-liberation for drawtext title burn-in
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv and source from builder
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src
COPY --from=builder /build/workers /app/workers

# Alembic migrations bundled so the container can run `alembic upgrade head`
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    # Point drawtext to Liberation Sans (installed above)
    FFMPEG_DRAWTEXT_FONT="/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

EXPOSE 8000

# Default: run the FastAPI app.
# Override CMD to run alembic migrations or the RQ worker.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
