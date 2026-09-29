"""Backfill canonical graph observations from existing nf_grant_sparks rows."""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from typing import Any

from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.opportunity_identity_versioning_service import (
    build_opportunity_identity,
)

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
        identity = build_opportunity_identity(
            opportunity_number=fields.get("opportunity_number"),
            doc_type=fields.get("doc_type"),
            opportunity_id=fields.get("source_record_id"),
            aln_list=fields.get("assistance_listings"),
            agency_code=fields.get("funder_agency_code"),
        )
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
        "canonical_metrics": metrics,
    }
