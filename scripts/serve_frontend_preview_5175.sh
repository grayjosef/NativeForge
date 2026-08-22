#!/usr/bin/env bash
# Fail-closed Vite preview of stamped dist on 127.0.0.1:5175 only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
python3 - <<'PY'
from pathlib import Path

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    require_stamped_dist,
)

require_stamped_dist(Path("frontend/dist"))
print("fail-closed dist checks passed")
PY

cd "$ROOT/frontend"
exec npm exec vite preview -- --host 127.0.0.1 --port 5175 --strictPort
