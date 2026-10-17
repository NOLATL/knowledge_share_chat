# Build context = repo root (the api package depends on the shared workspace
# member, so the whole uv workspace must be present). On Railway set this
# service's Dockerfile path to `api/Dockerfile` and keep the root as context.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY . .
# Install only the api package (+ its workspace deps, incl. shared); no dev group.
RUN uv sync --frozen --no-dev --package playbook-api

EXPOSE 8000
# Railway injects $PORT; sh -c expands it (JSON form avoids the CMD lint warning).
CMD ["sh", "-c", "uv run --no-dev --package playbook-api uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
