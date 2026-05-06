"""
Model-agnostic demo/real isolation rules (NF-001).

Aligned with `execution/03-demo-isolation-spec.md`: demo orgs see only demo-flagged
records; real orgs see only non-demo records; writes must match org type.

No ContractForge code; no `nf_*` tables required at this layer.
"""

from __future__ import annotations

import uuid
from typing import Literal

OrgType = Literal["real", "demo"]


class DemoIsolationError(ValueError):
    """Raised when an operation violates demo/real isolation rules."""


def parse_demo_org_ids(raw: str) -> frozenset[uuid.UUID]:
    """Parse comma-separated UUID list from settings env string."""
    out: list[uuid.UUID] = []
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        out.append(uuid.UUID(p))
    return frozenset(out)


def is_demo_org(org_id: uuid.UUID, demo_org_ids: frozenset[uuid.UUID]) -> bool:
    return org_id in demo_org_ids


def org_type_for(org_id: uuid.UUID, demo_org_ids: frozenset[uuid.UUID]) -> OrgType:
    return "demo" if is_demo_org(org_id, demo_org_ids) else "real"


def row_matches_reader_org_type(reader_org_type: OrgType, record_is_demo: bool) -> bool:
    """
    Layer-4 style filter: demo org queries scope to is_demo=TRUE rows;
    real org queries scope to is_demo=FALSE rows.
    """
    if reader_org_type == "demo":
        return record_is_demo
    return not record_is_demo


def can_read_record(
    *,
    reader_org_id: uuid.UUID,
    reader_org_type: OrgType,
    record_org_id: uuid.UUID,
    record_is_demo: bool,
) -> bool:
    """Tenant boundary + demo scope (same-org only for this helper)."""
    if reader_org_id != record_org_id:
        return False
    return row_matches_reader_org_type(reader_org_type, record_is_demo)


def validate_record_write(
    *,
    org_id: uuid.UUID,
    record_is_demo: bool,
    demo_org_ids: frozenset[uuid.UUID],
) -> None:
    """
    Enforce agreement: demo orgs may only persist demo-flagged rows;
    real orgs only non-demo.

    Mirrors Layer 2 agreement (spec) before DB triggers exist.
    """
    expected_demo = is_demo_org(org_id, demo_org_ids)
    if record_is_demo != expected_demo:
        raise DemoIsolationError(
            "record is_demo flag does not match organization demo/real classification "
            f"(org_demo={expected_demo}, record_is_demo={record_is_demo})"
        )


def assert_demo_route_org(reader_org_type: OrgType) -> None:
    """Layer 3: demo-marked HTTP routes require a demo org (403 if violated)."""
    if reader_org_type != "demo":
        raise DemoIsolationError("demo-only route requires a demo organization context")


def assert_real_route_org(reader_org_type: OrgType) -> None:
    """Layer 3: production routes require a real org (403 if violated)."""
    if reader_org_type != "real":
        raise DemoIsolationError("real-data route requires a real organization context")


def require_explicit_demo_seed_context(
    *,
    is_demo_content: bool,
    explicit_demo_context: bool,
) -> None:
    """
    Fake/demo seeds must be loaded through an explicit demo context flag (loader gate).

    Prevents accidental attachment of demo-tagged rows without calling the demo seed
    path.
    """
    if is_demo_content and not explicit_demo_context:
        raise DemoIsolationError(
            "demo-classified content requires explicit_demo_context=True "
            "on the seed/load path"
        )
