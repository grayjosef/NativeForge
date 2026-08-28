"""Award requirement proof and audit trail (Gate 108F).

What proves a tenant filed what they owed, and the record of every status change.

## Proof is customer data, and this service never creates it

The only thing here that can produce a proof reference is a caller handing one
over, or a demo fixture that says so on its face. There is no code path that
generates a plausible-looking receipt.

That matters more than it sounds. A compliance system that can invent proof is a
system whose proof means nothing - and the one time it would be discovered is an
audit, which is the worst possible time.

```text
proof_ref supplied by a caller            recorded as given
proof_ref labelled demo_fixture           recorded, and labelled everywhere
no proof_ref                              proof_missing, never a placeholder
```

A `submitted` status without a proof reference is allowed - a tenant may have
filed something and not yet attached the receipt - but it is reported as
`proof_missing`, not quietly treated as proved.

## Nothing is deleted on a status change

Rejecting a report does not remove the proof that it was submitted. Waiving a
requirement does not remove its history. Every action appends; nothing
overwrites.

```text
proof_preserved            true
source_evidence_preserved  true
proof_deleted              false
audit_record_deleted       false
```

Held by invariants on every result, following the same rule Gate 104's
suppression contract holds: a record that can erase its own history is
indistinguishable from data loss.

## The audit event is the point

Each action produces an `audit_event_id` derived from the action and its
subject, so the trail is reproducible from its own contents rather than from an
incrementing counter somebody could reset.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.award_requirement_model_service import (
    PROOF_STATUSES,
    REQUIREMENT_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirement_proof_audit_v1"

PROOF_ACTIONS = frozenset(
    {
        "attach_proof",
        "mark_submitted",
        "mark_accepted",
        "mark_rejected",
        "mark_waived",
        "unknown",
    }
)

# Where each action leaves the requirement.
ACTION_TO_REQUIREMENT_STATUS: dict[str, str] = {
    "mark_submitted": "submitted",
    "mark_accepted": "accepted",
    "mark_rejected": "rejected",
    "mark_waived": "waived",
}

# Actions that assert the tenant filed something, and therefore want proof.
PROOF_EXPECTING_ACTIONS = frozenset({"mark_submitted", "mark_accepted"})

# The only label under which a non-customer proof reference may exist.
DEMO_PROOF_LABEL = "demo_fixture"

RESULT_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "award_id",
    "requirement_id",
    "action",
    "status_before",
    "status_after",
    "proof_ref",
    "audit_event_id",
    "proof_preserved",
    "source_evidence_preserved",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_audit_event_id(
    *, tenant_id: Any, award_id: Any, requirement_id: Any, action: Any, at: Any
) -> str:
    """Reproducible from the event's own contents."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (tenant_id, award_id, requirement_id, action, at)
        ).encode()
    ).hexdigest()


def record_proof_action(
    *,
    tenant_id: Any,
    award_id: Any,
    requirement_id: Any,
    action: Any,
    status_before: Any = None,
    proof_ref: Any = None,
    proof_label: Any = None,
    at: Any = None,
    actor: Any = None,
    prior_proof_refs: list[Any] | None = None,
    human_review_acknowledged: bool = False,
) -> dict[str, Any]:
    """Record one action against one requirement. Nothing is invented."""
    act = str(action).strip() if action else "unknown"
    if act not in PROOF_ACTIONS:
        act = "unknown"

    blocked_reasons: list[str] = []

    if not tenant_id:
        blocked_reasons.append("proof_action_without_a_tenant")
    if not award_id:
        blocked_reasons.append("proof_action_without_an_award")
    if not requirement_id:
        blocked_reasons.append("proof_action_without_a_requirement")
    if act == "unknown":
        blocked_reasons.append("proof_action_unknown")

    before = str(status_before).strip() if status_before else "unknown"
    if before not in REQUIREMENT_STATUSES:
        before = "unknown"

    # A demo proof reference must say so on its face, everywhere it appears.
    label = str(proof_label).strip() if proof_label else None
    is_demo_proof = label == DEMO_PROOF_LABEL
    if proof_ref and label and label != DEMO_PROOF_LABEL:
        blocked_reasons.append(f"unrecognised_proof_label:{label}")

    if proof_ref:
        proof_status = "proof_attached"
    else:
        proof_status = "proof_missing" if act in PROOF_EXPECTING_ACTIONS else (
            "not_submitted"
        )

    if act in PROOF_EXPECTING_ACTIONS and not proof_ref:
        # Allowed, but never reported as proved.
        blocked_reasons.append(f"{act}_without_a_proof_reference")

    if act == "mark_accepted" and proof_ref:
        proof_status = "proof_accepted"
    if act == "mark_rejected":
        # Rejection never removes the proof that was filed.
        proof_status = "proof_rejected" if proof_ref or prior_proof_refs else (
            "proof_missing"
        )

    if act in {"attach_proof"} and not proof_ref:
        blocked_reasons.append("attach_proof_without_a_reference")

    status_after = ACTION_TO_REQUIREMENT_STATUS.get(act)
    if status_after is None:
        status_after = before if act == "attach_proof" else "needs_human_review"

    human_review_required = bool(
        (blocked_reasons and not human_review_acknowledged)
        or status_after == "needs_human_review"
    )

    # History is appended to, never replaced.
    preserved_refs = [ref for ref in (prior_proof_refs or []) if ref]
    if proof_ref and proof_ref not in preserved_refs:
        preserved_refs = [*preserved_refs, proof_ref]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "award_id": award_id,
            "requirement_id": requirement_id,
            "action": act,
            "actor": actor,
            "at": at,
            "status_before": before,
            "status_after": status_after,
            "proof_ref": proof_ref,
            "proof_label": label,
            "proof_is_demo_fixture": is_demo_proof,
            "proof_of_submission_status": proof_status,
            "proof_ref_history": preserved_refs,
            "audit_event_id": build_audit_event_id(
                tenant_id=tenant_id,
                award_id=award_id,
                requirement_id=requirement_id,
                action=act,
                at=at,
            ),
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this records what a person did. It creates no proof.
            "proof_preserved": True,
            "source_evidence_preserved": True,
            "proof_deleted": False,
            "audit_record_deleted": False,
            "proof_fabricated": False,
            "fabricated": False,
            "external_storage_contacted": False,
            "live_fetch_performed": False,
        }
    )


def build_audit_trail(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Every action against a requirement, in the order it was recorded."""
    demo_events = [e for e in events if e.get("proof_is_demo_fixture")]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_count": len(events),
            "audit_event_ids": [e.get("audit_event_id") for e in events],
            "proof_refs_seen": sorted(
                {str(e.get("proof_ref")) for e in events if e.get("proof_ref")}
            ),
            "demo_fixture_proof_count": len(demo_events),
            "events_needing_human_review": sum(
                1 for e in events if e.get("human_review_required")
            ),
            "proof_deleted": 0,
            "audit_records_deleted": 0,
            "proof_fabricated": False,
            "fabricated": False,
        }
    )


def proof_audit_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"proof_result_missing_field:{field}")

    # Nothing is ever deleted or invented.
    for constant in (
        "proof_deleted",
        "audit_record_deleted",
        "proof_fabricated",
        "fabricated",
        "external_storage_contacted",
        "live_fetch_performed",
    ):
        if result.get(constant) is not False:
            fails.append(f"proof_result_claimed:{constant}")

    for constant in ("proof_preserved", "source_evidence_preserved"):
        if result.get(constant) is not True:
            fails.append(f"proof_result_dropped:{constant}")

    if result.get("action") not in PROOF_ACTIONS:
        fails.append("proof_action_out_of_vocabulary")
    if result.get("proof_of_submission_status") not in PROOF_STATUSES:
        fails.append("proof_status_out_of_vocabulary")
    if result.get("status_after") not in REQUIREMENT_STATUSES:
        fails.append("status_after_out_of_vocabulary")

    # Tenant-scoped by construction.
    if not result.get("tenant_id"):
        fails.append("proof_action_without_a_tenant")

    # A proof reference that is not the customer's must be labelled as such.
    if result.get("proof_is_demo_fixture") and (
        result.get("proof_label") != DEMO_PROOF_LABEL
    ):
        fails.append("demo_proof_without_its_label")

    # Filing without a receipt is allowed, but never reported as proved.
    if result.get("action") in PROOF_EXPECTING_ACTIONS and not result.get("proof_ref"):
        if result.get("proof_of_submission_status") in {
            "proof_attached",
            "proof_accepted",
        }:
            fails.append("proof_claimed_without_a_reference")

    # A rejection may not erase the history of what was filed.
    if result.get("action") == "mark_rejected" and result.get("proof_ref_history"):
        if not result.get("proof_preserved"):
            fails.append("rejection_dropped_the_proof_history")

    # A refusal must name itself.
    if result.get("human_review_required") and not result.get("blocked_reasons"):
        if result.get("status_after") != "needs_human_review":
            fails.append("human_review_without_a_reason")

    # Identity reproducible from the event's own fields.
    expected_id = build_audit_event_id(
        tenant_id=result.get("tenant_id"),
        award_id=result.get("award_id"),
        requirement_id=result.get("requirement_id"),
        action=result.get("action"),
        at=result.get("at"),
    )
    if result.get("audit_event_id") != expected_id:
        fails.append("audit_event_id_not_derivable_from_its_fields")

    return fails
