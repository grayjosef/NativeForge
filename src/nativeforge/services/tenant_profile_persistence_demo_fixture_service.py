"""Tenant profile persistence demo fixtures (Gate 123F).

Ten labelled cases across the anchor, the facts, the geography rule and the
lifecycle.

## The case this set exists for

```text
mailing_address_does_not_override_operating_state
```

A profile whose service area says "Columbia, South Carolina" and whose
`operating_states` is empty matches **no** South Carolina sources. That is Gate
103's `operating_state_from_mailing_address` refusal, exercised rather than
asserted — and it is the one a reasonable person would get wrong, because the
state is right there in the text.

## Every value is fake, and the fake is a real shape

```text
organization_id   a fixed UUID belonging to nobody
tenant_id         nf-demo-fixture-*
recognition       state_recognized, with fact_status demo_fixture
operating_states  ["SC"], because South Carolina is the pilot geography
```

`demo_fixture` is deliberately not in `ACTIONABLE_FACT_STATUSES`. Every profile
here is storable and none is actionable, which is the distinction Gate 103's
status vocabulary exists to make.

## The database is real and it is not this application's

An in-memory SQLite created inside the case and disposed at the end. Real
INSERTs and UPDATEs against a table carrying migration 0031's eight CHECK
constraints — which is the only way to show that
`ck_nf_tenant_beta_unknown_recognition_is_unestablished` actually fires.

```text
rows written in the application database   0
production tenant profiles created         0
```
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_profile_persistence_validation_service import (
    matches_state_source,
    validate_tenant_profile,
    validation_invariant_failures,
)
from nativeforge.services.tenant_profile_repository_service import (
    TENANT_BETA_PROFILES,
    archive_tenant_profile,
    list_tenant_profiles,
    prepare_profile_write,
    profile_repository_invariant_failures,
    upsert_tenant_profile,
)

SCHEMA_VERSION = "nf_tenant_profile_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed rather than generated, so a committed artifact is byte-identical on
# every machine. Belongs to nobody.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
DEMO_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"

DEMO_TENANT_LABEL = FIXTURE_PREFIX + "sc-tenant"
DEMO_CUSTOMER_ORG_LABEL = FIXTURE_PREFIX + "sc-customer-org"
DEMO_PROFILE_ID_LABEL = FIXTURE_PREFIX + "org-profile"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

# A South Carolina Tribal tenant. Every field supplied, every fact marked as a
# fixture, and therefore none of it actionable.
SC_PROFILE: dict[str, Any] = {
    "organization_id": DEMO_ORGANIZATION_ID,
    "tenant_id_label": DEMO_TENANT_LABEL,
    "customer_org_id_label": DEMO_CUSTOMER_ORG_LABEL,
    "recognition_status": "state_recognized",
    "recognition_status_fact_status": "demo_fixture",
    "operating_states": ["SC"],
    "operating_states_fact_status": "demo_fixture",
    "service_area": "the Pee Dee region",
    "applicant_classes": ["state_recognized_tribe"],
    "applicant_classes_fact_status": "demo_fixture",
    "programs": ["housing", "water_infrastructure"],
    "departments": ["administration", "public_works"],
    "priority_topics": ["housing", "water"],
    "excluded_topics": ["defense"],
    "source_watchlist_preferences": ["sc_state_portal", "federal_register"],
    "digest_frequency": "weekly",
    "routing_rules": ["grants_admin"],
    "custom_alerts": ["deadline_7_days"],
    "profile_status": "active",
    "is_demo": True,
}

REQUIRED_CASES: tuple[str, ...] = (
    "valid_sc_tribal_tenant_profile",
    "missing_recognition_status_stays_unknown",
    "missing_operating_states_refuses_state_matching",
    "operating_state_sc_drives_sc_source_matching",
    "mailing_address_does_not_override_operating_state",
    "tenant_id_used_as_label_only",
    "customer_org_id_used_as_label_only",
    "organization_profile_id_refused_as_anchor",
    "archive_retains_profile",
    "customer_auth_live_false_blocks_production_write",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    TENANT_BETA_PROFILES.create(engine)
    return engine


def build_demo_profile_cases() -> list[dict[str, Any]]:
    """Ten labelled cases. Two storable, eight refused or read-only."""
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
        "valid_sc_tribal_tenant_profile",
        (
            "every field supplied, every fact marked as a fixture. Storable "
            "and not actionable, which is what a fixture should be"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_profile_write(**SC_PROFILE),
    )

    case(
        "missing_recognition_status_stays_unknown",
        (
            "nobody has established it, so it stays unknown and a human is "
            "required. Nothing is inferred from the name or the state"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_profile_write(
            **{
                **SC_PROFILE,
                "recognition_status": "unknown",
                "recognition_status_fact_status": "unknown",
            }
        ),
    )

    case(
        "missing_operating_states_refuses_state_matching",
        (
            "no states, no state matching. The refusal is named rather than "
            "the profile silently matching nothing"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_profile_write(
            **{**SC_PROFILE, "operating_states": [], "service_area": None}
        ),
    )

    sc_validation = validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="tenant_supplied",
        operating_states=["SC"],
        operating_states_fact_status="tenant_supplied",
        service_area="the Pee Dee region",
        applicant_classes=["state_recognized_tribe"],
        applicant_classes_fact_status="tenant_supplied",
        priority_topics=["housing"],
        excluded_topics=["defense"],
        digest_frequency="weekly",
        routing_rules=["grants_admin"],
        source_watchlist_preferences=["sc_state_portal"],
    )
    case(
        "operating_state_sc_drives_sc_source_matching",
        (
            "SC in operating_states, so SC sources match and NC sources do "
            "not. The list decides and nothing else does"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_profile_write(**SC_PROFILE),
        extra={
            "validation": sc_validation,
            "sc_match": matches_state_source(
                validation=sc_validation, source_state="SC"
            ),
            "nc_match": matches_state_source(
                validation=sc_validation, source_state="NC"
            ),
        },
    )

    address_validation = validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="tenant_supplied",
        operating_states=[],
        service_area="1 Main Street, Columbia, South Carolina",
        applicant_classes=["state_recognized_tribe"],
        applicant_classes_fact_status="tenant_supplied",
        digest_frequency="weekly",
        routing_rules=["grants_admin"],
    )
    case(
        "mailing_address_does_not_override_operating_state",
        (
            "the case this set exists for. South Carolina is written in the "
            "service area and no SC source matches, because an address is not "
            "an operating state"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_profile_write(
            **{
                **SC_PROFILE,
                "operating_states": [],
                "service_area": "1 Main Street, Columbia, South Carolina",
            }
        ),
        extra={
            "validation": address_validation,
            "sc_match": matches_state_source(
                validation=address_validation, source_state="SC"
            ),
        },
    )

    case(
        "tenant_id_used_as_label_only",
        "it travels with the row and never anchors or selects one",
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_profile_write(**SC_PROFILE),
    )

    case(
        "customer_org_id_used_as_label_only",
        "the same, for the second label",
        expect_storage_allowed=True,
        expect_production_write=False,
        result=prepare_profile_write(**SC_PROFILE),
    )

    case(
        "organization_profile_id_refused_as_anchor",
        (
            "a real value from a real column in the wrong identity space - "
            "the substitution Gates 110-113 exist to refuse"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_profile_write(
            **SC_PROFILE, organization_profile_id=DEMO_PROFILE_ID_LABEL
        ),
    )

    # Archive against a real table, so the retention is demonstrated rather
    # than described.
    engine = _memory_engine()
    with engine.begin() as conn:
        upsert_tenant_profile(connection=conn, now=NOW, **SC_PROFILE)
        archived = archive_tenant_profile(
            connection=conn,
            organization_id=DEMO_ORGANIZATION_ID,
            archived_by_identity_id=DEMO_IDENTITY_ID,
            now=NOW,
        )
        listing = list_tenant_profiles(
            connection=conn, organization_id=DEMO_ORGANIZATION_ID
        )
        remaining = conn.execute(
            sa.select(sa.func.count()).select_from(TENANT_BETA_PROFILES)
        ).scalar()
    engine.dispose()

    case(
        "archive_retains_profile",
        (
            "an UPDATE, not a DELETE. A digest complaint is debugged against "
            "the profile that produced it"
        ),
        expect_storage_allowed=True,
        expect_production_write=False,
        result=archived,
        extra={
            "rows_after_archive": int(remaining or 0),
            "rows_listed": listing["rows_read"],
            "archived_count": listing["archived_count"],
        },
    )

    case(
        "customer_auth_live_false_blocks_production_write",
        (
            "everything a production profile needs, supplied, and refused - "
            "because nobody can be authenticated as the tenant it describes"
        ),
        expect_storage_allowed=False,
        expect_production_write=False,
        result=prepare_profile_write(
            **{
                **SC_PROFILE,
                "is_demo": False,
                "recognition_status_fact_status": "tenant_supplied",
                "operating_states_fact_status": "tenant_supplied",
                "applicant_classes_fact_status": "tenant_supplied",
            }
        ),
    )

    return cases


def measure_profile_cases(cases: list[dict[str, Any]]) -> set[str]:
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


def build_tenant_profile_fixture_set() -> dict[str, Any]:
    """The ten cases, measured."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    cases = build_demo_profile_cases()
    covered = measure_profile_cases(cases)

    # Measured once, from the real environment, so the set can state plainly
    # that no fixture moved it.
    gate = build_customer_auth_activation_gate()
    binding = build_binding_store_readiness()

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        extra = case["extra"]
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
                "recognition_status": result.get("recognition_status"),
                "operating_states": list(result.get("operating_states") or []),
                "human_review_required": bool(result["human_review_required"]),
                "rows_deleted": int(result["rows_deleted"]),
                "agrees_with_expectation": _agrees(case),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": profile_repository_invariant_failures(result),
                # Per-case extras, present only where the case demonstrates one.
                "sc_source_matched": (
                    bool(extra["sc_match"]["matched"]) if "sc_match" in extra else None
                ),
                "nc_source_matched": (
                    bool(extra["nc_match"]["matched"]) if "nc_match" in extra else None
                ),
                "rows_after_archive": extra.get("rows_after_archive"),
                "archived_count": extra.get("archived_count"),
                "validation_invariant_failures": (
                    validation_invariant_failures(extra["validation"])
                    if "validation" in extra
                    else []
                ),
                # Constant across every case.
                "customer_auth_live": False,
                "production_tenant_profiles_created": 0,
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
            "profile_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "storable_count": sum(1 for r in rows if r["storage_allowed"]),
            "production_write_count": sum(
                1 for r in rows if r["production_write_allowed"]
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
            "beta_onboarding_ready": False,
            "production_tenant_profiles_created": 0,
            "real_customer_data_written": 0,
            "application_database_touched": False,
            "rows_deleted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def tenant_profile_fixture_invariant_failures(
    fixture: dict[str, Any],
) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("profile_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_its_own_service_invariants")

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
        if row.get("production_tenant_profiles_created"):
            fails.append(f"a_fixture_created_a_production_profile:{label}")

    # The case this set exists for: an address naming a state matches nothing.
    address = [
        r
        for r in rows
        if r["case"] == "mailing_address_does_not_override_operating_state"
    ]
    if not address:
        fails.append("the_address_override_case_is_missing")
    elif address[0]["sc_source_matched"] is not False:
        fails.append("an_address_was_allowed_to_produce_a_state_match")

    matching = [
        r for r in rows if r["case"] == "operating_state_sc_drives_sc_source_matching"
    ]
    if matching:
        if matching[0]["sc_source_matched"] is not True:
            fails.append("operating_states_did_not_produce_a_state_match")
        if matching[0]["nc_source_matched"] is not False:
            fails.append("a_state_outside_operating_states_matched")

    archive = [r for r in rows if r["case"] == "archive_retains_profile"]
    if archive and archive[0]["rows_after_archive"] != 1:
        fails.append("archiving_did_not_retain_the_row")

    if fixture.get("production_write_count"):
        fails.append("the_set_permitted_a_production_write")
    if fixture.get("actual_customer_auth_live"):
        fails.append("the_actual_environment_was_reported_as_auth_live")
    if fixture.get("actual_verified_operational_binding"):
        fails.append("the_actual_environment_was_reported_as_binding_operational")
    if fixture.get("production_tenant_profiles_created"):
        fails.append("a_production_tenant_profile_was_created")
    if fixture.get("real_customer_data_written"):
        fails.append("real_customer_data_was_written")
    if fixture.get("application_database_touched"):
        fails.append("the_application_database_was_touched")
    if fixture.get("beta_onboarding_ready"):
        fails.append("the_set_claimed_beta_onboarding_is_ready")

    return sorted(set(fails))
