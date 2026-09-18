FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Stage 1: install dependencies only (cacheable layer — skips reinstall if only source changes)
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-install-project

# Stage 2: copy source, then install the project itself (registers rnd_test_task + entry points)
COPY . ./
RUN uv sync --locked

EXPOSE 8501

CMD ["uv", "run", "app"]
