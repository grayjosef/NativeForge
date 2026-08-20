#!/usr/bin/env bash
# SC Monday demo staging verify — offline curated pack + assembler + bridge.
# No live ingest, source activation, migrations, or external URLs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

python3 <<'PY'
from nativeforge.services.sc_monday_curated_pack_service import (
    load_sc_curated_opportunity_pack,
    pack_invariant_failures,
)
from nativeforge.services.sc_monday_demo_assembler_service import (
    build_sc_monday_demo_artifact,
    demo_artifact_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.sc_monday_demo_labels_service import (
    build_demo_lane_claim_matrix,
)

pack = load_sc_curated_opportunity_pack()
pf = pack_invariant_failures(pack)
assert not pf, pf
art = build_sc_monday_demo_artifact()
af = demo_artifact_invariant_failures(art)
assert not af, af
payload = build_sc_customer_demo_bridge_payload(artifact=art)
bf = bridge_payload_invariant_failures(payload)
assert not bf, bf
claims = build_demo_lane_claim_matrix()
assert claims["live_ingestion"] == "NOT_CLAIMED"
assert payload["demo_route_path"] == DEMO_ROUTE_PATH
assert art["opportunities"]["south_carolina_count"] >= 1
assert art["opportunities"]["federal_count"] >= 1
print("sc_monday_demo_staging_verify: OK")
print(f"route={DEMO_ROUTE_PATH}")
print(f"profiles={art['profiles']['profile_count']}")
print(f"opportunities={art['opportunities']['total']}")
print(f"rows={art['combined_summary']['row_count']}")
print(f"digest={art['content_digest']}")
PY
