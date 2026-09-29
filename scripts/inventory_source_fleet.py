#!/usr/bin/env python3
"""Print source fleet expansion inventory JSON (read-only)."""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")

from nativeforge.db.rls import apply_org_rls_gucs
from nativeforge.db.session import SessionLocal
from nativeforge.services.source_collector_gate_evidence_service import (
    fleet_health_summary,
    fleet_live_source_rows,
)
from nativeforge.services.source_fleet_expansion_inventory_service import (
    build_source_fleet_inventory,
)
from nativeforge.services.source_fleet_live_readiness_service import (
    derive_collectors_live,
)
from nativeforge.services.south_carolina_grant_listing_research_service import (
    build_south_carolina_listing_research,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def main() -> int:
    session = SessionLocal()
    try:
        apply_org_rls_gucs(session, DEMO, "demo")
        live = derive_collectors_live(
            sources=fleet_live_source_rows(session, organization_id=DEMO)
        )
        inv = build_source_fleet_inventory(
            session.connection(),
            organization_id=DEMO,
            live_source_ids=list(live.get("fleet_live_sources") or []),
        )
        health = fleet_health_summary(session, organization_id=DEMO)
        sc = build_south_carolina_listing_research()
        print(
            json.dumps(
                {
                    "inventory": inv,
                    "fleet_health": health,
                    "south_carolina": sc,
                    "collectors_live": live,
                },
                sort_keys=True,
                default=str,
            )
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
