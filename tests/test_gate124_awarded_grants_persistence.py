"""Gate 124: awarded grants persistence.

Somewhere for an awarded grant to live, without letting a pursuit turn into one
or a projection turn into an obligation.

One thing must stay true: **nothing here obliges a Tribe to anything.**

The tests are grouped by what they would catch:

```text
anchor      a label treated as an RLS authority
separation  a pursuit becoming an award, or a projection becoming an obligation
derivation  a field named for a capability that reports a declaration
lifecycle   a DELETE where an archive belongs
liveness    a table existing being read as compliance tracking starting
```
"""

from __future__ import annotations

import ast
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import awarded_grant_record_service as award_svc
from nativeforge.services import (
    awarded_grants_persistence_artifact_service as art,
)
from nativeforge.services import (
    awarded_grants_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    awarded_grants_persistence_validation_service as val_svc,
)
from nativeforge.services import awarded_grants_repository_service as repo_svc
from nativeforge.services import (
    awarded_grants_requirements_readiness_service as readiness_svc,
)
from nativeforge.services import customer_persistence_capability_service as cap_svc
from nativeforge.services import (
    org_scoped_customer_persistence_guard_service as guard_svc,
)
from nativeforge.services import (
    pursuit_reporting_burden_projection_service as projection_svc,
)
from nativeforge.services import tenant_beta_profile_service as beta_svc

ORG = fixtures.DEMO_ORGANIZATION_ID
IDENTITY = fixtures.DEMO_IDENTITY_ID
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

MIGRATION = "alembic/versions/0032_nf_awarded_grants.py"


@pytest.fixture
def awards_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.AWARDED_GRANTS.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


def _award(**overrides):
    kwargs = dict(fixtures.DEMO_AWARD)
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- anchor


def test_organization_id_is_the_only_anchor():
    result = repo_svc.prepare_award_write(**_award())
    assert result["rls_anchor"] == "organization_id"
    assert result["organization_id"] == ORG
    assert repo_svc.awarded_grants_repository_invariant_failures(result) == []


def test_an_award_without_an_organization_id_is_refused():
    result = repo_svc.prepare_award_write(**_award(organization_id=None))
    assert result["storage_allowed"] is False
    assert "award_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_an_anchor_that_is_not_uuid_shaped_is_refused():
    """The RLS predicate casts to ::uuid. A label would raise, not deny."""
    result = repo_svc.prepare_award_write(**_award(organization_id="tribe-sc-01"))
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_tenant_id_and_customer_org_id_are_labels_not_authorities():
    result = repo_svc.prepare_award_write(**_award(organization_id=None))
    # Both labels were supplied by the fixture and neither rescued the write.
    assert result["tenant_id_label"] == fixtures.DEMO_TENANT_LABEL
    assert result["customer_org_id_label"] == fixtures.DEMO_CUSTOMER_ORG_LABEL
    assert result["storage_allowed"] is False


def test_organization_profile_id_is_refused_by_name():
    result = repo_svc.prepare_award_write(
        **_award(), organization_profile_id="nf-demo-fixture-org-profile"
    )
    assert (
        "organization_profile_id_is_not_an_organization_id_anchor"
        in result["blocked_reasons"]
    )


def test_the_forbidden_anchor_names_are_the_campaigns_three():
    assert repo_svc.FORBIDDEN_ANCHOR_NAMES == frozenset(
        {"tenant_id", "customer_org_id", "organization_profile_id"}
    )


def test_a_beta_profile_id_is_context_and_not_an_anchor():
    """A real foreign key, and still not authority."""
    result = repo_svc.prepare_award_write(**_award(tenant_beta_profile_id="not-a-uuid"))
    assert "tenant_beta_profile_id_is_not_uuid_shaped" in result["blocked_reasons"]
    # The column exists and is nullable, which is what SET NULL requires.
    column = repo_svc.AWARDED_GRANTS.c.tenant_beta_profile_id
    assert column.nullable is True


# ------------------------------------------------- separation: pursuit vs award


def test_lineage_is_recorded_and_is_never_a_reason_to_create_an_award():
    result = repo_svc.prepare_award_write(**_award(award_title=None))
    assert result["source_pursuit_id"] == fixtures.DEMO_PURSUIT_ID
    assert result["source_opportunity_id"] == fixtures.DEMO_OPPORTUNITY_ID
    # Lineage present, award absent, and the refusal is about the award.
    assert result["storage_allowed"] is False
    assert "award_without_a_title" in result["blocked_reasons"]
    assert result["award_created_from_lineage"] is False


def test_the_lineage_columns_carry_no_foreign_key():
    """A foreign key would make a pursuit a precondition for an award."""
    for name in repo_svc.LINEAGE_FIELDS:
        assert repo_svc.AWARDED_GRANTS.c[name].foreign_keys == set()

    migration = Path(MIGRATION).read_text(encoding="utf-8")
    for name in repo_svc.LINEAGE_FIELDS:
        line = next(
            row for row in migration.splitlines() if f'sa.Column("{name}"' in row
        )
        assert "ForeignKey" not in line


def test_an_award_status_is_never_inferred_from_a_pursuit():
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award", award_status=None
    )
    assert result["award_status"] == "unknown"
    assert "award_status_unestablished_and_never_inferred" in result["blocked_reasons"]
    assert result["award_status_inferred_from_pursuit"] is False


# ------------------------------------------------- separation: projection vs obligation


def test_a_fully_evidenced_projection_establishes_no_obligation():
    """Gate 91's rule, exercised from the pursuit side inwards."""
    projection = projection_svc.project_pursuit_reporting_burden(
        opportunity_id=fixtures.DEMO_OPPORTUNITY_ID,
        reporting_requirements=[
            {
                "report_name": "Quarterly performance report",
                "evidence_quote": "Recipients shall submit quarterly reports.",
                "evidence_location": "demo NOFO section IV.B",
            }
        ],
        extraction_complete=True,
    )
    assert projection["is_active_obligation"] is False
    assert projection["requires_award_before_obligations_begin"] is True
    assert projection["projected_reporting_requirements"]

    award = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        fact_status="verified",
        award_amount="250000.00",
        award_currency="USD",
    )
    assert award["obligations_established"] is False
    assert award["projected_burden_considered"] is False


def test_the_repository_has_no_parameter_that_could_carry_a_projection():
    """The separation expressed as a signature, not as a runtime check."""
    import inspect

    names = set(inspect.signature(repo_svc.prepare_award_write).parameters)
    for forbidden in (
        "projected_reporting_requirements",
        "projected_financial_requirements",
        "projected_performance_requirements",
        "projected_compliance_requirements",
        "projected_closeout_requirements",
        "burden_fit",
        "projection",
    ):
        assert forbidden not in names


def test_active_obligation_status_is_its_own_column():
    columns = {c.name for c in repo_svc.AWARDED_GRANTS.columns}
    assert "active_obligation_status" in columns
    assert "award_status" in columns
    # Two columns, because an award can be live and oblige nothing yet.
    result = repo_svc.prepare_award_write(**_award(award_status="active_award"))
    assert result["award_status"] == "active_award"
    assert result["active_obligation_status"] == "no_obligations_established"


def test_obligations_need_established_facts_a_capable_extraction_and_a_live_award():
    """Three conjuncts. Each one alone is enough to refuse."""
    settled = dict(
        award_title="Housing Award",
        award_status="active_award",
        active_obligation_status="obligations_established",
        fact_status="verified",
        award_amount="250000.00",
        award_currency="USD",
        requirements_extraction_status="human_entered",
    )
    assert val_svc.validate_awarded_grant(**settled)["obligations_established"] is True

    for override, reason in (
        ({"fact_status": "unknown"}, "requires_verified_or_tenant_supplied_facts"),
        (
            {"requirements_extraction_status": "not_attempted"},
            "without_a_capable_extraction",
        ),
        ({"award_status": "closed"}, "on_a_non_live_award"),
    ):
        result = val_svc.validate_awarded_grant(**{**settled, **override})
        assert result["obligations_established"] is False
        assert any(reason in r for r in result["blocked_reasons"]), override


def test_a_demo_fixture_can_never_establish_an_obligation():
    """`demo_fixture` sits outside ACTIONABLE_FACT_STATUSES for this reason."""
    assert "demo_fixture" not in beta_svc.ACTIONABLE_FACT_STATUSES
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        active_obligation_status="obligations_established",
        fact_status="demo_fixture",
        requirements_extraction_status="human_entered",
    )
    assert result["obligations_established"] is False


# ------------------------------------------------- derivation, not declaration


def test_a_claim_is_reported_separately_from_the_derivation():
    """The defect this campaign keeps finding, kept out of this service."""
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        active_obligation_status="obligations_established",
        fact_status="verified",
        requirements_extraction_status="not_attempted",
    )
    assert result["obligations_claimed"] is True
    assert result["obligations_established"] is False


def test_a_refused_claim_never_trips_the_services_own_invariants():
    """An invariant ordinary bad input can fire is a validation rule misnamed."""
    for case in (
        {"active_obligation_status": "obligations_established"},
        {
            "active_obligation_status": "obligations_established",
            "award_status": "closed",
        },
        {"award_amount": "not-a-number", "award_currency": "USD"},
        {"period_start": "2026-12-31", "period_end": "2026-01-01"},
        {"award_title": None},
        {"award_status": "invented_status"},
        {"fact_status": "invented_status"},
    ):
        result = val_svc.validate_awarded_grant(
            **{"award_title": "Housing Award", **case}
        )
        assert val_svc.validation_invariant_failures(result) == [], case


def test_a_refused_claim_always_says_why():
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        active_obligation_status="obligations_established",
        fact_status="verified",
        award_amount="1.00",
        award_currency="USD",
        requirements_extraction_status="not_attempted",
    )
    assert result["obligations_claimed"] is True
    assert result["obligations_established"] is False
    assert result["blocked_reasons"]


def test_the_permitted_branch_is_reachable():
    """Gates 117-121 each shipped an invariant whose True branch was not."""
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        active_obligation_status="obligations_established",
        fact_status="verified",
        award_amount="250000.00",
        award_currency="USD",
        period_start="2026-01-01",
        period_end="2026-12-31",
        requirements_extraction_status="evidence_extracted",
    )
    assert result["award_ready_for_obligation_tracking"] is True
    assert result["human_review_required"] is False
    assert val_svc.validation_invariant_failures(result) == []


def test_a_production_write_is_reachable_and_needs_both_gates():
    settled = _award(fact_status="verified", is_demo=False)
    assert (
        repo_svc.prepare_award_write(
            **settled, customer_auth_live=True, verified_operational_binding=True
        )["production_write_allowed"]
        is True
    )
    for kwargs, reason in (
        (
            {"customer_auth_live": False, "verified_operational_binding": True},
            "production_award_write_requires_live_customer_auth",
        ),
        (
            {"customer_auth_live": True, "verified_operational_binding": False},
            "production_award_write_requires_a_verified_operational_binding",
        ),
    ):
        result = repo_svc.prepare_award_write(**settled, **kwargs)
        assert result["production_write_allowed"] is False
        assert reason in result["blocked_reasons"]


def test_both_gates_are_false_in_this_repository():
    result = repo_svc.prepare_award_write(
        **_award(fact_status="verified", is_demo=False)
    )
    assert result["production_write_allowed"] is False
    assert set(result["blocked_reasons"]) == {
        "production_award_write_requires_live_customer_auth",
        "production_award_write_requires_a_verified_operational_binding",
    }


# ------------------------------------------------- money and dates


def test_an_unknown_amount_stays_unknown_and_is_never_defaulted_to_zero():
    result = repo_svc.prepare_award_write(
        **_award(award_amount=None, award_currency=None)
    )
    assert result["award_amount"] is None
    assert result["storage_allowed"] is True
    assert result["human_review_required"] is True


def test_an_unknown_amount_cannot_sit_on_an_established_fact_status():
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        fact_status="verified",
        award_amount=None,
    )
    assert (
        "unknown_award_amount_cannot_carry_an_established_fact_status"
        in result["blocked_reasons"]
    )


def test_money_needs_a_currency_and_a_currency_needs_money():
    for kwargs in (
        {"award_amount": "250000.00", "award_currency": None},
        {"award_amount": None, "award_currency": "USD"},
    ):
        result = val_svc.validate_awarded_grant(
            award_title="Housing Award", award_status="active_award", **kwargs
        )
        assert (
            "award_amount_and_currency_must_both_be_present"
            in result["blocked_reasons"]
        )


def test_the_amount_column_is_numeric_not_float():
    """A float is a rounding error waiting for an audit."""
    column = repo_svc.AWARDED_GRANTS.c.award_amount
    assert isinstance(column.type, sa.Numeric)
    assert not isinstance(column.type, sa.Float)
    assert column.type.scale == 2


def test_a_reversed_period_is_refused_rather_than_swapped():
    result = val_svc.validate_awarded_grant(
        award_title="Housing Award",
        award_status="active_award",
        period_start="2026-12-31",
        period_end="2026-01-01",
    )
    assert "period_end_is_before_period_start" in result["blocked_reasons"]
    # Not silently corrected in either direction.
    assert result["period_start"] == "2026-12-31"
    assert result["period_end"] == "2026-01-01"


# ------------------------------------------------- lifecycle


def test_a_row_is_written_and_read_back(awards_db):
    award_id = uuid.uuid4()
    created = repo_svc.create_awarded_grant(
        connection=awards_db, award_id=award_id, now=NOW, **_award()
    )
    assert created["rows_written"] == 1
    read = repo_svc.get_awarded_grant(
        connection=awards_db, organization_id=ORG, award_id=str(award_id)
    )
    assert read["rows_read"] == 1
    assert read["award_title"] == fixtures.DEMO_AWARD["award_title"]
    assert repo_svc.awarded_grants_repository_invariant_failures(read) == []


def test_a_read_is_scoped_to_one_organization(awards_db):
    repo_svc.create_awarded_grant(connection=awards_db, now=NOW, **_award())
    other = repo_svc.get_awarded_grant(
        connection=awards_db, organization_id=str(uuid.uuid4())
    )
    assert other["rows_read"] == 0
    assert "no_awarded_grant_for_this_organization" in other["blocked_reasons"]


def test_archiving_retains_the_row(awards_db):
    award_id = uuid.uuid4()
    repo_svc.create_awarded_grant(
        connection=awards_db, award_id=award_id, now=NOW, **_award()
    )
    archived = repo_svc.archive_awarded_grant(
        connection=awards_db,
        organization_id=ORG,
        award_id=str(award_id),
        archived_by_identity_id=IDENTITY,
        award_status="mistaken_award",
        now=NOW,
    )
    assert archived["rows_written"] == 1
    assert archived["rows_deleted"] == 0

    remaining = awards_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.AWARDED_GRANTS)
    ).scalar()
    assert remaining == 1

    listed = repo_svc.list_awarded_grants(connection=awards_db, organization_id=ORG)
    assert listed["archived_count"] == 1
    assert listed["awards"][0]["award_status"] == "mistaken_award"


def test_an_archived_award_obliges_nobody(awards_db):
    award_id = uuid.uuid4()
    repo_svc.create_awarded_grant(
        connection=awards_db, award_id=award_id, now=NOW, **_award()
    )
    repo_svc.archive_awarded_grant(
        connection=awards_db,
        organization_id=ORG,
        award_id=str(award_id),
        award_status="cancelled",
        now=NOW,
    )
    listed = repo_svc.list_awarded_grants(connection=awards_db, organization_id=ORG)
    assert listed["awards"][0]["active_obligation_status"] == "obligations_closed"


def test_a_listing_shows_archived_rows_by_default(awards_db):
    """Hiding one would make a mistake look like an award that never happened."""
    award_id = uuid.uuid4()
    repo_svc.create_awarded_grant(
        connection=awards_db, award_id=award_id, now=NOW, **_award()
    )
    repo_svc.archive_awarded_grant(
        connection=awards_db,
        organization_id=ORG,
        award_id=str(award_id),
        award_status="mistaken_award",
        now=NOW,
    )
    assert (
        repo_svc.list_awarded_grants(connection=awards_db, organization_id=ORG)[
            "rows_read"
        ]
        == 1
    )
    assert (
        repo_svc.list_awarded_grants(
            connection=awards_db, organization_id=ORG, include_archived=False
        )["rows_read"]
        == 0
    )


def test_nothing_in_the_repository_deletes():
    """Gate 123's lesson: parse the module, do not grep it.

    A substring search finds `sa.delete` in the docstring that explains there is
    no delete path, which is the sixth time this campaign has produced a
    substring-versus-meaning false positive.
    """
    source = Path(repo_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"delete", "drop"}
    ]
    assert calls == []
    # And the prose that would trip a substring version is still present, so
    # this test would catch a real delete rather than the explanation of one.
    assert "no DELETE path" in source


def test_mistaken_award_is_a_status_and_not_a_deletion():
    assert "mistaken_award" in award_svc.AWARD_STATUSES
    assert "mistaken_award" not in award_svc.LIVE_AWARD_STATUSES


# ------------------------------------------------- schema parity


def test_the_core_table_matches_the_migration_columns():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.AWARDED_GRANTS.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'name="(ck_nf_awarded_grants_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.AWARDED_GRANTS.constraints
        if c.name and str(c.name).startswith("ck_nf_awarded_grants")
    }
    assert mapped == declared
    assert len(mapped) == 8


def test_the_migration_restates_the_gate_91_and_103_vocabularies_exactly():
    """A CHECK constraint cannot import Python, so a test holds them together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig0032", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.AWARD_STATUSES) == set(award_svc.AWARD_STATUSES)
    assert set(module.FACT_STATUSES) == set(beta_svc.FACT_STATUSES)
    assert set(module.ACTIVE_OBLIGATION_STATUSES) == set(
        val_svc.ACTIVE_OBLIGATION_STATUSES
    )


def test_the_database_refuses_what_the_module_would_have_missed(awards_db):
    """The CHECK constraints, exercised past the service that also refuses."""
    base = dict(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG),
        award_title="Demo Award",
        award_status="active_award",
        active_obligation_status="unknown",
        fact_status="demo_fixture",
        human_review_required=True,
        is_demo=True,
        blocked_reasons=[],
        created_at=NOW,
        updated_at=NOW,
    )
    for values in (
        {
            "active_obligation_status": "obligations_established",
            "fact_status": "unknown",
        },
        {"award_title": "   "},
        {"award_status": "invented_status"},
        {"fact_status": "invented_status"},
        {"award_amount": 1, "award_currency": None},
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with awards_db.begin_nested():
                awards_db.execute(
                    sa.insert(repo_svc.AWARDED_GRANTS).values(
                        **{**base, "id": uuid.uuid4(), **values}
                    )
                )


def test_the_rls_policy_scopes_on_organization_and_demo():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    assert (
        "organization_id = current_setting('app.current_org_id', true)::uuid"
        in migration
    )
    assert (
        "is_demo = current_setting('app.current_org_is_demo', true)::boolean"
        in migration
    )
    for forbidden in ("tenant_id", "customer_org_id", "organization_profile_id"):
        assert f"{forbidden} = current_setting" not in migration


# ------------------------------------------------- vocabularies bridged, not forked


def test_the_award_vocabularies_are_imported_rather_than_restated():
    vocab = repo_svc.repository_vocabularies()
    assert set(vocab["award_statuses"]) == set(award_svc.AWARD_STATUSES)
    assert set(vocab["live_award_statuses"]) == set(award_svc.LIVE_AWARD_STATUSES)
    assert set(vocab["requirements_extraction_statuses"]) == set(
        award_svc.REQUIREMENTS_EXTRACTION_STATUSES
    )
    assert set(vocab["obligation_capable_extraction"]) == set(
        award_svc.OBLIGATION_CAPABLE_EXTRACTION
    )
    assert set(vocab["fact_statuses"]) == set(beta_svc.FACT_STATUSES)
    assert set(vocab["actionable_fact_statuses"]) == set(
        beta_svc.ACTIONABLE_FACT_STATUSES
    )


# ------------------------------------------------- fixtures


def test_the_fixture_set_has_eleven_cases_and_they_all_agree():
    fixture = fixtures.build_awarded_grants_fixture_set()
    assert fixture["case_count"] == 11
    assert fixture["award_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.awarded_grants_fixture_invariant_failures(fixture) == []


def test_no_fixture_permits_a_production_write_or_establishes_an_obligation():
    fixture = fixtures.build_awarded_grants_fixture_set()
    assert fixture["production_write_count"] == 0
    assert fixture["obligations_established_count"] == 0
    assert fixture["production_awarded_grants_created"] == 0
    assert fixture["real_customer_data_written"] == 0
    assert fixture["rows_deleted"] == 0


def test_every_fixture_identifier_is_labelled_as_a_fixture():
    for value in (
        fixtures.DEMO_TENANT_LABEL,
        fixtures.DEMO_CUSTOMER_ORG_LABEL,
        fixtures.DEMO_PURSUIT_ID,
        fixtures.DEMO_OPPORTUNITY_ID,
        fixtures.DEMO_AWARD["award_number"],
        fixtures.DEMO_AWARD["funder_name"],
    ):
        assert value.startswith(fixtures.FIXTURE_PREFIX)
    assert fixtures.DEMO_AWARD["fact_status"] == "demo_fixture"


def test_a_shortened_fixture_set_reports_the_gap():
    """The coverage measure takes its input, so the gap is observable."""
    covered = fixtures.measure_award_cases([{"case": "valid_demo_awarded_grant"}])
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 10


def test_the_fixture_set_reports_the_real_environment_unchanged():
    fixture = fixtures.build_awarded_grants_fixture_set()
    assert fixture["actual_customer_auth_live"] is False
    assert fixture["actual_verified_operational_binding"] is False


# ------------------------------------------------- artifacts


def test_the_artifacts_write_four_files():
    with tempfile.TemporaryDirectory() as root:
        result = art.write_persistence_artifacts(repo_root=root)
        assert result["file_count"] == 4
        assert art.persistence_artifact_invariant_failures(result) == []
        for path in result["files_written"].values():
            assert Path(path).is_file()


def test_the_artifacts_report_storage_built_and_tracking_not_live():
    declaration = art.build_persistence_declaration()
    assert declaration["awarded_grants_storage_available"] is True
    assert declaration["awarded_grants_write_path_available"] is True
    assert declaration["awarded_grants_lane_operational"] is False
    assert declaration["ready_for_operational_awarded_tracking"] is False
    assert declaration["readiness_blocked_reasons"]


def test_the_obligation_scan_refuses_an_unqualified_assertion():
    assert art.scan_for_claimed_obligations(
        {"active_obligation_status": "obligations_established"}
    ) == ["claimed_obligation:active_obligation_status"]
    assert art.scan_for_claimed_obligations({"obligations_established": True}) == [
        "claimed_obligation:obligations_established"
    ]


def test_the_obligation_scan_permits_a_claim_beside_its_refusal():
    """Gate 121's lesson: narrow the scanner, do not drop it."""
    assert (
        art.scan_for_claimed_obligations(
            {
                "active_obligation_status": "obligations_established",
                "obligations_established": False,
            }
        )
        == []
    )


def test_a_real_award_amount_cannot_enter_an_artifact():
    assert "award_amount" in art.FORBIDDEN_VALUE_FIELDS
    assert art.scan_for_credential_fields({"award_amount": "250000.00"}) == [
        "award_amount"
    ]


def test_the_artifact_write_refuses_a_payload_claiming_an_inference(monkeypatch):
    monkeypatch.setattr(
        art, "build_repository_contract", lambda: {"obligations_inferred": True}
    )
    with tempfile.TemporaryDirectory() as root:
        with pytest.raises(ValueError, match="obligations_inferred"):
            art.write_persistence_artifacts(repo_root=root)


# ------------------------------------------------- the capability lane


def test_the_awarded_grants_lane_has_a_write_path_and_is_not_operational():
    lane = cap_svc.build_capability("awarded_grants_persistence")
    assert lane["schema_available"] is True
    assert lane["repository_available"] is True
    assert lane["write_path_available"] is True
    assert lane["operational"] is False
    assert lane["blocked_reasons"] == ["no_customer_auth_so_nobody_owns_the_row"]


def test_every_mapped_contract_module_that_claims_to_exist_does():
    """Gate 124A found two lanes named a module one token from a real service.

    Both reported `no_service_decides_what_may_be_written` while a 432-line and
    a 494-line service decided exactly that. This asserts the two that were
    fixed import, and that the three genuine absences are still absent - so a
    third typo cannot hide as a false negative.
    """
    import importlib.util

    def importable(name):
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False

    present = {
        lane
        for lane, module in cap_svc.CAPABILITY_CONTRACT_MODULES.items()
        if importable(module)
    }
    assert "awarded_grants_persistence" in present
    assert "award_requirements_persistence" in present
    assert present == {
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "identity_binding_persistence",
        "tenant_digest_persistence",
        "tenant_profile_persistence",
    }


def test_the_repository_is_detected_by_import_rather_than_by_filename():
    """Gate 120's defect: a repository built as a service was invisible."""
    assert (
        cap_svc.CAPABILITY_REPOSITORY_MODULES["awarded_grants_persistence"]
        == "nativeforge.services.awarded_grants_repository_service"
    )
    assert not Path("src/nativeforge/repositories/awarded_grants.py").exists()


def test_the_award_requirements_lane_is_untouched_by_this_gate():
    lane = cap_svc.build_capability("award_requirements_persistence")
    assert lane["schema_available"] is False
    assert lane["write_path_available"] is False
    assert lane["operational"] is False


# ------------------------------------------------- the guard


def test_an_awarded_grant_write_needs_a_verified_binding():
    result = guard_svc.evaluate_persistence_write(
        operation="write_awarded_grant", organization_id=ORG
    )
    assert result["write_allowed"] is False
    assert "write_awarded_grant" in guard_svc.LABEL_BOUND_OPERATIONS
    assert any("verified_binding_required" in r for r in result["blocked_reasons"])


def test_the_guard_refuses_a_label_as_a_write_authority():
    result = guard_svc.evaluate_persistence_write(
        operation="write_awarded_grant", tenant_id="tribe-sc-01"
    )
    assert result["write_allowed"] is False
    assert "tenant_id_is_not_a_write_authority" in result["blocked_reasons"]
    assert guard_svc.persistence_guard_invariant_failures(result) == []


# ------------------------------------------------- readiness


def test_readiness_reports_storage_built_and_tracking_still_blocked():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    assert readiness["awarded_grants_storage_available"] is True
    assert readiness["awarded_grants_schema_available"] is True
    assert readiness["awarded_grants_repository_available"] is True
    assert readiness["awarded_grants_write_path_available"] is True
    # And none of that moved the answer that matters.
    assert readiness["customer_persistence_live"] is False
    assert readiness["ready_for_operational_awarded_tracking"] is False
    assert readiness_svc.readiness_invariant_failures(readiness) == []


def test_storage_existing_can_never_be_read_as_persistence_working():
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["customer_persistence_live"] = True
    readiness["awarded_grants_storage_available"] = False
    assert (
        "persistence_live_without_storage"
        in readiness_svc.readiness_invariant_failures(readiness)
    )


def test_the_operational_blockers_are_named_individually():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    assert set(readiness["missing_operational_components"]) == {
        "ui_available",
        "customer_persistence_live",
        "document_storage_live",
        "requirement_extraction_live",
        "verified_operational_identity_binding",
    }


# ------------------------------------------------- liveness


def test_no_row_is_written_to_the_application_database():
    """Everything in this gate runs against a database that lives for one test."""
    for result in (
        repo_svc.prepare_award_write(**_award()),
        repo_svc.create_awarded_grant(**_award()),
    ):
        assert result["rows_written"] == 0
        assert result["production_awarded_grants_created"] == 0
        assert result["real_customer_rows_written"] == 0


def test_nothing_claims_awarded_grants_tracking_is_live():
    fixture = fixtures.build_awarded_grants_fixture_set()
    declaration = art.build_persistence_declaration()
    assert fixture["awarded_grants_operational_tracking_live"] is False
    assert declaration["awarded_grants_operational_tracking_live"] is False
    assert declaration["customer_auth_live"] is False
    assert declaration["login_live"] is False
    assert declaration["beta_onboarding_ready"] is False
    assert declaration["production_rollout_ready"] is False
