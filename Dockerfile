# Public demo image: FastAPI backend + widget + mock portal + cached demo answers.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    MEDINA_CACHE_DIR=demo_cache

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend backend
COPY data data
COPY data_access data_access
COPY widget widget
COPY demo demo
COPY demo_cache demo_cache
RUN uv sync --frozen --no-dev

EXPOSE 8000
# Render (and most hosts) pass the port in $PORT; forwarded headers give real client IPs for rate limiting.
CMD ["sh", "-c", "uv run --no-sync uvicorn medina.api:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
