"""Discovery intake runs — normalize structured batches into Grant Sparks (offline)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfDiscoveryIntakeCandidate,
    NfDiscoveryIntakeRun,
    NfGrantSpark,
    NfOpportunitySource,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryCandidateStatus,
    DiscoveryIntakeMode,
    DiscoveryIntakeRunStatus,
    FundingInstrument,
    GrantAwardType,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.services import (
    discovery_intake_dedupe_fingerprint_service as dedupe_fp_svc,
)
from nativeforge.services import discovery_review_service as d_rev
from nativeforge.services import (
    funding_opportunity_intake_discovery_bridge_service as foi_bridge_svc,
)
from nativeforge.services import grant_spark_service as gss
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.opportunity_discovery_service import (
    DiscoverySparkSeedPayload,
    compute_duplicate_key,
    compute_freshness_status,
    compute_native_relevance_reasons,
)

RUN_SCHEMA_VERSION = 1
INTAKE_SUMMARY_VERSION = "nf_discovery_intake_summary_v1"


def _after_candidate_persisted(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    candidate_row: NfDiscoveryIntakeCandidate,
    registry: NfOpportunitySource,
    now: datetime,
) -> None:
    session.flush()
    d_rev.process_intake_candidate_review_side_effects(
        session,
        org=org,
        org_type=org_type,
        candidate=candidate_row,
        registry=registry,
        now=now,
    )


class IntakeRunStateError(Exception):
    """Raised when an intake run cannot accept candidates in its current status."""


def intake_run_to_dict(row: NfDiscoveryIntakeRun) -> dict[str, Any]:
    def _d(v: object | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "source_registry_id": str(row.source_registry_id),
        "run_schema_version": row.run_schema_version,
        "run_status": row.run_status,
        "intake_mode": row.intake_mode,
        "started_at": _d(row.started_at),
        "completed_at": _d(row.completed_at),
        "candidate_count": row.candidate_count,
        "accepted_count": row.accepted_count,
        "duplicate_count": row.duplicate_count,
        "rejected_count": row.rejected_count,
        "error_count": row.error_count,
        "run_summary_json": row.run_summary_json,
        "error_summary_json": row.error_summary_json,
        "created_at": _d(row.created_at),
        "updated_at": _d(row.updated_at),
    }


def intake_candidate_to_dict(row: NfDiscoveryIntakeCandidate) -> dict[str, Any]:
    def _d(v: object | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "intake_run_id": str(row.intake_run_id),
        "source_registry_id": str(row.source_registry_id)
        if row.source_registry_id
        else None,
        "candidate_status": row.candidate_status,
        "raw_candidate_json": row.raw_candidate_json,
        "normalized_candidate_json": row.normalized_candidate_json,
        "normalization_errors_json": row.normalization_errors_json,
        "duplicate_key": row.duplicate_key,
        "duplicate_of_spark_id": str(row.duplicate_of_spark_id)
        if row.duplicate_of_spark_id
        else None,
        "created_spark_id": str(row.created_spark_id) if row.created_spark_id else None,
        "decision_reason": row.decision_reason,
        "native_relevance_score": row.native_relevance_score,
        "native_relevance_reasons_json": row.native_relevance_reasons_json,
        "freshness_status": row.freshness_status,
        "created_at": _d(row.created_at),
        "updated_at": _d(row.updated_at),
    }


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


def _parse_date(val: object | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        return date.fromisoformat(s[:10])
    return None


def _str_nonempty(raw: dict[str, Any], key: str) -> str | None:
    v = raw.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _parse_enum(
    label: str,
    raw_val: object | None,
    enum_cls: Any,
) -> tuple[Any | None, str | None]:
    if raw_val is None:
        return None, f"missing_{label}"
    try:
        if isinstance(raw_val, enum_cls):
            return raw_val, None
        return enum_cls(str(raw_val)), None
    except ValueError:
        return None, f"invalid_{label}"


def _eligibility_tags_from_raw(raw: dict[str, Any]) -> list[str] | None:
    et = raw.get("eligibility_tags")
    if isinstance(et, list):
        return [str(x) for x in et]
    ej = raw.get("eligibility_tags_json")
    if isinstance(ej, dict):
        t = ej.get("tags")
        if isinstance(t, list):
            return [str(x) for x in t]
    return None


def _spark_source_from_raw(raw: dict[str, Any]) -> GrantSparkSource:
    for key in ("ingest_source_key", "spark_source", "source"):
        v = raw.get(key)
        if v is None:
            continue
        try:
            return GrantSparkSource(str(v))
        except ValueError:
            pass
    return GrantSparkSource.manual


def _verification_for_spark(
    raw: dict[str, Any],
    registry: NfOpportunitySource,
) -> OpportunityVerificationStatus:
    v = raw.get("verification_status")
    if v is not None:
        try:
            return OpportunityVerificationStatus(str(v))
        except ValueError:
            pass
    try:
        return OpportunityVerificationStatus(registry.verification_status)
    except ValueError:
        return OpportunityVerificationStatus.unverified


@dataclass
class _NormalizedPreview:
    duplicate_key: str
    native_relevance_score: int
    native_relevance_reasons_json: list[str]
    freshness_status: str
    verification_status: str
    normalized_payload_extras: dict[str, Any]


def _preview_normalization(
    *,
    raw: dict[str, Any],
    seed: DiscoverySparkSeedPayload,
    registry: NfOpportunitySource,
    now: datetime,
) -> _NormalizedPreview:
    reasons, nscore = compute_native_relevance_reasons(
        tribal_eligible=seed.tribal_eligible,
        eligibility_tags=seed.eligibility_tags,
        opportunity_title=seed.opportunity_title,
        raw_nofo_text=seed.raw_nofo_text,
    )
    dup_url = seed.source_url or seed.url
    dup_key = compute_duplicate_key(
        source_url=dup_url,
        publisher_name=seed.publisher_name,
        opportunity_number=seed.opportunity_number,
        opportunity_title=seed.opportunity_title,
        opportunity_source_type=seed.opportunity_source_type,
    )
    ver = _verification_for_spark(raw, registry)
    discovered = seed.discovered_at or now
    verified = seed.last_verified_at or discovered
    fresh = compute_freshness_status(
        now=now,
        application_deadline=seed.application_deadline,
        last_verified_at=verified,
        stale_after_days=seed.stale_after_days,
    )
    extras: dict[str, Any] = {}
    for k in (
        "funding_domains_json",
        "description",
    ):
        if k in raw and raw[k] is not None:
            extras[k] = raw[k]
    for k, val in raw.items():
        if isinstance(k, str) and k.startswith("connector_") and val is not None:
            extras[k] = val
    return _NormalizedPreview(
        duplicate_key=dup_key,
        native_relevance_score=nscore,
        native_relevance_reasons_json=reasons,
        freshness_status=fresh.value,
        verification_status=ver.value,
        normalized_payload_extras=extras,
    )


def _build_seed_or_rejection(
    raw: dict[str, Any],
    *,
    source_registry_id: uuid.UUID,
    registry: NfOpportunitySource,
    stale_after_days: int,
) -> tuple[DiscoverySparkSeedPayload | None, str | None, list[str]]:
    """Return (payload, rejection_reason, normalization_warnings)."""
    warnings: list[str] = []
    title = _str_nonempty(raw, "opportunity_title")
    if not title:
        return None, "missing_or_empty_opportunity_title", warnings

    ost, err = _parse_enum(
        "opportunity_source_type",
        raw.get("opportunity_source_type"),
        OpportunitySourceType,
    )
    if ost is None:
        return None, err or "missing_opportunity_source_type", warnings

    award, err = _parse_enum("award_type", raw.get("award_type"), GrantAwardType)
    if award is None:
        return None, err or "missing_award_type", warnings

    agency = _str_nonempty(raw, "agency") or _str_nonempty(raw, "publisher_name")
    if not agency:
        return None, "missing_agency_and_publisher_name", warnings

    publisher = _str_nonempty(raw, "publisher_name") or agency

    raw_nofo = _str_nonempty(raw, "raw_nofo_text")
    desc = _str_nonempty(raw, "description")
    if raw_nofo is None and desc is not None:
        raw_nofo = desc

    elig_tags = _eligibility_tags_from_raw(raw)

    fi = None
    if raw.get("funding_instrument") is not None:
        try:
            fi = FundingInstrument(str(raw["funding_instrument"]))
        except ValueError:
            warnings.append("ignored_invalid_funding_instrument")

    posted = _parse_date(raw.get("posted_date"))
    loi = _parse_dt(raw.get("loi_deadline"))
    app_dl = _parse_dt(raw.get("application_deadline"))
    perf_start = _parse_date(raw.get("performance_period_start"))
    perf_end = _parse_date(raw.get("performance_period_end"))

    tribal_eligible = bool(raw.get("tribal_eligible", False))

    onum = _str_nonempty(raw, "opportunity_number")
    dup_key_preview = compute_duplicate_key(
        source_url=_str_nonempty(raw, "source_url") or _str_nonempty(raw, "url"),
        publisher_name=publisher,
        opportunity_number=onum,
        opportunity_title=title,
        opportunity_source_type=ost,
    )
    source_id = onum if onum else dup_key_preview

    seed = DiscoverySparkSeedPayload(
        source=_spark_source_from_raw(raw),
        source_id=source_id,
        agency=agency,
        opportunity_title=title,
        award_type=award,
        opportunity_source_type=ost,
        sub_agency=_str_nonempty(raw, "sub_agency"),
        program_name=_str_nonempty(raw, "program_name"),
        opportunity_number=onum,
        cfda_assistance_listing=_str_nonempty(raw, "cfda_assistance_listing"),
        url=_str_nonempty(raw, "url"),
        source_url=_str_nonempty(raw, "source_url"),
        publisher_name=publisher,
        posted_date=posted,
        loi_deadline=loi,
        application_deadline=app_dl,
        performance_period_start=perf_start,
        performance_period_end=perf_end,
        raw_nofo_text=raw_nofo,
        raw_nofo_url=_str_nonempty(raw, "raw_nofo_url"),
        eligibility_tags=elig_tags,
        eligibility_tags_json=raw.get("eligibility_tags_json")
        if isinstance(raw.get("eligibility_tags_json"), (dict, list))
        else None,
        geographic_scope_json=raw.get("geographic_scope_json")
        if raw.get("geographic_scope_json") is not None
        else None,
        applicant_types_json=raw.get("applicant_types_json")
        if raw.get("applicant_types_json") is not None
        else None,
        funding_instrument=fi,
        tribal_eligible=tribal_eligible,
        source_registry_id=source_registry_id,
        verification_status=_verification_for_spark(raw, registry),
        discovered_at=_parse_dt(raw.get("discovered_at")),
        last_verified_at=_parse_dt(raw.get("last_verified_at")),
        stale_after_days=stale_after_days,
    )
    return seed, None, warnings


def start_intake_run(
    session: Session,
    *,
    org: Organization,
    source_registry_id: uuid.UUID,
    intake_mode: DiscoveryIntakeMode,
    operator_note: str | None = None,
) -> NfDiscoveryIntakeRun:
    row = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=source_registry_id,
        org_id=org.id,
        org_type=cast(OrgType, org.org_type),
    )
    if row is None:
        raise ValueError("source_registry_id not found for this organization")

    is_demo = is_demo_for_org_type(org.org_type)
    summary: dict[str, Any] | None = None
    if operator_note and operator_note.strip():
        summary = {"operator_note": operator_note.strip()}

    run = NfDiscoveryIntakeRun(
        organization_id=org.id,
        is_demo=is_demo,
        source_registry_id=source_registry_id,
        run_schema_version=RUN_SCHEMA_VERSION,
        run_status=DiscoveryIntakeRunStatus.created.value,
        intake_mode=intake_mode.value,
        started_at=datetime.now(UTC),
        run_summary_json=summary,
    )
    session.add(run)
    session.flush()
    return run


def process_structured_candidates(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    run_id: uuid.UUID,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Process one structured batch for a run in `created` status; finalizes the run."""
    run = intake_repo.get_discovery_intake_run_scoped(
        session=session,
        run_id=run_id,
        org_id=org.id,
        org_type=org_type,
    )
    if run is None:
        raise ValueError("intake run not found")

    if run.run_status != DiscoveryIntakeRunStatus.created.value:
        raise IntakeRunStateError("intake run is not accepting candidates")

    registry = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=run.source_registry_id,
        org_id=org.id,
        org_type=org_type,
    )
    if registry is None:
        raise ValueError("opportunity source for this run is not visible")

    run.run_status = DiscoveryIntakeRunStatus.processing.value
    session.flush()

    now = datetime.now(UTC)
    dedupe_report = dedupe_fp_svc.build_intake_batch_dedupe_fingerprint_report(candidates)
    accepted = dup = rejected = err_cnt = 0
    error_entries: list[dict[str, Any]] = []

    for idx, cand in enumerate(candidates):
        raw_obj: dict[str, Any] = (
            dict(cand) if isinstance(cand, dict) else {"value": cand}
        )
        stale_days = 90
        if isinstance(raw_obj.get("stale_after_days"), int):
            stale_days = max(1, min(3650, int(raw_obj["stale_after_days"])))

        seed, rejection, norm_warnings = _build_seed_or_rejection(
            raw_obj,
            source_registry_id=run.source_registry_id,
            registry=registry,
            stale_after_days=stale_days,
        )

        preview: _NormalizedPreview | None = None
        if seed is not None:
            preview = _preview_normalization(
                raw=raw_obj,
                seed=seed,
                registry=registry,
                now=now,
            )

        dup_key_val = preview.duplicate_key if preview else None

        if rejection:
            rejected += 1
            cand = NfDiscoveryIntakeCandidate(
                organization_id=run.organization_id,
                is_demo=run.is_demo,
                intake_run_id=run.id,
                source_registry_id=run.source_registry_id,
                candidate_status=DiscoveryCandidateStatus.rejected.value,
                raw_candidate_json=raw_obj,
                normalized_candidate_json={"duplicate_key": dup_key_val}
                if dup_key_val
                else None,
                normalization_errors_json={"warnings": norm_warnings}
                if norm_warnings
                else None,
                duplicate_key=dup_key_val,
                decision_reason=rejection,
            )
            session.add(cand)
            _after_candidate_persisted(
                session,
                org=org,
                org_type=org_type,
                candidate_row=cand,
                registry=registry,
                now=now,
            )
            continue

        assert seed is not None and preview is not None

        existing = gs_repo.find_grant_spark_by_duplicate_key(
            session=session,
            duplicate_key=preview.duplicate_key,
            org_id=org.id,
            org_type=org_type,
        )
        if existing is not None:
            dup += 1
            cand = NfDiscoveryIntakeCandidate(
                organization_id=run.organization_id,
                is_demo=run.is_demo,
                intake_run_id=run.id,
                source_registry_id=run.source_registry_id,
                candidate_status=DiscoveryCandidateStatus.duplicate.value,
                raw_candidate_json=raw_obj,
                normalized_candidate_json=_normalized_json_from_preview(
                    preview, registry
                ),
                duplicate_key=preview.duplicate_key,
                duplicate_of_spark_id=existing.id,
                decision_reason="duplicate_key_matches_existing_grant_spark",
                native_relevance_score=preview.native_relevance_score,
                native_relevance_reasons_json=preview.native_relevance_reasons_json,
                freshness_status=preview.freshness_status,
            )
            session.add(cand)
            _after_candidate_persisted(
                session,
                org=org,
                org_type=org_type,
                candidate_row=cand,
                registry=registry,
                now=now,
            )
            continue

        spark: NfGrantSpark | None = None
        try:
            spark = ods.create_spark_from_discovery(session, org=org, body=seed)
        except gss.DuplicateGrantSparkError:
            spark = gs_repo.find_grant_spark_by_source_key(
                session=session,
                org_id=org.id,
                org_type=org_type,
                source=seed.source.value,
                source_id=seed.source_id,
            )
            if spark is not None:
                dup += 1
                cand = NfDiscoveryIntakeCandidate(
                    organization_id=run.organization_id,
                    is_demo=run.is_demo,
                    intake_run_id=run.id,
                    source_registry_id=run.source_registry_id,
                    candidate_status=DiscoveryCandidateStatus.duplicate.value,
                    raw_candidate_json=raw_obj,
                    normalized_candidate_json=_normalized_json_from_preview(
                        preview, registry
                    ),
                    duplicate_key=preview.duplicate_key,
                    duplicate_of_spark_id=spark.id,
                    decision_reason="unique_grant_spark_conflict_on_source_and_source_id",
                    native_relevance_score=preview.native_relevance_score,
                    native_relevance_reasons_json=preview.native_relevance_reasons_json,
                    freshness_status=preview.freshness_status,
                )
                session.add(cand)
                _after_candidate_persisted(
                    session,
                    org=org,
                    org_type=org_type,
                    candidate_row=cand,
                    registry=registry,
                    now=now,
                )
            else:
                err_cnt += 1
                msg = "duplicate_grant_spark_without_resolvable_existing_row"
                error_entries.append({"candidate_index": idx, "message": msg})
                session.add(
                    NfDiscoveryIntakeCandidate(
                        organization_id=run.organization_id,
                        is_demo=run.is_demo,
                        intake_run_id=run.id,
                        source_registry_id=run.source_registry_id,
                        candidate_status=DiscoveryCandidateStatus.error.value,
                        raw_candidate_json=raw_obj,
                        normalized_candidate_json=_normalized_json_from_preview(
                            preview, registry
                        ),
                        duplicate_key=preview.duplicate_key,
                        decision_reason=msg,
                    )
                )
            continue
        except Exception as ex:  # noqa: BLE001 — record per-candidate engine failures
            err_cnt += 1
            error_entries.append({"candidate_index": idx, "message": str(ex)})
            session.add(
                NfDiscoveryIntakeCandidate(
                    organization_id=run.organization_id,
                    is_demo=run.is_demo,
                    intake_run_id=run.id,
                    source_registry_id=run.source_registry_id,
                    candidate_status=DiscoveryCandidateStatus.error.value,
                    raw_candidate_json=raw_obj,
                    normalization_errors_json={"exception": str(ex)},
                    duplicate_key=dup_key_val,
                    decision_reason="unexpected_error_during_spark_creation",
                )
            )
            continue

        accepted += 1
        cand = NfDiscoveryIntakeCandidate(
            organization_id=run.organization_id,
            is_demo=run.is_demo,
            intake_run_id=run.id,
            source_registry_id=run.source_registry_id,
            candidate_status=DiscoveryCandidateStatus.accepted.value,
            raw_candidate_json=raw_obj,
            normalized_candidate_json=_normalized_json_from_spark_with_connector_extras(
                spark, registry, raw_obj
            ),
            duplicate_key=spark.duplicate_key,
            created_spark_id=spark.id,
            decision_reason="accepted_into_grant_spark",
            native_relevance_score=spark.native_relevance_score,
            native_relevance_reasons_json=spark.native_relevance_reasons_json,
            freshness_status=spark.freshness_status,
        )
        session.add(cand)
        _after_candidate_persisted(
            session,
            org=org,
            org_type=org_type,
            candidate_row=cand,
            registry=registry,
            now=now,
        )

    run.candidate_count = len(candidates)
    run.accepted_count = accepted
    run.duplicate_count = dup
    run.rejected_count = rejected
    run.error_count = err_cnt
    run.completed_at = datetime.now(UTC)
    if err_cnt > 0:
        run.run_status = DiscoveryIntakeRunStatus.completed_with_errors.value
    else:
        run.run_status = DiscoveryIntakeRunStatus.completed.value

    prior_summary = (
        run.run_summary_json if isinstance(run.run_summary_json, dict) else {}
    )
    summary_body: dict[str, Any] = {
        **prior_summary,
        "summary_version": INTAKE_SUMMARY_VERSION,
        "run_schema_version": RUN_SCHEMA_VERSION,
        "source_registry_id": str(run.source_registry_id),
        "counts": {
            "candidate_count": run.candidate_count,
            "accepted_count": run.accepted_count,
            "duplicate_count": run.duplicate_count,
            "rejected_count": run.rejected_count,
            "error_count": run.error_count,
        },
        "completed_at": run.completed_at.isoformat(),
    }
    summary_body = dedupe_fp_svc.attach_dedupe_fingerprint_report_to_intake_summary(
        summary_body,
        dedupe_report,
    )
    summary_body = foi_bridge_svc.attach_hardened_preview_to_intake_summary(
        summary_body,
        candidates,
    )
    run.run_summary_json = summary_body
    run.error_summary_json = {"errors": error_entries} if error_entries else None

    is_demo = is_demo_for_org_type(org.org_type)
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.discovery_intake_run_completed,
        payload={
            "intake_run_id": str(run.id),
            "source_registry_id": str(run.source_registry_id),
            "run_status": run.run_status,
            "counts": summary_body["counts"],
        },
        actor_id=None,
    )

    session.flush()

    return {
        "intake_run": intake_run_to_dict(run),
        "summary": summary_body,
    }


def _normalized_json_from_preview(
    preview: _NormalizedPreview,
    registry: NfOpportunitySource,
) -> dict[str, Any]:
    return {
        "duplicate_key": preview.duplicate_key,
        "native_relevance_score": preview.native_relevance_score,
        "native_relevance_reasons_json": preview.native_relevance_reasons_json,
        "freshness_status": preview.freshness_status,
        "verification_status": preview.verification_status,
        "source_attribution": {
            "source_registry_id": str(registry.id),
            "publisher_name": registry.publisher_name,
            "source_url": registry.source_url,
            "opportunity_source_type": registry.source_type,
        },
        "extras": preview.normalized_payload_extras,
    }


def _normalized_json_from_spark(
    spark: NfGrantSpark,
    registry: NfOpportunitySource,
) -> dict[str, Any]:
    return {
        "duplicate_key": spark.duplicate_key,
        "native_relevance_score": spark.native_relevance_score,
        "native_relevance_reasons_json": spark.native_relevance_reasons_json,
        "freshness_status": spark.freshness_status,
        "verification_status": spark.verification_status,
        "source_attribution": {
            "source_registry_id": str(spark.source_registry_id)
            if spark.source_registry_id
            else str(registry.id),
            "publisher_name": spark.publisher_name,
            "source_url": spark.source_url,
            "opportunity_source_type": spark.source_type,
        },
        "grant_spark_id": str(spark.id),
    }


def _normalized_json_from_spark_with_connector_extras(
    spark: NfGrantSpark,
    registry: NfOpportunitySource,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Accepted-spark snapshot plus connector provenance keys copied from raw intake."""
    base = _normalized_json_from_spark(spark, registry)
    conn = {
        k: v
        for k, v in raw.items()
        if isinstance(k, str) and k.startswith("connector_") and v is not None
    }
    if not conn:
        return base
    out = dict(base)
    out["extras"] = dict(conn)
    return out
