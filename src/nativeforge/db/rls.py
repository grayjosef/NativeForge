"""Postgres RLS session variables (Layer 5). SQLite no-ops."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from nativeforge.lib.demo_isolation import OrgType


def apply_org_rls_gucs(session: Session, org_id: uuid.UUID, org_type: OrgType) -> None:
    """Set per-transaction GUCs expected by nf_* RLS policies (PostgreSQL only)."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    is_demo = org_type == "demo"
    session.execute(
        text("SELECT set_config('app.current_org_id', :oid, true)"),
        {"oid": str(org_id)},
    )
    session.execute(
        text("SELECT set_config('app.current_org_is_demo', :d, true)"),
        {"d": "true" if is_demo else "false"},
    )
