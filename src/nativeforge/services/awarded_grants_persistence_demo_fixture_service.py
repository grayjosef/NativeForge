"""Awarded grants persistence demo fixtures (Gate 124G).

Eleven labelled cases exercised against a database that lives for the length of
one case, so the refusals are observed rather than asserted.

## What a fixture is allowed to be

```text
every identifier prefixed   nf-demo-fixture-
every fact_status           demo_fixture
every production write      refused
rows in the application database  0
```

`demo_fixture` is deliberately outside `ACTIONABLE_FACT_STATUSES`, which is why
a fixture award can be stored and can never establish an obligation. That is the
property this set exists to demonstrate: storable and inert.

## The case this set exists for

`projected_burden_does_not_become_an_active_obligation` takes a real result from
`pursuit_reporting_burden_projection_service` — fully evidenced, extraction
complete, the strongest projection the pursuit side can produce — and shows the
award side still reports `obligations_established: False`.

A projection carries `is_active_obligation: False` and
`requires_award_before_obligations_begin: True`. Gate 91 wrote those; this case
is the evidence that nothing downstream quietly ignores them.

## Two cases about the same word

```text
obligations_claimed      the fixture wrote `obligations_established`
obligations_established  and every condition for it held
```

`obligations_require_a_capable_extraction` claims the first without the second
and is refused with a named reason. A fixture that could establish an obligation
would mean a demo could produce a compliance calendar somebody might believe.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.awarded_grants_persistence_validation_service import (
    validation_invariant_failures,
)
from nativeforge.services.awarded_grants_repository_service import (
    AWARDED_GRANTS,
    archive_awarded_grant,
    awarded_grants_repository_invariant_failures,
    create_awarded_grant,
    list_awarded_grants,
    prepare_award_write,
)
from nativeforge.services.pursuit_reporting_burden_projection_service import (
    project_pursuit_reporting_burden,
)

SCHEMA_VERSION = "nf_awarded_grants_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed so the fixture set is reproducible. Not a real organization: no row is
# written to the application database by anything in this module.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
DEMO_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
DEMO_AWARD_ID = uuid.UUID("2b4d6f80-1a3c-4e5f-8b9d-0c1e2f3a4b5c")

DEMO_TENANT_LABEL = FIXTURE_PREFIX + "sc-tenant"
DEMO_CUSTOMER_ORG_LABEL = FIXTURE_PREFIX + "sc-customer-org"
DEMO_PROFILE_ID_LABEL = FIXTURE_PREFIX + "org-profile"
DEMO_PURSUIT_ID = FIXTURE_PREFIX + "pursuit-1"
DEMO_OPPORTUNITY_ID = FIXTURE_PREFIX + "opportunity-1"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

# One award, every field supplied, every fact marked as a fixture.
DEMO_AWARD: dict[str, Any] = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "tenant_id_label": DEMO_TENANT_LABEL,
    "customer_org_id_label": DEMO_CUSTOMER_ORG_LABEL,
    "source_pursuit_id": DEMO_PURSUIT_ID,
    "source_opportunity_id": DEMO_OPPORTUNITY_ID,
    "award_number": FIXTURE_PREFIX + "2026-001",
    "award_title": "Demo Tribal Housing Infrastructure Award",
    "funder_name": FIXTURE_PREFIX + "funder",
    "program_name": "Demo Housing Improvement Program",
    "award_status": "active_award",
    "award_amount": "250000.00",
    "award_currency": "USD",
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
    "active_obligation_status": "no_obligations_established",
    "fact_status": FIXTURE_LABEL,
    "requirements_extraction_status": "not_attempted",
    "created_by_identity_id": DEMO_IDENTITY_ID,
    "is_demo": True,
}

REQUIRED_CASES: tuple[str, ...] = (
    "valid_demo_awarded_grant",
    "award_without_a_title_refused",
    "unknown_award_amount_stays_unknown",
    "reversed_period_refused_not_swapped",
    "pursuit_lineage_does_not_create_an_award",
    "projected_burden_does_not_become_an_active_obligation",
    "obligations_require_a_capable_extraction",
    "tenant_id_and_customer_org_id_used_as_labels_only",
    "organization_profile_id_refused_as_anchor",
    "archive_retains_the_award_record",
    "customer_auth_live_false_blocks_production_write",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    AWARDED_GRANTS.create(engine)
    return engine


def build_demo_award_cases() -> list[dict[str, Any]]:
    """Eleven labelled cases. Four storable, seven refused."""
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
        "valid_demo_awarded_grant",
        (
            "every field supplied, every fact marked as a fixture. Storable and "
            "unable to oblige anybody, which is what a fixture should be"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_award_write(**DEMO_AWARD),
    )

    case(
        "award_without_a_title_refused",
        (
            "the one field that cannot be unknown. An award nobody can name is "
            "a row nobody can act on, and the database agrees"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_award_write(**{**DEMO_AWARD, "award_title": "   "}),
    )

    case(
        "unknown_award_amount_stays_unknown",
        (
            "no amount, so no currency and no default. A zero in a funding "
            "column reads as a real number to everything downstream"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_award_write(
            **{**DEMO_AWARD, "award_amount": None, "award_currency": None}
        ),
    )

    case(
        "reversed_period_refused_not_swapped",
        (
            "refused rather than corrected. Swapping the dates and trusting one "
            "of them are both guesses about which end was mistyped"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_award_write(
            **{
                **DEMO_AWARD,
                "period_start": "2026-12-31",
                "period_end": "2026-01-01",
            }
        ),
    )

    # -- lineage, and the projection it carries ------------------------------
    lineage_only = prepare_award_write(
        **{
            **DEMO_AWARD,
            "award_title": None,
            "source_pursuit_id": DEMO_PURSUIT_ID,
            "source_opportunity_id": DEMO_OPPORTUNITY_ID,
        }
    )
    case(
        "pursuit_lineage_does_not_create_an_award",
        (
            "a pursuit id and an opportunity id, and nothing else. Lineage says "
            "where an award came from and is never a reason for one to exist, "
            "so this is refused for want of an award, not for want of a pursuit"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=lineage_only,
        extra={"lineage_recorded": True},
    )

    # The strongest projection the pursuit side can produce: fully evidenced,
    # extraction complete, no unevidenced requirements.
    projection = project_pursuit_reporting_burden(
        opportunity_id=DEMO_OPPORTUNITY_ID,
        reporting_requirements=[
            {
                "report_name": "Quarterly performance report",
                "evidence_quote": (
                    "Recipients shall submit quarterly performance reports."
                ),
                "evidence_location": "demo NOFO section IV.B",
            }
        ],
        financial_requirements=[
            {
                "report_name": "Annual federal financial report",
                "evidence_quote": "Recipients shall submit an SF-425 annually.",
                "evidence_location": "demo NOFO section IV.C",
            }
        ],
        extraction_complete=True,
    )
    projected_award = prepare_award_write(
        **{
            **DEMO_AWARD,
            # The projection is *not* passed in. It cannot be: there is no
            # parameter for it, which is the separation expressed as a signature.
            "requirements_extraction_status": "not_attempted",
        }
    )
    case(
        "projected_burden_does_not_become_an_active_obligation",
        (
            "two evidenced projected requirements on the pursuit side, and the "
            "award still establishes no obligation. The projection carries "
            "is_active_obligation False and requires_award_before_obligations "
            "True; nothing here overrides either"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=projected_award,
        extra={
            "projection": projection,
            "projected_requirement_count": (
                len(projection["projected_reporting_requirements"])
                + len(projection["projected_financial_requirements"])
            ),
        },
    )

    case(
        "obligations_require_a_capable_extraction",
        (
            "the row claims obligations_established with nothing behind it. The "
            "claim is recorded, the derivation refuses it, and the refusal is "
            "named rather than silently downgrading the status"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_award_write(
            **{
                **DEMO_AWARD,
                "active_obligation_status": "obligations_established",
                "requirements_extraction_status": "not_attempted",
            }
        ),
    )

    # -- the anchor ----------------------------------------------------------
    labels_only = prepare_award_write(
        **{**DEMO_AWARD, "organization_id": None},
        organization_profile_id=None,
    )
    case(
        "tenant_id_and_customer_org_id_used_as_labels_only",
        (
            "both labels supplied and no organization_id. Neither is a write "
            "authority, so the award is refused for want of an anchor - not "
            "quietly anchored on whichever label happened to be present"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=labels_only,
    )

    case(
        "organization_profile_id_refused_as_anchor",
        (
            "refused by name rather than ignored, so a caller who sent one is "
            "told which identity space it was in"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_award_write(
            **DEMO_AWARD, organization_profile_id=DEMO_PROFILE_ID_LABEL
        ),
    )

    # -- archive, never delete -----------------------------------------------
    engine = _memory_engine()
    with engine.begin() as connection:
        create_awarded_grant(
            connection=connection,
            award_id=DEMO_AWARD_ID,
            now=NOW,
            **DEMO_AWARD,
        )
        archived = archive_awarded_grant(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            award_id=str(DEMO_AWARD_ID),
            archived_by_identity_id=DEMO_IDENTITY_ID,
            award_status="mistaken_award",
            now=NOW,
        )
        listed = list_awarded_grants(
            connection=connection, organization_id=DEMO_ORGANIZATION_ID
        )
        rows_in_table = connection.execute(
            sa.select(sa.func.count()).select_from(AWARDED_GRANTS)
        ).scalar()
    engine.dispose()

    case(
        "archive_retains_the_award_record",
        (
            "an award recorded and later found not to exist is archived as "
            "mistaken_award, and the row stays. A funder's audit does not "
            "accept 'we removed it', and a listing that hid it would make a "
            "mistake indistinguishable from an award that never happened"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=archived,
        extra={
            "rows_after_archive": int(rows_in_table or 0),
            "archived_count": int(listed["archived_count"]),
            "award_status_after_archive": listed["awards"][0]["award_status"],
            "obligation_after_archive": (
                listed["awards"][0]["active_obligation_status"]
            ),
        },
    )

    # -- the two gates that are both false -----------------------------------
    case(
        "customer_auth_live_false_blocks_production_write",
        (
            "the same award with fact_status verified instead of demo_fixture, "
            "which makes it a production write. Both gates are named "
            "separately, because auth arriving without a verified binding would "
            "still not be enough"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_award_write(
            **{**DEMO_AWARD, "fact_status": "verified", "is_demo": False}
        ),
    )

    return cases


def measure_award_cases(cases: list[dict[str, Any]]) -> set[str]:
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


def build_awarded_grants_fixture_set() -> dict[str, Any]:
    """The eleven cases, measured."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    cases = build_demo_award_cases()
    covered = measure_award_cases(cases)

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
                "award_status": result.get("award_status"),
                "active_obligation_status": result.get("active_obligation_status"),
                "fact_status": result.get("fact_status"),
                "obligations_claimed": bool(validation.get("obligations_claimed")),
                "obligations_established": bool(
                    validation.get("obligations_established")
                ),
                "award_ready_for_obligation_tracking": bool(
                    validation.get("award_ready_for_obligation_tracking")
                ),
                "human_review_required": bool(result["human_review_required"]),
                "rows_deleted": int(result["rows_deleted"]),
                "agrees_with_expectation": _agrees(case),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": awarded_grants_repository_invariant_failures(
                    result
                ),
                "validation_invariant_failures": (
                    validation_invariant_failures(validation) if validation else []
                ),
                # Per-case extras, present only where the case demonstrates one.
                "lineage_recorded": extra.get("lineage_recorded"),
                "projected_requirement_count": extra.get("projected_requirement_count"),
                "projection_is_active_obligation": (
                    bool(extra["projection"]["is_active_obligation"])
                    if "projection" in extra
                    else None
                ),
                "rows_after_archive": extra.get("rows_after_archive"),
                "archived_count": extra.get("archived_count"),
                "award_status_after_archive": extra.get("award_status_after_archive"),
                # Constant across every case.
                "customer_auth_live": False,
                "production_awarded_grants_created": 0,
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
            "award_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "storable_count": sum(1 for r in rows if r["storage_allowed"]),
            "production_write_count": sum(
                1 for r in rows if r["production_write_allowed"]
            ),
            "obligations_established_count": sum(
                1 for r in rows if r["obligations_established"]
            ),
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
            "beta_onboarding_ready": False,
            "production_awarded_grants_created": 0,
            "production_award_requirements_created": 0,
            "real_customer_data_written": 0,
            "application_database_touched": False,
            "projected_burden_promoted": False,
            "rows_deleted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def awarded_grants_fixture_invariant_failures(
    fixture: dict[str, Any],
) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("award_cases_missing"):
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
        if row.get("production_awarded_grants_created"):
            fails.append(f"a_fixture_created_a_production_award:{label}")
        # `demo_fixture` sits outside ACTIONABLE_FACT_STATUSES precisely so this
        # cannot happen. A fixture that established an obligation would mean a
        # demo could produce a compliance calendar somebody might believe.
        if row.get("obligations_established"):
            fails.append(f"a_fixture_established_an_obligation:{label}")

    if fixture.get("obligations_established_count"):
        fails.append("a_fixture_set_established_obligations")

    # The case this set exists for.
    projected = [
        r
        for r in rows
        if r["case"] == "projected_burden_does_not_become_an_active_obligation"
    ]
    if not projected:
        fails.append("the_projected_burden_case_is_missing")
    else:
        row = projected[0]
        if not row.get("projected_requirement_count"):
            fails.append("the_projected_burden_case_projected_nothing")
        if row.get("projection_is_active_obligation") is not False:
            fails.append("a_projection_claimed_to_be_an_active_obligation")
        if row.get("obligations_established"):
            fails.append("a_projected_burden_became_an_active_obligation")

    # Archive, never delete.
    archived = [r for r in rows if r["case"] == "archive_retains_the_award_record"]
    if not archived:
        fails.append("the_archive_case_is_missing")
    else:
        row = archived[0]
        if row.get("rows_after_archive") != 1:
            fails.append("archiving_did_not_retain_the_row")
        if row.get("archived_count") != 1:
            fails.append("the_archived_row_was_not_reported_as_archived")
        if row.get("award_status_after_archive") != "mistaken_award":
            fails.append("the_archived_award_lost_the_status_it_was_archived_with")

    return sorted(set(fails))
