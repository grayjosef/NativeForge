"""Gate 125: award requirements persistence.

Somewhere for an award's obligations to live, without inventing an obligation,
a deadline, a filing, an acceptance, or a document.

One thing must stay true: **nothing here tells a Tribe a date they can rely on
unless somebody established it.**

The tests are grouped by what they would catch:

```text
anchor      a relationship treated as an RLS authority
derivation  a boolean named for provenance that reports a declaration
dates       an estimate counted down to
proof       a reference read as a document, or a filing read as an acceptance
lifecycle   a DELETE where an archive belongs
liveness    two tables existing being read as compliance tracking starting
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

from nativeforge.services import award_requirement_model_service as model_svc
from nativeforge.services import (
    award_requirements_persistence_artifact_service as art,
)
from nativeforge.services import (
    award_requirements_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    award_requirements_persistence_validation_service as val_svc,
)
from nativeforge.services import award_requirements_repository_service as repo_svc
from nativeforge.services import (
    awarded_grants_requirements_readiness_service as readiness_svc,
)
from nativeforge.services import customer_persistence_capability_service as cap_svc
from nativeforge.services import (
    customer_persistence_spine_decision_service as spine_svc,
)
from nativeforge.services import (
    org_scoped_customer_persistence_guard_service as guard_svc,
)
from nativeforge.services import tenant_beta_profile_service as beta_svc

ORG = fixtures.DEMO_ORGANIZATION_ID
AWARD = fixtures.DEMO_AWARDED_GRANT_ID
IDENTITY = fixtures.DEMO_IDENTITY_ID
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

MIGRATION = "alembic/versions/0033_nf_award_requirements.py"


@pytest.fixture
def requirements_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.AWARD_REQUIREMENTS.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


def _requirement(**overrides):
    kwargs = dict(fixtures.DEMO_REQUIREMENT)
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- anchor


def test_organization_id_is_the_only_anchor():
    result = repo_svc.prepare_requirement_write(**_requirement())
    assert result["rls_anchor"] == "organization_id"
    assert result["organization_id"] == ORG
    assert repo_svc.award_requirements_repository_invariant_failures(result) == []


def test_a_requirement_without_an_organization_id_is_refused():
    result = repo_svc.prepare_requirement_write(**_requirement(organization_id=None))
    assert result["storage_allowed"] is False
    assert "requirement_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_an_anchor_that_is_not_uuid_shaped_is_refused():
    """The RLS predicate casts to ::uuid. A label would raise, not deny."""
    result = repo_svc.prepare_requirement_write(
        **_requirement(organization_id="tribe-sc-01")
    )
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_awarded_grant_id_is_required():
    result = repo_svc.prepare_requirement_write(**_requirement(awarded_grant_id=None))
    assert result["storage_allowed"] is False
    assert "requirement_without_an_awarded_grant_id" in result["blocked_reasons"]


def test_awarded_grant_id_must_be_uuid_shaped():
    result = repo_svc.prepare_requirement_write(
        **_requirement(awarded_grant_id="award-2026-1")
    )
    assert result["storage_allowed"] is False
    assert "awarded_grant_id_is_not_uuid_shaped" in result["blocked_reasons"]


def test_awarded_grant_id_cannot_substitute_for_organization_id():
    """The substitution this gate is most likely to be asked for."""
    result = repo_svc.prepare_requirement_write(**_requirement(organization_id=None))
    assert result["awarded_grant_id"] == AWARD
    assert result["storage_allowed"] is False
    assert (
        "awarded_grant_id_is_not_an_organization_id_anchor" in result["blocked_reasons"]
    )


def test_awarded_grant_id_is_listed_among_the_forbidden_anchors():
    assert "awarded_grant_id" in repo_svc.FORBIDDEN_ANCHOR_NAMES
    assert repo_svc.ROW_RELATIONSHIP_COLUMN == "awarded_grant_id"
    # Required as a relationship, refused as authority. Both, not one.
    assert repo_svc.AWARD_REQUIREMENTS.c.awarded_grant_id.nullable is False


@pytest.mark.parametrize(
    "label",
    ["tenant_id", "customer_org_id", "organization_profile_id"],
)
def test_a_label_is_refused_as_an_anchor_by_name(label):
    result = repo_svc.prepare_requirement_write(
        **_requirement(), **{label: "nf-demo-fixture-value"}
    )
    assert result["storage_allowed"] is False
    assert f"{label}_is_not_an_organization_id_anchor" in result["blocked_reasons"]


def test_the_requirement_row_carries_no_tenant_label_at_all():
    """A requirement inherits its tenant through the award."""
    columns = {c.name for c in repo_svc.AWARD_REQUIREMENTS.columns}
    assert "tenant_id_label" not in columns
    assert "customer_org_id_label" not in columns


# ------------------------------------------------- derivation, not declaration


def test_the_three_booleans_are_derived_from_provenance_alone():
    expected = {
        "human_entered": (True, False, False),
        "evidence_extracted": (True, False, False),
        "projected_from_nofo": (False, True, False),
        "unsupported_document_type": (False, False, True),
        "unknown": (False, False, False),
        "needs_human_review": (False, False, False),
    }
    assert set(expected) == set(model_svc.EXTRACTION_STATUSES)
    for source, (active, projected, unsupported) in expected.items():
        flags = val_svc.derive_obligation_flags(source)
        assert flags["active_obligation"] is active, source
        assert flags["projected_burden"] is projected, source
        assert flags["unsupported_requirement"] is unsupported, source


def test_the_repository_has_no_parameter_for_any_derived_boolean():
    """The separation expressed as a signature, not as a runtime check."""
    import inspect

    names = set(inspect.signature(repo_svc.prepare_requirement_write).parameters)
    for field in repo_svc.DERIVED_ONLY_FIELDS:
        assert field not in names
    assert set(repo_svc.DERIVED_ONLY_FIELDS) == {
        "active_obligation",
        "projected_burden",
        "unsupported_requirement",
    }


def test_a_projection_is_stored_and_is_not_an_obligation():
    """Gate 91's rule, and the column it would otherwise make unreachable."""
    result = repo_svc.prepare_requirement_write(
        **_requirement(
            requirement_source="projected_from_nofo",
            requirement_due_date=None,
            due_date_status="unknown",
        )
    )
    assert result["storage_allowed"] is True
    assert result["projected_burden"] is True
    assert result["active_obligation"] is False
    assert "projected_burden_is_not_an_active_obligation" in result["refused_claims"]
    # And the refusal is not a storage veto.
    assert (
        "projected_burden_is_not_an_active_obligation"
        not in (result["blocked_reasons"])
    )


def test_an_unsupported_document_is_stored_and_obliges_nobody():
    result = repo_svc.prepare_requirement_write(
        **_requirement(requirement_source="unsupported_document_type")
    )
    assert result["storage_allowed"] is True
    assert result["unsupported_requirement"] is True
    assert result["active_obligation"] is False


def test_a_refused_claim_never_trips_the_services_own_invariants():
    """An invariant ordinary bad input can fire is a validation rule misnamed."""
    for case in (
        {"requirement_source": "projected_from_nofo"},
        {"requirement_source": "unsupported_document_type"},
        {"requirement_source": "invented_source"},
        {"requirement_title": None},
        {"requirement_type": "invented_type"},
        {"due_date_status": "estimated"},
        {"due_date_status": "invented"},
        {"proof_status": "proof_accepted"},
        {"accepted_at": NOW},
        {"fact_status": "invented"},
        {"fact_status": "unknown"},
        {"submission_status": "invented"},
        {"recurrence_rule": "fortnightly"},
    ):
        result = val_svc.validate_award_requirement(
            **{
                "requirement_title": "Quarterly report",
                "requirement_type": "financial_report",
                "requirement_source": "human_entered",
                "fact_status": "demo_fixture",
                **case,
            }
        )
        assert val_svc.validation_invariant_failures(result) == [], case


def test_every_invariant_reads_a_derived_value_rather_than_an_echoed_input():
    """The structural rule Gate 125 adopted after Gate 124D's three failures."""
    source = Path(val_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "validation_invariant_failures"
    )
    read = {
        node.args[0].value
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    # These come straight from the caller and must never be asserted about.
    for echoed in (
        "proof_status",
        "submission_status",
        "submitted",
        "accepted",
        "rejected",
        "requirement_due_date",
        "proof_document_ref",
    ):
        assert echoed not in read, echoed
    # And the derived replacements are present.
    assert "proof_is_accepted" in read
    assert "acceptance_recorded" in read
    assert "date_is_calculable" in read


def test_the_permitted_branch_is_reachable():
    """Gates 117-124 each shipped an invariant whose True branch was not."""
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly federal financial report",
        requirement_type="financial_report",
        requirement_status="not_started",
        requirement_source="human_entered",
        requirement_due_date="2026-04-30",
        due_date_status="verified",
        recurrence_rule="quarterly",
        proof_status="not_submitted",
        submission_status="not_submitted",
        fact_status="verified",
    )
    assert result["requirement_ready_for_calendar"] is True
    assert result["human_review_required"] is False
    assert val_svc.validation_invariant_failures(result) == []


# ------------------------------------------------- dates


def test_an_unknown_due_date_requires_human_review():
    result = repo_svc.prepare_requirement_write(
        **_requirement(requirement_due_date=None, due_date_status="unknown")
    )
    assert result["storage_allowed"] is True
    assert result["human_review_required"] is True
    assert result["date_is_calculable"] is False


def test_an_estimated_due_date_is_not_treated_as_known():
    result = repo_svc.prepare_requirement_write(
        **_requirement(due_date_status="estimated")
    )
    assert result["storage_allowed"] is True
    assert result["due_date_status"] == "estimated"
    # Stored, shown, and never counted down to.
    assert result["date_is_calculable"] is False
    assert result["human_review_required"] is True
    assert "estimated" not in model_svc.DATE_CALCULABLE_STATUSES


def test_an_unreadable_documents_date_is_downgraded_before_it_is_counted():
    """Statement order defeated this once: the downgrade must come first."""
    result = val_svc.validate_award_requirement(
        requirement_title="Requirement from an unreadable packet",
        requirement_type="financial_report",
        requirement_source="unsupported_document_type",
        requirement_due_date="2026-04-30",
        due_date_status="verified",
        fact_status="demo_fixture",
    )
    assert result["due_date_status"] == "unsupported"
    assert result["date_is_calculable"] is False
    assert "unsupported_document_claimed_a_supported_date" in result["refused_claims"]
    assert val_svc.validation_invariant_failures(result) == []


def test_a_calculable_status_without_a_date_is_refused():
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        due_date_status="verified",
        fact_status="demo_fixture",
    )
    assert "due_date_status_claims_support_without_a_date" in result["blocked_reasons"]


def test_nothing_derives_a_due_date_from_a_recurrence_rule():
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        recurrence_rule="quarterly",
        due_date_status="unknown",
        fact_status="demo_fixture",
    )
    assert result["recurrence_rule"] == "quarterly"
    assert result["requirement_due_date"] is None
    assert result["due_date_inferred_from_recurrence"] is False
    assert result["due_date_inferred"] is False


# ------------------------------------------------- proof


def test_a_document_reference_does_not_imply_a_document_store():
    result = repo_svc.prepare_requirement_write(
        **_requirement(proof_document_ref="nf-demo-fixture-sf425.pdf")
    )
    assert result["storage_allowed"] is False
    assert (
        "proof_document_reference_without_a_document_store" in result["blocked_reasons"]
    )
    assert result["document_storage_available"] is False


def test_the_document_store_refusal_is_falsifiable():
    """Injectable, so the refusal is a measurement rather than a constant."""
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        proof_document_ref="nf-demo-fixture-sf425.pdf",
        fact_status="demo_fixture",
        document_storage_available=True,
    )
    assert result["blocked_reasons"] == []
    assert result["document_reference_not_storage"] is False


def test_a_submitted_proof_does_not_imply_an_accepted_proof():
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        requirement_status="submitted",
        submission_status="submitted",
        submitted_at=NOW,
        proof_status="proof_missing",
        fact_status="demo_fixture",
    )
    assert result["submitted"] is True
    assert result["proof_is_accepted"] is False
    assert result["acceptance_recorded"] is False
    assert result["acceptance_inferred_from_submission"] is False


def test_an_acceptance_cannot_precede_its_submission():
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        accepted_at=NOW,
        fact_status="demo_fixture",
    )
    assert "accepted_without_having_been_submitted" in result["blocked_reasons"]


def test_an_accepted_proof_needs_a_reference():
    result = val_svc.validate_award_requirement(
        requirement_title="Quarterly report",
        requirement_type="financial_report",
        requirement_source="human_entered",
        proof_status="proof_accepted",
        fact_status="demo_fixture",
    )
    assert result["proof_is_accepted"] is False
    assert "proof_accepted_without_a_document_reference" in result["blocked_reasons"]


# ------------------------------------------------- lifecycle


def test_a_row_is_written_and_read_back(requirements_db):
    requirement_id = uuid.uuid4()
    created = repo_svc.create_award_requirement(
        connection=requirements_db,
        requirement_id=requirement_id,
        now=NOW,
        **_requirement(),
    )
    assert created["rows_written"] == 1
    read = repo_svc.get_award_requirement(
        connection=requirements_db,
        organization_id=ORG,
        requirement_id=str(requirement_id),
    )
    assert read["rows_read"] == 1
    assert read["requirement_title"] == fixtures.DEMO_REQUIREMENT["requirement_title"]
    assert read["awarded_grant_id"] == AWARD
    assert repo_svc.award_requirements_repository_invariant_failures(read) == []


def test_a_read_is_scoped_to_one_organization(requirements_db):
    repo_svc.create_award_requirement(
        connection=requirements_db, now=NOW, **_requirement()
    )
    other = repo_svc.get_award_requirement(
        connection=requirements_db, organization_id=str(uuid.uuid4())
    )
    assert other["rows_read"] == 0
    assert "no_award_requirement_for_this_organization" in other["blocked_reasons"]


def test_listing_for_an_award_still_needs_the_organization(requirements_db):
    repo_svc.create_award_requirement(
        connection=requirements_db, now=NOW, **_requirement()
    )
    # The award narrows; it does not scope.
    scoped = repo_svc.list_requirements_for_award(
        connection=requirements_db, organization_id=ORG, awarded_grant_id=AWARD
    )
    assert scoped["rows_read"] == 1
    unscoped = repo_svc.list_requirements_for_award(
        connection=requirements_db,
        organization_id=str(uuid.uuid4()),
        awarded_grant_id=AWARD,
    )
    assert unscoped["rows_read"] == 0


def test_listing_for_an_award_without_an_award_is_refused(requirements_db):
    result = repo_svc.list_requirements_for_award(
        connection=requirements_db, organization_id=ORG
    )
    assert result["rows_read"] == 0
    assert (
        "listing_for_an_award_without_an_awarded_grant_id" in result["blocked_reasons"]
    )


def test_the_organization_listing_spans_awards(requirements_db):
    other_award = str(uuid.uuid4())
    repo_svc.create_award_requirement(
        connection=requirements_db, now=NOW, **_requirement()
    )
    repo_svc.create_award_requirement(
        connection=requirements_db,
        now=NOW,
        **_requirement(
            awarded_grant_id=other_award,
            requirement_title="Annual performance report",
        ),
    )
    listed = repo_svc.list_requirements_for_organization(
        connection=requirements_db, organization_id=ORG
    )
    assert listed["rows_read"] == 2
    for_one = repo_svc.list_requirements_for_award(
        connection=requirements_db, organization_id=ORG, awarded_grant_id=AWARD
    )
    assert for_one["rows_read"] == 1


def test_archiving_retains_the_row(requirements_db):
    requirement_id = uuid.uuid4()
    repo_svc.create_award_requirement(
        connection=requirements_db,
        requirement_id=requirement_id,
        now=NOW,
        **_requirement(),
    )
    archived = repo_svc.archive_award_requirement(
        connection=requirements_db,
        organization_id=ORG,
        requirement_id=str(requirement_id),
        archived_by_identity_id=IDENTITY,
        requirement_status="not_applicable",
        now=NOW,
    )
    assert archived["rows_written"] == 1
    assert archived["rows_deleted"] == 0

    remaining = requirements_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.AWARD_REQUIREMENTS)
    ).scalar()
    assert remaining == 1

    listed = repo_svc.list_requirements_for_organization(
        connection=requirements_db, organization_id=ORG
    )
    assert listed["archived_count"] == 1
    assert listed["requirements"][0]["requirement_status"] == "not_applicable"


def test_an_archived_requirement_obliges_nobody(requirements_db):
    requirement_id = uuid.uuid4()
    repo_svc.create_award_requirement(
        connection=requirements_db,
        requirement_id=requirement_id,
        now=NOW,
        **_requirement(),
    )
    before = repo_svc.list_requirements_for_organization(
        connection=requirements_db, organization_id=ORG
    )
    assert before["active_obligation_count"] == 1

    repo_svc.archive_award_requirement(
        connection=requirements_db,
        organization_id=ORG,
        requirement_id=str(requirement_id),
        requirement_status="waived",
        now=NOW,
    )
    after = repo_svc.list_requirements_for_organization(
        connection=requirements_db, organization_id=ORG
    )
    assert after["active_obligation_count"] == 0
    # The provenance stays; the obligation does not.
    assert after["requirements"][0]["requirement_source"] == "human_entered"


def test_nothing_in_the_repository_deletes():
    """Gate 123's lesson: parse the module, do not grep it."""
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
    # And the prose that would trip a substring version is still present.
    assert "no DELETE path" in source


# ------------------------------------------------- production write gates


def test_a_production_write_is_reachable_and_needs_both_gates():
    settled = _requirement(fact_status="verified", is_demo=False)
    assert (
        repo_svc.prepare_requirement_write(
            **settled, customer_auth_live=True, verified_operational_binding=True
        )["production_write_allowed"]
        is True
    )
    for kwargs, reason in (
        (
            {"customer_auth_live": False, "verified_operational_binding": True},
            "production_requirement_write_requires_live_customer_auth",
        ),
        (
            {"customer_auth_live": True, "verified_operational_binding": False},
            "production_requirement_write_requires_a_verified_operational_binding",
        ),
    ):
        result = repo_svc.prepare_requirement_write(**settled, **kwargs)
        assert result["production_write_allowed"] is False
        assert reason in result["blocked_reasons"]


def test_both_gates_are_false_in_this_repository():
    result = repo_svc.prepare_requirement_write(
        **_requirement(fact_status="verified", is_demo=False)
    )
    assert result["production_write_allowed"] is False
    assert set(result["blocked_reasons"]) == {
        "production_requirement_write_requires_live_customer_auth",
        "production_requirement_write_requires_a_verified_operational_binding",
    }


def test_a_requirement_write_needs_a_verified_binding():
    assert "write_award_requirement" in guard_svc.LABEL_BOUND_OPERATIONS
    result = guard_svc.evaluate_persistence_write(
        operation="write_award_requirement",
        organization_id=ORG,
        persistence_capability=cap_svc.build_capability(
            "award_requirements_persistence", customer_auth_live=True
        ),
    )
    assert result["write_allowed"] is False
    assert any("verified_binding_required" in r for r in result["blocked_reasons"])
    assert guard_svc.persistence_guard_invariant_failures(result) == []


# ------------------------------------------------- schema parity


def test_the_core_table_matches_the_migration_columns():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.AWARD_REQUIREMENTS.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'name="(ck_nf_award_requirements_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.AWARD_REQUIREMENTS.constraints
        if c.name and str(c.name).startswith("ck_nf_award_requirements")
    }
    assert mapped == declared
    assert len(mapped) == 19


def test_the_migration_restates_the_gate_108_vocabularies_exactly():
    """A CHECK constraint cannot import Python, so a test holds them together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig0033", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.REQUIREMENT_TYPES) == set(model_svc.REQUIREMENT_TYPES)
    assert set(module.REQUIREMENT_STATUSES) == set(model_svc.REQUIREMENT_STATUSES)
    assert set(module.REQUIREMENT_SOURCES) == set(model_svc.EXTRACTION_STATUSES)
    assert set(module.ACTIVE_CAPABLE_SOURCES) == set(
        model_svc.ACTIVE_CAPABLE_EXTRACTION_STATUSES
    )
    assert set(module.DUE_DATE_STATUSES) == set(model_svc.DUE_DATE_STATUSES)
    assert set(module.DATE_CALCULABLE_STATUSES) == set(
        model_svc.DATE_CALCULABLE_STATUSES
    )
    assert set(module.PROOF_STATUSES) == set(model_svc.PROOF_STATUSES)
    assert set(module.RECURRENCES) == set(model_svc.RECURRENCES)
    assert set(module.SUBMISSION_STATUSES) == set(val_svc.SUBMISSION_STATUSES)
    assert set(module.FACT_STATUSES) == set(beta_svc.FACT_STATUSES)


def test_the_database_refuses_what_the_module_would_have_missed(requirements_db):
    """The CHECK constraints, exercised past the service that also refuses."""
    base = dict(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG),
        awarded_grant_id=uuid.UUID(AWARD),
        requirement_type="financial_report",
        requirement_title="Quarterly report",
        requirement_status="not_started",
        requirement_source="human_entered",
        requirement_due_date=None,
        due_date_status="estimated",
        recurrence_rule="quarterly",
        proof_required=False,
        proof_status="not_submitted",
        submission_status="not_submitted",
        active_obligation=True,
        projected_burden=False,
        unsupported_requirement=False,
        fact_status="demo_fixture",
        human_review_required=True,
        is_demo=True,
        blocked_reasons=[],
        created_at=NOW,
        updated_at=NOW,
    )
    for values in (
        {"projected_burden": True, "requirement_source": "projected_from_nofo"},
        {"projected_burden": True},
        {"unsupported_requirement": True},
        {
            "requirement_source": "unsupported_document_type",
            "unsupported_requirement": True,
            "active_obligation": True,
        },
        {"requirement_title": "   "},
        {"due_date_status": "verified"},
        {"requirement_due_date": NOW.date(), "due_date_status": "unknown"},
        {"accepted_at": NOW},
        {"proof_status": "proof_accepted"},
        {"fact_status": "unknown"},
        {"requirement_source": "invented_source"},
        {"requirement_type": "invented_type"},
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with requirements_db.begin_nested():
                requirements_db.execute(
                    sa.insert(repo_svc.AWARD_REQUIREMENTS).values(
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
    for forbidden in (
        "tenant_id",
        "customer_org_id",
        "organization_profile_id",
        "awarded_grant_id",
    ):
        assert f"{forbidden} = current_setting" not in migration


def test_the_vocabularies_are_imported_rather_than_restated():
    vocab = repo_svc.repository_vocabularies()
    assert set(vocab["requirement_types"]) == set(model_svc.REQUIREMENT_TYPES)
    assert set(vocab["requirement_sources"]) == set(model_svc.EXTRACTION_STATUSES)
    assert set(vocab["active_capable_sources"]) == set(
        model_svc.ACTIVE_CAPABLE_EXTRACTION_STATUSES
    )
    assert set(vocab["due_date_statuses"]) == set(model_svc.DUE_DATE_STATUSES)
    assert set(vocab["date_calculable_statuses"]) == set(
        model_svc.DATE_CALCULABLE_STATUSES
    )
    assert set(vocab["proof_statuses"]) == set(model_svc.PROOF_STATUSES)
    assert set(vocab["fact_statuses"]) == set(beta_svc.FACT_STATUSES)


# ------------------------------------------------- fixtures


def test_the_fixture_set_has_fourteen_cases_and_they_all_agree():
    fixture = fixtures.build_award_requirements_fixture_set()
    assert fixture["case_count"] == 14
    assert fixture["requirement_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.award_requirements_fixture_invariant_failures(fixture) == []


def test_no_fixture_permits_a_production_write_or_a_proof_record():
    fixture = fixtures.build_award_requirements_fixture_set()
    assert fixture["production_write_count"] == 0
    assert fixture["production_award_requirements_created"] == 0
    assert fixture["production_proof_records_created"] == 0
    assert fixture["real_customer_data_written"] == 0
    assert fixture["rows_deleted"] == 0
    assert fixture["document_storage_available"] is False
    # `proof_audit_persistence_available` was asserted here and Gate 126 built
    # the store. A fixture set states what it did; the state of a neighbouring
    # lane is readiness's question, and this file asking it made the claim go
    # stale the moment the lane moved.
    assert "proof_audit_persistence_available" not in fixture


def test_every_fixture_identifier_is_labelled_as_a_fixture():
    for value in (
        fixtures.DEMO_TENANT_LABEL,
        fixtures.DEMO_CUSTOMER_ORG_LABEL,
        fixtures.DEMO_PROFILE_ID_LABEL,
        fixtures.DEMO_SOURCE_REF,
        fixtures.DEMO_DOCUMENT_REF,
    ):
        assert value.startswith(fixtures.FIXTURE_PREFIX)
    assert fixtures.DEMO_REQUIREMENT["fact_status"] == "demo_fixture"


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_requirement_cases(
        [{"case": "valid_demo_active_reporting_requirement"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 13


def test_the_fixture_set_reports_the_real_environment_unchanged():
    fixture = fixtures.build_award_requirements_fixture_set()
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


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        art.write_persistence_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            committed = (repo_root / art.ARTIFACT_DIR / path.name).read_text(
                encoding="utf-8"
            )
            assert fresh == committed, f"stale artifact: {path.name}"


def test_the_artifacts_report_both_lanes_built_and_tracking_not_live():
    declaration = art.build_persistence_declaration()
    assert declaration["award_requirements_storage_available"] is True
    assert declaration["awarded_tracking_storage_available"] is True
    assert declaration["award_requirements_write_path_available"] is True
    assert declaration["award_requirements_operational"] is False
    assert declaration["ready_for_operational_awarded_tracking"] is False
    assert declaration["operational_awarded_recommended"] is False
    assert declaration["readiness_blocked_reasons"]


def test_the_obligation_scan_refuses_an_unsupported_claim():
    assert art.scan_for_claimed_obligations(
        {"active_obligation": True, "requirement_source": "projected_from_nofo"}
    ) == ["claimed_obligation:from_source:projected_from_nofo"]
    assert art.scan_for_claimed_obligations(
        {
            "active_obligation": True,
            "requirement_source": "human_entered",
            "projected_burden": True,
        }
    ) == ["claimed_obligation:while_projected"]


def test_the_obligation_scan_permits_a_supported_claim():
    assert (
        art.scan_for_claimed_obligations(
            {"active_obligation": True, "requirement_source": "human_entered"}
        )
        == []
    )


def test_the_countdown_scan_refuses_an_estimate():
    assert art.scan_for_claimed_obligations(
        {"date_is_calculable": True, "due_date_is_estimate_only": True}
    ) == ["claimed_countdown:on_an_estimate"]
    assert art.scan_for_claimed_obligations(
        {"date_is_calculable": True, "unsupported_requirement": True}
    ) == ["claimed_countdown:on_an_unreadable_document"]


def test_the_capability_scan_refuses_a_store_this_gate_did_not_build():
    """Two sets now, because the scan answers two questions.

    `document_storage_available` this gate can state flatly: there is no store.
    `proof_audit_persistence_available` was frozen here as False and Gate 126
    built it, so the scan measures that one - and refuses denying an available
    capability as well as claiming an unavailable one.
    """
    assert art.scan_for_claimed_capabilities({"document_storage_available": True}) == [
        "claimed_capability:document_storage_available"
    ]
    assert (
        art.scan_for_claimed_capabilities({"proof_audit_persistence_available": True})
        == []
    )
    assert art.scan_for_claimed_capabilities(
        {"proof_audit_persistence_available": False}
    ) == ["capability_claim_disagrees_with_reality:proof_audit_persistence_available"]


def test_the_artifact_write_refuses_a_payload_claiming_a_document_store(monkeypatch):
    monkeypatch.setattr(
        art,
        "build_repository_contract",
        lambda: {"document_storage_available": True},
    )
    with tempfile.TemporaryDirectory() as root:
        with pytest.raises(ValueError, match="document_storage_available"):
            art.write_persistence_artifacts(repo_root=root)


# ------------------------------------------------- the capability lane


def test_the_award_requirements_lane_has_a_write_path_and_is_not_operational():
    lane = cap_svc.build_capability("award_requirements_persistence")
    assert lane["schema_available"] is True
    assert lane["repository_available"] is True
    assert lane["write_path_available"] is True
    assert lane["operational"] is False
    assert lane["blocked_reasons"] == ["no_customer_auth_so_nobody_owns_the_row"]


def test_the_repository_is_detected_by_import_rather_than_by_filename():
    """Gate 120's defect: a repository built as a service was invisible."""
    assert (
        cap_svc.CAPABILITY_REPOSITORY_MODULES["award_requirements_persistence"]
        == "nativeforge.services.award_requirements_repository_service"
    )
    assert not Path("src/nativeforge/repositories/award_requirements.py").exists()


def test_a_repository_does_not_make_customer_persistence_live():
    matrix = cap_svc.build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    assert all(not row["operational"] for row in matrix["rows"])


# ------------------------------------------------- the spine


def test_capability_operational_is_not_the_same_as_ready_to_operate():
    """Gate 125's defect: the recommendation contradicted its own invariant.

    With auth forged, both awarded lanes report `operational` - schema, anchor,
    RLS, repository, contract and auth are all present. Neither is ready to
    operate: award_requirements lists document_storage as a prerequisite and
    there is no document store.
    """
    decision = spine_svc.build_persistence_spine_decision(
        capability_matrix=cap_svc.build_capability_matrix(customer_auth_live=True),
        preconditions={
            "customer_auth": True,
            "document_storage": False,
            "email_delivery": False,
            "live_source_collection": False,
        },
    )
    by_name = {e["capability"]: e for e in decision["recommended_sequence"]}
    assert by_name["awarded_grants_persistence"]["operational"] is True
    assert by_name["award_requirements_persistence"]["operational"] is True
    assert by_name["award_requirements_persistence"]["unmet_prerequisites"] == [
        "document_storage"
    ]
    # Operable, and not yet due.
    assert (
        by_name["award_requirements_persistence"]["operational_out_of_sequence"] is True
    )
    assert decision["operational_awarded_recommended"] is False
    assert spine_svc.spine_decision_invariant_failures(decision) == []


def test_the_spine_still_recommends_customer_authentication():
    decision = spine_svc.build_persistence_spine_decision()
    assert (
        decision["next_gate_recommendation"]["recommendation"]
        == "customer_authentication"
    )
    assert decision["operational_awarded_recommended"] is False
    assert decision["customer_persistence_live"] is False


def test_award_requirements_left_the_requires_migrations_set():
    decision = spine_svc.build_persistence_spine_decision()
    assert "award_requirements_persistence" not in decision["requires_migrations"]
    assert "awarded_grants_persistence" not in decision["requires_migrations"]


# ------------------------------------------------- readiness


def test_readiness_reports_both_lanes_built_and_tracking_still_blocked():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    for key in readiness_svc.STORAGE_COMPONENT_KEYS:
        assert readiness[key] is True, key
    assert readiness["award_requirements_storage_available"] is True
    assert readiness["awarded_tracking_storage_available"] is True
    # And none of that moved the answer that matters.
    assert readiness["customer_persistence_live"] is False
    assert readiness["ready_for_operational_awarded_tracking"] is False
    assert readiness_svc.readiness_invariant_failures(readiness) == []


def test_document_storage_remains_false_and_proof_audit_moved():
    """Gate 125 measured this rather than asserting it, and it moved.

    `proof_audit_persistence_available` was built by Gate 126, which is exactly
    what a measured flag is for: this test records the move rather than pinning
    a value that a later gate has to come back and edit. Document storage is
    still absent and still measured the same way.
    """
    readiness = readiness_svc.build_awarded_requirements_readiness()
    assert readiness["document_storage_live"] is False
    assert readiness["proof_audit_contract_available"] is True
    # Built by Gate 126. The flag followed on its own, which is the point.
    assert readiness["proof_audit_persistence_available"] is True


def test_storage_for_both_lanes_can_never_read_as_tracking():
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["awarded_tracking_storage_available"] = True
    readiness["award_requirements_storage_available"] = False
    assert (
        "tracking_storage_claimed_without_both_lanes"
        in readiness_svc.readiness_invariant_failures(readiness)
    )


def test_operational_tracking_cannot_be_claimed_without_proof_audit_persistence():
    """Both halves forged, because Gate 126 made the second one true.

    The invariant fires when tracking is claimed while proof audit persistence
    is absent. Gate 126 built the store, so the absence has to be forged too -
    otherwise this test would pass for the wrong reason and stop guarding
    anything.
    """
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["ready_for_operational_awarded_tracking"] = True
    readiness["proof_audit_persistence_available"] = False
    assert (
        "operational_tracking_claimed_without_proof_audit_persistence"
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
    for result in (
        repo_svc.prepare_requirement_write(**_requirement()),
        repo_svc.create_award_requirement(**_requirement()),
    ):
        assert result["rows_written"] == 0
        assert result["production_award_requirements_created"] == 0
        assert result["production_proof_records_created"] == 0
        assert result["real_customer_rows_written"] == 0


def test_nothing_claims_awarded_tracking_is_live():
    fixture = fixtures.build_award_requirements_fixture_set()
    declaration = art.build_persistence_declaration()
    assert fixture["awarded_grants_operational_tracking_live"] is False
    assert declaration["awarded_grants_operational_tracking_ready"] is False
    assert declaration["customer_auth_live"] is False
    assert declaration["login_live"] is False
    assert declaration["customer_persistence_live"] is False
    assert declaration["beta_onboarding_ready"] is False
    assert declaration["production_rollout_ready"] is False


def test_no_api_route_serves_a_requirement():
    """Gate 125F: skipped, and the survey records why."""
    assert not Path("src/nativeforge/api/award_requirements.py").exists()
    survey = Path(
        "docs/operations/672_GATE125_AWARD_REQUIREMENTS_PERSISTENCE_SURVEY.md"
    ).read_text(encoding="utf-8")
    assert "## 10. No API route" in survey
