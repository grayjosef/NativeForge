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

# OCR system dependencies, installed at BUILD time. A runtime apt-get would
# make the image non-deterministic and would fail in any environment without
# outbound package access.
#
# `tesseract-ocr-eng` is the language data and is not optional: without it
# tesseract installs, runs, and recognises nothing - which arrives downstream
# as a blank page rather than as an error, and a blank page that was never
# really read is exactly what must never reach a conclusion. `poppler-utils`
# backs the PDF tooling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

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

# Self-verification, carried in the image on purpose.
#
# Two facts can only be established from inside the deployed artifact on the
# provider's own network: that the MANAGED database refuses the wrong tenant,
# and that OCR actually executes here. A verifier that lives on a developer
# machine proves neither. About 800 KB of fixtures is a small price for being
# able to ask the running deployment rather than infer from a build log.
#
# This is a one-shot command, never a route. Nothing here is reachable from
# the internet.
COPY deploy/verify_managed_runtime.py ./deploy/verify_managed_runtime.py
COPY deploy/bootstrap_runtime_role.py ./deploy/bootstrap_runtime_role.py
COPY scripts/check_postgres_tenant_isolation.py ./scripts/check_postgres_tenant_isolation.py
# Gate 163 operator tools. Dry-run by default; --apply is the human write.
# The seed file is what those scripts use to confirm the one public source.
# Nothing else under scripts/ or fixtures/ is copied.
COPY scripts/record_gate163_grants_gov_decisions.py ./scripts/record_gate163_grants_gov_decisions.py
COPY scripts/record_gate163_live_fetch_opt_in.py ./scripts/record_gate163_live_fetch_opt_in.py
COPY scripts/run_gate163_robots_preflight.py ./scripts/run_gate163_robots_preflight.py
COPY fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv ./fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv
COPY tests/fixtures/document_ocr/ ./fixtures/document_ocr/

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
