"""Proof audit persistence demo fixtures (Gate 126G).

Fourteen labelled cases exercised against a database that lives for the length
of one case, so the refusals are observed rather than asserted.

## What a fixture is allowed to be

```text
every identifier prefixed         nf-demo-fixture-
every fact_status                 demo_fixture
every production write            refused
rows in the application database  0
production proof records          0
```

## The three cases this set exists for

```text
submitted_proof_is_not_accepted_proof   a filing is not a decision
rejected_proof_is_retained              the reference survives the rejection
superseded_proof_is_retained            two rows change, neither loses anything
```

The last two are the reason an audit trail is a separate table. A rejection that
erased what was filed would make "we rejected it" indistinguishable from
"nothing was ever filed", and a supersession that replaced the prior row would
erase what was believed before the correction. Both are opposite facts about the
same Tribe, and a funder's auditor asks about exactly this.

## The document store that does not exist

`proof_document_reference_does_not_imply_document_storage` sets the storage flag
with no store behind it and is refused. The same case runs again with a store
injected, so the refusal is a measurement rather than a constant.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_requirement_proof_audit_persistence_validation_service import (  # noqa: E501
    validate_proof_event,
    validation_invariant_failures,
    vocabulary_invariant_failures,
)
from nativeforge.services.award_requirement_proof_audit_repository_service import (
    PROOF_EVENTS,
    archive_proof_event,
    create_proof_event,
    list_proof_events_for_organization,
    list_proof_events_for_requirement,
    prepare_proof_event_write,
    proof_audit_repository_invariant_failures,
    supersede_proof_event,
)

SCHEMA_VERSION = "nf_award_requirement_proof_audit_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed so the fixture set is reproducible. Not a real organization, not a real
# award, not a real filing.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
DEMO_AWARDED_GRANT_ID = "2b4d6f80-1a3c-4e5f-8b9d-0c1e2f3a4b5c"
DEMO_REQUIREMENT_ID = "3c5e7f91-2b4d-4f60-9c0e-1d2f3a4b5c6d"
DEMO_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
DEMO_EVENT_ID = uuid.UUID("4d6f80a2-3c5e-4071-ad1f-2e3f4a5b6c7d")
DEMO_REPLACEMENT_ID = uuid.UUID("5e7f91b3-4d6f-4182-be20-3f4a5b6c7d8e")

DEMO_TENANT_LABEL = FIXTURE_PREFIX + "sc-tenant"
DEMO_CUSTOMER_ORG_LABEL = FIXTURE_PREFIX + "sc-customer-org"
DEMO_PROFILE_ID_LABEL = FIXTURE_PREFIX + "org-profile"
DEMO_DOCUMENT_REF = FIXTURE_PREFIX + "sf425-2026-q1.pdf"
DEMO_CORRECTED_REF = FIXTURE_PREFIX + "sf425-2026-q1-corrected.pdf"
DEMO_SOURCE_REF = FIXTURE_PREFIX + "award-packet#section-4.2"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)

# One event, every field supplied, every fact marked as a fixture.
DEMO_EVENT: dict[str, Any] = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "award_requirement_id": DEMO_REQUIREMENT_ID,
    "awarded_grant_id": DEMO_AWARDED_GRANT_ID,
    "event_type": "mark_submitted",
    "event_status": "proof_attached",
    "proof_document_ref": DEMO_DOCUMENT_REF,
    "proof_summary": "Demo filing. Not a real submission to a real funder.",
    "proof_source": "human_entered",
    "proof_source_ref": DEMO_SOURCE_REF,
    "submitted_at": NOW,
    "fact_status": FIXTURE_LABEL,
    "created_by_identity_id": DEMO_IDENTITY_ID,
    "is_demo": True,
}

REQUIRED_CASES: tuple[str, ...] = (
    "valid_demo_submitted_proof_event",
    "accepted_proof_without_submission_refused",
    "accepted_proof_without_document_reference_refused",
    "submitted_proof_is_not_accepted_proof",
    "rejected_proof_is_retained",
    "superseded_proof_is_retained",
    "proof_document_reference_does_not_imply_document_storage",
    "award_requirement_id_cannot_substitute_for_organization_id",
    "awarded_grant_id_cannot_substitute_for_organization_id",
    "tenant_id_refused_as_anchor",
    "customer_org_id_refused_as_anchor",
    "organization_profile_id_refused_as_anchor",
    "archive_retains_the_event",
    "customer_auth_live_false_blocks_production_write",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    PROOF_EVENTS.create(engine)
    return engine


def build_demo_proof_event_cases() -> list[dict[str, Any]]:
    """Fourteen labelled cases. Five storable, nine refused."""
    cases: list[dict[str, Any]] = []

    def case(
        name: str,
        why: str,
        *,
        expect_storage_allowed: bool,
        expect_production_write: bool,
        result: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> None:
        cases.append(
            {
                "case": name,
                "fixture_label": FIXTURE_LABEL,
                "why": why,
                "expect_storage_allowed": expect_storage_allowed,
                "expect_production_write": expect_production_write,
                "result": result,
                "extra": extra or {},
            }
        )

    case(
        "valid_demo_submitted_proof_event",
        (
            "a filing with a reference, a source and a timestamp, every fact "
            "marked as a fixture. Storable, and it decides nothing"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_proof_event_write(**DEMO_EVENT),
    )

    case(
        "accepted_proof_without_submission_refused",
        (
            "a funder cannot accept what nobody filed. Refused by name rather "
            "than the submission being invented to make the acceptance work"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(
            **{
                **DEMO_EVENT,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "submitted_at": None,
                "accepted_at": LATER,
            }
        ),
    )

    case(
        "accepted_proof_without_document_reference_refused",
        (
            "an acceptance names what was accepted. Without a reference the row "
            "asserts a funder approved something nobody can identify"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(
            **{
                **DEMO_EVENT,
                "event_type": "mark_accepted",
                "event_status": "proof_accepted",
                "proof_document_ref": None,
                "accepted_at": LATER,
            }
        ),
    )

    submitted = prepare_proof_event_write(**DEMO_EVENT)
    case(
        "submitted_proof_is_not_accepted_proof",
        (
            "filed and not accepted. A funder accepting a report is a separate "
            "event with its own timestamp, and a screen that read the filing as "
            "the acceptance would tell a Tribe they are done when they are not"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=submitted,
        extra={
            "proof_is_accepted": submitted["proof_is_accepted"],
            "submission_recorded": submitted["submission_recorded"],
        },
    )

    rejected = prepare_proof_event_write(
        **{
            **DEMO_EVENT,
            "event_type": "mark_rejected",
            "event_status": "proof_rejected",
            "rejected_at": LATER,
        }
    )
    case(
        "rejected_proof_is_retained",
        (
            "the funder rejected it and the reference stays on the row. A "
            "rejection that erased what was filed would make 'we rejected it' "
            "indistinguishable from 'nothing was ever filed'"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=rejected,
        extra={
            "proof_is_rejected": rejected["proof_is_rejected"],
            "reference_after_rejection": rejected["proof_document_ref"],
        },
    )

    # -- superseding: two rows change, neither loses anything ----------------
    engine = _memory_engine()
    with engine.begin() as connection:
        create_proof_event(
            connection=connection, event_id=DEMO_EVENT_ID, now=NOW, **DEMO_EVENT
        )
        superseded = supersede_proof_event(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            superseded_event_id=str(DEMO_EVENT_ID),
            event_id=DEMO_REPLACEMENT_ID,
            now=LATER,
            award_requirement_id=DEMO_REQUIREMENT_ID,
            awarded_grant_id=DEMO_AWARDED_GRANT_ID,
            event_status="proof_attached",
            proof_document_ref=DEMO_CORRECTED_REF,
            proof_summary="Demo correction. Not a real refiling.",
            proof_source="human_entered",
            submitted_at=LATER,
            fact_status=FIXTURE_LABEL,
            created_by_identity_id=DEMO_IDENTITY_ID,
            is_demo=True,
        )
        after_supersede = list_proof_events_for_requirement(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            award_requirement_id=DEMO_REQUIREMENT_ID,
        )
        rows_after_supersede = connection.execute(
            sa.select(sa.func.count()).select_from(PROOF_EVENTS)
        ).scalar()
        prior = next(
            e for e in after_supersede["events"] if e["event_id"] == str(DEMO_EVENT_ID)
        )
    engine.dispose()

    case(
        "superseded_proof_is_retained",
        (
            "a correction writes a new event pointing back, and marks the "
            "prior one superseded. The prior row keeps its reference, its "
            "timestamps and its actor, so an auditor can still read what was "
            "believed before the correction"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=superseded,
        extra={
            "rows_after_supersede": int(rows_after_supersede or 0),
            "superseded_count": int(after_supersede["superseded_count"]),
            "live_count": int(after_supersede["live_count"]),
            "predecessor_retained": superseded["predecessor_retained"],
            "predecessor_reference_kept": prior["proof_document_ref"],
            "predecessor_superseded_at": prior["superseded_at"],
            "derived_proof_status": after_supersede["derived_proof_status"][
                "proof_status"
            ],
            "written_back_to_requirement": after_supersede["derived_proof_status"][
                "written_back_to_requirement"
            ],
        },
    )

    # The permitted branch, run only to prove the refusal below is falsifiable.
    with_store = validate_proof_event(
        event_type="mark_submitted",
        event_status="proof_attached",
        proof_document_ref=DEMO_DOCUMENT_REF,
        proof_document_storage_available=True,
        proof_source="human_entered",
        submitted_at=NOW,
        fact_status=FIXTURE_LABEL,
        document_storage_available=True,
    )
    case(
        "proof_document_reference_does_not_imply_document_storage",
        (
            "the storage flag set with nothing behind it is refused by name. "
            "The same event with a store injected is permitted, so the refusal "
            "is a measurement rather than a constant"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(
            **{**DEMO_EVENT, "proof_document_storage_available": True}
        ),
        extra={
            "with_document_store_blocked": with_store["blocked_reasons"],
            "with_document_store_present": with_store["document_store_present"],
            "with_document_store_reference_not_storage": with_store[
                "document_reference_not_storage"
            ],
        },
    )

    case(
        "award_requirement_id_cannot_substitute_for_organization_id",
        (
            "the requirement is supplied and the organization is not. Refused "
            "by name: the RLS predicate reads organization_id, so reaching it "
            "through a join would make this table's policy depend on another "
            "table's policy"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(**{**DEMO_EVENT, "organization_id": None}),
    )

    case(
        "awarded_grant_id_cannot_substitute_for_organization_id",
        (
            "the award is context, carried so a portfolio view need not join "
            "through the requirement. It is not authority, and supplying it "
            "without the anchor is refused under its own name"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(
            **{
                **DEMO_EVENT,
                "organization_id": None,
                "award_requirement_id": None,
            }
        ),
    )

    for label, kwargs in (
        ("tenant_id_refused_as_anchor", {"tenant_id": DEMO_TENANT_LABEL}),
        (
            "customer_org_id_refused_as_anchor",
            {"customer_org_id": DEMO_CUSTOMER_ORG_LABEL},
        ),
        (
            "organization_profile_id_refused_as_anchor",
            {"organization_profile_id": DEMO_PROFILE_ID_LABEL},
        ),
    ):
        case(
            label,
            (
                "refused by name rather than ignored, so a caller who sent one "
                "is told which identity space it was in"
            ),
            expect_storage_allowed=False,
            expect_production_write=False,
            result=prepare_proof_event_write(**DEMO_EVENT, **kwargs),
        )

    # -- archive, never delete -----------------------------------------------
    engine = _memory_engine()
    with engine.begin() as connection:
        create_proof_event(
            connection=connection, event_id=DEMO_EVENT_ID, now=NOW, **DEMO_EVENT
        )
        archived = archive_proof_event(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            event_id=str(DEMO_EVENT_ID),
            now=LATER,
        )
        listed = list_proof_events_for_organization(
            connection=connection, organization_id=DEMO_ORGANIZATION_ID
        )
        rows_after_archive = connection.execute(
            sa.select(sa.func.count()).select_from(PROOF_EVENTS)
        ).scalar()
    engine.dispose()

    case(
        "archive_retains_the_event",
        (
            "archiving takes an event out of the active view and changes "
            "nothing about what it says. A listing returns it regardless, "
            "because an audit trail that hid a row would make it "
            "indistinguishable from an event that never happened"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=archived,
        extra={
            "rows_after_archive": int(rows_after_archive or 0),
            "archived_count": int(listed["archived_count"]),
            "still_listed": int(listed["rows_read"]),
            "reference_after_archive": listed["events"][0]["proof_document_ref"],
        },
    )

    case(
        "customer_auth_live_false_blocks_production_write",
        (
            "the same event with fact_status verified instead of demo_fixture, "
            "which makes it a production write. Both gates are named "
            "separately, because auth arriving without a verified binding "
            "would still not be enough"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_proof_event_write(
            **{**DEMO_EVENT, "fact_status": "verified", "is_demo": False}
        ),
    )

    return cases


def measure_proof_event_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def _agrees(case: dict[str, Any]) -> bool:
    result = case["result"]
    return bool(
        bool(result["storage_allowed"]) is bool(case["expect_storage_allowed"])
        and bool(result["production_write_allowed"])
        is bool(case["expect_production_write"])
    )


def build_proof_audit_fixture_set() -> dict[str, Any]:
    """The fourteen cases, measured."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    cases = build_demo_proof_event_cases()
    covered = measure_proof_event_cases(cases)

    # Measured once, from the real environment, so the set can state plainly
    # that no fixture moved either of them.
    gate = build_customer_auth_activation_gate()
    binding = build_binding_store_readiness()

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        extra = case["extra"]
        validation = result.get("validation") or {}
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "why": case["why"],
                "operation": result["operation"],
                "storage_allowed": bool(result["storage_allowed"]),
                "production_write_allowed": bool(result["production_write_allowed"]),
                "write_performed": bool(result["write_performed"]),
                "rows_written": int(result["rows_written"]),
                "event_type": result.get("event_type"),
                "event_status": result.get("event_status"),
                "proof_source": result.get("proof_source"),
                "document_reference_present": bool(result.get("proof_document_ref")),
                "submission_recorded": bool(result.get("submission_recorded")),
                "proof_is_accepted": bool(result.get("proof_is_accepted")),
                "proof_is_rejected": bool(result.get("proof_is_rejected")),
                "proof_retained": bool(result.get("proof_retained", True)),
                "fact_status": result.get("fact_status"),
                "human_review_required": bool(result["human_review_required"]),
                "rows_deleted": int(result["rows_deleted"]),
                "agrees_with_expectation": _agrees(case),
                "refused_claims": list(result.get("refused_claims") or []),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": proof_audit_repository_invariant_failures(result),
                "validation_invariant_failures": (
                    validation_invariant_failures(validation) if validation else []
                ),
                # Per-case extras, present only where the case demonstrates one.
                "rows_after_supersede": extra.get("rows_after_supersede"),
                "superseded_count": extra.get("superseded_count"),
                "predecessor_retained": extra.get("predecessor_retained"),
                "predecessor_reference_kept": extra.get("predecessor_reference_kept"),
                "derived_proof_status": extra.get("derived_proof_status"),
                "written_back_to_requirement": extra.get("written_back_to_requirement"),
                "reference_after_rejection": extra.get("reference_after_rejection"),
                "rows_after_archive": extra.get("rows_after_archive"),
                "archived_count": extra.get("archived_count"),
                "still_listed": extra.get("still_listed"),
                "reference_after_archive": extra.get("reference_after_archive"),
                "with_document_store_blocked": extra.get("with_document_store_blocked"),
                "with_document_store_present": extra.get("with_document_store_present"),
                # Constant across every case.
                "customer_auth_live": False,
                "production_proof_records_created": 0,
                "document_storage_built_by_gate_126": False,
            }
        )

    missing = [name for name in REQUIRED_CASES if name not in covered]
    disagreeing = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "case_count": len(rows),
            "cases": rows,
            "proof_event_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "storable_count": sum(1 for r in rows if r["storage_allowed"]),
            "production_write_count": sum(
                1 for r in rows if r["production_write_allowed"]
            ),
            "accepted_count": sum(1 for r in rows if r["proof_is_accepted"]),
            "rejected_count": sum(1 for r in rows if r["proof_is_rejected"]),
            "invariant_failures": sorted(
                {
                    f
                    for r in rows
                    for f in (
                        *r["invariant_failures"],
                        *r["validation_invariant_failures"],
                    )
                }
            ),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            # The real environment, measured once and unmoved by any of this.
            "actual_customer_auth_live": bool(gate["customer_auth_live"]),
            "actual_verified_operational_binding": bool(
                binding["operational_verified_binding"]
            ),
            # Constants. A fixture set demonstrates; it stores nothing real.
            "customer_auth_live": False,
            "login_live": False,
            "customer_persistence_live": False,
            "awarded_grants_operational_tracking_live": False,
            "document_storage_available": False,
            "proof_audit_operational": False,
            "beta_onboarding_ready": False,
            "production_proof_records_created": 0,
            "production_award_requirements_created": 0,
            "production_awarded_grants_created": 0,
            "real_customer_data_written": 0,
            "application_database_touched": False,
            "audit_record_deleted": False,
            "proof_deleted": False,
            "rows_deleted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def proof_audit_fixture_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("proof_event_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_its_own_service_invariants")

    if fixture.get("vocabulary_invariant_failures"):
        fails.append("the_event_vocabulary_drifted")

    for constant in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "awarded_grants_operational_tracking_live",
        "document_storage_available",
        "proof_audit_operational",
        "beta_onboarding_ready",
        "application_database_touched",
        "audit_record_deleted",
        "proof_deleted",
        "persisted",
        "fabricated",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"fixture_set_claimed:{constant}")

    for row in rows:
        label = row.get("case")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")
        if row.get("production_write_allowed"):
            fails.append(f"a_fixture_permitted_a_production_write:{label}")
        if row.get("customer_auth_live"):
            fails.append(f"a_fixture_claimed_auth_is_live:{label}")
        if row.get("rows_deleted"):
            fails.append(f"a_fixture_deleted_a_row:{label}")
        if row.get("production_proof_records_created"):
            fails.append(f"a_fixture_created_a_production_proof_record:{label}")
        if row.get("document_storage_built_by_gate_126"):
            fails.append(f"a_fixture_claimed_a_document_store:{label}")
        if not row.get("proof_retained"):
            fails.append(f"a_fixture_stopped_retaining_its_proof:{label}")
        # A filing is not a decision.
        if row.get("proof_is_accepted") and not row.get("submission_recorded"):
            fails.append(f"an_acceptance_without_a_submission:{label}")

    # A filing is not an acceptance.
    submitted = [
        r for r in rows if r["case"] == "submitted_proof_is_not_accepted_proof"
    ]
    if not submitted:
        fails.append("the_submitted_proof_case_is_missing")
    else:
        row = submitted[0]
        if row.get("proof_is_accepted"):
            fails.append("a_submitted_proof_was_reported_as_accepted")
        if not row.get("submission_recorded"):
            fails.append("the_submitted_proof_case_recorded_no_submission")

    # A rejection retains.
    rejected = [r for r in rows if r["case"] == "rejected_proof_is_retained"]
    if not rejected:
        fails.append("the_rejected_proof_case_is_missing")
    else:
        row = rejected[0]
        if not row.get("proof_is_rejected"):
            fails.append("the_rejected_proof_case_did_not_derive_a_rejection")
        if not row.get("reference_after_rejection"):
            fails.append("a_rejection_discarded_the_proof_reference")

    # A supersession retains.
    superseded = [r for r in rows if r["case"] == "superseded_proof_is_retained"]
    if not superseded:
        fails.append("the_superseded_proof_case_is_missing")
    else:
        row = superseded[0]
        if row.get("rows_after_supersede") != 2:
            fails.append("superseding_did_not_leave_two_rows")
        if row.get("superseded_count") != 1:
            fails.append("the_superseded_row_was_not_marked")
        if not row.get("predecessor_retained"):
            fails.append("a_supersede_did_not_retain_its_predecessor")
        if not row.get("predecessor_reference_kept"):
            fails.append("a_supersede_discarded_the_prior_reference")
        if row.get("written_back_to_requirement"):
            fails.append("a_derived_status_was_written_back_onto_the_requirement")

    # A reference is not a document, and the refusal is falsifiable.
    document = [
        r
        for r in rows
        if r["case"] == "proof_document_reference_does_not_imply_document_storage"
    ]
    if not document:
        fails.append("the_document_reference_case_is_missing")
    else:
        row = document[0]
        if row.get("storage_allowed"):
            fails.append("a_storage_flag_was_accepted_without_a_store")
        if row.get("with_document_store_blocked"):
            fails.append("the_document_store_refusal_is_not_falsifiable")
        if row.get("with_document_store_present") is not True:
            fails.append("the_injected_document_store_was_not_observed")

    # Archive retains.
    archived = [r for r in rows if r["case"] == "archive_retains_the_event"]
    if not archived:
        fails.append("the_archive_case_is_missing")
    else:
        row = archived[0]
        if row.get("rows_after_archive") != 1:
            fails.append("archiving_did_not_retain_the_row")
        if row.get("archived_count") != 1:
            fails.append("the_archived_row_was_not_reported_as_archived")
        if row.get("still_listed") != 1:
            fails.append("an_archived_event_left_the_audit_trail")
        if not row.get("reference_after_archive"):
            fails.append("archiving_discarded_the_proof_reference")

    return sorted(set(fails))
