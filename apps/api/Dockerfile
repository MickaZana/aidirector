# ─── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build the virtualenv at the same absolute path used by the runtime image.
# Console scripts otherwise retain a /build/.venv shebang when copied into /app.
WORKDIR /app

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
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/workers /app/workers

# Alembic migrations bundled so the container can run `alembic upgrade head`
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    # Point drawtext to Liberation Sans (installed above)
    FFMPEG_DRAWTEXT_FONT="/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# Create non-root user for security
RUN groupadd -r aidirector && useradd -r -g aidirector -d /app -s /sbin/nologin aidirector \
    && chown -R aidirector:aidirector /app

EXPOSE 8000

USER aidirector

# Default: run the FastAPI app.
# Override CMD to run alembic migrations or the RQ worker.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
