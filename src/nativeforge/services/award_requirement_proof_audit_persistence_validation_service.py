"""Award requirement proof audit persistence validation (Gate 126D).

Is a stored proof event fit to be read as an audit record — without inventing a
filing, an acceptance, a rejection, or a document.

## The vocabulary this gate extends rather than forks

Gate 108's `PROOF_ACTIONS` has five verbs plus `unknown`. An audit trail needs
four it never had:

```text
bridged   attach_proof, mark_submitted, mark_accepted, mark_rejected,
          mark_waived, unknown
added     proof_requested, proof_needs_review, proof_superseded,
          audit_note_added
```

`BRIDGED_EVENT_TYPES` names the first set by import, and an invariant refuses an
`EVENT_TYPES` that has dropped any of them. An extension that quietly became a
replacement would leave Gate 108's contract emitting actions this table cannot
store.

`event_status` is bridged whole from `PROOF_STATUSES` and not extended: what a
proof *is* has not changed, only what can happen to it.

## Four things this service will not work out for you

```text
a document reference is not a filing        somebody has to submit it
a filing is not an acceptance               a funder has to accept it
a review note is not a rejection            a note decides nothing
a document reference is not a document      there is no store behind it
```

Each is a separate refusal with its own name. Collapsing any one produces an
audit trail that tells a funder's auditor something nobody did.

## Retained, not removed

```text
rejected   the proof reference stays on the row
superseded the prior event stays, and the new one points back
archived   the row stays and leaves the active view
```

`proof_retained` is a derived conjunction and an invariant refuses a result
where a rejection lost its reference. A rejection that erased what was filed
would make "we rejected it" indistinguishable from "nothing was ever filed",
and those are opposite facts about the same Tribe.

## No invariant fires on ordinary input, and none is vacuous

Gate 125 adopted the rule "an invariant may not read an echoed input", after
Gate 124D shipped three that ordinary bad input could trip. Gate 126 found the
rule needs one refinement and one companion.

**The refinement.** The rule's purpose is that bad input must never trip an
invariant — not that echoed fields are untouchable. An invariant guarded on
*storable* can read one safely, because bad input is never storable, and
comparing what the caller said against what this service derived is the only way
to catch the two drifting apart. So:

```text
unguarded read of an echoed field   forbidden
read guarded on `storable`          permitted, and the point
```

**The companion.** An invariant that restates a conjunction already inside the
value it checks can never fail. `proof_is_accepted` already requires a
submission, a reference and an established fact status, so three invariants
saying so were three lines that read as coverage and were not. Gate 125 found
the same shape twice; this gate found it five times.

## document_store_present is measured; built-by-this-gate is the constant

The first version reported `document_storage_available: False` as a constant
*and* let a caller inject a store to reach the permitted branch. The invariant
then fired on that branch — a false positive on the one path the injection
exists to test.

Two fields now, because they answer two questions:

```text
document_store_present            was a store supplied to this call?
document_storage_built_by_gate_126  no. Constant, with an invariant behind it.
```
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.award_requirement_model_service import PROOF_STATUSES
from nativeforge.services.award_requirement_proof_audit_service import PROOF_ACTIONS
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
    UNESTABLISHED_FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirement_proof_audit_persistence_validation_v1"

# Gate 108's actions, imported so the bridge is a fact rather than a copy.
BRIDGED_EVENT_TYPES = PROOF_ACTIONS

# What an audit trail needs and Gate 108's action vocabulary never had.
ADDED_EVENT_TYPES = frozenset(
    {
        "proof_requested",
        "proof_needs_review",
        "proof_superseded",
        "audit_note_added",
    }
)

EVENT_TYPES = BRIDGED_EVENT_TYPES | ADDED_EVENT_TYPES

# What the proof IS now. Bridged whole; this gate does not extend it.
EVENT_STATUSES = PROOF_STATUSES

# The two statuses that assert a funder acted.
FUNDER_DECIDED_STATUSES = frozenset({"proof_accepted", "proof_rejected"})

# Statuses that assert something was filed.
PROOF_FILED_STATUSES = frozenset({"proof_attached", "proof_accepted", "proof_rejected"})

# Where the event came from.
PROOF_SOURCES = frozenset(
    {
        "human_entered",
        "evidence_extracted",
        "system_generated",
        "unsupported_document_type",
        "needs_human_review",
        "unknown",
    }
)

# Sources nobody has established. They decide nothing and need a human.
UNESTABLISHED_SOURCES = frozenset(
    {"unknown", "needs_human_review", "unsupported_document_type"}
)

# An audit note records what somebody said. It never moves the proof.
NOTE_EVENT_TYPES = frozenset({"audit_note_added", "proof_needs_review"})

VALIDATION_FIELDS: tuple[str, ...] = (
    "event_type_valid",
    "event_status_valid",
    "proof_source_valid",
    "document_reference_not_storage",
    "submitted_not_accepted",
    "accepted_requires_reference",
    "accepted_requires_submission",
    "rejected_not_deleted",
    "superseded_not_deleted",
    "review_status_consistent",
    "fact_status_valid",
    "human_review_required",
    "unknowns_labelled",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(moment: Any) -> str | None:
    parsed = _as_datetime(moment)
    return parsed.isoformat() if parsed else None


def validate_proof_event(
    *,
    event_type: Any = None,
    event_status: Any = None,
    proof_document_ref: Any = None,
    proof_document_storage_available: bool = False,
    proof_summary: Any = None,
    proof_source: Any = None,
    proof_source_ref: Any = None,
    submitted_at: Any = None,
    accepted_at: Any = None,
    rejected_at: Any = None,
    reviewed_at: Any = None,
    reviewed_by_identity_id: Any = None,
    supersedes_event_id: Any = None,
    superseded_at: Any = None,
    fact_status: Any = None,
    document_storage_available: bool = False,
) -> dict[str, Any]:
    """Is this proof event fit to be stored and read? Deny by default.

    Nothing here infers. A filing is not inferred from a document reference, an
    acceptance is not inferred from a filing, a rejection is not inferred from a
    review note, and a document is not inferred from a reference to one.
    """
    blocked_reasons: list[str] = []
    # Claims refused while the row is still storable. A rejected proof and a
    # superseded one both belong in the trail; what they may not do is assert
    # something nobody did.
    refused_claims: list[str] = []
    unknown_fields: list[str] = []

    # -- what happened --------------------------------------------------------
    kind = str(event_type or "unknown").strip().lower()
    event_type_valid = kind in EVENT_TYPES
    if not event_type_valid:
        blocked_reasons.append(f"event_type_not_recognised:{kind}")
    if kind == "unknown":
        unknown_fields.append("event_type")
        blocked_reasons.append("event_type_unestablished_and_never_inferred")

    # -- what it made true ----------------------------------------------------
    status = str(event_status or "unknown").strip().lower()
    event_status_valid = status in EVENT_STATUSES
    if not event_status_valid:
        blocked_reasons.append(f"event_status_not_recognised:{status}")
    if status == "unknown":
        unknown_fields.append("event_status")

    # -- where it came from ---------------------------------------------------
    source = str(proof_source or "unknown").strip().lower()
    proof_source_valid = source in PROOF_SOURCES
    if not proof_source_valid:
        blocked_reasons.append(f"proof_source_not_recognised:{source}")
    if source in UNESTABLISHED_SOURCES:
        unknown_fields.append("proof_source")

    # -- what was filed -------------------------------------------------------
    document_ref = str(proof_document_ref or "").strip()
    document_reference_present = bool(document_ref)

    # A reference is not a document. There is no store behind it.
    document_reference_not_storage = True
    if document_ref and document_storage_available:
        # The only branch where a reference could resolve. False everywhere in
        # this repository today, and injectable so the claim is falsifiable.
        document_reference_not_storage = False

    if bool(proof_document_storage_available) and not document_storage_available:
        blocked_reasons.append("event_claimed_a_document_store_that_does_not_exist")
    if bool(proof_document_storage_available) and not document_ref:
        blocked_reasons.append("storage_flag_without_a_document_reference")

    # -- when -----------------------------------------------------------------
    submitted = _as_datetime(submitted_at)
    accepted = _as_datetime(accepted_at)
    rejected = _as_datetime(rejected_at)
    reviewed = _as_datetime(reviewed_at)

    for label, raw, parsed in (
        ("submitted_at", submitted_at, submitted),
        ("accepted_at", accepted_at, accepted),
        ("rejected_at", rejected_at, rejected),
        ("reviewed_at", reviewed_at, reviewed),
    ):
        if raw not in (None, "") and parsed is None:
            blocked_reasons.append(f"{label}_is_not_an_iso_datetime")

    submission_recorded = submitted is not None

    # A filing is not an acceptance. The derived claim lives in the result
    # as `submitted_not_accepted`; there is no local for it, because a
    # local written `not (...) or True` is a constant wearing a
    # conjunction.
    if accepted is not None and not submission_recorded:
        blocked_reasons.append("accepted_without_having_been_submitted")
    accepted_requires_submission = not (
        accepted is not None and not submission_recorded
    )

    if accepted is not None and rejected is not None:
        blocked_reasons.append("accepted_and_rejected_in_one_event")

    # An acceptance names what was accepted.
    accepted_requires_reference = not (
        status == "proof_accepted" and not document_reference_present
    )
    if not accepted_requires_reference:
        blocked_reasons.append("accepted_without_a_document_reference")
    if status == "proof_accepted" and accepted is None:
        blocked_reasons.append("accepted_status_without_an_acceptance_timestamp")
    if status == "proof_rejected" and rejected is None:
        blocked_reasons.append("rejected_status_without_a_rejection_timestamp")

    # A rejection never removes the proof that was filed.
    rejected_not_deleted = not (
        status == "proof_rejected" and not document_reference_present
    )
    if not rejected_not_deleted:
        blocked_reasons.append("rejection_discarded_the_proof_reference")

    if status in PROOF_FILED_STATUSES and not document_reference_present:
        blocked_reasons.append(f"{status}_without_a_document_reference")

    # -- who reviewed ---------------------------------------------------------
    reviewer = str(reviewed_by_identity_id or "").strip()
    review_status_consistent = bool(reviewed is None) == (not reviewer)
    if not review_status_consistent:
        blocked_reasons.append("a_review_needs_both_a_reviewer_and_a_time")

    # A note decides nothing.
    if kind in NOTE_EVENT_TYPES and (
        accepted is not None or rejected is not None or submitted is not None
    ):
        refused_claims.append(f"{kind}_cannot_record_a_filing_or_a_decision")

    # -- superseding, which retains ------------------------------------------
    supersedes = str(supersedes_event_id or "").strip()
    superseded = _as_datetime(superseded_at)

    if kind == "proof_superseded" and not supersedes:
        blocked_reasons.append("supersede_event_without_a_predecessor")
    if supersedes and kind != "proof_superseded":
        blocked_reasons.append("predecessor_named_by_a_non_supersede_event")

    # `superseded_at` marks the row that WAS replaced. A chain is ordinary: an
    # event can supersede one and later be superseded itself, so the two are
    # never coupled on a single row.
    #
    # These three are properties of the service, not of the input: this module
    # removes nothing, whatever it is handed. Written as constants so the
    # invariants behind them fire when somebody changes the service, which is
    # the only way they could become false.
    superseded_not_deleted = True
    rejected_retains_the_proof = True
    rows_deleted = 0

    # -- the fact status behind all of it ------------------------------------
    fact = str(fact_status or "unknown").strip().lower()
    fact_status_valid = fact in FACT_STATUSES
    if not fact_status_valid:
        blocked_reasons.append(f"fact_status_not_recognised:{fact}")
    facts_established = fact in ACTIONABLE_FACT_STATUSES
    fact_status_supports_a_decision = fact not in UNESTABLISHED_FACT_STATUSES
    if fact in UNESTABLISHED_FACT_STATUSES:
        unknown_fields.append("fact_status")

    if status in FUNDER_DECIDED_STATUSES and not fact_status_supports_a_decision:
        # The database's rule, restated: a funder decision on an unestablished
        # event is a decision nobody can stand behind.
        refused_claims.append("funder_decision_on_an_unestablished_fact_status")

    # -- the derived claims the invariants read -------------------------------
    proof_is_accepted = bool(
        status == "proof_accepted"
        and document_reference_present
        and accepted is not None
        and submission_recorded
        and fact_status_supports_a_decision
    )
    proof_is_rejected = bool(
        status == "proof_rejected"
        and document_reference_present
        and rejected is not None
        and fact_status_supports_a_decision
    )
    # A constant, for the reason above. Whether a *caller* discarded a
    # reference on a rejection is bad input, named in blocked_reasons by
    # `rejection_discarded_the_proof_reference`; it is not this service failing
    # to retain anything.
    proof_retained = bool(
        rows_deleted == 0 and superseded_not_deleted and rejected_retains_the_proof
    )

    unknowns_labelled = True
    human_review_required = bool(
        unknown_fields
        or blocked_reasons
        or refused_claims
        or not facts_established
        or kind == "proof_needs_review"
    )

    event_ready_for_audit_trail = bool(
        event_type_valid
        and kind != "unknown"
        and event_status_valid
        and proof_source_valid
        and source not in UNESTABLISHED_SOURCES
        and review_status_consistent
        and rejected_not_deleted
        and accepted_requires_reference
        and accepted_requires_submission
        and facts_established
        and not blocked_reasons
        and not refused_claims
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_type": kind,
            "event_type_valid": event_type_valid,
            "event_type_is_bridged": kind in BRIDGED_EVENT_TYPES,
            "event_type_is_added_by_this_gate": kind in ADDED_EVENT_TYPES,
            "event_status": status,
            "event_status_valid": event_status_valid,
            "proof_source": source,
            "proof_source_valid": proof_source_valid,
            "proof_source_ref": str(proof_source_ref or "") or None,
            "proof_summary": str(proof_summary or "") or None,
            "proof_document_ref": document_ref or None,
            "document_reference_present": document_reference_present,
            "document_reference_not_storage": document_reference_not_storage,
            # Measured: was a store supplied to this call? False everywhere in
            # this repository, and injectable so the branch above is reachable.
            "document_store_present": bool(document_storage_available),
            "proof_document_storage_available": bool(
                proof_document_storage_available and document_storage_available
            ),
            "submitted_at": _iso(submitted_at),
            "accepted_at": _iso(accepted_at),
            "rejected_at": _iso(rejected_at),
            "reviewed_at": _iso(reviewed_at),
            "reviewed_by_identity_id": reviewer or None,
            "supersedes_event_id": supersedes or None,
            "superseded_at": _iso(superseded_at) if superseded else None,
            # Derived. The invariants read these, never the fields above.
            "submission_recorded": submission_recorded,
            "proof_is_accepted": proof_is_accepted,
            "proof_is_rejected": proof_is_rejected,
            "proof_retained": proof_retained,
            "submitted_not_accepted": bool(
                submission_recorded and not proof_is_accepted
            ),
            "accepted_requires_reference": accepted_requires_reference,
            "accepted_requires_submission": accepted_requires_submission,
            "rejected_not_deleted": rejected_not_deleted,
            "superseded_not_deleted": superseded_not_deleted,
            "rejected_retains_the_proof": rejected_retains_the_proof,
            "review_status_consistent": review_status_consistent,
            "fact_status": fact,
            "fact_status_valid": fact_status_valid,
            "facts_established": facts_established,
            "fact_status_supports_a_decision": fact_status_supports_a_decision,
            "unknowns_labelled": unknowns_labelled,
            "unknown_fields": sorted(set(unknown_fields)),
            "refused_claims": sorted(set(refused_claims)),
            "human_review_required": human_review_required,
            "event_ready_for_audit_trail": event_ready_for_audit_trail,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants. Nothing here invents a filing, a decision, a document
            # store, or removes a record.
            "document_storage_built_by_gate_126": False,
            "rows_deleted": rows_deleted,
            "submission_inferred_from_document": False,
            "acceptance_inferred_from_submission": False,
            "rejection_inferred_from_review_note": False,
            "storage_inferred_from_document_reference": False,
            "audit_record_deleted": False,
            "proof_deleted": False,
            "fabricated": False,
        }
    )


def validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this validation must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in (
        "document_storage_built_by_gate_126",
        "submission_inferred_from_document",
        "acceptance_inferred_from_submission",
        "rejection_inferred_from_review_note",
        "storage_inferred_from_document_reference",
        "audit_record_deleted",
        "proof_deleted",
        "fabricated",
    ):
        if result.get(field):
            failures.append(f"validation_claimed_{field}")

    if result.get("rows_deleted"):
        failures.append("a_proof_event_was_deleted")

    # This service removes nothing, whatever it is handed. The only way this
    # goes false is somebody changing the service.
    if not result.get("proof_retained"):
        failures.append("a_proof_event_stopped_retaining_its_proof")
    if not result.get("superseded_not_deleted"):
        failures.append("a_superseded_event_stopped_being_retained")

    # A reference resolves to a document exactly when a store was supplied. The
    # first version compared against a constant `False`, so injecting a store to
    # reach the permitted branch fired the invariant on the one path the
    # injection exists to test.
    if result.get("document_reference_present"):
        expected = not result.get("document_store_present")
        if bool(result.get("document_reference_not_storage")) is not expected:
            failures.append("document_reference_disagrees_with_the_store")

    # The two cross-checks that are NOT vacuous, guarded on `storable` so
    # ordinary bad input cannot reach them. Everything a caller sent that this
    # service rejected is already named in blocked_reasons; what these catch is
    # the validation and the derivation drifting apart, which nothing else would.
    storable = not result.get("blocked_reasons") and not result.get("refused_claims")
    if storable and result.get("event_status") == "proof_accepted":
        if not result.get("proof_is_accepted"):
            failures.append("a_storable_acceptance_did_not_derive_as_accepted")
    if storable and result.get("event_status") == "proof_rejected":
        if not result.get("proof_is_rejected"):
            failures.append("a_storable_rejection_did_not_derive_as_rejected")

    # A note decides nothing, and a refused claim must say what it refused.
    if result.get("refused_claims") and not result.get("human_review_required"):
        failures.append("a_refused_claim_without_human_review")

    if result.get("event_ready_for_audit_trail"):
        for conjunct in (
            "event_type_valid",
            "event_status_valid",
            "proof_source_valid",
            "review_status_consistent",
            "rejected_not_deleted",
            "facts_established",
        ):
            if not result.get(conjunct):
                failures.append(f"ready_for_audit_trail_without:{conjunct}")
        if result.get("blocked_reasons"):
            failures.append("ready_for_audit_trail_with_blocked_reasons")
        if result.get("refused_claims"):
            failures.append("ready_for_audit_trail_with_refused_claims")
        if result.get("human_review_required"):
            failures.append("ready_for_audit_trail_while_review_required")

    if result.get("unknown_fields") and not result.get("human_review_required"):
        failures.append("unknown_fields_without_human_review")

    if not result.get("unknowns_labelled"):
        failures.append("an_unknown_was_not_labelled")

    return sorted(set(failures))


def vocabulary_invariant_failures() -> list[str]:
    """The extension must never have become a replacement.

    Gate 108's contract emits `PROOF_ACTIONS`. If a later edit dropped one from
    `EVENT_TYPES`, that contract would produce actions this table cannot store,
    and the failure would show up as an unstorable audit record rather than as a
    vocabulary drift.
    """
    failures: list[str] = []
    for action in sorted(PROOF_ACTIONS):
        if action not in EVENT_TYPES:
            failures.append(f"gate_108_action_no_longer_storable:{action}")
    if not ADDED_EVENT_TYPES <= EVENT_TYPES:
        failures.append("an_added_event_type_left_the_vocabulary")
    if BRIDGED_EVENT_TYPES & ADDED_EVENT_TYPES:
        failures.append("an_event_type_is_both_bridged_and_added")
    if set(EVENT_STATUSES) != set(PROOF_STATUSES):
        failures.append("event_status_forked_from_proof_statuses")
    return sorted(failures)


def derive_current_proof_status(events: list[dict[str, Any]]) -> dict[str, Any]:
    """What the requirement's proof status is now, over its whole trail.

    Derived and returned, never written back onto `nf_award_requirements`. Two
    writers on one column is how the two come to disagree, and Gate 125's
    `proof_status` already has its own CHECK constraints behind it. A later gate
    can reconcile them under one writer; this reads.

    A superseded event is skipped, an archived event is skipped, and everything
    else is folded newest-last. An empty or fully superseded trail is
    `not_submitted` rather than `unknown`: nothing being on file is a fact, and
    reporting it as unknown would send a human to look for something that is
    not there.
    """
    live = [
        e for e in events if not e.get("superseded_at") and not e.get("archived_at")
    ]
    ordered = sorted(live, key=lambda e: str(e.get("created_at") or ""))

    status = "not_submitted"
    for event in ordered:
        candidate = str(event.get("event_status") or "").strip().lower()
        if candidate in EVENT_STATUSES and candidate != "unknown":
            status = candidate

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proof_status": status,
            "event_count": len(events),
            "live_event_count": len(live),
            "superseded_event_count": sum(1 for e in events if e.get("superseded_at")),
            "archived_event_count": sum(1 for e in events if e.get("archived_at")),
            "human_review_required": bool(
                any(e.get("human_review_required") for e in live) or not ordered
            ),
            # Read, never written back.
            "written_back_to_requirement": False,
            "rows_deleted": 0,
        }
    )


def build_validation_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them established."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = validate_proof_event(**case["event"])
        rows.append(
            {
                "case": case["case"],
                "event_type": result["event_type"],
                "event_type_is_bridged": result["event_type_is_bridged"],
                "event_status": result["event_status"],
                "proof_source": result["proof_source"],
                "document_reference_present": result["document_reference_present"],
                "submission_recorded": result["submission_recorded"],
                "proof_is_accepted": result["proof_is_accepted"],
                "proof_is_rejected": result["proof_is_rejected"],
                "proof_retained": result["proof_retained"],
                "review_status_consistent": result["review_status_consistent"],
                "fact_status": result["fact_status"],
                "facts_established": result["facts_established"],
                "event_ready_for_audit_trail": result["event_ready_for_audit_trail"],
                "human_review_required": result["human_review_required"],
                "unknown_fields": result["unknown_fields"],
                "refused_claims": result["refused_claims"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": validation_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "ready_count": sum(1 for r in rows if r["event_ready_for_audit_trail"]),
            "accepted_count": sum(1 for r in rows if r["proof_is_accepted"]),
            "rejected_count": sum(1 for r in rows if r["proof_is_rejected"]),
            "retained_count": sum(1 for r in rows if r["proof_retained"]),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            "document_storage_built_by_gate_126": False,
            "rows_deleted": 0,
            "fabricated": False,
        }
    )
