"""Award requirements persistence validation (Gate 125D).

Is a stored requirement fit to appear on a compliance calendar — without
inventing an obligation, a due date, a submission, or a document.

## Provenance decides everything

Gate 108 derives the projected-versus-active boundary from one field, in one
line:

```python
is_active_obligation = extraction in ACTIVE_CAPABLE_EXTRACTION_STATUSES
```

`requirement_source` is that field, bridged by import. Three booleans follow
from it and **none of them is an input**:

```text
requirement_source                    active  projected  unsupported
human_entered / evidence_extracted    true    false      false
projected_from_nofo                   false   true       false
unsupported_document_type             false   false      true
unknown / needs_human_review          false   false      false
```

The gate brief asks for `active_obligation` and `projected_burden` as columns,
and they are columns — a calendar has to filter on them. But a column that can
be *set* is a place to assert what the provenance does not support, which is the
declared-versus-derived defect this campaign has found in five consecutive
gates. So they are derived here, checked by the database, and an invariant
refuses a result where the pair disagrees with the source that produced it.

## An estimate is not a date

```text
DUE_DATE_STATUSES         verified, calculated, estimated,
                          unknown, unsupported, needs_human_review
DATE_CALCULABLE_STATUSES  verified, calculated
```

`estimated` is deliberately outside the calculable set — Gate 108 put it there.
An estimated date is recorded, reported as estimated, and never counted down to.
A compliance calendar that treats an estimate as a deadline is worse than one
with a visible gap, because the gap prompts a human and the estimate does not.

Nothing here derives a date from a recurrence rule. "Quarterly" says how often,
not when, and the quarter boundaries a funder uses are in the award terms.

## Four things a proof is not

```text
a document reference is not a document      there is no document store
a document reference is not a submission    somebody has to file it
a submission is not an acceptance           somebody has to accept it
an acceptance is not a proof                unless a reference exists
```

Each is a separate refusal with its own name, because collapsing any of them
produces a screen telling a Tribe they are compliant when they are not.

`document_storage_available` is a constant `False` here, with an invariant
behind it. Gate 125 built a column that holds a reference; it did not build the
thing the reference points at.

## A refused claim is not a refused row

Two lists, because they answer different questions:

```text
blocked_reasons   this row may not be stored
refused_claims    this row may be stored, and something it asserted was not
```

A projection is the case that forces the distinction. Recording what a NOFO
projected, alongside the award it turned into, is useful — it is how a Tribe
sees what they expected against what they got. Refusing to *store* it would make
`projected_burden` an unreachable column and every "a projection is not an
obligation" test vacuous, because there would be no projection to test.

So a projection is stored, `active_obligation` derives to `False`, the refusal
is named in `refused_claims`, and `human_review_required` is true. The same for
a requirement extracted from a document nobody could read.

## Every invariant reads a derived value

An invariant that ordinary bad input can trip is a validation rule with the
wrong name — Gate 124D shipped three of them and had to split a claim from its
derivation to fix it. Here the rule is structural: **no invariant reads an
echoed input.** `proof_status`, `submitted_at` and `accepted_at` come from the
caller, so the invariants read `proof_is_accepted` and `acceptance_recorded`,
which this service computes.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from nativeforge.services.award_requirement_model_service import (
    ACTIVE_CAPABLE_EXTRACTION_STATUSES,
    CLOSED_STATUSES,
    DATE_CALCULABLE_STATUSES,
    DUE_DATE_STATUSES,
    EXTRACTION_STATUSES,
    PROOF_STATUSES,
    RECURRENCES,
    REQUIREMENT_STATUSES,
    REQUIREMENT_TYPES,
    SUBMITTED_STATUSES,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
    UNESTABLISHED_FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_requirements_persistence_validation_v1"

# Gate 108 calls this `extraction_status`. The column is `requirement_source`
# because on a persisted row it answers "where did this come from", and the
# vocabulary is imported rather than restated so the two cannot drift.
REQUIREMENT_SOURCES = EXTRACTION_STATUSES
ACTIVE_CAPABLE_SOURCES = ACTIVE_CAPABLE_EXTRACTION_STATUSES

PROJECTED_SOURCE = "projected_from_nofo"
UNSUPPORTED_SOURCE = "unsupported_document_type"

# Sources nobody has established. They oblige nothing and need a human.
UNESTABLISHED_SOURCES = frozenset({"unknown", "needs_human_review"})

# Where a requirement can be in its own lifecycle. Wider than PROOF_STATUSES,
# which is about the evidence rather than the filing.
SUBMISSION_STATUSES = frozenset(
    {
        "not_submitted",
        "submitted",
        "accepted",
        "rejected",
        "waived",
        "needs_human_review",
        "unknown",
    }
)

# Proof statuses that assert somebody filed something.
PROOF_FILED_STATUSES = frozenset({"proof_attached", "proof_accepted", "proof_rejected"})

VALIDATION_FIELDS: tuple[str, ...] = (
    "requirement_title_present",
    "requirement_type_valid",
    "requirement_status_valid",
    "requirement_source_valid",
    "due_date_status_valid",
    "due_date_consistent",
    "recurrence_rule_valid_or_unknown",
    "proof_status_valid",
    "submission_status_valid",
    "active_vs_projected_consistent",
    "unsupported_not_active",
    "fact_status_valid",
    "human_review_required",
    "unknowns_labelled",
    "document_reference_not_storage",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def derive_obligation_flags(requirement_source: Any) -> dict[str, bool]:
    """The three booleans, from provenance alone.

    Exposed so a caller can see the derivation rather than pass the answer in,
    and so a test can walk every source value against it.
    """
    source = str(requirement_source or "unknown").strip().lower()
    return {
        "active_obligation": source in ACTIVE_CAPABLE_SOURCES,
        "projected_burden": source == PROJECTED_SOURCE,
        "unsupported_requirement": source == UNSUPPORTED_SOURCE,
    }


def validate_award_requirement(
    *,
    requirement_title: Any = None,
    requirement_type: Any = None,
    requirement_status: Any = None,
    requirement_source: Any = None,
    requirement_source_ref: Any = None,
    requirement_due_date: Any = None,
    due_date_status: Any = None,
    recurrence_rule: Any = None,
    proof_required: bool = False,
    proof_status: Any = None,
    proof_document_ref: Any = None,
    submission_status: Any = None,
    submitted_at: Any = None,
    accepted_at: Any = None,
    rejected_at: Any = None,
    fact_status: Any = None,
    document_storage_available: bool = False,
) -> dict[str, Any]:
    """Is this requirement fit to be stored and acted on? Deny by default.

    Nothing here infers. An obligation is not inferred from a title, a date is
    not inferred from a recurrence, a submission is not inferred from a
    document reference, and an acceptance is not inferred from a submission.
    """
    blocked_reasons: list[str] = []
    # Claims this service refused while still permitting the row. See the
    # docstring: a projection is stored, and is not an obligation.
    refused_claims: list[str] = []
    unknown_fields: list[str] = []

    # -- the title, the one thing that cannot be unknown ---------------------
    title = str(requirement_title or "").strip()
    requirement_title_present = bool(title)
    if not requirement_title_present:
        blocked_reasons.append("requirement_without_a_title")

    # -- what kind of requirement --------------------------------------------
    req_type = str(requirement_type or "unknown").strip().lower()
    requirement_type_valid = req_type in REQUIREMENT_TYPES
    if not requirement_type_valid:
        blocked_reasons.append(f"requirement_type_not_recognised:{req_type}")
    if req_type == "unknown":
        unknown_fields.append("requirement_type")
        # Never guessed from the title. "Quarterly report" could be financial,
        # narrative or performance, and the three have different proof.
        blocked_reasons.append("requirement_type_unestablished_and_never_inferred")

    # -- where it came from, which decides whether it obliges anybody --------
    source = str(requirement_source or "unknown").strip().lower()
    requirement_source_valid = source in REQUIREMENT_SOURCES
    if not requirement_source_valid:
        blocked_reasons.append(f"requirement_source_not_recognised:{source}")
    if source in UNESTABLISHED_SOURCES:
        unknown_fields.append("requirement_source")

    flags = derive_obligation_flags(source)
    active_obligation = bool(flags["active_obligation"] and requirement_source_valid)
    projected_burden = bool(flags["projected_burden"])
    unsupported_requirement = bool(flags["unsupported_requirement"])

    if projected_burden:
        # Gate 108's message, kept verbatim so the two layers say one thing.
        # A refused *claim*, not a refused row: a projection is worth storing
        # beside the award it became, and vetoing it here would make
        # `projected_burden` an unreachable column.
        refused_claims.append("projected_burden_is_not_an_active_obligation")
    if unsupported_requirement:
        refused_claims.append("unsupported_document_cannot_produce_an_obligation")

    # Evidence extraction that names no evidence is a claim, not an extraction.
    source_ref = str(requirement_source_ref or "").strip()
    if source == "evidence_extracted" and not source_ref:
        # The extraction is recorded; the obligation it claimed is not.
        refused_claims.append("evidence_extracted_without_a_source_reference")
        active_obligation = False

    # -- the requirement's own status ----------------------------------------
    status = str(requirement_status or "unknown").strip().lower()
    requirement_status_valid = status in REQUIREMENT_STATUSES
    if not requirement_status_valid:
        blocked_reasons.append(f"requirement_status_not_recognised:{status}")
    if status == "unknown":
        unknown_fields.append("requirement_status")

    # -- when ----------------------------------------------------------------
    date_status = str(due_date_status or "unknown").strip().lower()
    due_date_status_valid = date_status in DUE_DATE_STATUSES
    if not due_date_status_valid:
        blocked_reasons.append(f"due_date_status_not_recognised:{date_status}")

    due_date = _as_date(requirement_due_date)
    if requirement_due_date not in (None, "") and due_date is None:
        blocked_reasons.append("requirement_due_date_is_not_an_iso_date")

    due_date_consistent = True
    if date_status in DATE_CALCULABLE_STATUSES and due_date is None:
        due_date_consistent = False
        blocked_reasons.append("due_date_status_claims_support_without_a_date")
    if due_date is not None and date_status == "unknown":
        due_date_consistent = False
        blocked_reasons.append("due_date_present_without_a_date_status")

    # The downgrade happens BEFORE `date_is_calculable` is decided. Computing it
    # first left an unreadable document reporting a countdown-ready deadline -
    # the exact thing DATE_CALCULABLE_STATUSES exists to prevent, defeated by
    # statement order.
    if unsupported_requirement and date_status in DATE_CALCULABLE_STATUSES:
        # An unreadable document cannot yield a verified date. Gate 108 downgrades
        # the status rather than refusing the row, and so does this.
        refused_claims.append("unsupported_document_claimed_a_supported_date")
        date_status = "unsupported"
        due_date_consistent = True

    date_is_calculable = bool(
        date_status in DATE_CALCULABLE_STATUSES and due_date is not None
    )

    if date_status in {"unknown", "needs_human_review", "unsupported"}:
        unknown_fields.append("requirement_due_date")
    if date_status == "estimated":
        # Recorded, reported as estimated, and never counted down to.
        unknown_fields.append("requirement_due_date_is_only_estimated")

    # -- how often, which is not when ----------------------------------------
    recurrence = str(recurrence_rule or "unknown").strip().lower()
    recurrence_rule_valid_or_unknown = recurrence in RECURRENCES
    if not recurrence_rule_valid_or_unknown:
        blocked_reasons.append(f"recurrence_rule_not_recognised:{recurrence}")
    if recurrence == "unknown":
        unknown_fields.append("recurrence_rule")
    # Nothing derives a date from a recurrence. "Quarterly" says how often; the
    # quarter boundaries a funder uses are in the award terms.
    due_date_inferred_from_recurrence = False

    # -- what proves it was done ---------------------------------------------
    proof = str(proof_status or "not_submitted").strip().lower()
    proof_status_valid = proof in PROOF_STATUSES
    if not proof_status_valid:
        blocked_reasons.append(f"proof_status_not_recognised:{proof}")
    if proof == "unknown":
        unknown_fields.append("proof_status")

    document_ref = str(proof_document_ref or "").strip()

    # A reference is not a document. There is no store behind it.
    document_reference_not_storage = True
    if document_ref and document_storage_available:
        # The only branch where a reference could resolve. False everywhere in
        # this repository today, and injectable so the claim is falsifiable.
        document_reference_not_storage = False

    if document_ref and not document_storage_available:
        blocked_reasons.append("proof_document_reference_without_a_document_store")

    # A reference is not a submission either.
    submission = str(submission_status or "not_submitted").strip().lower()
    submission_status_valid = submission in SUBMISSION_STATUSES
    if not submission_status_valid:
        blocked_reasons.append(f"submission_status_not_recognised:{submission}")
    if submission == "unknown":
        unknown_fields.append("submission_status")

    if document_ref and submission == "not_submitted":
        # Not an error: a document can be attached before it is filed. Named so
        # nothing downstream reads the attachment as the filing.
        unknown_fields.append("document_attached_but_not_submitted")

    if proof in PROOF_FILED_STATUSES and not document_ref:
        blocked_reasons.append(f"{proof}_without_a_document_reference")

    # A submission is not an acceptance.
    if proof == "proof_accepted" and submission not in {"accepted"}:
        blocked_reasons.append("proof_accepted_while_submission_is_not_accepted")

    # Derived, so the invariant below is about this service's conclusion rather
    # than about what a caller typed. Every conjunct, or False.
    proof_is_accepted = bool(
        proof == "proof_accepted" and bool(document_ref) and submission == "accepted"
    )
    if submission == "accepted" and proof != "proof_accepted":
        unknown_fields.append("submission_accepted_without_an_accepted_proof")

    submitted = bool(submitted_at)
    accepted = bool(accepted_at)
    rejected = bool(rejected_at)
    if accepted and not submitted:
        blocked_reasons.append("accepted_without_having_been_submitted")
    if accepted and rejected:
        blocked_reasons.append("accepted_and_rejected_at_the_same_time")
    if submission in SUBMITTED_STATUSES and not submitted:
        blocked_reasons.append(f"submission_status_{submission}_without_a_timestamp")

    # Same shape: an acceptance is recorded only where the submission it
    # followed is also recorded.
    acceptance_recorded = bool(accepted and submitted and not rejected)

    if proof_is_accepted and not acceptance_recorded:
        # An acceptance is an event with a date. A status saying a funder
        # accepted something, with no record of when, is the status without the
        # event - and a proof audit trail is built out of exactly those dates.
        blocked_reasons.append("proof_accepted_without_an_acceptance_timestamp")

    if proof_required and proof == "not_submitted" and status in CLOSED_STATUSES:
        blocked_reasons.append("requirement_closed_while_its_proof_is_outstanding")

    # -- the fact status behind all of it ------------------------------------
    fact = str(fact_status or "unknown").strip().lower()
    fact_status_valid = fact in FACT_STATUSES
    if not fact_status_valid:
        blocked_reasons.append(f"fact_status_not_recognised:{fact}")
    facts_established = fact in ACTIONABLE_FACT_STATUSES
    if fact in UNESTABLISHED_FACT_STATUSES:
        unknown_fields.append("fact_status")

    # The database's rule, restated: an obligation needs a fact status somebody
    # established. `demo_fixture` counts as established *for a fixture row* -
    # it is established to be a fixture - which is why the CHECK constraint
    # names all three and this does too.
    fact_status_supports_an_obligation = fact not in UNESTABLISHED_FACT_STATUSES
    if active_obligation and not fact_status_supports_an_obligation:
        refused_claims.append("active_obligation_on_an_unestablished_fact_status")
        active_obligation = False

    # -- the pair the database also refuses ----------------------------------
    active_vs_projected_consistent = not (active_obligation and projected_burden)
    unsupported_not_active = not (unsupported_requirement and active_obligation)

    unknowns_labelled = True
    human_review_required = bool(
        unknown_fields
        or blocked_reasons
        or refused_claims
        or not facts_established
        or date_status in {"estimated", "unknown", "needs_human_review", "unsupported"}
    )

    requirement_ready_for_calendar = bool(
        requirement_title_present
        and requirement_type_valid
        and req_type != "unknown"
        and requirement_source_valid
        and active_obligation
        and requirement_status_valid
        and due_date_status_valid
        and due_date_consistent
        and date_is_calculable
        and recurrence_rule_valid_or_unknown
        and proof_status_valid
        and submission_status_valid
        and facts_established
        and not blocked_reasons
        and not refused_claims
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requirement_title_present": requirement_title_present,
            "requirement_type": req_type,
            "requirement_type_valid": requirement_type_valid,
            "requirement_status": status,
            "requirement_status_valid": requirement_status_valid,
            "requirement_source": source,
            "requirement_source_valid": requirement_source_valid,
            "requirement_source_ref": source_ref or None,
            # Derived from provenance. Never accepted as input.
            "active_obligation": active_obligation,
            "projected_burden": projected_burden,
            "unsupported_requirement": unsupported_requirement,
            "active_vs_projected_consistent": active_vs_projected_consistent,
            "unsupported_not_active": unsupported_not_active,
            "requirement_due_date": due_date.isoformat() if due_date else None,
            "due_date_status": date_status,
            "due_date_status_valid": due_date_status_valid,
            "due_date_consistent": due_date_consistent,
            # The whole point of DATE_CALCULABLE_STATUSES: an estimate is not
            # something a calendar may count down to.
            "date_is_calculable": date_is_calculable,
            "due_date_is_estimate_only": date_status == "estimated",
            "recurrence_rule": recurrence,
            "recurrence_rule_valid_or_unknown": recurrence_rule_valid_or_unknown,
            "proof_required": bool(proof_required),
            "proof_status": proof,
            "proof_status_valid": proof_status_valid,
            "proof_document_ref": document_ref or None,
            "document_reference_present": bool(document_ref),
            "document_reference_not_storage": document_reference_not_storage,
            "submission_status": submission,
            "submission_status_valid": submission_status_valid,
            "submitted": submitted,
            "accepted": accepted,
            "rejected": rejected,
            # Derived. The invariants read these, never the three above.
            "proof_is_accepted": proof_is_accepted,
            "acceptance_recorded": acceptance_recorded,
            "fact_status": fact,
            "fact_status_valid": fact_status_valid,
            "facts_established": facts_established,
            "fact_status_supports_an_obligation": fact_status_supports_an_obligation,
            "unknowns_labelled": unknowns_labelled,
            "refused_claims": sorted(set(refused_claims)),
            "unknown_fields": sorted(set(unknown_fields)),
            "human_review_required": human_review_required,
            "requirement_ready_for_calendar": requirement_ready_for_calendar,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants. Nothing here invents an obligation, a date, a filing,
            # an acceptance or a document store.
            "document_storage_available": False,
            "proof_audit_persistence_available": False,
            "due_date_inferred": False,
            "due_date_inferred_from_recurrence": due_date_inferred_from_recurrence,
            "obligation_inferred_from_title": False,
            "submission_inferred_from_document": False,
            "acceptance_inferred_from_submission": False,
            "projected_burden_promoted": False,
            "fabricated": False,
        }
    )


def validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this validation must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in (
        "document_storage_available",
        "proof_audit_persistence_available",
        "due_date_inferred",
        "due_date_inferred_from_recurrence",
        "obligation_inferred_from_title",
        "submission_inferred_from_document",
        "acceptance_inferred_from_submission",
        "projected_burden_promoted",
        "fabricated",
    ):
        if result.get(field):
            failures.append(f"validation_claimed_{field}")

    # The three booleans must agree with the provenance that produced them.
    # This can only fire if the derivation itself breaks, never on bad input.
    source = str(result.get("requirement_source") or "")
    if result.get("projected_burden") is not (source == PROJECTED_SOURCE):
        failures.append("projected_burden_disagrees_with_the_source")
    if result.get("unsupported_requirement") is not (source == UNSUPPORTED_SOURCE):
        failures.append("unsupported_requirement_disagrees_with_the_source")
    if result.get("active_obligation") and source not in ACTIVE_CAPABLE_SOURCES:
        failures.append("active_obligation_without_a_capable_source")

    # The rule Gate 91 and Gate 108 both exist to protect.
    if result.get("active_obligation") and result.get("projected_burden"):
        failures.append("a_projection_was_also_an_active_obligation")
    if result.get("active_obligation") and result.get("unsupported_requirement"):
        failures.append("an_unsupported_requirement_was_an_active_obligation")
    if result.get("active_obligation") and not result.get(
        "fact_status_supports_an_obligation"
    ):
        failures.append("active_obligation_on_an_unestablished_fact_status")

    # An estimate is not a deadline, and neither is a date from a document
    # nobody could read.
    if result.get("date_is_calculable") and result.get("due_date_is_estimate_only"):
        failures.append("an_estimated_date_was_reported_as_calculable")
    if result.get("date_is_calculable") and result.get("unsupported_requirement"):
        failures.append("an_unsupported_documents_date_was_reported_as_calculable")
    if (
        result.get("date_is_calculable")
        and result.get("due_date_status") not in DATE_CALCULABLE_STATUSES
    ):
        failures.append("a_calculable_date_outside_the_calculable_statuses")
    #  used to sit here and was
    # vacuous the same way:  is a conjunction that already
    # includes the date being present. The three checks above are not - each
    # compares two values derived separately, so each can actually fail.

    # A proof is not a document, a filing or an acceptance.
    if result.get("document_reference_present") and not result.get(
        "document_reference_not_storage"
    ):
        failures.append("a_document_reference_was_treated_as_storage")
    # Every read below is a value this service derived, never one a caller
    # supplied. A caller writing `accepted_at` with no `submitted_at` is bad
    # input, which `blocked_reasons` names; an invariant ordinary input can trip
    # is a validation rule misnamed, which Gate 124D shipped three of.
    #
    # `acceptance_recorded and not submitted` was here and was vacuous -
    # `acceptance_recorded` is a conjunction that already includes `submitted`,
    # so the check could never fire whatever went wrong. Replaced by a genuine
    # cross-check between two independently derived values: one is about
    # statuses, the other about timestamps, and an accepted proof needs both.
    if result.get("proof_is_accepted") and not result.get("acceptance_recorded"):
        failures.append("a_proof_was_accepted_without_a_recorded_acceptance")
    if result.get("proof_is_accepted") and not result.get("document_reference_present"):
        failures.append("a_proof_was_accepted_without_a_reference")

    # A refused claim must say what it refused, or the refusal is invisible to
    # the caller that made it.
    if result.get("projected_burden") and not result.get("refused_claims"):
        failures.append("a_projection_was_stored_without_naming_the_refusal")
    if result.get("unsupported_requirement") and not result.get("refused_claims"):
        failures.append("an_unsupported_row_was_stored_without_naming_the_refusal")

    if result.get("requirement_ready_for_calendar"):
        for conjunct in (
            "requirement_title_present",
            "requirement_type_valid",
            "requirement_source_valid",
            "active_obligation",
            "due_date_consistent",
            "date_is_calculable",
            "facts_established",
        ):
            if not result.get(conjunct):
                failures.append(f"ready_for_calendar_without:{conjunct}")
        if result.get("blocked_reasons"):
            failures.append("ready_for_calendar_with_blocked_reasons")
        if result.get("refused_claims"):
            failures.append("ready_for_calendar_with_refused_claims")
        if result.get("human_review_required"):
            failures.append("ready_for_calendar_while_review_required")

    if result.get("unknown_fields") and not result.get("human_review_required"):
        failures.append("unknown_fields_without_human_review")

    if not result.get("unknowns_labelled"):
        failures.append("an_unknown_was_not_labelled")

    return sorted(set(failures))


def build_validation_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them established."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = validate_award_requirement(**case["requirement"])
        rows.append(
            {
                "case": case["case"],
                "requirement_title_present": result["requirement_title_present"],
                "requirement_type": result["requirement_type"],
                "requirement_status": result["requirement_status"],
                "requirement_source": result["requirement_source"],
                # All three, so a matrix can show a claim being refused.
                "active_obligation": result["active_obligation"],
                "projected_burden": result["projected_burden"],
                "unsupported_requirement": result["unsupported_requirement"],
                "due_date_status": result["due_date_status"],
                "due_date_consistent": result["due_date_consistent"],
                "date_is_calculable": result["date_is_calculable"],
                "proof_status": result["proof_status"],
                "submission_status": result["submission_status"],
                "document_reference_present": result["document_reference_present"],
                "fact_status": result["fact_status"],
                "facts_established": result["facts_established"],
                "requirement_ready_for_calendar": result[
                    "requirement_ready_for_calendar"
                ],
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
            "ready_count": sum(1 for r in rows if r["requirement_ready_for_calendar"]),
            "active_obligation_count": sum(1 for r in rows if r["active_obligation"]),
            "projected_burden_count": sum(1 for r in rows if r["projected_burden"]),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            "document_storage_available": False,
            "proof_audit_persistence_available": False,
            "fabricated": False,
        }
    )
