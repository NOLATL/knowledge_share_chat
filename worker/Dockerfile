# Build context = repo root (worker depends on the shared workspace member).
# On Railway set this service's Dockerfile path to `worker/Dockerfile`.
# The worker is a cron one-off: it runs the pipeline and exits 0.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY . .
RUN uv sync --frozen --no-dev --package playbook-worker

CMD ["uv", "run", "--no-dev", "--package", "playbook-worker", "python", "-m", "worker.main"]
