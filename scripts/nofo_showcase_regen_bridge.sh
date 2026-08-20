#!/usr/bin/env bash
# Regen SC customer demo bridge JSON including NOFO showcase surface.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export NO_COLOR=1
python - <<'PY'
from nativeforge.services.nofo_showcase_demo_surface_service import build_nofo_showcase_demo_surface
from nativeforge.services.sc_monday_demo_bridge_service import write_sc_customer_demo_bridge_json
build_nofo_showcase_demo_surface(write_fixtures=True)
path = write_sc_customer_demo_bridge_json()
print("wrote", path)
PY
