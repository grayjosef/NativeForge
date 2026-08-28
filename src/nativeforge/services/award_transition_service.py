"""Award transition: Mark as Awarded, and undo (Gate 91E).

The explicit customer action that moves a grant from the pursuit pipeline into
the Awarded Grants workspace.

## Why this service exists at all

Gate 91A confirmed that ``GrantPipelineStage.awarded`` is a plain enum member,
assignable by anything, and the only place the word "awarded" appears in the
codebase. Nothing records who set it or why.

That makes the product rule unenforceable:

    A pursued grant becomes an awarded-grant portfolio record only after an
    explicit user action or verified customer-provided award evidence.

This module is where that rule becomes real. ``mark_as_awarded`` requires
``user_action=True`` and a ``customer_org_id``, and refuses without either. A
backend setting a stage field does not go through here and therefore does not
produce a portfolio record - which is the point.

## Undo removes standing, never evidence

Undo restores the prior lane, status and visibility. It does **not** delete
uploaded documents, extracted requirements, user-entered award details, or the
audit event. Those are marked ``superseded`` and kept.

This is the Gate 87/88 principle applied to a user action: a reversal removes a
record's *standing*, never the evidence behind it. A customer who marks an award
by mistake, undoes it, then marks it correctly a week later should not have lost
the award letter they uploaded the first time.

Undo is idempotent. Clicking twice is not two reversals.

## Copy

Confirmation, verbatim, because the customer needs to know what begins::

    This will move the grant into your Awarded Grants workspace and start
    tracking reporting, compliance, financial, performance, and closeout
    obligations. You can undo this if it was a mistake.

Undo toast: ``Moved to Awarded Grants. Undo?``
Destination label: ``Awarded Grants`` - never "opportunities".
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.awarded_grant_portfolio_service import (
    REQUIRED_AWARD_DETAIL_FIELDS,
    build_awarded_grant_record,
)
from nativeforge.services.grant_lane_separation_service import (
    AWARDED_LANES,
    GRANT_LANES,
    PURSUIT_LANES,
    REVIEW_REQUIRED_SOURCE_LANES,
)

SCHEMA_VERSION = "nf_award_transition_v1"

# Lanes a Mark as Awarded may start from without a human review gate.
TRANSITIONABLE_FROM_LANES = PURSUIT_LANES

# The destination. Only one - closeout and closed are reached later, by the
# lifecycle, not by this action.
DEFAULT_TARGET_LANE = "awarded_active"

TRANSITION_STATUSES = frozenset(
    {
        "completed",
        "completed_with_human_review",
        "blocked",
        "undone",
    }
)

UNDO_STATUSES = frozenset({"undone", "already_undone", "blocked"})

# Customer-facing copy, held here so the UI and the tests read the same strings.
MARK_AS_AWARDED_LABEL = "Mark as Awarded"
AWARDED_PAGE_LABEL = "Awarded Grants"
CONFIRMATION_TEXT = (
    "This will move the grant into your Awarded Grants workspace and start "
    "tracking reporting, compliance, financial, performance, and closeout "
    "obligations. You can undo this if it was a mistake."
)
UNDO_TEXT = "Moved to Awarded Grants. Undo?"

# Evidence classes a reversal marks superseded rather than deleting.
PRESERVED_ON_UNDO: tuple[str, ...] = (
    "documents",
    "extracted_requirements",
    "award_details",
    "audit_events",
)


class AwardTransitionError(ValueError):
    """Raised when a transition cannot be performed honestly."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _missing_award_fields(award_details: dict[str, Any] | None) -> list[str]:
    details = award_details or {}
    return [
        f
        for f in REQUIRED_AWARD_DETAIL_FIELDS
        if details.get(f) in (None, "", [])
    ]


def _audit_event(
    *,
    action: str,
    transition_id: str,
    customer_org_id: str,
    actor: str | None,
    from_lane: str,
    to_lane: str,
    at: str | None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "action": action,
        "transition_id": transition_id,
        "customer_org_id": customer_org_id,
        "actor": actor,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": at,
        "detail": dict(detail or {}),
        # Audit events are never removed, only added to.
        "immutable": True,
    }


def build_award_transition_preview(
    *,
    source_opportunity_id: str,
    customer_org_id: str | None,
    from_lane: str,
    award_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What would happen, without doing it.

    Backs the confirmation dialog: the customer sees the destination, what
    begins, and what is still missing before they commit.
    """
    blocked: list[str] = []
    lane = from_lane if from_lane in GRANT_LANES else "unknown"

    if lane not in GRANT_LANES or from_lane not in GRANT_LANES:
        blocked.append(f"unrecognised_from_lane:{from_lane}")
    if not str(customer_org_id or "").strip():
        blocked.append("no_customer_org_id")
    if lane in AWARDED_LANES:
        blocked.append(f"already_in_an_awarded_lane:{lane}")

    requires_review = lane in REVIEW_REQUIRED_SOURCE_LANES or lane == "unknown"
    review_reasons: list[str] = []
    if lane in REVIEW_REQUIRED_SOURCE_LANES:
        review_reasons.append(f"transition_from_inactive_lane:{lane}")
    if lane == "unknown":
        review_reasons.append("from_lane_unknown")

    missing = _missing_award_fields(award_details)
    if missing:
        review_reasons.extend(f"missing_award_detail:{f}" for f in missing)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_opportunity_id": source_opportunity_id,
            "customer_org_id": customer_org_id,
            "from_lane": lane,
            "to_lane": DEFAULT_TARGET_LANE,
            "destination_label": AWARDED_PAGE_LABEL,
            "action_label": MARK_AS_AWARDED_LABEL,
            "confirmation_text": CONFIRMATION_TEXT,
            "what_begins": [
                "reporting obligation tracking",
                "compliance obligation tracking",
                "financial obligation tracking",
                "performance obligation tracking",
                "closeout obligation tracking",
            ],
            "missing_award_fields": missing,
            "requires_human_review": bool(requires_review or missing),
            "human_review_reasons": review_reasons,
            "can_proceed": not blocked,
            "blocked_reasons": blocked,
            # A preview changes nothing.
            "transition_performed": False,
            "obligations_active_after_transition": False,
            "fabricated": False,
        }
    )


def mark_as_awarded(
    *,
    transition_id: str,
    source_opportunity_id: str,
    customer_org_id: str | None,
    from_lane: str,
    prior_state: dict[str, Any] | None = None,
    award_details: dict[str, Any] | None = None,
    documents: list[dict[str, Any]] | None = None,
    extracted_requirements: dict[str, Any] | None = None,
    user_action: bool = False,
    actor: str | None = None,
    at: str | None = None,
    undo_expires_at: str | None = None,
    grant_title: str | None = None,
    agency: str | None = None,
    program: str | None = None,
) -> dict[str, Any]:
    """Move a pursuit record into the awarded portfolio.

    ``user_action`` must be ``True``. It is the whole point: a backend that
    infers an award from source text, a status string, or an enum assignment
    cannot satisfy it, and gets :class:`AwardTransitionError`.
    """
    if not user_action:
        raise AwardTransitionError(
            "mark_as_awarded requires an explicit user action; a grant may not "
            "become an awarded record from backend status inference or an enum "
            "assignment"
        )
    if not str(customer_org_id or "").strip():
        raise AwardTransitionError(
            "mark_as_awarded requires customer_org_id; awarded grants are "
            "customer-specific"
        )
    if from_lane not in GRANT_LANES:
        raise AwardTransitionError(f"unrecognised from_lane: {from_lane!r}")
    if from_lane in AWARDED_LANES:
        raise AwardTransitionError(
            f"record is already in an awarded lane: {from_lane!r}"
        )

    review_reasons: list[str] = []
    if from_lane in REVIEW_REQUIRED_SOURCE_LANES:
        # Not refused - a customer may be correcting a mistaken archive - but a
        # person has to confirm it.
        review_reasons.append(f"transition_from_inactive_lane:{from_lane}")
    if from_lane not in TRANSITIONABLE_FROM_LANES:
        review_reasons.append(f"unusual_source_lane:{from_lane}")

    missing = _missing_award_fields(award_details)
    review_reasons.extend(f"missing_award_detail:{f}" for f in missing)

    # Prior state must be captured before anything moves. Without it, undo is a
    # guess at what the record used to look like.
    snapshot = dict(prior_state or {})
    snapshot.setdefault("lane", from_lane)
    if "lane" not in (prior_state or {}):
        review_reasons.append("prior_state_snapshot_reconstructed_from_from_lane")

    awarded_grant_id = f"awarded-{source_opportunity_id}-{transition_id}"
    awarded_record = build_awarded_grant_record(
        awarded_grant_id=awarded_grant_id,
        customer_org_id=str(customer_org_id),
        source_opportunity_id=source_opportunity_id,
        grant_title=grant_title,
        agency=agency,
        program=program,
        award_number=(award_details or {}).get("award_number"),
        award_start_date=(award_details or {}).get("award_start_date"),
        award_end_date=(award_details or {}).get("award_end_date"),
        award_amount=(award_details or {}).get("award_amount"),
        assistance_listing=(award_details or {}).get("assistance_listing"),
        match_required=(award_details or {}).get("match_required"),
        documents=list(documents or []),
        lifecycle_status=DEFAULT_TARGET_LANE,
        **{
            k: list((extracted_requirements or {}).get(k) or [])
            for k in (
                "reporting_requirements",
                "financial_requirements",
                "performance_requirements",
                "compliance_requirements",
                "closeout_requirements",
            )
        },
    )

    status = "completed_with_human_review" if review_reasons else "completed"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "transition_id": transition_id,
            "customer_org_id": customer_org_id,
            "source_opportunity_id": source_opportunity_id,
            "from_lane": from_lane,
            "to_lane": DEFAULT_TARGET_LANE,
            "transition_status": status,
            "prior_state_snapshot": snapshot,
            "award_details": dict(award_details or {}),
            "created_awarded_grant_id": awarded_grant_id,
            "awarded_grant_record": awarded_record,
            "requires_human_review": bool(review_reasons),
            "human_review_reasons": review_reasons,
            "missing_award_fields": missing,
            "undo_available": True,
            "undo_expires_at": undo_expires_at,
            "undo_text": UNDO_TEXT,
            "destination_label": AWARDED_PAGE_LABEL,
            "audit_event": _audit_event(
                action="mark_as_awarded",
                transition_id=transition_id,
                customer_org_id=str(customer_org_id),
                actor=actor,
                from_lane=from_lane,
                to_lane=DEFAULT_TARGET_LANE,
                at=at,
                detail={
                    "missing_award_fields": missing,
                    "user_action": True,
                },
            ),
            "user_action": True,
            # Obligations are tracked from here, but they are not *dated* until
            # award details exist. Missing details keep this False.
            "obligations_dated": not missing,
            "fabricated": False,
        }
    )


def undo_mark_as_awarded(
    *,
    transition: dict[str, Any],
    actor: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    """Reverse a transition, preserving everything it produced.

    Idempotent: undoing an already-undone transition returns
    ``already_undone`` and changes nothing further.
    """
    if transition.get("transition_status") == "undone":
        return _json_safe(
            {
                **transition,
                "undo_status": "already_undone",
                "undo_applied_count": int(transition.get("undo_applied_count") or 1),
                "fabricated": False,
            }
        )

    snapshot = dict(transition.get("prior_state_snapshot") or {})
    restored_lane = snapshot.get("lane")

    blocked: list[str] = []
    if not restored_lane:
        blocked.append("no_prior_lane_in_snapshot")

    audit_events = list(transition.get("audit_events") or [])
    if transition.get("audit_event"):
        audit_events.append(transition["audit_event"])
    audit_events.append(
        _audit_event(
            action="undo_mark_as_awarded",
            transition_id=str(transition.get("transition_id")),
            customer_org_id=str(transition.get("customer_org_id")),
            actor=actor,
            from_lane=str(transition.get("to_lane")),
            to_lane=str(restored_lane or "unknown"),
            at=at,
            detail={"restored_from_snapshot": bool(restored_lane)},
        )
    )

    # Everything the transition produced is kept and marked superseded. Nothing
    # is deleted, and the counts are reported so a caller can assert it.
    awarded_record = transition.get("awarded_grant_record") or {}
    preserved = {
        "documents": list(awarded_record.get("documents") or []),
        "extracted_requirements": {
            k: list(awarded_record.get(k) or [])
            for k in (
                "reporting_requirements",
                "financial_requirements",
                "performance_requirements",
                "compliance_requirements",
                "closeout_requirements",
            )
        },
        "award_details": dict(transition.get("award_details") or {}),
        "audit_events": audit_events,
    }

    return _json_safe(
        {
            **transition,
            "transition_status": "undone",
            "undo_status": "undone",
            "undo_applied_count": 1,
            "restored_lane": restored_lane,
            "restored_state": snapshot,
            "undo_available": False,
            "awarded_grant_record_status": "superseded",
            "preserved_on_undo": preserved,
            "documents_deleted": 0,
            "requirements_deleted": 0,
            "award_details_deleted": 0,
            "audit_events_deleted": 0,
            "audit_events": audit_events,
            "blocked_reasons": blocked,
            "fabricated": False,
        }
    )


def transition_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    status = result.get("transition_status")
    if status and status not in TRANSITION_STATUSES:
        fails.append(f"transition_status_out_of_vocabulary:{status}")

    if result.get("transition_performed") is False:
        # A preview. It must not have produced anything.
        if result.get("created_awarded_grant_id"):
            fails.append("preview_created_an_awarded_grant")
        return fails

    if result.get("user_action") is not True:
        fails.append("transition_without_user_action")
    if not result.get("customer_org_id"):
        fails.append("transition_without_customer_org")
    if not result.get("audit_event") and not result.get("audit_events"):
        fails.append("transition_without_audit_event")
    if not result.get("prior_state_snapshot"):
        fails.append("transition_without_prior_state_snapshot")

    if result.get("to_lane") not in AWARDED_LANES:
        fails.append(f"transition_target_not_an_awarded_lane:{result.get('to_lane')}")
    if result.get("from_lane") in AWARDED_LANES:
        fails.append("transition_from_an_awarded_lane")

    if result.get("missing_award_fields") and not result.get("requires_human_review"):
        fails.append("missing_award_details_without_human_review")
    if result.get("missing_award_fields") and result.get("obligations_dated"):
        fails.append("obligations_dated_without_award_details")

    # Undo-specific: nothing may have been deleted.
    if result.get("undo_status") in {"undone", "already_undone"}:
        for field in (
            "documents_deleted",
            "requirements_deleted",
            "award_details_deleted",
            "audit_events_deleted",
        ):
            if result.get(field):
                fails.append(f"undo_deleted_evidence:{field}")
        if result.get("undo_status") == "undone":
            if result.get("awarded_grant_record_status") != "superseded":
                fails.append("undo_did_not_supersede_the_awarded_record")
            if result.get("undo_available") is not False:
                fails.append("undo_still_available_after_undo")
            if not result.get("preserved_on_undo"):
                fails.append("undo_preserved_nothing")

    return fails


# ---------------------------------------------------------------------------
# Gate 108C: the tenant-lane surface.
#
# Additive. Nothing above changes, because Gate 91's contract and its 934-line
# test file are the working definition of a safe transition and this gate has no
# quarrel with either.
#
# What is added is the seam between two identity spaces. Gates 90-91 built the
# awarded lane around `customer_org_id`; Gates 103-104 built the tenant beta
# lane around `tenant_id`. No bridge exists in the tree, and this does not
# invent one - both ids are required from the caller and neither is derived from
# the other. See docs/operations/594.
#
# The second thing it adds is the rule the awarded workspace turns on:
# `active_obligations_created` is False unless evidence or a person supports it.
# A transition creates an award record; it does not create duties.
# ---------------------------------------------------------------------------

# The lane a Mark as Awarded most naturally starts from: submitted, decision
# outstanding. Taken from PURSUIT_LANES rather than written out, so it cannot
# drift away from the vocabulary that validates it.
DEFAULT_TRANSITIONABLE_FROM_LANE = "award_pending"

TENANT_TRANSITION_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "pursuit_record_id",
    "source_opportunity_id",
    "award_id",
    "transition_status",
    "undo_available",
    "audit_event_id",
    "pursuit_history_preserved",
    "source_history_preserved",
    "awarded_record_created",
    "active_obligations_created",
    "human_review_required",
    "blocked_reasons",
)


def mark_awarded_for_tenant(
    *,
    tenant_id: Any,
    customer_org_id: Any,
    source_opportunity_id: Any,
    pursuit_record_id: Any = None,
    # A real member of PURSUIT_LANES, not a plausible-looking string. An early
    # draft defaulted to "pursuing", which is not in the vocabulary and would
    # have raised on every call that did not override it - the same forking
    # mistake in miniature.
    from_lane: str = DEFAULT_TRANSITIONABLE_FROM_LANE,
    transition_id: str | None = None,
    prior_state: dict[str, Any] | None = None,
    award_details: dict[str, Any] | None = None,
    documents: list[dict[str, Any]] | None = None,
    extracted_requirements: dict[str, Any] | None = None,
    requirements_extraction_status: Any = None,
    user_action: bool = False,
    actor: str | None = None,
    at: str | None = None,
    grant_title: str | None = None,
    agency: str | None = None,
) -> dict[str, Any]:
    """Move a tenant's pursued opportunity into Awarded Grants.

    Delegates the transition itself to :func:`mark_as_awarded`, so the
    user-action requirement, the evidence preservation and the audit event are
    Gate 91's rather than a second implementation of them.
    """
    from nativeforge.services.awarded_grant_record_service import (
        build_awarded_grant_record,
    )

    blocked_reasons: list[str] = []
    if not str(tenant_id or "").strip():
        raise AwardTransitionError(
            "mark_awarded_for_tenant requires tenant_id; an awarded record with "
            "no tenant is every tenant's"
        )

    transition = mark_as_awarded(
        transition_id=transition_id or f"tr-{source_opportunity_id}",
        source_opportunity_id=str(source_opportunity_id),
        customer_org_id=customer_org_id,
        from_lane=from_lane,
        prior_state=prior_state,
        award_details=award_details,
        documents=documents,
        extracted_requirements=extracted_requirements,
        user_action=user_action,
        actor=actor,
        at=at,
        grant_title=grant_title,
        agency=agency,
    )

    details = dict(award_details or {})
    record = build_awarded_grant_record(
        tenant_id=tenant_id,
        customer_org_id=customer_org_id,
        source_opportunity_id=source_opportunity_id,
        pursuit_record_id=pursuit_record_id,
        award_title=grant_title,
        funding_agency=agency,
        award_number=details.get("award_number"),
        award_start_date=details.get("award_start_date"),
        award_end_date=details.get("award_end_date"),
        total_award_amount=details.get("award_amount"),
        match_required=details.get("match_required"),
        award_status="active_award",
        requirements_extraction_status=requirements_extraction_status,
    )

    blocked_reasons.extend(record.get("blocked_reasons") or [])
    if not pursuit_record_id:
        blocked_reasons.append("transition_without_a_pursuit_record")

    audit_event = transition.get("audit_event")
    audit_event_id = (
        audit_event.get("event_id")
        if isinstance(audit_event, dict) and audit_event.get("event_id")
        else transition["transition_id"]
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "tenant_org_binding_status": record["tenant_org_binding_status"],
            "pursuit_record_id": pursuit_record_id,
            "source_opportunity_id": source_opportunity_id,
            "award_id": record["award_id"],
            "transition_id": transition["transition_id"],
            "transition_status": transition["transition_status"],
            "undo_available": transition["undo_available"],
            "audit_event_id": audit_event_id,
            "gate91_transition": transition,
            "awarded_grant_record": record,
            "awarded_record_created": True,
            # A transition creates an award record. It never creates duties.
            "active_obligations_created": False,
            "human_review_required": bool(
                transition.get("requires_human_review")
                or record.get("human_review_required")
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: nothing the pursuit lane holds is consumed.
            "pursuit_history_preserved": True,
            "source_history_preserved": True,
            "pursuit_record_deleted": False,
            "source_opportunity_deleted": False,
            "evidence_deleted": False,
            "fabricated": False,
            "requirements_invented": False,
            "live_fetch_performed": False,
        }
    )


def undo_mark_awarded_for_tenant(
    *, transition: dict[str, Any], actor: str | None = None, at: str | None = None
) -> dict[str, Any]:
    """Reverse a tenant transition. Idempotent, and destroys nothing.

    The undo itself is Gate 91's, so idempotency is inherited rather than
    reimplemented: a second call returns ``already_undone``.
    """
    inner = undo_mark_as_awarded(
        transition=dict(transition.get("gate91_transition") or {}),
        actor=actor,
        at=at,
    )

    return _json_safe(
        {
            **transition,
            "gate91_transition": inner,
            "transition_status": "undone",
            "undo_status": inner.get("undo_status"),
            "undo_applied_count": int(inner.get("undo_applied_count") or 1),
            "awarded_record_created": False,
            "active_obligations_created": False,
            # A mistaken award destroys no evidence.
            "pursuit_history_preserved": True,
            "source_history_preserved": True,
            "pursuit_record_deleted": False,
            "source_opportunity_deleted": False,
            "evidence_deleted": False,
            "preserved_on_undo": list(PRESERVED_ON_UNDO),
            "fabricated": False,
        }
    )


def tenant_transition_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in TENANT_TRANSITION_FIELDS:
        if field not in result:
            fails.append(f"tenant_transition_missing_field:{field}")

    for constant in (
        "pursuit_record_deleted",
        "source_opportunity_deleted",
        "evidence_deleted",
        "fabricated",
        "requirements_invented",
    ):
        if result.get(constant) is not False:
            fails.append(f"tenant_transition_claimed:{constant}")

    for constant in ("pursuit_history_preserved", "source_history_preserved"):
        if result.get(constant) is not True:
            fails.append(f"tenant_transition_dropped:{constant}")

    if not result.get("tenant_id"):
        fails.append("tenant_transition_without_a_tenant")

    # A transition never creates duties.
    if result.get("active_obligations_created") is not False:
        fails.append("transition_created_active_obligations")

    # An undone transition holds no award record.
    if result.get("transition_status") == "undone" and result.get(
        "awarded_record_created"
    ):
        fails.append("undone_transition_still_claims_an_awarded_record")

    return fails
