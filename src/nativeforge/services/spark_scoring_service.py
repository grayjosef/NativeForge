"""Sprint 4: orchestrate deterministic Spark scoring + persistence."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfGrantSpark,
    NfSparkScore,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import spark_scores as score_repo
from nativeforge.repositories import tribal_profiles as tp_repo
from nativeforge.services.deterministic_spark_scorer import (
    SCORER_ENGINE,
    compute_deterministic_score,
)


class TribalProfileRequiredError(Exception):
    """Org must have an nf_tribal_profiles row before scoring."""


class NofoExtractionRequiredError(Exception):
    """Latest NOFO extraction is required for structured requirements."""


class GrantSparkNotFoundError(Exception):
    """Scoped grant spark missing."""


def _tags_for_scorer(spark: NfGrantSpark) -> list[str]:
    raw = spark.eligibility_tags or []
    tags = [t for t in raw if isinstance(t, str)]
    if spark.tribal_eligible and not any(x.lower() == "tribal_eligible" for x in tags):
        tags.append("tribal_eligible")
    return tags


def spark_score_to_dict(row: NfSparkScore) -> dict[str, Any]:
    comp = row.composite
    comp_f = float(comp) if comp is not None else 0.0
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "grant_spark_id": str(row.grant_spark_id),
        "tribal_profile_id": str(row.tribal_profile_id)
        if row.tribal_profile_id
        else None,
        "nofo_extraction_run_id": str(row.nofo_extraction_run_id)
        if row.nofo_extraction_run_id
        else None,
        "scorer_engine": row.scorer_engine,
        "dimension_scores": row.dimension_scores,
        "weights_used": row.weights_used,
        "composite": comp_f,
        "recommendation": row.recommendation,
        "explanation_text": row.explanation_text,
        "rationale_detail": row.rationale_detail,
        "disqualified": row.disqualified,
        "disqualification_reason": row.disqualification_reason,
        "override_reason": row.override_reason,
        "override_actor_id": str(row.override_actor_id)
        if row.override_actor_id
        else None,
        "overridden_at": row.overridden_at.isoformat() if row.overridden_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def run_deterministic_score(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> NfSparkScore:
    profile = tp_repo.get_tribal_profile_for_org(
        session=session,
        org_id=org.id,
        org_type=org_type,
    )
    if profile is None:
        raise TribalProfileRequiredError(
            "Create a tribal profile before scoring a Grant Spark."
        )

    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise GrantSparkNotFoundError("grant spark not found")

    nofo = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if nofo is None:
        raise NofoExtractionRequiredError(
            "Run NOFO extraction for this spark before scoring."
        )

    dims, composite, tier, dq, dq_reason, explanation, rationale = (
        compute_deterministic_score(
            profile_entity_type=profile.entity_type,
            profile_legal_name=profile.legal_name,
            profile_sam_status=profile.sam_registration_status,
            profile_standard_narratives=profile.standard_narratives,
            spark_program_name=spark.program_name,
            spark_title=spark.opportunity_title,
            spark_tribal_eligible=spark.tribal_eligible,
            spark_eligibility_tags=_tags_for_scorer(spark),
            spark_match_required=spark.match_required,
            spark_match_percent=spark.match_percent,
            spark_match_waiver_available=spark.match_waiver_available,
            spark_indirect_cost_allowable=spark.indirect_cost_allowable,
            spark_funding_ceiling=spark.funding_ceiling,
            spark_application_deadline=spark.application_deadline,
            structured_requirements=nofo.structured_requirements,
        )
    )

    is_demo = is_demo_for_org_type(org.org_type)
    comp_dec = Decimal(f"{composite:.2f}")

    row = NfSparkScore(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_spark_id=spark.id,
        is_demo=is_demo,
        tribal_profile_id=profile.id,
        nofo_extraction_run_id=nofo.id,
        scorer_engine=SCORER_ENGINE,
        dimension_scores=dims,
        weights_used=rationale.get("weights", {}),
        composite=comp_dec,
        recommendation=tier.value,
        explanation_text=explanation,
        rationale_detail=rationale,
        disqualified=dq,
        disqualification_reason=dq_reason,
    )
    session.add(row)
    session.flush()

    score_repo.append_spark_score_audit(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        tribal_profile_id=profile.id,
        extraction_run_id=nofo.id,
        action=AuditAction.spark_scored,
        payload={
            "spark_score_id": str(row.id),
            "grant_spark_id": str(spark.id),
            "composite": float(comp_dec),
            "recommendation": tier.value,
            "disqualified": dq,
        },
        actor_id=actor_id,
    )
    session.flush()
    return row


def apply_override(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    spark_score_id: uuid.UUID | None,
    reason: str,
    actor_id: uuid.UUID | None,
) -> NfSparkScore | None:
    is_demo = is_demo_for_org_type(org.org_type)
    if spark_score_id is not None:
        row = score_repo.get_spark_score_for_spark(
            session=session,
            score_id=spark_score_id,
            spark_id=spark_id,
            org_id=org.id,
            org_type=org_type,
        )
    else:
        row = score_repo.get_latest_spark_score(
            session=session,
            spark_id=spark_id,
            org_id=org.id,
            org_type=org_type,
        )
    if row is None:
        return None

    score_repo.apply_override_to_score(
        session,
        row=row,
        reason=reason,
        actor_id=actor_id,
    )
    score_repo.append_spark_score_audit(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        tribal_profile_id=row.tribal_profile_id,
        extraction_run_id=row.nofo_extraction_run_id,
        action=AuditAction.spark_score_overridden,
        payload={
            "spark_score_id": str(row.id),
            "grant_spark_id": str(spark_id),
            "override_reason": reason,
        },
        actor_id=actor_id,
    )
    session.flush()
    return row
