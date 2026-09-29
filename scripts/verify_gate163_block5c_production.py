"""Compact Block 5C production verification (read-only summary)."""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")

from nativeforge.db.rls import apply_org_rls_gucs
from nativeforge.db.session import SessionLocal
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.services.grants_gov_collector_gate_evidence_service import (
    fleet_live_source_rows,
    measure_grants_gov_collector_gates,
)
from nativeforge.services.source_fleet_live_readiness_service import (
    derive_collectors_live,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"


def main() -> int:
    session = SessionLocal()
    try:
        apply_org_rls_gucs(session, DEMO, "demo")
        sparks = len(
            gs_repo.list_grant_sparks_for_org(session=session, org_id=DEMO, org_type="demo")
        )
        gates = measure_grants_gov_collector_gates(session, organization_id=DEMO)
        live = derive_collectors_live(
            sources=fleet_live_source_rows(session, organization_id=DEMO)
        )
        out = {
            "grant_sparks": sparks,
            "raw_payloads": gates["payload_count"],
            "observations": gates["observation_count"],
            "canonical_opportunities": gates["canonical_count"],
            "provenance_rows": gates["provenance_count"],
            "collectors_live": live["collectors_live"],
            "unsatisfied_gates": gates["unsatisfied_gates"],
            "last_success_at": gates.get("last_success_at"),
            "source_id": SOURCE,
        }
        print(json.dumps(out, sort_keys=True, default=str))
        ok = (
            sparks >= 200
            and gates["payload_count"] >= 1
            and gates["observation_count"] >= 1
            and gates["canonical_count"] >= 1
            and gates["provenance_count"] >= 1
        )
        return 0 if ok else 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
