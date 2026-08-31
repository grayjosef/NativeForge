"""Award requirements persistence demo fixtures (Gate 125G).

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

A fixture requirement *can* be an active obligation, and that is deliberate:
`active_obligation` is a property of the requirement's provenance, not a claim
about a real tenant. Gate 108 derives it from `extraction_status` alone and this
does the same. What keeps a fixture inert is the label on every identifier and
the two production gates, both false.

## Two lists, and the case that forces the distinction

```text
blocked_reasons   the row may not be stored
refused_claims    the row is stored, and something it asserted was not
```

`projected_burden_refused_as_active_obligation` is stored. That is the point: a
projection recorded beside the award it became is how a Tribe sees what they
expected against what they got, and refusing the row would leave
`projected_burden` an unreachable column with nothing to test.

## The document store that does not exist

`proof_document_reference_does_not_imply_document_storage` supplies a reference
and is refused, because there is nowhere for it to resolve. The same case also
runs with `document_storage_available=True` injected, so the permitted branch is
reachable and the refusal is falsifiable rather than a constant.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.award_requirements_persistence_validation_service import (
    validate_award_requirement,
    validation_invariant_failures,
)
from nativeforge.services.award_requirements_repository_service import (
    AWARD_REQUIREMENTS,
    archive_award_requirement,
    award_requirements_repository_invariant_failures,
    create_award_requirement,
    list_requirements_for_organization,
    prepare_requirement_write,
)

SCHEMA_VERSION = "nf_award_requirements_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed so the fixture set is reproducible. Not a real organization, not a real
# award: no row is written to the application database by anything here.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
DEMO_AWARDED_GRANT_ID = "2b4d6f80-1a3c-4e5f-8b9d-0c1e2f3a4b5c"
DEMO_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
DEMO_REQUIREMENT_ID = uuid.UUID("3c5e7f91-2b4d-4f60-9c0e-1d2f3a4b5c6d")

DEMO_TENANT_LABEL = FIXTURE_PREFIX + "sc-tenant"
DEMO_CUSTOMER_ORG_LABEL = FIXTURE_PREFIX + "sc-customer-org"
DEMO_PROFILE_ID_LABEL = FIXTURE_PREFIX + "org-profile"
DEMO_SOURCE_REF = FIXTURE_PREFIX + "award-packet#section-4.2"
DEMO_DOCUMENT_REF = FIXTURE_PREFIX + "sf425-2026-q1.pdf"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

# One requirement, every field supplied, every fact marked as a fixture.
DEMO_REQUIREMENT: dict[str, Any] = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "awarded_grant_id": DEMO_AWARDED_GRANT_ID,
    "requirement_type": "financial_report",
    "requirement_title": "Quarterly federal financial report (SF-425)",
    "requirement_description": "Demo requirement. Not a real reporting duty.",
    "requirement_status": "not_started",
    "requirement_source": "human_entered",
    "requirement_due_date": "2026-04-30",
    "due_date_status": "verified",
    "recurrence_rule": "quarterly",
    "owner_identity_id": DEMO_IDENTITY_ID,
    "proof_required": True,
    "proof_status": "not_submitted",
    "submission_status": "not_submitted",
    "fact_status": FIXTURE_LABEL,
    "created_by_identity_id": DEMO_IDENTITY_ID,
    "is_demo": True,
}

REQUIRED_CASES: tuple[str, ...] = (
    "valid_demo_active_reporting_requirement",
    "missing_requirement_title_refused",
    "unknown_due_date_requires_human_review",
    "estimated_due_date_remains_estimated_not_known",
    "projected_burden_refused_as_active_obligation",
    "unsupported_requirement_refused_as_active_obligation",
    "proof_document_reference_does_not_imply_document_storage",
    "submitted_proof_does_not_imply_accepted_proof",
    "awarded_grant_id_cannot_substitute_for_organization_id",
    "tenant_id_refused_as_anchor",
    "customer_org_id_refused_as_anchor",
    "organization_profile_id_refused_as_anchor",
    "archive_retains_the_requirement",
    "customer_auth_live_false_blocks_production_write",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    AWARD_REQUIREMENTS.create(engine)
    return engine


def build_demo_requirement_cases() -> list[dict[str, Any]]:
    """Fourteen labelled cases. Seven storable, seven refused."""
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
        "valid_demo_active_reporting_requirement",
        (
            "human_entered provenance, a verified date, every fact marked as a "
            "fixture. Storable, an obligation of a demo award, and unable to "
            "reach anybody real"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_requirement_write(**DEMO_REQUIREMENT),
    )

    case(
        "missing_requirement_title_refused",
        (
            "the one field that cannot be unknown. A requirement nobody can "
            "name is a deadline nobody can act on, and the database agrees"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_requirement_write(
            **{**DEMO_REQUIREMENT, "requirement_title": "   "}
        ),
    )

    unknown_date = prepare_requirement_write(
        **{
            **DEMO_REQUIREMENT,
            "requirement_due_date": None,
            "due_date_status": "unknown",
        }
    )
    case(
        "unknown_due_date_requires_human_review",
        (
            "stored, because a requirement with no known deadline is still a "
            "requirement. Flagged for a human, and never counted down to"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=unknown_date,
        extra={"date_is_calculable": unknown_date["date_is_calculable"]},
    )

    estimated = prepare_requirement_write(
        **{**DEMO_REQUIREMENT, "due_date_status": "estimated"}
    )
    case(
        "estimated_due_date_remains_estimated_not_known",
        (
            "a date is recorded and the status stays estimated. Gate 108 put "
            "`estimated` outside DATE_CALCULABLE_STATUSES, so a calendar may "
            "show it and may not count down to it"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=estimated,
        extra={
            "date_is_calculable": estimated["date_is_calculable"],
            "due_date_is_estimate_only": estimated["validation"][
                "due_date_is_estimate_only"
            ],
        },
    )

    projected = prepare_requirement_write(
        **{
            **DEMO_REQUIREMENT,
            "requirement_source": "projected_from_nofo",
            "requirement_title": "Projected annual performance report",
            "requirement_due_date": None,
            "due_date_status": "unknown",
        }
    )
    case(
        "projected_burden_refused_as_active_obligation",
        (
            "stored and not an obligation. Gate 91 stamps every projection "
            "is_active_obligation False; this is the other end of that refusal, "
            "and the row exists so a Tribe can see what a NOFO projected beside "
            "what the award actually required"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=projected,
        extra={"refused_claims": projected["refused_claims"]},
    )

    unsupported = prepare_requirement_write(
        **{
            **DEMO_REQUIREMENT,
            "requirement_source": "unsupported_document_type",
            "requirement_title": "Requirement from an unreadable award packet",
            "due_date_status": "verified",
        }
    )
    case(
        "unsupported_requirement_refused_as_active_obligation",
        (
            "an unreadable document is recorded as unreadable rather than "
            "dropped, and its claimed verified date is downgraded to "
            "unsupported. Neither an obligation nor a deadline"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=unsupported,
        extra={
            "refused_claims": unsupported["refused_claims"],
            "due_date_status_after": unsupported["due_date_status"],
        },
    )

    # The permitted branch, run only to prove the refusal below is falsifiable.
    with_store = validate_award_requirement(
        requirement_title=DEMO_REQUIREMENT["requirement_title"],
        requirement_type="financial_report",
        requirement_source="human_entered",
        proof_document_ref=DEMO_DOCUMENT_REF,
        fact_status=FIXTURE_LABEL,
        document_storage_available=True,
    )
    case(
        "proof_document_reference_does_not_imply_document_storage",
        (
            "a reference with nowhere to resolve is refused by name. The same "
            "case with a document store injected is permitted, so the refusal "
            "is a measurement rather than a constant"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_requirement_write(
            **{**DEMO_REQUIREMENT, "proof_document_ref": DEMO_DOCUMENT_REF}
        ),
        extra={
            "with_document_store_blocked": with_store["blocked_reasons"],
            "with_document_store_reference_not_storage": with_store[
                "document_reference_not_storage"
            ],
        },
    )

    submitted = prepare_requirement_write(
        **{
            **DEMO_REQUIREMENT,
            "requirement_status": "submitted",
            "submission_status": "submitted",
            "submitted_at": NOW,
            "proof_status": "proof_missing",
        }
    )
    case(
        "submitted_proof_does_not_imply_accepted_proof",
        (
            "filed and not accepted. A funder accepting a report is a separate "
            "event with its own timestamp, and a screen that read the filing as "
            "the acceptance would tell a Tribe they are done when they are not"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=submitted,
        extra={
            "proof_is_accepted": submitted["validation"]["proof_is_accepted"],
            "acceptance_recorded": submitted["validation"]["acceptance_recorded"],
        },
    )

    case(
        "awarded_grant_id_cannot_substitute_for_organization_id",
        (
            "the award is supplied and the organization is not. Refused by "
            "name: the RLS predicate reads organization_id, so reaching it "
            "through a join would make this table's policy depend on another "
            "table's policy"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_requirement_write(
            **{**DEMO_REQUIREMENT, "organization_id": None}
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
            result=prepare_requirement_write(**DEMO_REQUIREMENT, **kwargs),
        )

    # -- archive, never delete -----------------------------------------------
    engine = _memory_engine()
    with engine.begin() as connection:
        create_award_requirement(
            connection=connection,
            requirement_id=DEMO_REQUIREMENT_ID,
            now=NOW,
            **DEMO_REQUIREMENT,
        )
        archived = archive_award_requirement(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            requirement_id=str(DEMO_REQUIREMENT_ID),
            archived_by_identity_id=DEMO_IDENTITY_ID,
            requirement_status="not_applicable",
            now=NOW,
        )
        listed = list_requirements_for_organization(
            connection=connection, organization_id=DEMO_ORGANIZATION_ID
        )
        rows_in_table = connection.execute(
            sa.select(sa.func.count()).select_from(AWARD_REQUIREMENTS)
        ).scalar()
    engine.dispose()

    case(
        "archive_retains_the_requirement",
        (
            "a requirement that turned out not to apply becomes "
            "not_applicable and the row stays. A funder's audit asks what was "
            "believed and when, and a listing that hid it would make a "
            "withdrawn requirement indistinguishable from one never recorded"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=archived,
        extra={
            "rows_after_archive": int(rows_in_table or 0),
            "archived_count": int(listed["archived_count"]),
            "status_after_archive": listed["requirements"][0]["requirement_status"],
            "active_obligation_after_archive": listed["requirements"][0][
                "active_obligation"
            ],
        },
    )

    case(
        "customer_auth_live_false_blocks_production_write",
        (
            "the same requirement with fact_status verified instead of "
            "demo_fixture, which makes it a production write. Both gates are "
            "named separately, because auth arriving without a verified binding "
            "would still not be enough"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_requirement_write(
            **{**DEMO_REQUIREMENT, "fact_status": "verified", "is_demo": False}
        ),
    )

    return cases


def measure_requirement_cases(cases: list[dict[str, Any]]) -> set[str]:
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


def build_award_requirements_fixture_set() -> dict[str, Any]:
    """The fourteen cases, measured."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    cases = build_demo_requirement_cases()
    covered = measure_requirement_cases(cases)

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
                "requirement_type": result.get("requirement_type"),
                "requirement_status": result.get("requirement_status"),
                "requirement_source": result.get("requirement_source"),
                "active_obligation": bool(result.get("active_obligation")),
                "projected_burden": bool(result.get("projected_burden")),
                "unsupported_requirement": bool(result.get("unsupported_requirement")),
                "due_date_status": result.get("due_date_status"),
                "date_is_calculable": bool(result.get("date_is_calculable")),
                "proof_status": result.get("proof_status"),
                "submission_status": result.get("submission_status"),
                "fact_status": result.get("fact_status"),
                "human_review_required": bool(result["human_review_required"]),
                "rows_deleted": int(result["rows_deleted"]),
                "agrees_with_expectation": _agrees(case),
                "refused_claims": list(result.get("refused_claims") or []),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": (
                    award_requirements_repository_invariant_failures(result)
                ),
                "validation_invariant_failures": (
                    validation_invariant_failures(validation) if validation else []
                ),
                # Per-case extras, present only where the case demonstrates one.
                "proof_is_accepted": extra.get("proof_is_accepted"),
                "acceptance_recorded": extra.get("acceptance_recorded"),
                "due_date_is_estimate_only": extra.get("due_date_is_estimate_only"),
                "due_date_status_after": extra.get("due_date_status_after"),
                "with_document_store_blocked": extra.get("with_document_store_blocked"),
                "rows_after_archive": extra.get("rows_after_archive"),
                "archived_count": extra.get("archived_count"),
                "status_after_archive": extra.get("status_after_archive"),
                "active_obligation_after_archive": extra.get(
                    "active_obligation_after_archive"
                ),
                # Constant across every case.
                "customer_auth_live": False,
                "production_award_requirements_created": 0,
                "production_proof_records_created": 0,
                "document_storage_available": False,
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
            "requirement_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "storable_count": sum(1 for r in rows if r["storage_allowed"]),
            "production_write_count": sum(
                1 for r in rows if r["production_write_allowed"]
            ),
            "active_obligation_count": sum(1 for r in rows if r["active_obligation"]),
            "projected_burden_count": sum(1 for r in rows if r["projected_burden"]),
            "calendarable_count": sum(1 for r in rows if r["date_is_calculable"]),
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
            # `proof_audit_persistence_available` was frozen here and Gate
            # 126 built the store, which made this set's own constant
            # disagree with reality. A fixture set states what it did; the
            # state of a neighbouring lane is readiness's question, and
            # freezing it here was this file answering one it was not
            # asked.
            "beta_onboarding_ready": False,
            "production_award_requirements_created": 0,
            "production_proof_records_created": 0,
            "production_awarded_grants_created": 0,
            "real_customer_data_written": 0,
            "application_database_touched": False,
            "projected_burden_promoted": False,
            "rows_deleted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def award_requirements_fixture_invariant_failures(
    fixture: dict[str, Any],
) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("requirement_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_its_own_service_invariants")

    for constant in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "awarded_grants_operational_tracking_live",
        "document_storage_available",
        "beta_onboarding_ready",
        "application_database_touched",
        "projected_burden_promoted",
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
        if row.get("production_award_requirements_created"):
            fails.append(f"a_fixture_created_a_production_requirement:{label}")
        if row.get("production_proof_records_created"):
            fails.append(f"a_fixture_created_a_production_proof_record:{label}")
        if row.get("document_storage_available"):
            fails.append(f"a_fixture_claimed_a_document_store:{label}")
        # The pair the database also refuses.
        if row.get("active_obligation") and row.get("projected_burden"):
            fails.append(f"a_projection_was_also_an_obligation:{label}")
        if row.get("active_obligation") and row.get("unsupported_requirement"):
            fails.append(f"an_unsupported_row_was_an_obligation:{label}")

    # The case this set exists for.
    projected = [
        r for r in rows if r["case"] == "projected_burden_refused_as_active_obligation"
    ]
    if not projected:
        fails.append("the_projected_burden_case_is_missing")
    else:
        row = projected[0]
        if not row.get("storage_allowed"):
            fails.append("the_projection_case_was_not_storable")
        if row.get("active_obligation"):
            fails.append("a_projected_burden_became_an_active_obligation")
        if not row.get("projected_burden"):
            fails.append("the_projection_case_did_not_record_a_projection")
        if not row.get("refused_claims"):
            fails.append("the_projection_case_did_not_name_what_it_refused")

    # An estimate is not a deadline.
    estimated = [
        r for r in rows if r["case"] == "estimated_due_date_remains_estimated_not_known"
    ]
    if not estimated:
        fails.append("the_estimated_date_case_is_missing")
    else:
        row = estimated[0]
        if row.get("date_is_calculable"):
            fails.append("an_estimated_date_was_reported_as_calculable")
        if row.get("due_date_status") != "estimated":
            fails.append("the_estimated_date_case_lost_its_status")

    # A filing is not an acceptance.
    submitted = [
        r for r in rows if r["case"] == "submitted_proof_does_not_imply_accepted_proof"
    ]
    if not submitted:
        fails.append("the_submitted_proof_case_is_missing")
    else:
        row = submitted[0]
        if row.get("proof_is_accepted"):
            fails.append("a_submitted_proof_was_reported_as_accepted")
        if row.get("acceptance_recorded"):
            fails.append("an_acceptance_was_recorded_for_a_submission")

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
            fails.append("a_document_reference_was_stored_without_a_document_store")
        if row.get("with_document_store_blocked"):
            fails.append("the_document_reference_refusal_is_not_falsifiable")

    # Archive, never delete.
    archived = [r for r in rows if r["case"] == "archive_retains_the_requirement"]
    if not archived:
        fails.append("the_archive_case_is_missing")
    else:
        row = archived[0]
        if row.get("rows_after_archive") != 1:
            fails.append("archiving_did_not_retain_the_row")
        if row.get("archived_count") != 1:
            fails.append("the_archived_row_was_not_reported_as_archived")
        if row.get("status_after_archive") != "not_applicable":
            fails.append("the_archived_requirement_lost_its_status")
        if row.get("active_obligation_after_archive"):
            fails.append("an_archived_requirement_still_obliged_somebody")

    return sorted(set(fails))
