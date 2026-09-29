"""Backfill canonical graph observations from existing nf_grant_sparks rows."""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

SCHEMA_VERSION = "nf_grants_gov_spark_graph_reconciliation_v1"
SOURCE = "nf-seed-2026-api-grants-gov-search2"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalized_from_spark_row(row: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    title = str(row.opportunity_title or "").strip()
    if title:
        fields["title"] = title
    opp_num = str(row.opportunity_number or "").strip()
    if opp_num:
        fields["opportunity_number"] = opp_num
    agency = str(row.agency or "").strip()
    if agency:
        fields["funder_agency_name"] = agency
    if row.posted_date:
        fields["open_date"] = row.posted_date.isoformat()
    if row.application_deadline:
        fields["application_deadline"] = row.application_deadline.isoformat()
    if row.url:
        fields["source_url"] = row.url
    record_id = str(row.source_id or "").strip()
    if record_id:
        fields["source_record_id"] = record_id
    status_json = row.applicant_types_json or {}
    if isinstance(status_json, dict):
        st = status_json.get("grants_gov_opp_status")
        if st:
            fields["status"] = str(st)
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        content_fingerprint,
    )

    return {
        "schema_version": "nf_canonical_opportunity_normalizer_v1",
        "parser_version": "reconcile_from_grant_spark_v1",
        "parser_name": "grant_spark_reconcile",
        "adapter_key": "grants_gov_search2",
        "parseable": bool(fields.get("title")),
        "fields": fields,
        "fields_absent": [],
        "fields_not_supported": [],
        "content_fingerprint": content_fingerprint(fields),
        "source_record_id": fields.get("source_record_id"),
        "lifecycle_state": fields.get("status") or "unknown",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }


def _purge_spark_reconcile_l1_shell_observations(
    connection: Any, *, source_id: str
) -> int:
    """Remove bogus L1: rows from an earlier reconcile missing doc_type."""
    shell_obs = """
        SELECT observation_id FROM nf_opportunity_source_observations
        WHERE source_id = :sid AND canonical_id = 'L1:'
    """
    version_ids_sub = f"""
        SELECT version_id FROM nf_opportunity_versions
        WHERE observation_id IN ({shell_obs})
    """
    connection.execute(
        sa.text(
            f"""
            DELETE FROM nf_opportunity_change_events
            WHERE new_version_id IN ({version_ids_sub})
               OR prior_version_id IN ({version_ids_sub})
            """
        ),
        {"sid": source_id},
    )
    prov_result = connection.execute(
        sa.text(
            f"""
            DELETE FROM nf_opportunity_field_provenance
            WHERE version_id IN ({version_ids_sub})
            OR observation_id IN ({shell_obs})
            """
        ),
        {"sid": source_id},
    )
    prov = int(prov_result.rowcount or 0)
    connection.execute(
        sa.text(
            f"""
            DELETE FROM nf_opportunity_versions
            WHERE observation_id IN ({shell_obs})
            """
        ),
        {"sid": source_id},
    )
    result = connection.execute(
        sa.text(
            """
            DELETE FROM nf_opportunity_source_observations
            WHERE source_id = :sid AND canonical_id = 'L1:'
            """
        ),
        {"sid": source_id},
    )
    obs = int(result.rowcount or 0)
    connection.execute(
        sa.text(
            """
            DELETE FROM nf_canonical_opportunities
            WHERE canonical_id = 'L1:'
              AND NOT EXISTS (
                SELECT 1 FROM nf_opportunity_source_observations o
                WHERE o.canonical_id = nf_canonical_opportunities.canonical_id
              )
            """
        )
    )
    return obs + prov


def reconcile_grants_gov_sparks_to_canonical_graph(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    org_type: OrgType,
    source_id: str = SOURCE,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """No network. Idempotent graph backfill from persisted sparks."""
    stamp = now or dt.datetime.now(dt.UTC)
    shells_removed = _purge_spark_reconcile_l1_shell_observations(
        connection, source_id=source_id
    )
    rows = gs_repo.list_grant_sparks_for_org(
        session=connection, org_id=organization_id, org_type=org_type
    )
    grants_gov = [
        r
        for r in rows
        if str(r.source or "") == "grants_gov" and str(r.source_id or "").strip()
    ]
    observations: list[NormalizedSourceObservation] = []
    for row in grants_gov:
        normalized = _normalized_from_spark_row(row)
        if not normalized.get("parseable"):
            continue
        fields = normalized["fields"]
        meta = row.applicant_types_json if isinstance(row.applicant_types_json, dict) else {}
        if meta.get("grants_gov_doc_type"):
            fields["doc_type"] = str(meta["grants_gov_doc_type"])
        elif meta.get("grants_gov_opp_status") in ("posted", "forecasted"):
            fields["doc_type"] = (
                "synopsis" if meta.get("grants_gov_opp_status") == "posted" else "forecast"
            )
        identity = identity_for_normalized(normalized, source_id=source_id)
        dup = str(row.duplicate_key or row.id)
        observations.append(
            NormalizedSourceObservation(
                source_id=source_id,
                normalized=normalized,
                raw_payload_sha256=_sha256(f"spark-reconcile:{dup}"),
                identity=identity,
                raw_payload_attempt_id=_sha256(f"attempt:{dup}"),
                source_authority_host="api.grants.gov",
                observed_at=stamp,
            )
        )

    metrics = persist_observations(connection=connection, observations=observations)
    return {
        "schema_version": SCHEMA_VERSION,
        "sparks_considered": len(grants_gov),
        "observations_built": len(observations),
        "l1_shell_rows_removed": shells_removed,
        "canonical_metrics": metrics,
    }
