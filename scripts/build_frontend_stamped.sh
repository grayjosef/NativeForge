#!/usr/bin/env bash
# Build once, stamp identity, write static /health /version + manifest.
# Does not source .env. Does not print secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${NF_ALLOW_DIRTY_BUILD:-0}" != "1" ]]; then
  if ! git diff --quiet --ignore-submodules HEAD --; then
    echo "refusing dirty tracked tree (set NF_ALLOW_DIRTY_BUILD=1 to override)" >&2
    exit 1
  fi
  if ! git diff --cached --quiet --ignore-submodules --; then
    echo "refusing dirty index (set NF_ALLOW_DIRTY_BUILD=1 to override)" >&2
    exit 1
  fi
fi

SOURCE_DIRTY="false"
if ! git diff --quiet --ignore-submodules HEAD -- \
  || ! git diff --cached --quiet --ignore-submodules --; then
  SOURCE_DIRTY="true"
fi

GIT_SHA="$(git rev-parse HEAD)"
BUILD_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo "building frontend (one Vite production build)"
npm --prefix frontend run build

export NF_STAMP_GIT_SHA="$GIT_SHA"
export NF_STAMP_BUILD_TIME="$BUILD_TIME"
export NF_STAMP_SOURCE_DIRTY="$SOURCE_DIRTY"
# shellcheck disable=SC1091
source .venv/bin/activate
python3 - <<'PY'
import os
from pathlib import Path

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    stamp_dist_tree,
)

dirty = os.environ["NF_STAMP_SOURCE_DIRTY"].lower() == "true"
stamp_dist_tree(
    Path("frontend/dist"),
    git_sha=os.environ["NF_STAMP_GIT_SHA"],
    build_time=os.environ["NF_STAMP_BUILD_TIME"],
    source_dirty=dirty,
)
print("stamped frontend/dist (nativeforge-build-sha + health + version + manifest)")
PY
