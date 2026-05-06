"""Deterministic discovery quality scoring for candidates and Grant Sparks (offline)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from nativeforge.db.models import (
    NfDiscoveryIntakeCandidate,
    NfGrantSpark,
    NfOpportunitySource,
)
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    DiscoveryRecommendedAction,
    FundingDomain,
    OpportunityVerificationStatus,
    SourceReliabilityRating,
    SparkFreshnessStatus,
)

QUALITY_SCHEMA_VERSION = "nf_discovery_quality_v1"


def _clamp_int(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _parse_str_enum(raw: object | None, enum_cls: type[Any]) -> Any | None:
    if raw is None:
        return None
    try:
        return enum_cls(str(raw))
    except ValueError:
        return None


def _parse_dt(val: object | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    return None


def _coalesce_dict(
    primary: dict[str, Any] | None,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    out = dict(fallback)
    if primary:
        out.update(primary)
    return out


def _domain_tokens(raw: object | None) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, list):
        out: set[str] = set()
        for x in raw:
            try:
                out.add(FundingDomain(str(x)).value)
            except ValueError:
                out.add(str(x).strip().lower())
        return {x for x in out if x}
    return set()


def _record_funding_domains(blob: dict[str, Any]) -> set[str]:
    direct = blob.get("funding_domains_json")
    if isinstance(direct, list):
        return _domain_tokens(direct)
    return set()


def _funding_domain_overlap_score(
    record_domains: set[str],
    registry_domains: set[str],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    if not registry_domains:
        return 72, ["registry_domains_unknown"]
    if not record_domains:
        return 38, ["record_funding_domains_missing"]
    inter = record_domains & registry_domains
    union = record_domains | registry_domains
    jacc = len(inter) / len(union) if union else 0.0
    score = _clamp_int(int(round(jacc * 100)))
    if score < 55:
        reasons.append("weak_funding_domain_alignment")
    return score, reasons


def _applicant_clarity(blob: dict[str, Any]) -> tuple[int, list[str]]:
    raw = blob.get("applicant_types_json")
    if raw is None:
        return 22, ["applicant_types_missing"]
    if isinstance(raw, list) and len(raw) > 0:
        return 100, []
    if isinstance(raw, dict) and len(raw) > 0:
        return 92, []
    return 30, ["applicant_types_unclear"]


def _reliability_points(r: SourceReliabilityRating | None) -> int:
    if r is None:
        return 42
    return {
        SourceReliabilityRating.unknown: 38,
        SourceReliabilityRating.low: 48,
        SourceReliabilityRating.medium: 62,
        SourceReliabilityRating.high: 82,
    }[r]


def _verification_points(v: OpportunityVerificationStatus | None) -> int:
    if v is None:
        return 36
    return {
        OpportunityVerificationStatus.unverified: 34,
        OpportunityVerificationStatus.operator_reviewed: 62,
        OpportunityVerificationStatus.trusted: 86,
        OpportunityVerificationStatus.deprecated: 5,
    }[v]


def _required_field_score(blob: dict[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    title = str(blob.get("opportunity_title") or "").strip()
    agency = str(blob.get("agency") or "").strip()
    sid = str(blob.get("source_id") or blob.get("ingest_source_id") or "").strip()
    score = 0
    if title:
        score += 40
    else:
        reasons.append("missing_opportunity_title")
    if agency:
        score += 30
    else:
        reasons.append("missing_agency")
    if sid:
        score += 30
    else:
        reasons.append("missing_source_identifier")
    return score, reasons


def _deadline_score(
    *,
    now: datetime,
    application_deadline: datetime | None,
    loi_deadline: datetime | None,
    freshness_status: str | None,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    now_a = _aware_utc(now)
    primary = application_deadline or loi_deadline
    if primary is None:
        reasons.append("missing_deadline")
        return 28, reasons
    p = _aware_utc(primary)
    if p < now_a:
        reasons.append("deadline_passed")
        return 12, reasons
    if freshness_status == SparkFreshnessStatus.closed.value:
        reasons.append("freshness_closed")
        return 10, reasons
    return 96, reasons


def _url_score(blob: dict[str, Any]) -> tuple[int, list[str]]:
    url = str(blob.get("url") or "").strip()
    src_url = str(blob.get("source_url") or "").strip()
    if url or src_url:
        return 100, []
    return 18, ["missing_opportunity_url"]


def _publisher_score(blob: dict[str, Any]) -> tuple[int, list[str]]:
    pub = str(blob.get("publisher_name") or "").strip()
    if pub:
        return 100, []
    return 35, ["publisher_missing"]


def _compute_duplicate_risk(
    *,
    duplicate_cluster_id: uuid.UUID | None,
    duplicate_of_spark_id: uuid.UUID | None,
    candidate_status: str | None,
    opportunity_number: str | None,
    opportunity_title: str | None,
    url: str | None,
    source_url: str | None,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    if duplicate_cluster_id is not None:
        score += 36
        reasons.append("duplicate_cluster_assigned")
    if duplicate_of_spark_id is not None:
        score += 40
        reasons.append("duplicate_of_known_spark")
    if candidate_status == DiscoveryCandidateStatus.duplicate.value:
        score = max(score, 58)
        reasons.append("candidate_marked_duplicate")
    onum = (opportunity_number or "").strip()
    if not onum:
        score += 14
        reasons.append("missing_opportunity_number_dup_signal")
    title = (opportunity_title or "").strip()
    if len(title) < 10:
        score += 12
        reasons.append("short_title_dup_noise")
    if not (url or "").strip() and not (source_url or "").strip():
        score += 16
        reasons.append("missing_urls_dup_noise")
    return _clamp_int(score), reasons


def _confidence_score(
    *,
    verification: OpportunityVerificationStatus | None,
    reliability: SourceReliabilityRating | None,
    missing_deadline: bool,
    missing_url: bool,
    applicant_weak: bool,
    domain_weak: bool,
) -> int:
    c = 100
    if verification in (None, OpportunityVerificationStatus.unverified):
        c -= 18
    if reliability in (None, SourceReliabilityRating.unknown):
        c -= 10
    if verification == OpportunityVerificationStatus.deprecated:
        c -= 55
    if missing_deadline:
        c -= 14
    if missing_url:
        c -= 12
    if applicant_weak:
        c -= 9
    if domain_weak:
        c -= 8
    return _clamp_int(c)


def _pick_recommended_action(
    *,
    quality: int,
    dup_risk: int,
    verification: OpportunityVerificationStatus | None,
) -> DiscoveryRecommendedAction:
    if verification == OpportunityVerificationStatus.deprecated:
        return DiscoveryRecommendedAction.reject
    if dup_risk >= 74:
        return DiscoveryRecommendedAction.merge
    if dup_risk >= 46:
        return DiscoveryRecommendedAction.needs_human_review
    if dup_risk >= 30 and quality < 72:
        return DiscoveryRecommendedAction.needs_human_review
    if quality < 44:
        return DiscoveryRecommendedAction.reject
    if quality < 62:
        return DiscoveryRecommendedAction.needs_human_review
    if verification == OpportunityVerificationStatus.unverified and quality < 78:
        return DiscoveryRecommendedAction.verify_source
    if quality >= 78 and dup_risk <= 26:
        return DiscoveryRecommendedAction.approve
    return DiscoveryRecommendedAction.needs_human_review


def _review_required(
    *,
    action: DiscoveryRecommendedAction,
    quality: int,
    dup_risk: int,
    confidence: int,
) -> bool:
    if action != DiscoveryRecommendedAction.approve:
        return True
    if quality < 85:
        return True
    if dup_risk > 22:
        return True
    if confidence < 74:
        return True
    return False


@dataclass(frozen=True)
class DiscoveryQualityInputs:
    """Normalized snapshot for scoring (Spark, candidate payload, or merged dict)."""

    reliability_rating: SourceReliabilityRating | None
    verification_status: OpportunityVerificationStatus | None
    opportunity_title: str
    agency: str | None
    opportunity_number: str | None
    source_id: str | None
    url: str | None
    source_url: str | None
    publisher_name: str | None
    application_deadline: datetime | None
    loi_deadline: datetime | None
    native_relevance_score: int | None
    funding_domains_record: set[str]
    funding_domains_registry: set[str]
    applicant_types_json: object | None
    duplicate_cluster_id: uuid.UUID | None
    duplicate_of_spark_id: uuid.UUID | None
    candidate_status: str | None
    freshness_status: str | None


def quality_summary_from_inputs(
    inp: DiscoveryQualityInputs,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the Sprint 13 deterministic quality summary JSON."""
    now_utc = _aware_utc(now or datetime.now(UTC))
    blob: dict[str, Any] = {
        "opportunity_title": inp.opportunity_title,
        "agency": inp.agency,
        "source_id": inp.source_id,
        "url": inp.url,
        "source_url": inp.source_url,
        "publisher_name": inp.publisher_name,
        "applicant_types_json": inp.applicant_types_json,
    }

    rel = _reliability_points(inp.reliability_rating)
    ver = _verification_points(inp.verification_status)
    req_score, req_reasons = _required_field_score(blob)
    dl_score, dl_reasons = _deadline_score(
        now=now_utc,
        application_deadline=inp.application_deadline,
        loi_deadline=inp.loi_deadline,
        freshness_status=inp.freshness_status,
    )
    u_score, u_reasons = _url_score(blob)
    p_score, p_reasons = _publisher_score(blob)
    dom_score, dom_reasons = _funding_domain_overlap_score(
        inp.funding_domains_record,
        inp.funding_domains_registry,
    )
    app_score, app_reasons = _applicant_clarity(blob)

    nrs = inp.native_relevance_score
    nrs_component = _clamp_int(int(round((nrs if nrs is not None else 44) * 0.85)))

    dup_risk, dup_reasons = _compute_duplicate_risk(
        duplicate_cluster_id=inp.duplicate_cluster_id,
        duplicate_of_spark_id=inp.duplicate_of_spark_id,
        candidate_status=inp.candidate_status,
        opportunity_number=inp.opportunity_number,
        opportunity_title=inp.opportunity_title,
        url=inp.url,
        source_url=inp.source_url,
    )

    # Weighted blend → quality_score (0–100), integers only.
    weighted = int(
        round(
            rel * 0.13
            + ver * 0.14
            + req_score * 0.13
            + dl_score * 0.13
            + u_score * 0.09
            + p_score * 0.07
            + nrs_component * 0.14
            + dom_score * 0.09
            + app_score * 0.08
        )
    )
    quality = _clamp_int(weighted - int(round(dup_risk * 0.28)))

    conf = _confidence_score(
        verification=inp.verification_status,
        reliability=inp.reliability_rating,
        missing_deadline="missing_deadline" in dl_reasons,
        missing_url="missing_opportunity_url" in u_reasons,
        applicant_weak=app_score < 70,
        domain_weak=dom_score < 60,
    )

    reason_codes = sorted(
        {
            *req_reasons,
            *dl_reasons,
            *u_reasons,
            *p_reasons,
            *dom_reasons,
            *app_reasons,
            *dup_reasons,
        }
    )

    action = _pick_recommended_action(
        quality=quality,
        dup_risk=dup_risk,
        verification=inp.verification_status,
    )

    return {
        "quality_schema_version": QUALITY_SCHEMA_VERSION,
        "quality_score": quality,
        "confidence_score": conf,
        "duplicate_risk_score": dup_risk,
        "reason_codes": reason_codes,
        "recommended_action": action.value,
        "review_required": _review_required(
            action=action,
            quality=quality,
            dup_risk=dup_risk,
            confidence=conf,
        ),
    }


def _registry_domains(registry: NfOpportunitySource | None) -> set[str]:
    if registry is None:
        return set()
    raw = registry.funding_domains_json
    return _domain_tokens(raw)


def quality_summary_for_grant_spark(
    spark: NfGrantSpark,
    registry: NfOpportunitySource | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Score a persisted Grant Spark using registry metadata when available."""
    rel = (
        _parse_str_enum(registry.reliability_rating, SourceReliabilityRating)
        if registry
        else None
    )
    ver = _parse_str_enum(spark.verification_status, OpportunityVerificationStatus)
    blob = {
        "opportunity_title": spark.opportunity_title,
        "agency": spark.agency,
        "source_id": spark.source_id,
        "url": spark.url,
        "source_url": spark.source_url,
        "publisher_name": spark.publisher_name,
        "applicant_types_json": spark.applicant_types_json,
    }
    record_domains: set[str] = set()
    # Eligibility JSON may carry domain hints from intake extras.
    ej = spark.eligibility_tags_json
    if isinstance(ej, dict):
        record_domains |= _domain_tokens(ej.get("funding_domains_json"))
    inp = DiscoveryQualityInputs(
        reliability_rating=rel,
        verification_status=ver,
        opportunity_title=str(blob["opportunity_title"] or ""),
        agency=blob["agency"],
        opportunity_number=spark.opportunity_number,
        source_id=str(blob["source_id"] or ""),
        url=blob["url"],
        source_url=blob["source_url"],
        publisher_name=blob["publisher_name"],
        application_deadline=spark.application_deadline,
        loi_deadline=spark.loi_deadline,
        native_relevance_score=spark.native_relevance_score,
        funding_domains_record=record_domains,
        funding_domains_registry=_registry_domains(registry),
        applicant_types_json=blob["applicant_types_json"],
        duplicate_cluster_id=spark.duplicate_cluster_id,
        duplicate_of_spark_id=None,
        candidate_status=None,
        freshness_status=spark.freshness_status,
    )
    return quality_summary_from_inputs(inp, now=now)


def quality_summary_for_intake_candidate(
    candidate: NfDiscoveryIntakeCandidate,
    registry: NfOpportunitySource | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Score an intake candidate row (prefers normalized JSON when present)."""
    raw = (
        candidate.raw_candidate_json
        if isinstance(candidate.raw_candidate_json, dict)
        else {}
    )
    norm = (
        candidate.normalized_candidate_json
        if isinstance(candidate.normalized_candidate_json, dict)
        else {}
    )
    blob = _coalesce_dict(norm, raw)

    rel = (
        _parse_str_enum(registry.reliability_rating, SourceReliabilityRating)
        if registry
        else None
    )
    ver_raw = blob.get("verification_status") or (
        registry.verification_status if registry else None
    )
    ver = _parse_str_enum(ver_raw, OpportunityVerificationStatus)

    title = str(blob.get("opportunity_title") or "")
    agency = str(blob.get("agency") or "").strip() or None
    publisher = str(blob.get("publisher_name") or "").strip() or None
    onum = str(blob.get("opportunity_number") or "").strip() or None
    sid = str(blob.get("source_id") or onum or "").strip() or None

    app_dl = _parse_dt(blob.get("application_deadline"))
    loi_dl = _parse_dt(blob.get("loi_deadline"))

    record_domains = _record_funding_domains(blob)

    inp = DiscoveryQualityInputs(
        reliability_rating=rel,
        verification_status=ver,
        opportunity_title=title,
        agency=agency,
        opportunity_number=onum,
        source_id=sid,
        url=str(blob.get("url") or "").strip() or None,
        source_url=str(blob.get("source_url") or "").strip() or None,
        publisher_name=publisher,
        application_deadline=app_dl,
        loi_deadline=loi_dl,
        native_relevance_score=candidate.native_relevance_score,
        funding_domains_record=record_domains,
        funding_domains_registry=_registry_domains(registry),
        applicant_types_json=blob.get("applicant_types_json"),
        duplicate_cluster_id=None,
        duplicate_of_spark_id=candidate.duplicate_of_spark_id,
        candidate_status=candidate.candidate_status,
        freshness_status=candidate.freshness_status,
    )
    return quality_summary_from_inputs(inp, now=now)
