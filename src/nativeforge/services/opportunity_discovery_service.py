"""Discovery Engine — source registry and Grant Spark intelligence (no scraping)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfGrantSpark,
    NfOpportunitySource,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    FundingInstrument,
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceReliabilityRating,
    SparkFreshnessStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.services import grant_spark_service as gss

INTELLIGENCE_VERSION = "nf_discovery_v1"

_NATIVE_TAG_HINTS = frozenset(
    {
        "tribal_eligible",
        "native_serving_nonprofit",
        "language_preservation",
        "culture",
        "ihs_service_population",
        "climate_resilience",
        "ihbg",
        "tribal_college",
        "alaska_native",
        "native_hawaiian",
    }
)

_TITLE_HINTS = (
    "tribal",
    "native",
    "indian country",
    "indigenous",
    "alaska native",
    "native hawaiian",
)


def opportunity_source_to_dict(row: NfOpportunitySource) -> dict[str, Any]:
    def _d(v: object | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id) if row.organization_id else None,
        "is_demo": row.is_demo,
        "source_name": row.source_name,
        "source_type": row.source_type,
        "source_url": row.source_url,
        "publisher_name": row.publisher_name,
        "description": row.description,
        "geographic_scope_json": row.geographic_scope_json,
        "native_relevance_notes": row.native_relevance_notes,
        "reliability_rating": row.reliability_rating,
        "freshness_interval_days": row.freshness_interval_days,
        "last_checked_at": _d(row.last_checked_at),
        "last_successful_check_at": _d(row.last_successful_check_at),
        "last_error": row.last_error,
        "is_active": row.is_active,
        "verification_status": row.verification_status,
        "created_at": _d(row.created_at),
        "updated_at": _d(row.updated_at),
    }


@dataclass(frozen=True)
class OpportunitySourcePayload:
    source_name: str
    source_type: OpportunitySourceType
    source_url: str | None = None
    publisher_name: str | None = None
    description: str | None = None
    geographic_scope_json: dict | list | None = None
    native_relevance_notes: str | None = None
    reliability_rating: SourceReliabilityRating = SourceReliabilityRating.unknown
    freshness_interval_days: int | None = None
    verification_status: OpportunityVerificationStatus = (
        OpportunityVerificationStatus.unverified
    )
    is_active: bool = True
    scope_global: bool = False


def create_opportunity_source(
    session: Session,
    *,
    org: Organization,
    body: OpportunitySourcePayload,
) -> NfOpportunitySource:
    """Persist one opportunity source registry row (tenant or global catalog)."""
    is_demo = is_demo_for_org_type(org.org_type)
    org_id = None if body.scope_global else org.id
    row = NfOpportunitySource(
        organization_id=org_id,
        is_demo=is_demo,
        source_name=body.source_name,
        source_type=body.source_type.value,
        source_url=body.source_url,
        publisher_name=body.publisher_name,
        description=body.description,
        geographic_scope_json=body.geographic_scope_json,
        native_relevance_notes=body.native_relevance_notes,
        reliability_rating=body.reliability_rating.value,
        freshness_interval_days=body.freshness_interval_days,
        verification_status=body.verification_status.value,
        is_active=body.is_active,
    )
    session.add(row)
    session.flush()
    return row


def list_sources(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfOpportunitySource]:
    return os_repo.list_opportunity_sources_for_org(
        session=session, org_id=org_id, org_type=org_type
    )


def normalize_canonical_url(url: str | None) -> str:
    """Deterministic URL normalization for duplicate_key stability."""
    if not url or not str(url).strip():
        return ""
    raw = str(url).strip()
    parsed = urlparse(raw)
    if not parsed.netloc and parsed.path:
        return raw.lower()
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or ""
    return urlunparse((scheme, netloc, path, "", "", "")).lower()


def compute_duplicate_key(
    *,
    source_url: str | None,
    publisher_name: str | None,
    opportunity_number: str | None,
    opportunity_title: str | None,
    opportunity_source_type: OpportunitySourceType | None,
) -> str:
    parts = [
        normalize_canonical_url(source_url),
        (publisher_name or "").strip().lower(),
        (opportunity_number or "").strip().lower(),
        (opportunity_title or "").strip().lower()[:400],
        opportunity_source_type.value if opportunity_source_type else "",
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_native_relevance_reasons(
    *,
    tribal_eligible: bool,
    eligibility_tags: list[str] | None,
    opportunity_title: str,
    raw_nofo_text: str | None,
) -> tuple[list[str], int]:
    """Deterministic Native relevance signals and bounded score (0–100)."""
    reasons: list[str] = []
    score = 0
    if tribal_eligible:
        reasons.append("tribal_eligible_true")
        score += 38
    tags = set(eligibility_tags or [])
    for tag in sorted(tags & _NATIVE_TAG_HINTS):
        reasons.append(f"eligibility_tag:{tag}")
        score += 7
    blob = f"{opportunity_title}\n{raw_nofo_text or ''}".lower()
    for hint in _TITLE_HINTS:
        if hint in blob:
            reasons.append(f"text_signal:{hint.replace(' ', '_')}")
            score += 6
            break
    # De-duplicate reasons while preserving order
    seen: set[str] = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq, min(100, score)


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def compute_freshness_status(
    *,
    now: datetime,
    application_deadline: datetime | None,
    last_verified_at: datetime | None,
    stale_after_days: int = 90,
) -> SparkFreshnessStatus:
    """Rule-based freshness from deadlines and verification timestamps."""
    now_a = _aware_utc(now)
    if application_deadline is not None:
        dl = _aware_utc(application_deadline)
        if dl < now_a:
            return SparkFreshnessStatus.closed
    if last_verified_at is None:
        return SparkFreshnessStatus.unknown
    lv = _aware_utc(last_verified_at)
    if (now_a - lv).days > stale_after_days:
        return SparkFreshnessStatus.stale
    return SparkFreshnessStatus.fresh


@dataclass(frozen=True)
class DiscoverySparkSeedPayload:
    """Structured intake used to seed a Grant Spark with Discovery metadata."""

    source: GrantSparkSource
    source_id: str
    agency: str
    opportunity_title: str
    award_type: GrantAwardType
    opportunity_source_type: OpportunitySourceType
    sub_agency: str | None = None
    program_name: str | None = None
    opportunity_number: str | None = None
    cfda_assistance_listing: str | None = None
    url: str | None = None
    source_url: str | None = None
    publisher_name: str | None = None
    posted_date: date | None = None
    loi_deadline: datetime | None = None
    application_deadline: datetime | None = None
    performance_period_start: date | None = None
    performance_period_end: date | None = None
    raw_nofo_text: str | None = None
    raw_nofo_url: str | None = None
    eligibility_tags: list[str] | None = None
    eligibility_tags_json: list | dict | None = None
    geographic_scope_json: dict | list | None = None
    applicant_types_json: list | dict | None = None
    funding_instrument: FundingInstrument | None = None
    tribal_eligible: bool = False
    pipeline_stage: GrantPipelineStage = GrantPipelineStage.new
    source_registry_id: uuid.UUID | None = None
    verification_status: OpportunityVerificationStatus | None = None
    discovered_at: datetime | None = None
    last_verified_at: datetime | None = None
    duplicate_cluster_id: uuid.UUID | None = None
    stale_after_days: int = 90


def create_spark_from_discovery(
    session: Session,
    *,
    org: Organization,
    body: DiscoverySparkSeedPayload,
) -> NfGrantSpark:
    """Normalize structured discovery intake into a scoped Grant Spark row."""
    now = datetime.now(UTC)
    reasons, nscore = compute_native_relevance_reasons(
        tribal_eligible=body.tribal_eligible,
        eligibility_tags=body.eligibility_tags,
        opportunity_title=body.opportunity_title,
        raw_nofo_text=body.raw_nofo_text,
    )
    dup_url = body.source_url or body.url
    dup_key = compute_duplicate_key(
        source_url=dup_url,
        publisher_name=body.publisher_name,
        opportunity_number=body.opportunity_number,
        opportunity_title=body.opportunity_title,
        opportunity_source_type=body.opportunity_source_type,
    )
    discovered = body.discovered_at or now
    verified = body.last_verified_at or discovered
    freshness = compute_freshness_status(
        now=now,
        application_deadline=body.application_deadline,
        last_verified_at=verified,
        stale_after_days=body.stale_after_days,
    )
    spark_verification = (
        body.verification_status or OpportunityVerificationStatus.unverified
    )

    elig_json = body.eligibility_tags_json
    if elig_json is None and body.eligibility_tags:
        elig_json = {"tags": body.eligibility_tags}

    gpayload = gss.GrantSparkPayload(
        source=body.source,
        source_id=body.source_id,
        agency=body.agency,
        opportunity_title=body.opportunity_title,
        award_type=body.award_type,
        sub_agency=body.sub_agency,
        program_name=body.program_name,
        opportunity_number=body.opportunity_number,
        cfda_assistance_listing=body.cfda_assistance_listing,
        url=body.url,
        posted_date=body.posted_date,
        loi_deadline=body.loi_deadline,
        application_deadline=body.application_deadline,
        performance_period_start=body.performance_period_start,
        performance_period_end=body.performance_period_end,
        raw_nofo_text=body.raw_nofo_text,
        raw_nofo_url=body.raw_nofo_url,
        eligibility_tags=body.eligibility_tags,
        tribal_eligible=body.tribal_eligible,
        pipeline_stage=body.pipeline_stage,
        source_registry_id=body.source_registry_id,
        opportunity_source_type=body.opportunity_source_type,
        source_url=body.source_url,
        publisher_name=body.publisher_name,
        discovered_at=discovered,
        last_verified_at=verified,
        freshness_status=freshness,
        verification_status=spark_verification,
        duplicate_key=dup_key,
        duplicate_cluster_id=body.duplicate_cluster_id,
        native_relevance_score=nscore,
        native_relevance_reasons_json=reasons,
        eligibility_tags_json=elig_json,
        geographic_scope_json=body.geographic_scope_json,
        funding_instrument=body.funding_instrument,
        applicant_types_json=body.applicant_types_json,
    )
    return gss.create_grant_spark(session, org=org, body=gpayload)


def opportunity_intelligence_summary(
    spark: NfGrantSpark,
) -> dict[str, Any]:
    """Compact opportunity intelligence view for a Grant Spark."""

    def _d(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return dt.isoformat()

    elig_fit: dict[str, Any] = {}
    if spark.eligibility_tags_json is not None:
        elig_fit["structured"] = spark.eligibility_tags_json
    if spark.eligibility_tags:
        elig_fit["tags"] = spark.eligibility_tags

    return {
        "opportunity_intelligence_version": INTELLIGENCE_VERSION,
        "grant_spark_id": str(spark.id),
        "duplicate_key": spark.duplicate_key,
        "duplicate_cluster_id": str(spark.duplicate_cluster_id)
        if spark.duplicate_cluster_id
        else None,
        "native_relevance": {
            "score": spark.native_relevance_score,
            "reasons": spark.native_relevance_reasons_json,
        },
        "freshness": {
            "freshness_status": spark.freshness_status,
            "application_deadline": _d(spark.application_deadline),
            "last_verified_at": _d(spark.last_verified_at),
        },
        "verification": {"verification_status": spark.verification_status},
        "source_attribution": {
            "source_registry_id": str(spark.source_registry_id)
            if spark.source_registry_id
            else None,
            "publisher_name": spark.publisher_name,
            "source_url": spark.source_url,
            "opportunity_source_type": spark.source_type,
            "ingest_source_key": spark.source,
        },
        "eligibility_fit": elig_fit,
        "geographic_scope_json": spark.geographic_scope_json,
        "funding_instrument": spark.funding_instrument,
        "applicant_types_json": spark.applicant_types_json,
    }


def get_spark_for_discovery_intel(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    spark_id: uuid.UUID,
) -> NfGrantSpark | None:
    return gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
