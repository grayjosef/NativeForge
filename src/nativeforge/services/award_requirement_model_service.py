"""Award requirement model (Gate 108D).

One obligation attached to one awarded grant, for one tenant, with a lifecycle.

## What Gate 91 already had, and what was missing

Gate 91 could record *that* an award carries reporting requirements, each with
quoted evidence. It could not record who owes a requirement, by when, whether it
was filed, or what proves it. A requirement was a list entry; here it is a record
with a status.

## Three separate questions, three separate vocabularies

The design mistake this avoids is a single `status` field carrying all of it.

```text
requirement_status   where the work stands      not_started ... accepted
due_date_status      how the date was arrived at verified ... unsupported
extraction_status    where the requirement came from human_entered ... unknown
```

A requirement can be `in_progress` against an `estimated` due date that was
`projected_from_nofo`. Collapsing those into one field forces a caller to guess
which meaning is intended, and guessing is how an estimate becomes a deadline.

## Projected is not active

The rule the whole gate turns on. `projected_from_nofo` records a burden guessed
from a notice **before** the award existed. It is not something the tenant owes.

```text
projected_from_nofo, no award-specific evidence, no human entry
    -> is_active_obligation: False
    -> a person must confirm before it becomes an obligation
```

Gate 91's `pursuit_reporting_burden_projection_service` already stamps
`is_active_obligation: False` on every projection. This carries that boundary
across the award transition rather than letting it dissolve there. An invariant
fails any requirement that is active on projection alone.

## Unsupported is not unknown, and neither is verified

An `unsupported_document_type` means a document arrived that nobody could read.
That is a different state from a requirement nobody has looked for, and both are
different from one with a confirmed date. A requirement extracted from an
unreadable document may not carry a verified due date, and an invariant enforces
it.

## Unknown due dates stay unknown

No date is ever computed from a default. A requirement with no date carries
`due_date: None` and `due_date_status: unknown`, and remains visible. Gate 91's
calendar established this ("dates_inferred: 0") and it holds here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.awarded_grant_portfolio_service import (
    REQUIREMENT_CATEGORIES as PORTFOLIO_REQUIREMENT_CATEGORIES,
)

SCHEMA_VERSION = "nf_award_requirement_model_v1"

REQUIREMENT_TYPES = frozenset(
    {
        "narrative_report",
        "financial_report",
        "audit",
        "reimbursement",
        "drawdown",
        "match_documentation",
        "budget_revision",
        "performance_measure",
        "board_or_council_resolution",
        "subrecipient_report",
        "vendor_documentation",
        "closeout",
        "document_retention",
        "other",
        "unknown",
    }
)

# Gate 91's five portfolio categories mapped onto the types above, so the two
# vocabularies stay related rather than merely coexisting. Imported and checked
# at import time - if Gate 91 grows a category, this stops being complete and a
# test says so.
PORTFOLIO_CATEGORY_TO_TYPES: dict[str, frozenset[str]] = {
    "reporting_requirements": frozenset({"narrative_report", "financial_report"}),
    "financial_requirements": frozenset(
        {"financial_report", "reimbursement", "drawdown", "budget_revision"}
    ),
    "performance_requirements": frozenset({"performance_measure"}),
    "compliance_requirements": frozenset(
        {
            "audit",
            "match_documentation",
            "board_or_council_resolution",
            "subrecipient_report",
            "vendor_documentation",
        }
    ),
    "closeout_requirements": frozenset({"closeout", "document_retention"}),
}

REQUIREMENT_STATUSES = frozenset(
    {
        "not_started",
        "in_progress",
        "submitted",
        "accepted",
        "rejected",
        "waived",
        "overdue",
        "not_applicable",
        "unknown",
        "needs_human_review",
    }
)

# Statuses meaning the tenant has done the thing.
SUBMITTED_STATUSES = frozenset({"submitted", "accepted"})

# Statuses that stop a requirement counting as outstanding work.
CLOSED_STATUSES = frozenset({"accepted", "waived", "not_applicable"})

DUE_DATE_STATUSES = frozenset(
    {
        "verified",
        "calculated",
        "estimated",
        "unknown",
        "needs_human_review",
        "unsupported",
    }
)

# The only due-date statuses a countdown may be computed from. Derived
# affirmatively: an estimate is not a deadline and an unknown is not "no
# deadline".
DATE_CALCULABLE_STATUSES = frozenset({"verified", "calculated"})

EXTRACTION_STATUSES = frozenset(
    {
        "human_entered",
        "evidence_extracted",
        "projected_from_nofo",
        "unsupported_document_type",
        "unknown",
        "needs_human_review",
    }
)

# Provenance that can support an active obligation on its own.
ACTIVE_CAPABLE_EXTRACTION_STATUSES = frozenset(
    {"human_entered", "evidence_extracted"}
)

PROOF_STATUSES = frozenset(
    {
        "not_submitted",
        "proof_attached",
        "proof_accepted",
        "proof_rejected",
        "proof_missing",
        "unknown",
    }
)

RECURRENCES = frozenset(
    {
        "one_time",
        "monthly",
        "quarterly",
        "semi_annual",
        "annual",
        "on_request",
        "unknown",
    }
)

REQUIREMENT_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "award_id",
    "requirement_id",
    "requirement_type",
    "requirement_title",
    "requirement_description",
    "requirement_status",
    "due_date",
    "due_date_status",
    "recurrence",
    "source_document_id",
    "source_evidence_ref",
    "evidence_status",
    "extraction_status",
    "assigned_owner",
    "internal_reminder_schedule",
    "proof_of_submission_status",
    "proof_of_submission_ref",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_requirement_id(
    *, tenant_id: Any, award_id: Any, requirement_type: Any, requirement_title: Any
) -> str:
    """Deterministic, tenant- and award-scoped by construction."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (tenant_id, award_id, requirement_type, requirement_title)
        ).encode()
    ).hexdigest()


def build_award_requirement(
    *,
    tenant_id: Any,
    award_id: Any,
    requirement_type: Any = None,
    requirement_title: Any = None,
    requirement_description: Any = None,
    requirement_status: Any = None,
    due_date: Any = None,
    due_date_status: Any = None,
    recurrence: Any = None,
    source_document_id: Any = None,
    source_evidence_ref: Any = None,
    extraction_status: Any = None,
    assigned_owner: Any = None,
    internal_reminder_schedule: Any = None,
    proof_of_submission_status: Any = None,
    proof_of_submission_ref: Any = None,
    human_review_acknowledged: bool = False,
) -> dict[str, Any]:
    """One obligation on one award for one tenant. Nothing is inferred."""
    req_type = _norm(requirement_type, REQUIREMENT_TYPES, fallback="unknown")
    extraction = _norm(extraction_status, EXTRACTION_STATUSES, fallback="unknown")
    recur = _norm(recurrence, RECURRENCES, fallback="unknown")
    proof_status = _norm(
        proof_of_submission_status, PROOF_STATUSES, fallback="not_submitted"
    )

    blocked_reasons: list[str] = []

    if not tenant_id:
        blocked_reasons.append("requirement_without_a_tenant")
    if not award_id:
        blocked_reasons.append("requirement_without_an_award")
    if req_type == "unknown":
        blocked_reasons.append("requirement_type_unknown")
    if extraction == "unknown":
        blocked_reasons.append("requirement_provenance_unknown")

    # A date is only as good as the account of where it came from.
    date_status = _norm(due_date_status, DUE_DATE_STATUSES, fallback="unknown")
    if extraction == "unsupported_document_type":
        # An unreadable document cannot yield a verified date.
        if date_status in DATE_CALCULABLE_STATUSES:
            blocked_reasons.append("unsupported_document_claimed_a_supported_date")
            date_status = "unsupported"
        elif date_status == "unknown":
            date_status = "unsupported"
    if due_date and date_status == "unknown":
        blocked_reasons.append("due_date_present_without_a_date_status")
    if not due_date and date_status in DATE_CALCULABLE_STATUSES:
        blocked_reasons.append("date_status_claims_support_without_a_date")
        date_status = "unknown"

    # Evidence status is derived from provenance, never passed in.
    if extraction == "human_entered":
        evidence_status = "human_entered"
    elif extraction == "evidence_extracted":
        evidence_status = (
            "evidence_backed"
            if (source_evidence_ref or source_document_id)
            else "evidence_claimed_without_reference"
        )
        if evidence_status == "evidence_claimed_without_reference":
            blocked_reasons.append("evidence_extracted_without_a_reference")
    elif extraction == "projected_from_nofo":
        evidence_status = "projected_only"
    elif extraction == "unsupported_document_type":
        evidence_status = "unsupported_document_type"
    else:
        evidence_status = "unknown"

    # The rule the gate turns on: a projection is not an obligation.
    is_active_obligation = (
        extraction in ACTIVE_CAPABLE_EXTRACTION_STATUSES
        and bool(tenant_id)
        and bool(award_id)
    )
    if extraction == "projected_from_nofo":
        blocked_reasons.append("projected_burden_is_not_an_active_obligation")

    status = _norm(requirement_status, REQUIREMENT_STATUSES, fallback="unknown")
    human_review_required = bool(
        blocked_reasons
        and not human_review_acknowledged
        or status == "needs_human_review"
        or extraction in {"unknown", "needs_human_review", "unsupported_document_type"}
        or date_status in {"needs_human_review", "unsupported"}
    )
    if human_review_required and status == "unknown":
        status = "needs_human_review"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "award_id": award_id,
            "requirement_id": build_requirement_id(
                tenant_id=tenant_id,
                award_id=award_id,
                requirement_type=req_type,
                requirement_title=requirement_title,
            ),
            "requirement_type": req_type,
            "requirement_title": requirement_title,
            "requirement_description": requirement_description,
            "requirement_status": status,
            "due_date": due_date,
            "due_date_status": date_status,
            "date_is_calculable": date_status in DATE_CALCULABLE_STATUSES
            and bool(due_date),
            "recurrence": recur,
            "source_document_id": source_document_id,
            "source_evidence_ref": source_evidence_ref,
            "evidence_status": evidence_status,
            "extraction_status": extraction,
            "assigned_owner": assigned_owner,
            "internal_reminder_schedule": list(internal_reminder_schedule or []),
            "proof_of_submission_status": proof_status,
            "proof_of_submission_ref": proof_of_submission_ref,
            "is_active_obligation": is_active_obligation,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this records an obligation, it does not discover one.
            "fabricated": False,
            "due_date_inferred": False,
            "requirement_invented": False,
            "live_fetch_performed": False,
        }
    )


def portfolio_categories_are_fully_mapped() -> bool:
    """Every Gate 91 category has a mapping here. Detected, not assumed."""
    return set(PORTFOLIO_REQUIREMENT_CATEGORIES) == set(PORTFOLIO_CATEGORY_TO_TYPES)


def summarise_requirements(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts a person can act on. Nothing uncertain is rounded away."""
    by_status = {status: 0 for status in sorted(REQUIREMENT_STATUSES)}
    by_extraction = {status: 0 for status in sorted(EXTRACTION_STATUSES)}
    for requirement in requirements:
        status = requirement.get("requirement_status")
        if status in by_status:
            by_status[status] += 1
        extraction = requirement.get("extraction_status")
        if extraction in by_extraction:
            by_extraction[extraction] += 1

    active = [r for r in requirements if r.get("is_active_obligation")]
    projected = [
        r for r in requirements if r.get("extraction_status") == "projected_from_nofo"
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requirements_total": len(requirements),
            "active_obligations": len(active),
            "projected_not_active": len(projected),
            "unassigned": sum(1 for r in requirements if not r.get("assigned_owner")),
            "needing_human_review": sum(
                1 for r in requirements if r.get("human_review_required")
            ),
            "unknown_due_dates": sum(
                1 for r in requirements if r.get("due_date_status") == "unknown"
            ),
            "unsupported_documents": sum(
                1
                for r in requirements
                if r.get("extraction_status") == "unsupported_document_type"
            ),
            "by_requirement_status": by_status,
            "by_extraction_status": by_extraction,
            "fabricated": False,
        }
    )


def requirement_invariant_failures(requirement: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if requirement.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in REQUIREMENT_FIELDS:
        if field not in requirement:
            fails.append(f"requirement_missing_field:{field}")

    for constant in (
        "fabricated",
        "due_date_inferred",
        "requirement_invented",
        "live_fetch_performed",
    ):
        if requirement.get(constant) is not False:
            fails.append(f"requirement_claimed:{constant}")

    if requirement.get("requirement_type") not in REQUIREMENT_TYPES:
        fails.append("requirement_type_out_of_vocabulary")
    if requirement.get("requirement_status") not in REQUIREMENT_STATUSES:
        fails.append("requirement_status_out_of_vocabulary")
    if requirement.get("due_date_status") not in DUE_DATE_STATUSES:
        fails.append("due_date_status_out_of_vocabulary")
    if requirement.get("extraction_status") not in EXTRACTION_STATUSES:
        fails.append("extraction_status_out_of_vocabulary")
    if requirement.get("proof_of_submission_status") not in PROOF_STATUSES:
        fails.append("proof_status_out_of_vocabulary")
    if requirement.get("recurrence") not in RECURRENCES:
        fails.append("recurrence_out_of_vocabulary")

    # Tenant- and award-scoped by construction.
    if not requirement.get("tenant_id"):
        fails.append("requirement_without_a_tenant")
    if not requirement.get("award_id"):
        fails.append("requirement_without_an_award")

    # A projection is never an active obligation.
    if (
        requirement.get("extraction_status") == "projected_from_nofo"
        and requirement.get("is_active_obligation") is not False
    ):
        fails.append("projected_burden_treated_as_active_obligation")

    # An active obligation needs provenance that can carry it.
    if requirement.get("is_active_obligation") and requirement.get(
        "extraction_status"
    ) not in ACTIVE_CAPABLE_EXTRACTION_STATUSES:
        fails.append("active_obligation_without_supporting_provenance")

    # An unreadable document may not produce a supported date.
    if requirement.get("extraction_status") == "unsupported_document_type" and (
        requirement.get("due_date_status") in DATE_CALCULABLE_STATUSES
    ):
        fails.append("unsupported_document_produced_a_supported_date")

    # date_is_calculable must agree with the status and the date.
    expected_calculable = (
        requirement.get("due_date_status") in DATE_CALCULABLE_STATUSES
        and bool(requirement.get("due_date"))
    )
    if requirement.get("date_is_calculable") is not expected_calculable:
        fails.append("date_is_calculable_disagrees_with_the_date_status")

    # A refusal must name itself.
    if requirement.get("requirement_status") == "needs_human_review" and not (
        requirement.get("blocked_reasons") or requirement.get("human_review_required")
    ):
        fails.append("human_review_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected_id = build_requirement_id(
        tenant_id=requirement.get("tenant_id"),
        award_id=requirement.get("award_id"),
        requirement_type=requirement.get("requirement_type"),
        requirement_title=requirement.get("requirement_title"),
    )
    if requirement.get("requirement_id") != expected_id:
        fails.append("requirement_id_not_derivable_from_its_fields")

    return fails
