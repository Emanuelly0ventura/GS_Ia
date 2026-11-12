FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY app ./app
COPY dashboard ./dashboard
COPY migrations ./migrations
ENV PATH="/opt/venv/bin:$PATH"

# O Render fornece PORT; localmente usa 8000.
CMD ["sh", "-c", "uvicorn app.principal:app --host 0.0.0.0 --port ${PORT:-8000}"]
