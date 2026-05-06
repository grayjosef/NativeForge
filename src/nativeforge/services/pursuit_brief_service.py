"""Deterministic pursuit brief builder for Grant Spark intelligence (Sprint 9)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfGrantSpark,
    NfNofoExtractionRun,
    NfPursuitBrief,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    NfSparkRequirement,
    NfSparkScore,
    NfTribalProfile,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    AuditAction,
    PursuitTaskStatus,
    ReviewArtifactType,
    ReviewStatus,
    SparkRequirementKind,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import pursuit_briefs as pb_repo
from nativeforge.repositories import pursuits as pursuit_repo
from nativeforge.repositories import review_artifacts as ra_repo
from nativeforge.repositories import spark_scores as score_repo
from nativeforge.repositories import tribal_profiles as tp_repo
from nativeforge.services.pursuit_service import PursuitNotFoundError

BRIEF_SCHEMA_VERSION = "1"
PURSUIT_BRIEF_ENGINE = "pursuit_brief_v1"


class GrantSparkNotFoundError(Exception):
    """Grant Spark not visible to org/plane."""


class PursuitMismatchError(Exception):
    """Provided pursuit does not belong to this Grant Spark."""


class PursuitBriefNotFoundError(Exception):
    """No pursuit brief row exists yet."""


def _iso(dt: object | None) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()  # type: ignore[no-any-return]
    return str(dt)


def _digest(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _count_requirements_by_kind(
    rows: list[NfSparkRequirement],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r.requirement_type
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _build_readiness(profile: NfTribalProfile | None) -> dict[str, Any]:
    if profile is None:
        return {
            "has_profile": False,
            "summary": "No tribal profile on file.",
            "readiness_band": "blocked",
            "signals": ["Create or load a tribal profile to anchor readiness."],
        }
    gm = profile.grants_manager if isinstance(profile.grants_manager, dict) else {}
    has_gm = bool(gm.get("email") or gm.get("name"))
    sam = profile.sam_registration_status
    signals = [
        f"Legal name recorded: {bool(profile.legal_name.strip())}",
        f"SAM snapshot status: {sam}",
        f"Grants contact present: {has_gm}",
    ]
    band = "strong"
    if sam == "unknown":
        band = "needs_attention"
    if not has_gm:
        band = "needs_attention"
    return {
        "has_profile": True,
        "legal_name": profile.legal_name,
        "entity_type": profile.entity_type,
        "sam_registration_status": sam,
        "has_grants_contact": has_gm,
        "readiness_band": band,
        "signals": signals,
        "summary": (
            "Organization readiness reflects SAM snapshot and contact completeness."
        ),
    }


def _build_opportunity(spark: NfGrantSpark) -> dict[str, Any]:
    opp_summary = f'{spark.agency} — "{spark.opportunity_title}" ({spark.award_type}).'
    return {
        "grant_spark_id": str(spark.id),
        "opportunity_title": spark.opportunity_title,
        "agency": spark.agency,
        "sub_agency": spark.sub_agency,
        "program_name": spark.program_name,
        "opportunity_number": spark.opportunity_number,
        "cfda_assistance_listing": spark.cfda_assistance_listing,
        "award_type": spark.award_type,
        "pipeline_stage": spark.pipeline_stage,
        "tribal_eligible": spark.tribal_eligible,
        "eligibility_tags": spark.eligibility_tags or [],
        "funding_floor": str(spark.funding_floor)
        if spark.funding_floor is not None
        else None,
        "funding_ceiling": str(spark.funding_ceiling)
        if spark.funding_ceiling is not None
        else None,
        "match_required": spark.match_required,
        "application_deadline": _iso(spark.application_deadline),
        "loi_deadline": _iso(spark.loi_deadline),
        "posted_date": _iso(spark.posted_date),
        "performance_period_start": _iso(spark.performance_period_start),
        "performance_period_end": _iso(spark.performance_period_end),
        "summary": opp_summary,
    }


def _build_eligibility_fit(
    spark: NfGrantSpark,
    profile: NfTribalProfile | None,
    score: NfSparkScore | None,
) -> dict[str, Any]:
    tier = "needs_review"
    rationale: list[str] = []
    if score is not None and score.disqualified:
        tier = "disqualified"
        rationale.append(
            score.disqualification_reason or "Spark score marked disqualified."
        )
    elif not spark.tribal_eligible:
        tier = "limited"
        rationale.append(
            "Grant Spark is not flagged as tribal-eligible — verify manual eligibility."
        )
    elif profile is None:
        tier = "needs_review"
        rationale.append(
            "Without a tribal profile, eligibility fit cannot be confirmed."
        )
    else:
        et = profile.entity_type
        tribal_surface = et.startswith("tribal_") or et in (
            "federally_recognized_tribe",
            "alaska_native_corporation",
            "alaska_native_village",
            "native_hawaiian_organization",
            "native_serving_nonprofit",
        )
        if spark.tribal_eligible and tribal_surface:
            tier = "strong"
            rationale.append(
                "Tribal applicant surface aligns with tribal-eligible Grant Spark."
            )
        elif spark.tribal_eligible:
            tier = "moderate"
            rationale.append(
                "Grant Spark is tribal-eligible — confirm entity classification."
            )
        else:
            tier = "limited"
            rationale.append(
                "Verify eligibility against NOFO text and tribal policies."
            )

    return {
        "fit_tier": tier,
        "tribal_eligible_flag_on_spark": spark.tribal_eligible,
        "profile_entity_type": profile.entity_type if profile else None,
        "rationale": rationale,
        "summary": f"Eligibility fit ({tier}) is advisory — human review gate applies.",
    }


def _build_requirement_summary(
    extraction_run: NfNofoExtractionRun | None,
    rows: list[NfSparkRequirement],
) -> dict[str, Any]:
    by_kind = _count_requirements_by_kind(rows)
    required_n = sum(1 for r in rows if r.required)
    return {
        "nofo_extraction_run_id": str(extraction_run.id) if extraction_run else None,
        "extractor_engine": extraction_run.extractor_engine if extraction_run else None,
        "requirement_row_count": len(rows),
        "required_row_count": required_n,
        "by_kind": by_kind,
        "summary": f"{len(rows)} NOFO requirement rows projected from extraction.",
    }


def _build_score_summary(score: NfSparkScore | None) -> dict[str, Any]:
    if score is None:
        return {
            "has_score": False,
            "summary": "No pursuit readiness score on file for this Grant Spark.",
        }
    return {
        "has_score": True,
        "spark_score_id": str(score.id),
        "composite": str(score.composite),
        "recommendation": score.recommendation,
        "disqualified": score.disqualified,
        "explanation_excerpt": (score.explanation_text[:320] + "…")
        if len(score.explanation_text) > 320
        else score.explanation_text,
        "dimension_scores": score.dimension_scores,
        "summary": (
            f"Readiness recommendation: {score.recommendation} "
            f"(composite {score.composite})."
        ),
    }


def _build_risks(
    profile: NfTribalProfile | None,
    nofo: NfNofoExtractionRun | None,
    req_rows: list[NfSparkRequirement],
    score: NfSparkScore | None,
    spark: NfGrantSpark,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if profile is None:
        items.append(
            {
                "severity": "high",
                "code": "NO_TRIBAL_PROFILE",
                "detail": "Create a tribal profile before exports and SF-424 previews.",
            }
        )
    elif profile.sam_registration_status == "unknown":
        items.append(
            {
                "severity": "medium",
                "code": "SAM_UNKNOWN",
                "detail": (
                    "SAM.gov registration unknown — confirm before submission prep."
                ),
            }
        )
    if nofo is None:
        items.append(
            {
                "severity": "medium",
                "code": "NO_NOFO_EXTRACTION",
                "detail": "Run NOFO extraction to materialize checklist rows.",
            }
        )
    elif len(req_rows) == 0:
        items.append(
            {
                "severity": "low",
                "code": "NO_REQUIREMENT_ROWS",
                "detail": (
                    "Extraction exists but no checklist rows — re-run or verify stub."
                ),
            }
        )
    if score is None:
        items.append(
            {
                "severity": "low",
                "code": "NO_SCORE",
                "detail": (
                    "Score this Grant Spark for a deterministic readiness signal."
                ),
            }
        )
    elif score.disqualified:
        items.append(
            {
                "severity": "high",
                "code": "SCORE_DISQUALIFIED",
                "detail": score.disqualification_reason
                or "Score flagged disqualified.",
            }
        )

    dl = spark.application_deadline
    if isinstance(dl, datetime):
        end = dl if dl.tzinfo else dl.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if timedelta(0) < end - now < timedelta(days=14):
            items.append(
                {
                    "severity": "medium",
                    "code": "DEADLINE_NEAR",
                    "detail": (
                        "Application deadline within two weeks — prioritize tasks."
                    ),
                }
            )

    return {"items": items, "summary": f"{len(items)} tracked risk / gap signals."}


def _build_required_documents(rows: list[NfSparkRequirement]) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    for r in rows:
        if r.requirement_type in (
            SparkRequirementKind.attachment.value,
            SparkRequirementKind.narrative_section.value,
            SparkRequirementKind.form.value,
        ):
            docs.append(
                {
                    "requirement_id": str(r.id),
                    "kind": r.requirement_type,
                    "label": r.label,
                    "required": r.required,
                    "page_limit": r.page_limit,
                }
            )
    docs.sort(key=lambda x: (x["kind"], x["label"]))
    return {
        "documents": docs,
        "summary": (
            f"{len(docs)} attachment / narrative / form rows from NOFO requirements."
        ),
    }


def _build_timeline(
    spark: NfGrantSpark,
    pursuit: Any | None,
    tasks: list[NfPursuitTask],
    calendar: list[NfPursuitCalendarEvent],
) -> dict[str, Any]:
    anchors: list[dict[str, Any]] = []
    if spark.loi_deadline:
        anchors.append(
            {
                "kind": "loi_deadline",
                "title": "Letter of intent deadline (Grant Spark)",
                "occurs_at": _iso(spark.loi_deadline),
                "source": "grant_spark",
            }
        )
    if spark.application_deadline:
        anchors.append(
            {
                "kind": "application_deadline",
                "title": "Application deadline (Grant Spark)",
                "occurs_at": _iso(spark.application_deadline),
                "source": "grant_spark",
            }
        )
    for ev in calendar:
        anchors.append(
            {
                "kind": ev.kind,
                "title": ev.title,
                "occurs_at": _iso(ev.occurs_at),
                "source": "pursuit_calendar",
                "event_id": str(ev.id),
            }
        )
    open_tasks = [t for t in tasks if t.status != PursuitTaskStatus.done.value]
    anchors.sort(key=lambda a: a.get("occurs_at") or "")
    return {
        "grant_spark_deadlines_recorded": bool(
            spark.loi_deadline or spark.application_deadline
        ),
        "pursuit_calendar_events": len(calendar),
        "open_tasks": len(open_tasks),
        "anchors": anchors[:40],
        "summary": (
            "Timeline merges Grant Spark deadlines with pursuit calendar anchors."
        ),
    }


def _build_review_gate_notes(
    profile: NfTribalProfile | None,
    nofo: NfNofoExtractionRun | None,
    score: NfSparkScore | None,
) -> list[str]:
    notes = [
        ("Deterministic brief — staff review before go/no-go decisions."),
        ("Trust exports and SF-424 previews are separate review-gated artifacts."),
    ]
    if profile is None:
        notes.append(
            "Establish a tribal profile before exporting organization-owned snapshots."
        )
    if nofo is None:
        notes.append(
            "Run NOFO extraction so checklist rows reflect the opportunity text."
        )
    if score is None:
        notes.append("Generate a readiness score to tighten recommendation language.")
    return notes


def _build_next_actions(
    profile: NfTribalProfile | None,
    nofo: NfNofoExtractionRun | None,
    req_rows: list[NfSparkRequirement],
    score: NfSparkScore | None,
    pursuit: Any | None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    order = 1
    if profile is None:
        actions.append(
            {
                "order": order,
                "action": "Create tribal profile",
                "reason": (
                    "Profile intelligence anchors eligibility and export readiness."
                ),
            }
        )
        order += 1
    if nofo is None:
        actions.append(
            {
                "order": order,
                "action": "Extract NOFO requirements",
                "reason": "Materialize checklist rows for pursuit mapping.",
            }
        )
        order += 1
    elif len(req_rows) == 0:
        actions.append(
            {
                "order": order,
                "action": "Re-run NOFO extraction or verify stub checklist",
                "reason": "No requirement rows are projected yet.",
            }
        )
        order += 1
    if score is None:
        actions.append(
            {
                "order": order,
                "action": "Score this Grant Spark",
                "reason": (
                    "Deterministic readiness scoring informs pursuit prioritization."
                ),
            }
        )
        order += 1
    if pursuit is None:
        actions.append(
            {
                "order": order,
                "action": "Open a pursuit",
                "reason": "Activate tasks and calendar anchors for application prep.",
            }
        )
        order += 1
    else:
        actions.append(
            {
                "order": order,
                "action": "Advance pursuit tasks",
                "reason": (
                    f"Pursuit {pursuit.id} is active — drive checklist completion."
                ),
            }
        )
        order += 1
    actions.append(
        {
            "order": order,
            "action": "Review pursuit brief in Trust workflow",
            "reason": "Human review gate applies before treating outputs as final.",
        }
    )
    return actions


def _digest_inputs(
    *,
    profile: NfTribalProfile | None,
    spark: NfGrantSpark,
    nofo: NfNofoExtractionRun | None,
    req_rows: list[NfSparkRequirement],
    score: NfSparkScore | None,
    pursuit: Any | None,
    tasks: list[NfPursuitTask],
    calendar: list[NfPursuitCalendarEvent],
) -> str:
    payload: dict[str, Any] = {
        "engine": PURSUIT_BRIEF_ENGINE,
        "schema": BRIEF_SCHEMA_VERSION,
        "profile": (
            {
                "id": str(profile.id),
                "updated_at": _iso(profile.updated_at),
            }
            if profile
            else None
        ),
        "spark": {"id": str(spark.id), "updated_at": _iso(spark.updated_at)},
        "nofo_run": (
            {"id": str(nofo.id), "created_at": _iso(nofo.created_at)} if nofo else None
        ),
        "requirement_row_ids": sorted(str(r.id) for r in req_rows),
        "score": (
            {"id": str(score.id), "created_at": _iso(score.created_at)}
            if score
            else None
        ),
        "pursuit": (
            {
                "id": str(pursuit.id),
                "updated_at": _iso(pursuit.updated_at),
            }
            if pursuit
            else None
        ),
        "task_ids": sorted(str(t.id) for t in tasks),
        "calendar_event_ids": sorted(str(c.id) for c in calendar),
    }
    return _digest(payload)


def build_brief_sections(
    *,
    profile: NfTribalProfile | None,
    spark: NfGrantSpark,
    nofo: NfNofoExtractionRun | None,
    req_rows: list[NfSparkRequirement],
    score: NfSparkScore | None,
    pursuit: Any | None,
    tasks: list[NfPursuitTask],
    calendar: list[NfPursuitCalendarEvent],
) -> tuple[dict[str, dict[str, Any]], str]:
    readiness = _build_readiness(profile)
    opportunity = _build_opportunity(spark)
    eligibility = _build_eligibility_fit(spark, profile, score)
    req_summary = _build_requirement_summary(nofo, req_rows)
    score_summary = _build_score_summary(score)
    risks = _build_risks(profile, nofo, req_rows, score, spark)
    req_docs = _build_required_documents(req_rows)
    timeline = _build_timeline(spark, pursuit, tasks, calendar)
    review_notes = _build_review_gate_notes(profile, nofo, score)
    next_actions = _build_next_actions(profile, nofo, req_rows, score, pursuit)
    recommended = {
        "review_gate_recommendations": review_notes,
        "next_actions": next_actions,
        "summary": "Review-gated recommendations precede operational next actions.",
    }
    digest = _digest_inputs(
        profile=profile,
        spark=spark,
        nofo=nofo,
        req_rows=req_rows,
        score=score,
        pursuit=pursuit,
        tasks=tasks,
        calendar=calendar,
    )
    sections = {
        "readiness_summary_json": readiness,
        "opportunity_summary_json": opportunity,
        "eligibility_fit_json": eligibility,
        "requirement_summary_json": req_summary,
        "score_summary_json": score_summary,
        "risks_and_gaps_json": risks,
        "required_documents_json": req_docs,
        "timeline_summary_json": timeline,
        "recommended_next_actions_json": recommended,
    }
    return sections, digest


def pursuit_brief_to_dict(row: NfPursuitBrief) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "grant_spark_id": str(row.grant_spark_id),
        "pursuit_id": str(row.pursuit_id) if row.pursuit_id else None,
        "review_artifact_id": str(row.review_artifact_id),
        "brief_engine": PURSUIT_BRIEF_ENGINE,
        "brief_schema_version": row.brief_schema_version,
        "status": row.status,
        "input_digest": row.input_digest,
        "readiness_summary": row.readiness_summary_json,
        "opportunity_summary": row.opportunity_summary_json,
        "eligibility_fit": row.eligibility_fit_json,
        "requirement_summary": row.requirement_summary_json,
        "score_summary": row.score_summary_json,
        "risks_and_gaps": row.risks_and_gaps_json,
        "required_documents": row.required_documents_json,
        "timeline_summary": row.timeline_summary_json,
        "recommended_next_actions": row.recommended_next_actions_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def generate_pursuit_brief(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    pursuit_id_explicit: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> NfPursuitBrief:
    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise GrantSparkNotFoundError("grant spark not found")

    pursuit = None
    if pursuit_id_explicit is not None:
        pursuit = pursuit_repo.get_grant_pursuit_scoped(
            session=session,
            pursuit_id=pursuit_id_explicit,
            org_id=org.id,
            org_type=org_type,
        )
        if pursuit is None:
            raise PursuitNotFoundError("pursuit not found")
        if pursuit.grant_spark_id != spark_id:
            raise PursuitMismatchError("pursuit does not match this grant spark")
    else:
        pursuit = pursuit_repo.get_grant_pursuit_by_spark(
            session=session,
            spark_id=spark_id,
            org_id=org.id,
            org_type=org_type,
        )

    profile = tp_repo.get_tribal_profile_for_org(
        session=session,
        org_id=org.id,
        org_type=org_type,
    )

    nofo = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )

    req_rows: list[NfSparkRequirement] = []
    if nofo is not None:
        req_rows = ne_repo.list_requirements_for_run(
            session=session,
            extraction_run_id=nofo.id,
            org_id=org.id,
            org_type=org_type,
        )

    score = score_repo.get_latest_spark_score(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )

    tasks: list[NfPursuitTask] = []
    calendar: list[NfPursuitCalendarEvent] = []
    if pursuit is not None:
        tasks = pursuit_repo.list_tasks_for_pursuit(
            session=session,
            pursuit_id=pursuit.id,
            org_id=org.id,
            org_type=org_type,
        )
        calendar = pursuit_repo.list_calendar_for_pursuit(
            session=session,
            pursuit_id=pursuit.id,
            org_id=org.id,
            org_type=org_type,
        )

    sections, digest = build_brief_sections(
        profile=profile,
        spark=spark,
        nofo=nofo,
        req_rows=req_rows,
        score=score,
        pursuit=pursuit,
        tasks=tasks,
        calendar=calendar,
    )

    art = ra_repo.create_review_artifact(
        session,
        org=org,
        actor_id=actor_id,
        artifact_type=ReviewArtifactType.pursuit_brief,
    )
    art.review_status = ReviewStatus.pending_review.value
    session.flush()

    is_demo = is_demo_for_org_type(org.org_type)
    row = NfPursuitBrief(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_spark_id=spark.id,
        pursuit_id=pursuit.id if pursuit else None,
        review_artifact_id=art.id,
        is_demo=is_demo,
        brief_schema_version=BRIEF_SCHEMA_VERSION,
        status="pending_review",
        input_digest=digest,
        readiness_summary_json=sections["readiness_summary_json"],
        opportunity_summary_json=sections["opportunity_summary_json"],
        eligibility_fit_json=sections["eligibility_fit_json"],
        requirement_summary_json=sections["requirement_summary_json"],
        score_summary_json=sections["score_summary_json"],
        risks_and_gaps_json=sections["risks_and_gaps_json"],
        required_documents_json=sections["required_documents_json"],
        timeline_summary_json=sections["timeline_summary_json"],
        recommended_next_actions_json=sections["recommended_next_actions_json"],
    )
    session.add(row)
    session.flush()

    ra_repo.append_audit(
        session,
        artifact=art,
        action=AuditAction.pursuit_brief_generated,
        payload={
            "nf_pursuit_brief_id": str(row.id),
            "grant_spark_id": str(spark.id),
            "pursuit_id": str(pursuit.id) if pursuit else None,
            "input_digest": digest,
            "brief_schema_version": BRIEF_SCHEMA_VERSION,
        },
        actor_id=actor_id,
        extraction_run_id=nofo.id if nofo else None,
    )
    session.flush()
    return row


def get_latest_by_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    spark_id: uuid.UUID,
) -> NfPursuitBrief:
    row = pb_repo.get_latest_for_spark(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        raise PursuitBriefNotFoundError("no pursuit brief for this grant spark")
    return row


def get_latest_by_pursuit(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
) -> NfPursuitBrief:
    row = pb_repo.get_latest_for_pursuit(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        raise PursuitBriefNotFoundError("no pursuit brief for this pursuit")
    return row
