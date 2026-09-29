"""Read-only SQL for per-source nine-gate collector evidence."""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa


def fetch_catalog_source(connection: Any, *, source_id: str) -> bool:
    """Registered = code seed catalog row and/or legacy health-registry row."""
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        if source_id in load_registry_rows():
            return True
    except Exception:  # noqa: BLE001 - unreadable catalog is not registration
        pass
    row = connection.execute(
        sa.text("SELECT 1 FROM nf_opportunity_sources WHERE seed_id = :sid LIMIT 1"),
        {"sid": source_id},
    ).first()
    return row is not None


def _org_param(organization_id: uuid.UUID) -> str:
    return str(organization_id)


def list_active_source_ids(
    connection: Any, *, organization_id: uuid.UUID
) -> list[str]:
    rows = connection.execute(
        sa.text(
            """
            SELECT source_id FROM nf_active_opportunity_sources
            WHERE organization_id = :org AND disabled_at IS NULL
            ORDER BY source_id
            """
        ),
        {"org": _org_param(organization_id)},
    ).scalars()
    return [str(r).strip() for r in rows if str(r or "").strip()]


def fetch_active_source_row(
    connection: Any, *, organization_id: uuid.UUID, source_id: str
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            sa.text(
                """
                SELECT disabled_at, activation_approved_at, last_success_at,
                       last_checked_at, consecutive_failure_count
                FROM nf_active_opportunity_sources
                WHERE organization_id = :org AND source_id = :sid
                LIMIT 1
                """
            ),
            {"org": _org_param(organization_id), "sid": source_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def count_live_raw_payloads(
    connection: Any, *, organization_id: uuid.UUID, source_id: str
) -> int:
    return int(
        connection.execute(
            sa.text(
                """
                SELECT count(*) FROM nf_source_collection_raw_payloads
                WHERE organization_id = :org AND source_id = :sid
                  AND payload_size_bytes > 100
                """
            ),
            {"org": _org_param(organization_id), "sid": source_id},
        ).scalar()
        or 0
    )


def count_source_observations(connection: Any, *, source_id: str) -> int:
    return int(
        connection.execute(
            sa.text(
                """
                SELECT count(*) FROM nf_opportunity_source_observations
                WHERE source_id = :sid
                """
            ),
            {"sid": source_id},
        ).scalar()
        or 0
    )


def count_distinct_canonical_from_observations(
    connection: Any, *, source_id: str
) -> int:
    return int(
        connection.execute(
            sa.text(
                """
                SELECT count(DISTINCT canonical_id)
                FROM nf_opportunity_source_observations
                WHERE source_id = :sid
                """
            ),
            {"sid": source_id},
        ).scalar()
        or 0
    )


def count_field_provenance(connection: Any, *, source_id: str) -> int:
    return int(
        connection.execute(
            sa.text(
                """
                SELECT count(*) FROM nf_opportunity_field_provenance
                WHERE source_id = :sid
                """
            ),
            {"sid": source_id},
        ).scalar()
        or 0
    )


def has_approved_terms_decision(
    connection: Any, *, organization_id: uuid.UUID, source_id: str
) -> bool:
    row = connection.execute(
        sa.text(
            """
            SELECT 1 FROM nf_source_authorization_decisions
            WHERE organization_id = :org AND source_id = :sid
              AND decision_kind = 'terms' AND decision = 'approved'
            LIMIT 1
            """
        ),
        {"org": _org_param(organization_id), "sid": source_id},
    ).first()
    return row is not None
