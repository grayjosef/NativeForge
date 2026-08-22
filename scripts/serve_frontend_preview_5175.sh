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
from nativeforge.services.gate37_production_grade_hardening_service import (
    require_loopback_serve_contract,
    require_preview_port_free,
)

require_stamped_dist(Path("frontend/dist"))
script = Path("scripts/serve_frontend_preview_5175.sh").read_text(
    encoding="utf-8"
)
require_loopback_serve_contract(script)
require_preview_port_free()
print("fail-closed dist, loopback, and port checks passed")
PY

cd "$ROOT/frontend"
exec npm exec vite preview -- --host 127.0.0.1 --port 5175 --strictPort
