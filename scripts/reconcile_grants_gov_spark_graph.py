"""Backfill canonical graph from existing Grants.gov nf_grant_sparks (no network)."""

from __future__ import annotations

import sys
import uuid

sys.path.insert(0, "src")

from nativeforge.db.rls import apply_org_rls_gucs, reapply_org_rls_after_commit
from nativeforge.db.session import SessionLocal
from nativeforge.services.canonical_intelligence_projection_service import (
    project_all_canonical_opportunities,
)
from nativeforge.services.early_signal_change_bridge_service import (
    project_recent_change_events_to_signals,
)
from nativeforge.services.grants_gov_spark_graph_reconciliation_service import (
    reconcile_grants_gov_sparks_to_canonical_graph,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def main() -> int:
    session = SessionLocal()
    try:
        apply_org_rls_gucs(session, DEMO, "demo")
        report = reconcile_grants_gov_sparks_to_canonical_graph(
            session, organization_id=DEMO, org_type="demo"
        )
        projection = project_all_canonical_opportunities(
            session.connection(), dry_run=False
        )
        early_signals = project_recent_change_events_to_signals(
            session.connection()
        )
        session.commit()
        reapply_org_rls_after_commit(session, DEMO, "demo")
        print(
            {
                "reconcile": report,
                "intelligence_projection": projection,
                "early_signal_bridge": early_signals,
            }
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
