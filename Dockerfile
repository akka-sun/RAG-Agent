FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/
COPY pyproject.toml ./
COPY README.md ./

RUN uv sync --no-install-project --group dev --group test

COPY app ./app
COPY tests ./tests

CMD ["python", "--version"]
