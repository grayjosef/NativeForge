# syntax=docker/dockerfile:1.7
#
# One image, two stages, no provider in either of them.
#
# The frontend is built and then served by the API process from the same
# origin. That is a deliberate portability choice: one container, one
# hostname, no CORS, and no second service to reproduce on the next provider.
# It also removes the defect that made the built frontend unusable in any
# hosted environment - `apiFetchBase()` falls back to `http://127.0.0.1:8000`
# when `VITE_API_BASE` is unset, so a deployed page probed the *viewer's* own
# machine. Building with an empty base makes every request relative, which
# means this image is not bound to a hostname and can be promoted between
# environments unchanged.

########################  frontend  ########################
FROM node:22-slim AS frontend

WORKDIR /app/frontend

# Lockfile first: this layer rebuilds only when dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

#: Empty on purpose - see the header. Relative URLs, no hostname baked in.
ENV VITE_API_BASE=""
RUN npm run build

########################  runtime  ########################
FROM python:3.12-slim AS runtime

# Pinned to the same uv the CI lane uses, so a local build and a CI build
# resolve the identical dependency set.
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependencies before source: editing a service must not re-resolve the world.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
RUN uv sync --frozen --no-dev

COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY deploy/docker-entrypoint.sh /usr/local/bin/nativeforge-entrypoint
RUN chmod +x /usr/local/bin/nativeforge-entrypoint

# Stamped at build time. A container has no `.git` and no git binary, so the
# health endpoint cannot shell out for this the way the workstation services
# do - it has to be told, once, by whatever built the image.
ARG NF_GIT_SHA=unknown
ARG NF_SOURCE_DIRTY=unknown
ENV NF_GIT_SHA=${NF_GIT_SHA} \
    NF_SOURCE_DIRTY=${NF_SOURCE_DIRTY} \
    NF_FRONTEND_DIST=/app/frontend/dist

# Non-root: nothing in the running container needs to write to its own image.
RUN useradd --system --uid 10001 --create-home nativeforge \
    && chown -R nativeforge:nativeforge /app
USER nativeforge

EXPOSE 8000

# PORT is honoured because most PaaS providers inject it; it defaults to 8000
# so a plain `docker run` works with no environment at all.
ENTRYPOINT ["nativeforge-entrypoint"]
CMD ["serve"]
