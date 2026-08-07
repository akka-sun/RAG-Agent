FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libatomic1 \
    && git config --system core.autocrlf true \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY README.md ./

RUN uv sync --locked --no-install-project --group dev --group test

COPY app ./app
COPY tests ./tests

CMD ["python", "--version"]
