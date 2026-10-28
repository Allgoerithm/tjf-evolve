# Leaderboard server image: dependencies only. Code and data (including the
# heldout split) are mounted read-only from the instructor repo at /app, so
# the image itself contains nothing secret and never needs rebuilding for
# code or data changes. Build context: repo root (see .dockerignore).
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra server && rm -rf /root/.cache

WORKDIR /app
EXPOSE 8000
CMD ["python", "-m", "evolve_demo.leaderboard", "--host", "0.0.0.0", "--port", "8000"]
