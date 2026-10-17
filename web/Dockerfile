# Build context = repo root. On Railway set this service's Dockerfile path to
# `web/Dockerfile`. Next.js 15 production server.
FROM node:22-bookworm-slim

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
ENV NEXT_TELEMETRY_DISABLED=1

# Install deps first for layer caching. pnpm-workspace.yaml carries the
# allowBuilds config so esbuild/sharp/unrs-resolver postinstalls run.
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build

EXPOSE 3000
# Railway injects $PORT; sh -c expands it (JSON form avoids the CMD lint warning).
CMD ["sh", "-c", "pnpm start -p ${PORT:-3000}"]
