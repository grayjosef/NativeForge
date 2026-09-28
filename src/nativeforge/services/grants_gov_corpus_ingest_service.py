"""Ingest Grants.gov Search2 bytes into the canonical graph and grant sparks.

No network. The live fetch is upstream; this module normalizes, persists
provenance, and projects org-scoped discovery rows from one raw payload.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.domain.enums import (
    GrantAwardType,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    IDEMPOTENT,
    INSERTED,
    REJECTED,
    VERSIONED,
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (
    extract_records,
    normalize_record,
)
from nativeforge.services.grant_spark_service import (
    DuplicateGrantSparkError,
    GrantSparkPayload,
    create_grant_spark,
)
from nativeforge.services.opportunity_discovery_service import (
    compute_duplicate_key,
    compute_freshness_status,
    compute_native_relevance_reasons,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized
from nativeforge.services.source_definition_service import build_source_definition

SCHEMA_VERSION = "nf_grants_gov_corpus_ingest_v1"

GRANTS_GOV_DETAIL_URL = "https://www.grants.gov/search-results-detail/{opp_id}"


@dataclass(frozen=True)
class SparkProjectionMetrics:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    rejected: int = 0


@dataclass(frozen=True)
class CorpusIngestReport:
    fetched: int
    normalized: int
    rejected_unparseable: int
    canonical: dict[str, Any]
    sparks: SparkProjectionMetrics
    payload_sha256: str
    attempt_id: str | None


def _parse_grants_gov_date(raw: str | None) -> dt.date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_grants_gov_deadline(raw: str | None) -> dt.datetime | None:
    day = _parse_grants_gov_date(raw)
    if day is None:
        return None
    # Match ORM persistence: SQLite/tests store naive UTC datetimes.
    return dt.datetime.combine(day, dt.time(23, 59, 59))


def _spark_fields_from_hit(
    *,
    raw_hit: dict[str, Any],
    normalized: dict[str, Any],
    source_seed_id: str,
    now: dt.datetime,
) -> GrantSparkPayload | None:
    fields = dict(normalized.get("fields") or {})
    title = str(fields.get("title") or "").strip()
    if not title:
        return None
    agency = (
        str(fields.get("funder_agency_name") or "").strip()
        or str(fields.get("funder_agency_code") or "").strip()
        or "Unknown agency"
    )
    opp_num = str(fields.get("opportunity_number") or "").strip() or None
    record_id = str(fields.get("source_record_id") or raw_hit.get("id") or "").strip()
    if not record_id:
        return None
    url = (
        GRANTS_GOV_DETAIL_URL.format(opp_id=record_id)
        if record_id
        else None
    )
    cfda_list = fields.get("assistance_listings")
    cfda: str | None = None
    if isinstance(cfda_list, list) and cfda_list:
        cfda = str(cfda_list[0]).strip() or None
    posted = _parse_grants_gov_date(str(fields.get("open_date") or ""))
    deadline = _parse_grants_gov_deadline(str(fields.get("close_date") or ""))
    synopsis_status = str(fields.get("status") or "").strip().lower()
    tribal_eligible = False
    reasons, nscore = compute_native_relevance_reasons(
        tribal_eligible=tribal_eligible,
        eligibility_tags=None,
        opportunity_title=title,
        raw_nofo_text=None,
    )
    ost = OpportunitySourceType.federal
    dup_key = compute_duplicate_key(
        source_url=url,
        publisher_name=agency,
        opportunity_number=opp_num,
        opportunity_title=title,
        opportunity_source_type=ost,
    )
    freshness = compute_freshness_status(
        now=now,
        application_deadline=deadline,
        last_verified_at=now,
        stale_after_days=90,
    )
    return GrantSparkPayload(
        source=GrantSparkSource.grants_gov,
        source_id=record_id,
        agency=agency,
        opportunity_title=title,
        award_type=GrantAwardType.grant,
        sub_agency=str(fields.get("funder_agency_code") or "").strip() or None,
        program_name=None,
        opportunity_number=opp_num,
        cfda_assistance_listing=cfda,
        url=url,
        posted_date=posted,
        application_deadline=deadline,
        raw_nofo_text=None,
        raw_nofo_url=url,
        eligibility_tags=None,
        tribal_eligible=tribal_eligible,
        opportunity_source_type=ost,
        source_url=url,
        publisher_name=agency,
        discovered_at=now,
        last_verified_at=now,
        freshness_status=freshness,
        verification_status=OpportunityVerificationStatus.unverified,
        duplicate_key=dup_key,
        native_relevance_score=nscore,
        native_relevance_reasons_json=reasons,
        applicant_types_json={"grants_gov_opp_status": synopsis_status or None},
    )


def _spark_row_changed(row: Any, body: GrantSparkPayload) -> bool:
    checks: list[tuple[Any, Any]] = [
        (row.opportunity_title, body.opportunity_title),
        (row.agency, body.agency),
        (row.opportunity_number, body.opportunity_number),
        (row.posted_date, body.posted_date),
        (row.application_deadline, body.application_deadline),
        (row.url, body.url),
        (row.cfda_assistance_listing, body.cfda_assistance_listing),
    ]
    return any(existing != incoming for existing, incoming in checks)


def project_grant_sparks_from_hits(
    session: Session,
    *,
    org: Any,
    org_type: OrgType,
    source_seed_id: str,
    hits: list[dict[str, Any]],
    normalized_by_index: list[dict[str, Any]],
    now: dt.datetime | None = None,
) -> SparkProjectionMetrics:
    stamp = now or dt.datetime.now(dt.UTC)
    inserted = updated = unchanged = duplicates = rejected = 0

    for raw_hit, normalized in zip(hits, normalized_by_index, strict=False):
        if not normalized.get("parseable"):
            rejected += 1
            continue
        body = _spark_fields_from_hit(
            raw_hit=raw_hit,
            normalized=normalized,
            source_seed_id=source_seed_id,
            now=stamp,
        )
        if body is None:
            rejected += 1
            continue
        existing = gs_repo.find_grant_spark_by_duplicate_key(
            session=session,
            duplicate_key=body.duplicate_key,
            org_id=org.id,
            org_type=org_type,
        )
        if existing is None:
            try:
                create_grant_spark(session, org=org, body=body)
                inserted += 1
                continue
            except DuplicateGrantSparkError:
                existing = gs_repo.find_grant_spark_by_duplicate_key(
                    session=session,
                    duplicate_key=body.duplicate_key,
                    org_id=org.id,
                    org_type=org_type,
                )
                if existing is None:
                    rejected += 1
                    continue
                duplicates += 1

        if _spark_row_changed(existing, body):
            existing.opportunity_title = body.opportunity_title
            existing.agency = body.agency
            existing.opportunity_number = body.opportunity_number
            existing.posted_date = body.posted_date
            existing.application_deadline = body.application_deadline
            existing.url = body.url
            existing.source_url = body.source_url
            existing.cfda_assistance_listing = body.cfda_assistance_listing
            existing.last_verified_at = stamp
            if body.freshness_status is not None:
                existing.freshness_status = body.freshness_status.value
            session.flush()
            updated += 1
        else:
            unchanged += 1

    return SparkProjectionMetrics(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        duplicates=duplicates,
        rejected=rejected,
    )


def ingest_grants_gov_search2_payload(
    connection: Any,
    session: Session,
    *,
    organization_id: Any,
    org: Any,
    org_type: OrgType,
    source_id: str,
    body_bytes: bytes,
    payload_sha256: str,
    attempt_id: str | None = None,
    now: dt.datetime | None = None,
) -> CorpusIngestReport:
    """Normalize and persist one Search2 JSON payload."""
    stamp = now or dt.datetime.now(dt.UTC)
    definition = build_source_definition(
        source_id=source_id,
        connection=connection,
        organization_id=organization_id,
    )
    adapter_key = definition.get("adapter_key")
    payload = json.loads(body_bytes.decode("utf-8"))
    hits = extract_records(payload=payload, adapter_key=adapter_key)
    fetched = len(hits)

    observations: list[NormalizedSourceObservation] = []
    normalized_rows: list[dict[str, Any]] = []
    rejected_unparseable = 0
    authority_host = str(definition.get("authority_host") or "api.grants.gov")

    for hit in hits:
        normalized = normalize_record(record=hit, adapter_key=adapter_key)
        normalized_rows.append(normalized)
        if not normalized.get("parseable"):
            rejected_unparseable += 1
            continue
        identity = identity_for_normalized(normalized, source_id=source_id)
        observations.append(
            NormalizedSourceObservation(
                source_id=source_id,
                normalized=normalized,
                raw_payload_sha256=payload_sha256,
                identity=identity,
                raw_payload_attempt_id=attempt_id,
                source_authority_host=authority_host,
                observed_at=stamp,
            )
        )

    canonical_metrics = persist_observations(
        connection=connection, observations=observations, now=stamp
    )
    spark_metrics = project_grant_sparks_from_hits(
        session,
        org=org,
        org_type=org_type,
        source_seed_id=source_id,
        hits=hits,
        normalized_by_index=normalized_rows,
        now=stamp,
    )

    return CorpusIngestReport(
        fetched=fetched,
        normalized=len(observations),
        rejected_unparseable=rejected_unparseable,
        canonical=canonical_metrics,
        sparks=spark_metrics,
        payload_sha256=payload_sha256,
        attempt_id=attempt_id,
    )


def rollup_collection_metrics(report: CorpusIngestReport) -> dict[str, int]:
    """Map internal outcomes to Block 5B operator vocabulary."""
    cm = report.canonical
    sm = report.sparks
    inserted = int(cm.get("observations_inserted") or 0) + int(sm.inserted)
    updated = int(cm.get("observations_versioned") or 0) + int(sm.updated)
    unchanged = int(cm.get("observations_idempotent") or 0) + int(sm.unchanged)
    rejected = (
        report.rejected_unparseable
        + int(cm.get("observations_rejected") or 0)
        + int(cm.get("observations_failed") or 0)
        + int(sm.rejected)
    )
    duplicates = int(sm.duplicates)
    return {
        "fetched": report.fetched,
        "normalized": report.normalized,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "rejected": rejected,
        "duplicates": duplicates,
    }


def canonical_outcome_labels() -> dict[str, str]:
    return {
        INSERTED: "new observation linked to canonical graph",
        IDEMPOTENT: "identical observation already present",
        VERSIONED: "material field change produced new version",
        REJECTED: "refused before write",
    }
