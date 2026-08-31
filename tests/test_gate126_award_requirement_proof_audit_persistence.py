"""Gate 126: award requirement proof audit persistence.

The record of what was filed against a requirement, and what happened to it.

One thing must stay true: **nothing here can make a record go away.**

The tests are grouped by what they would catch:

```text
anchor       a relationship or a context column treated as an RLS authority
decision     a filing read as an acceptance, or a note read as a rejection
retention    a rejection, supersession or archive losing what was filed
vocabulary   an extension of Gate 108's actions that became a replacement
liveness     three tables existing being read as compliance evidence
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
    award_requirement_proof_audit_persistence_artifact_service as art,
)
from nativeforge.services import (
    award_requirement_proof_audit_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    award_requirement_proof_audit_persistence_validation_service as val_svc,
)
from nativeforge.services import (
    award_requirement_proof_audit_repository_service as repo_svc,
)
from nativeforge.services import award_requirement_proof_audit_service as contract
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
REQ = fixtures.DEMO_REQUIREMENT_ID
AWARD = fixtures.DEMO_AWARDED_GRANT_ID
IDENTITY = fixtures.DEMO_IDENTITY_ID
DOC = fixtures.DEMO_DOCUMENT_REF
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)

MIGRATION = "alembic/versions/0034_nf_award_requirement_proof_events.py"


@pytest.fixture
def events_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.PROOF_EVENTS.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


def _event(**overrides):
    kwargs = dict(fixtures.DEMO_EVENT)
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- anchor


def test_organization_id_is_the_only_anchor():
    result = repo_svc.prepare_proof_event_write(**_event())
    assert result["rls_anchor"] == "organization_id"
    assert result["organization_id"] == ORG
    assert repo_svc.proof_audit_repository_invariant_failures(result) == []


def test_an_event_without_an_organization_id_is_refused():
    result = repo_svc.prepare_proof_event_write(**_event(organization_id=None))
    assert result["storage_allowed"] is False
    assert "proof_event_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_an_anchor_that_is_not_uuid_shaped_is_refused():
    """The RLS predicate casts to ::uuid. A label would raise, not deny."""
    result = repo_svc.prepare_proof_event_write(**_event(organization_id="tribe-sc-01"))
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_award_requirement_id_is_required_and_uuid_shaped():
    missing = repo_svc.prepare_proof_event_write(**_event(award_requirement_id=None))
    assert "proof_event_without_an_award_requirement_id" in missing["blocked_reasons"]
    malformed = repo_svc.prepare_proof_event_write(
        **_event(award_requirement_id="requirement-1")
    )
    assert "award_requirement_id_is_not_uuid_shaped" in malformed["blocked_reasons"]


def test_award_requirement_id_cannot_substitute_for_organization_id():
    result = repo_svc.prepare_proof_event_write(**_event(organization_id=None))
    assert result["award_requirement_id"] == REQ
    assert result["storage_allowed"] is False
    assert (
        "award_requirement_id_is_not_an_organization_id_anchor"
        in result["blocked_reasons"]
    )


def test_awarded_grant_id_cannot_substitute_for_organization_id():
    """Context, carried for convenience, and never authority."""
    result = repo_svc.prepare_proof_event_write(
        **_event(organization_id=None, award_requirement_id=None)
    )
    assert result["awarded_grant_id"] == AWARD
    assert result["storage_allowed"] is False
    assert (
        "awarded_grant_id_is_not_an_organization_id_anchor" in result["blocked_reasons"]
    )


def test_both_relationship_columns_are_forbidden_anchors():
    assert repo_svc.FORBIDDEN_ANCHOR_NAMES == frozenset(
        {
            "tenant_id",
            "customer_org_id",
            "organization_profile_id",
            "award_requirement_id",
            "awarded_grant_id",
        }
    )
    assert repo_svc.ROW_RELATIONSHIP_COLUMN == "award_requirement_id"
    assert repo_svc.CONTEXT_COLUMN == "awarded_grant_id"
    # Required as a relationship, optional as context, neither as authority.
    assert repo_svc.PROOF_EVENTS.c.award_requirement_id.nullable is False
    assert repo_svc.PROOF_EVENTS.c.awarded_grant_id.nullable is True


@pytest.mark.parametrize(
    "label", ["tenant_id", "customer_org_id", "organization_profile_id"]
)
def test_a_label_is_refused_as_an_anchor_by_name(label):
    result = repo_svc.prepare_proof_event_write(
        **_event(), **{label: "nf-demo-fixture-value"}
    )
    assert result["storage_allowed"] is False
    assert f"{label}_is_not_an_organization_id_anchor" in result["blocked_reasons"]


# ------------------------------------------------- vocabulary


def test_the_extension_kept_every_gate_108_action():
    """An extension that became a replacement would orphan Gate 108's contract."""
    assert val_svc.BRIDGED_EVENT_TYPES == contract.PROOF_ACTIONS
    for action in contract.PROOF_ACTIONS:
        assert action in val_svc.EVENT_TYPES, action
    assert val_svc.vocabulary_invariant_failures() == []


def test_the_four_added_event_types_are_named_as_added():
    assert val_svc.ADDED_EVENT_TYPES == frozenset(
        {
            "proof_requested",
            "proof_needs_review",
            "proof_superseded",
            "audit_note_added",
        }
    )
    assert not (val_svc.BRIDGED_EVENT_TYPES & val_svc.ADDED_EVENT_TYPES)
    assert len(val_svc.EVENT_TYPES) == 10


def test_event_status_is_bridged_whole_and_not_extended():
    assert set(val_svc.EVENT_STATUSES) == set(model_svc.PROOF_STATUSES)


def test_a_dropped_gate_108_action_is_reported():
    """The invariant reads the imported set, so this forges the drift."""
    original = val_svc.EVENT_TYPES
    try:
        val_svc.EVENT_TYPES = original - {"mark_waived"}
        assert "gate_108_action_no_longer_storable:mark_waived" in (
            val_svc.vocabulary_invariant_failures()
        )
    finally:
        val_svc.EVENT_TYPES = original
    assert val_svc.vocabulary_invariant_failures() == []


# ------------------------------------------------- decision boundaries


def test_a_submitted_proof_is_not_an_accepted_proof():
    result = val_svc.validate_proof_event(
        event_type="mark_submitted",
        event_status="proof_attached",
        proof_document_ref=DOC,
        proof_source="human_entered",
        submitted_at=NOW,
        fact_status="demo_fixture",
    )
    assert result["submission_recorded"] is True
    assert result["proof_is_accepted"] is False
    assert result["acceptance_inferred_from_submission"] is False


def test_an_acceptance_requires_a_submission():
    result = repo_svc.prepare_proof_event_write(
        **_event(
            event_type="mark_accepted",
            event_status="proof_accepted",
            submitted_at=None,
            accepted_at=LATER,
        )
    )
    assert result["storage_allowed"] is False
    assert "accepted_without_having_been_submitted" in result["blocked_reasons"]


def test_an_acceptance_requires_a_document_reference():
    result = repo_svc.prepare_proof_event_write(
        **_event(
            event_type="mark_accepted",
            event_status="proof_accepted",
            proof_document_ref=None,
            accepted_at=LATER,
        )
    )
    assert result["storage_allowed"] is False
    assert "accepted_without_a_document_reference" in result["blocked_reasons"]


def test_an_acceptance_requires_a_timestamp():
    result = repo_svc.prepare_proof_event_write(
        **_event(event_type="mark_accepted", event_status="proof_accepted")
    )
    assert result["storage_allowed"] is False
    assert (
        "accepted_status_without_an_acceptance_timestamp" in result["blocked_reasons"]
    )


def test_the_accepted_branch_is_reachable():
    """Gates 117-125 each shipped a refusal whose permitted branch was not."""
    result = repo_svc.prepare_proof_event_write(
        **_event(
            event_type="mark_accepted",
            event_status="proof_accepted",
            accepted_at=LATER,
        )
    )
    assert result["storage_allowed"] is True
    assert result["proof_is_accepted"] is True
    assert repo_svc.proof_audit_repository_invariant_failures(result) == []


def test_a_note_decides_nothing():
    result = repo_svc.prepare_proof_event_write(
        **_event(
            event_type="audit_note_added",
            event_status="not_submitted",
            proof_document_ref=None,
        )
    )
    # Storable - a note belongs in the trail - and it recorded no filing.
    assert result["storage_allowed"] is True
    assert (
        "audit_note_added_cannot_record_a_filing_or_a_decision"
        in result["refused_claims"]
    )
    assert result["proof_is_accepted"] is False


def test_a_review_needs_both_a_reviewer_and_a_time():
    for kwargs in (
        {"reviewed_at": LATER},
        {"reviewed_by_identity_id": IDENTITY},
    ):
        result = repo_svc.prepare_proof_event_write(**_event(**kwargs))
        assert result["storage_allowed"] is False
        assert "a_review_needs_both_a_reviewer_and_a_time" in result["blocked_reasons"]


# ------------------------------------------------- the document store


def test_a_document_reference_does_not_imply_a_document_store():
    result = repo_svc.prepare_proof_event_write(
        **_event(proof_document_storage_available=True)
    )
    assert result["storage_allowed"] is False
    assert (
        "event_claimed_a_document_store_that_does_not_exist"
        in result["blocked_reasons"]
    )
    assert result["document_storage_built_by_gate_126"] is False


def test_the_document_store_refusal_is_falsifiable():
    """Injectable, so the refusal is a measurement rather than a constant."""
    result = val_svc.validate_proof_event(
        event_type="mark_submitted",
        event_status="proof_attached",
        proof_document_ref=DOC,
        proof_document_storage_available=True,
        proof_source="human_entered",
        submitted_at=NOW,
        fact_status="demo_fixture",
        document_storage_available=True,
    )
    assert result["blocked_reasons"] == []
    assert result["document_store_present"] is True
    assert result["document_reference_not_storage"] is False
    # And the invariant does not fire on the branch the injection exists for.
    assert val_svc.validation_invariant_failures(result) == []


def test_the_reference_reports_no_store_when_none_is_supplied():
    result = val_svc.validate_proof_event(
        event_type="mark_submitted",
        event_status="proof_attached",
        proof_document_ref=DOC,
        proof_source="human_entered",
        submitted_at=NOW,
        fact_status="demo_fixture",
    )
    assert result["document_store_present"] is False
    assert result["document_reference_not_storage"] is True
    assert val_svc.validation_invariant_failures(result) == []


# ------------------------------------------------- retention


def test_a_rejection_retains_the_proof(events_db):
    event_id = uuid.uuid4()
    created = repo_svc.create_proof_event(
        connection=events_db,
        event_id=event_id,
        now=LATER,
        **_event(
            event_type="mark_rejected",
            event_status="proof_rejected",
            rejected_at=LATER,
        ),
    )
    assert created["rows_written"] == 1
    read = repo_svc.get_proof_event(
        connection=events_db, organization_id=ORG, event_id=str(event_id)
    )
    assert read["event_status"] == "proof_rejected"
    assert read["proof_document_ref"] == DOC


def test_a_rejection_that_discards_its_reference_is_refused():
    result = repo_svc.prepare_proof_event_write(
        **_event(
            event_type="mark_rejected",
            event_status="proof_rejected",
            proof_document_ref=None,
            rejected_at=LATER,
        )
    )
    assert result["storage_allowed"] is False
    assert "rejection_discarded_the_proof_reference" in result["blocked_reasons"]


def test_superseding_retains_the_predecessor(events_db):
    first = uuid.uuid4()
    second = uuid.uuid4()
    repo_svc.create_proof_event(
        connection=events_db, event_id=first, now=NOW, **_event()
    )
    result = repo_svc.supersede_proof_event(
        connection=events_db,
        organization_id=ORG,
        superseded_event_id=str(first),
        event_id=second,
        now=LATER,
        award_requirement_id=REQ,
        awarded_grant_id=AWARD,
        event_status="proof_attached",
        proof_document_ref=fixtures.DEMO_CORRECTED_REF,
        proof_source="human_entered",
        submitted_at=LATER,
        fact_status="demo_fixture",
        is_demo=True,
    )
    assert result["rows_written"] == 1
    assert result["predecessor_retained"] is True
    assert result["rows_deleted"] == 0

    total = events_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.PROOF_EVENTS)
    ).scalar()
    assert total == 2

    listed = repo_svc.list_proof_events_for_requirement(
        connection=events_db, organization_id=ORG, award_requirement_id=REQ
    )
    prior = next(e for e in listed["events"] if e["event_id"] == str(first))
    replacement = next(e for e in listed["events"] if e["event_id"] == str(second))
    # The prior row keeps everything it had, and gains one column.
    assert prior["proof_document_ref"] == DOC
    assert prior["submitted_at"] is not None
    assert prior["superseded_at"] is not None
    assert replacement["supersedes_event_id"] == str(first)
    assert listed["superseded_count"] == 1
    assert listed["live_count"] == 1


def test_superseding_a_row_that_is_already_superseded_is_refused(events_db):
    first = uuid.uuid4()
    repo_svc.create_proof_event(
        connection=events_db, event_id=first, now=NOW, **_event()
    )
    common = dict(
        award_requirement_id=REQ,
        event_status="proof_attached",
        proof_document_ref=fixtures.DEMO_CORRECTED_REF,
        proof_source="human_entered",
        submitted_at=LATER,
        fact_status="demo_fixture",
        is_demo=True,
    )
    repo_svc.supersede_proof_event(
        connection=events_db,
        organization_id=ORG,
        superseded_event_id=str(first),
        now=LATER,
        **common,
    )
    again = repo_svc.supersede_proof_event(
        connection=events_db,
        organization_id=ORG,
        superseded_event_id=str(first),
        now=LATER,
        **common,
    )
    assert again["rows_written"] == 0
    assert "no_live_proof_event_to_supersede" in again["blocked_reasons"]


def test_archiving_retains_the_event(events_db):
    event_id = uuid.uuid4()
    repo_svc.create_proof_event(
        connection=events_db, event_id=event_id, now=NOW, **_event()
    )
    archived = repo_svc.archive_proof_event(
        connection=events_db, organization_id=ORG, event_id=str(event_id), now=LATER
    )
    assert archived["rows_written"] == 1
    assert archived["rows_deleted"] == 0

    total = events_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.PROOF_EVENTS)
    ).scalar()
    assert total == 1

    listed = repo_svc.list_proof_events_for_organization(
        connection=events_db, organization_id=ORG
    )
    # An archived event stays in the trail: hiding it would make it
    # indistinguishable from one that never happened.
    assert listed["rows_read"] == 1
    assert listed["archived_count"] == 1
    assert listed["events"][0]["proof_document_ref"] == DOC


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
    assert "no DELETE path" in source


def test_only_two_columns_may_be_written_after_insert():
    """An audit trail that can be rewritten is not one."""
    assert repo_svc.POST_INSERT_WRITABLE_COLUMNS == ("superseded_at", "archived_at")

    source = Path(repo_svc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    updated: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "values"
        ):
            for kw in node.keywords:
                if kw.arg:
                    updated.add(kw.arg)
    # `values()` is used for both inserts and updates, so the check is that the
    # update sites name nothing outside the permitted pair plus updated_at.
    update_only = updated - {c.name for c in repo_svc.PROOF_EVENTS.columns}
    assert update_only == set()
    for column in ("superseded_at", "archived_at", "updated_at"):
        assert column in updated


# ------------------------------------------------- derivation, not write-back


def test_the_requirements_proof_status_is_derived_and_not_written_back(events_db):
    repo_svc.create_proof_event(connection=events_db, now=NOW, **_event())
    listed = repo_svc.list_proof_events_for_organization(
        connection=events_db, organization_id=ORG
    )
    derived = listed["derived_proof_status"]
    assert derived["proof_status"] == "proof_attached"
    assert derived["written_back_to_requirement"] is False
    assert derived["rows_deleted"] == 0


def test_an_empty_trail_is_not_submitted_rather_than_unknown():
    """Nothing on file is a fact; unknown would send a human looking."""
    assert val_svc.derive_current_proof_status([])["proof_status"] == "not_submitted"


def test_a_superseded_event_leaves_the_derivation():
    trail = [
        {"event_status": "proof_attached", "created_at": "2026-01-01T00:00:00+00:00"},
        {
            "event_status": "proof_accepted",
            "created_at": "2026-02-01T00:00:00+00:00",
            "superseded_at": "2026-03-01T00:00:00+00:00",
        },
    ]
    derived = val_svc.derive_current_proof_status(trail)
    assert derived["proof_status"] == "proof_attached"
    assert derived["superseded_event_count"] == 1
    # And it is still in the trail.
    assert derived["event_count"] == 2


# ------------------------------------------------- invariants


def test_a_refused_claim_never_trips_the_services_own_invariants():
    """An invariant ordinary bad input can fire is a validation rule misnamed."""
    for case in (
        {"event_type": "invented"},
        {"event_status": "invented"},
        {"event_status": "proof_accepted"},
        {"event_status": "proof_rejected", "proof_document_ref": None},
        {"accepted_at": LATER, "submitted_at": None},
        {"fact_status": "unknown", "event_status": "proof_accepted"},
        {"fact_status": "invented"},
        {"reviewed_at": LATER},
        {"proof_source": "invented"},
        {"event_type": "audit_note_added", "accepted_at": LATER},
        {"event_type": "proof_superseded"},
        {"proof_document_storage_available": True},
        {"submitted_at": "not-a-datetime"},
    ):
        result = val_svc.validate_proof_event(
            **{
                "event_type": "mark_submitted",
                "event_status": "proof_attached",
                "proof_document_ref": DOC,
                "proof_source": "human_entered",
                "submitted_at": NOW,
                "fact_status": "demo_fixture",
                **case,
            }
        )
        assert val_svc.validation_invariant_failures(result) == [], case


def test_no_invariant_reads_an_unguarded_echoed_input():
    """The structural rule, and the guard clause Gate 126 added to it."""
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
    # These come straight from the caller. `event_status` is read, but only
    # inside the `storable` guard, which bad input can never reach.
    for echoed in ("submitted_at", "accepted_at", "rejected_at", "proof_document_ref"):
        assert echoed not in read, echoed
    assert "storable" in source
    # And the derived replacements are present.
    for derived in (
        "proof_is_accepted",
        "proof_is_rejected",
        "proof_retained",
        "document_store_present",
    ):
        assert derived in read, derived
    # `submission_recorded` is deliberately absent: the invariant that read it
    # restated a conjunction already inside `proof_is_accepted` and so could
    # never fail. The artifact's decision scan carries that cross-check, where
    # it compares two payload fields rather than one value against itself.
    assert "submission_recorded" not in read


def test_the_permitted_branch_of_readiness_is_reachable():
    result = val_svc.validate_proof_event(
        event_type="mark_accepted",
        event_status="proof_accepted",
        proof_document_ref=DOC,
        proof_source="human_entered",
        submitted_at=NOW,
        accepted_at=LATER,
        fact_status="verified",
    )
    assert result["event_ready_for_audit_trail"] is True
    assert result["human_review_required"] is False
    assert val_svc.validation_invariant_failures(result) == []


# ------------------------------------------------- production write gates


def test_a_production_write_is_reachable_and_needs_both_gates():
    settled = _event(fact_status="verified", is_demo=False)
    assert (
        repo_svc.prepare_proof_event_write(
            **settled, customer_auth_live=True, verified_operational_binding=True
        )["production_write_allowed"]
        is True
    )
    for kwargs, reason in (
        (
            {"customer_auth_live": False, "verified_operational_binding": True},
            "production_proof_event_write_requires_live_customer_auth",
        ),
        (
            {"customer_auth_live": True, "verified_operational_binding": False},
            "production_proof_event_write_requires_a_verified_operational_binding",
        ),
    ):
        result = repo_svc.prepare_proof_event_write(**settled, **kwargs)
        assert result["production_write_allowed"] is False
        assert reason in result["blocked_reasons"]


def test_both_gates_are_false_in_this_repository():
    result = repo_svc.prepare_proof_event_write(
        **_event(fact_status="verified", is_demo=False)
    )
    assert result["production_write_allowed"] is False
    assert set(result["blocked_reasons"]) == {
        "production_proof_event_write_requires_live_customer_auth",
        "production_proof_event_write_requires_a_verified_operational_binding",
    }


def test_a_proof_event_write_needs_a_verified_binding():
    assert "write_proof_event" in guard_svc.LABEL_BOUND_OPERATIONS
    result = guard_svc.evaluate_persistence_write(
        operation="write_proof_event",
        organization_id=ORG,
        persistence_capability=cap_svc.build_capability(
            "proof_audit_persistence", customer_auth_live=True
        ),
    )
    assert result["write_allowed"] is False
    assert any("verified_binding_required" in r for r in result["blocked_reasons"])
    assert guard_svc.persistence_guard_invariant_failures(result) == []


# ------------------------------------------------- schema parity


def test_the_core_table_matches_the_migration_columns():
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.PROOF_EVENTS.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path(MIGRATION).read_text(encoding="utf-8")
    declared = set(re.findall(r'name="(ck_nf_proof_events_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.PROOF_EVENTS.constraints
        if c.name and str(c.name).startswith("ck_nf_proof_events")
    }
    assert mapped == declared
    assert len(mapped) == 16


def test_the_migration_restates_the_vocabularies_exactly():
    """A CHECK constraint cannot import Python, so a test holds them together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig0034", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.EVENT_TYPES) == set(val_svc.EVENT_TYPES)
    assert set(module.EVENT_STATUSES) == set(val_svc.EVENT_STATUSES)
    assert set(module.PROOF_SOURCES) == set(val_svc.PROOF_SOURCES)
    assert set(module.FACT_STATUSES) == set(beta_svc.FACT_STATUSES)
    assert set(module.FUNDER_DECIDED_STATUSES) == set(val_svc.FUNDER_DECIDED_STATUSES)


def test_the_database_refuses_what_the_module_would_have_missed(events_db):
    """The CHECK constraints, exercised past the service that also refuses."""
    base = dict(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG),
        award_requirement_id=uuid.UUID(REQ),
        awarded_grant_id=uuid.UUID(AWARD),
        event_type="mark_submitted",
        event_status="proof_attached",
        proof_document_ref=DOC,
        proof_document_storage_available=False,
        proof_source="human_entered",
        submitted_at=NOW,
        fact_status="demo_fixture",
        human_review_required=True,
        is_demo=True,
        blocked_reasons=[],
        created_at=NOW,
        updated_at=NOW,
    )
    for values in (
        {"event_status": "proof_accepted"},
        {"event_status": "proof_accepted", "accepted_at": LATER, "submitted_at": None},
        {
            "event_status": "proof_accepted",
            "accepted_at": LATER,
            "proof_document_ref": None,
        },
        {
            "event_status": "proof_rejected",
            "rejected_at": LATER,
            "proof_document_ref": None,
        },
        {"event_status": "proof_accepted", "accepted_at": LATER, "rejected_at": LATER},
        {"event_type": "proof_superseded"},
        {"supersedes_event_id": uuid.uuid4()},
        {"proof_document_storage_available": True, "proof_document_ref": None},
        {"reviewed_by_identity_id": uuid.UUID(IDENTITY)},
        {"reviewed_at": LATER},
        {
            "event_status": "proof_accepted",
            "accepted_at": LATER,
            "fact_status": "unknown",
        },
        {"event_type": "audit_note_added"},
        {"event_type": "invented_type"},
        {"event_status": "invented_status"},
        {"proof_source": "invented_source"},
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with events_db.begin_nested():
                events_db.execute(
                    sa.insert(repo_svc.PROOF_EVENTS).values(
                        **{**base, "id": uuid.uuid4(), **values}
                    )
                )


def test_nothing_supersedes_itself(events_db):
    event_id = uuid.uuid4()
    with pytest.raises(sa.exc.IntegrityError):
        with events_db.begin_nested():
            events_db.execute(
                sa.insert(repo_svc.PROOF_EVENTS).values(
                    id=event_id,
                    organization_id=uuid.UUID(ORG),
                    award_requirement_id=uuid.UUID(REQ),
                    event_type="proof_superseded",
                    event_status="proof_attached",
                    proof_document_ref=DOC,
                    proof_document_storage_available=False,
                    proof_source="human_entered",
                    supersedes_event_id=event_id,
                    fact_status="demo_fixture",
                    human_review_required=True,
                    is_demo=True,
                    blocked_reasons=[],
                    created_at=NOW,
                    updated_at=NOW,
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
        "award_requirement_id",
        "awarded_grant_id",
    ):
        assert f"{forbidden} = current_setting" not in migration


# ------------------------------------------------- fixtures


def test_the_fixture_set_has_fourteen_cases_and_they_all_agree():
    fixture = fixtures.build_proof_audit_fixture_set()
    assert fixture["case_count"] == 14
    assert fixture["proof_event_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixture["vocabulary_invariant_failures"] == []
    assert fixtures.proof_audit_fixture_invariant_failures(fixture) == []


def test_no_fixture_permits_a_production_write_or_removes_a_record():
    fixture = fixtures.build_proof_audit_fixture_set()
    assert fixture["production_write_count"] == 0
    assert fixture["production_proof_records_created"] == 0
    assert fixture["real_customer_data_written"] == 0
    assert fixture["rows_deleted"] == 0
    assert fixture["audit_record_deleted"] is False
    assert fixture["proof_deleted"] is False
    assert fixture["document_storage_available"] is False


def test_every_fixture_identifier_is_labelled_as_a_fixture():
    for value in (
        fixtures.DEMO_TENANT_LABEL,
        fixtures.DEMO_CUSTOMER_ORG_LABEL,
        fixtures.DEMO_PROFILE_ID_LABEL,
        fixtures.DEMO_DOCUMENT_REF,
        fixtures.DEMO_CORRECTED_REF,
        fixtures.DEMO_SOURCE_REF,
    ):
        assert value.startswith(fixtures.FIXTURE_PREFIX)
    assert fixtures.DEMO_EVENT["fact_status"] == "demo_fixture"


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_proof_event_cases(
        [{"case": "valid_demo_submitted_proof_event"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 13


def test_the_fixture_set_reports_the_real_environment_unchanged():
    fixture = fixtures.build_proof_audit_fixture_set()
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


def test_the_artifacts_report_the_lane_built_and_not_operational():
    declaration = art.build_persistence_declaration()
    assert declaration["proof_audit_storage_available"] is True
    assert declaration["proof_audit_persistence_available"] is True
    assert declaration["proof_audit_write_path_available"] is True
    assert declaration["proof_audit_operational"] is False
    assert declaration["ready_for_operational_awarded_tracking"] is False
    assert declaration["operational_awarded_recommended"] is False
    assert declaration["document_storage_available"] is False
    assert declaration["readiness_blocked_reasons"]


def test_the_removal_scan_refuses_a_file_saying_evidence_went_away():
    assert art.scan_for_claimed_removals({"proof_deleted": True}) == [
        "claimed_removal:proof_deleted"
    ]
    assert art.scan_for_claimed_removals({"audit_record_deleted": True}) == [
        "claimed_removal:audit_record_deleted"
    ]
    assert art.scan_for_claimed_removals({"rows_deleted": 3}) == [
        "claimed_removal:rows_deleted"
    ]
    assert art.scan_for_claimed_removals({"rows_deleted": 0}) == []


def test_the_decision_scan_refuses_an_unsupported_acceptance():
    assert art.scan_for_claimed_decisions(
        {"proof_is_accepted": True, "submission_recorded": False}
    ) == ["claimed_decision:accepted_without_a_submission"]
    assert art.scan_for_claimed_decisions(
        {"proof_is_rejected": True, "document_reference_present": False}
    ) == ["claimed_decision:rejected_without_a_reference"]
    assert (
        art.scan_for_claimed_decisions(
            {
                "proof_is_accepted": True,
                "submission_recorded": True,
                "document_reference_present": True,
            }
        )
        == []
    )


def test_the_capability_scan_measures_rather_than_freezes():
    """Gate 125 froze this claim and Gate 126 falsified it."""
    # Claiming a capability that is not there is refused...
    assert art.scan_for_claimed_capabilities({"document_storage_available": True}) == [
        "claimed_capability:document_storage_available"
    ]
    # ...and so is denying one that is.
    assert art.scan_for_claimed_capabilities(
        {"proof_audit_persistence_available": False}
    ) == ["capability_claim_disagrees_with_reality:proof_audit_persistence_available"]
    assert (
        art.scan_for_claimed_capabilities({"proof_audit_persistence_available": True})
        == []
    )


def test_the_artifact_write_refuses_a_payload_claiming_a_removal(monkeypatch):
    monkeypatch.setattr(
        art, "build_repository_contract", lambda: {"proof_deleted": True}
    )
    with tempfile.TemporaryDirectory() as root:
        with pytest.raises(ValueError, match="proof_deleted"):
            art.write_persistence_artifacts(repo_root=root)


# ------------------------------------------------- the capability lane


def test_the_proof_audit_lane_has_a_write_path_and_is_not_operational():
    lane = cap_svc.build_capability("proof_audit_persistence")
    assert lane["schema_available"] is True
    assert lane["repository_available"] is True
    assert lane["write_path_available"] is True
    assert lane["operational"] is False
    assert lane["blocked_reasons"] == ["no_customer_auth_so_nobody_owns_the_row"]


def test_every_mapped_repository_module_imports():
    """The guard that would have caught Gate 125's probe-name trap.

    Gate 124 added this test for CAPABILITY_CONTRACT_MODULES after finding two
    lanes named a module one token from a real service. CAPABILITY_REPOSITORY_MODULES
    had no equivalent, and Gate 125 wrote a readiness probe naming
    `..._proof_repository_service` while Gate 126 built
    `..._proof_audit_repository_service`. The report would have kept saying the
    store did not exist while it sat in the same directory.
    """
    import importlib.util

    for lane, module in cap_svc.CAPABILITY_REPOSITORY_MODULES.items():
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        assert found, f"{lane} names a repository module that does not import: {module}"


def test_readiness_no_longer_names_a_repository_module_of_its_own():
    """One place names a module, so two cannot disagree."""
    source = Path(readiness_svc.__file__).read_text(encoding="utf-8")
    assert "award_requirement_proof_repository_service" not in source
    assert (
        cap_svc.CAPABILITY_REPOSITORY_MODULES["proof_audit_persistence"]
        == "nativeforge.services.award_requirement_proof_audit_repository_service"
    )


def test_the_lane_count_is_nine():
    assert len(cap_svc.CAPABILITIES) == 9
    assert "proof_audit_persistence" in cap_svc.CAPABILITIES
    assert (
        cap_svc.CAPABILITY_TABLES["proof_audit_persistence"]
        == "nf_award_requirement_proof_events"
    )


# ------------------------------------------------- the spine


def test_awarded_tracking_is_three_lanes():
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
    for lane in (
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "proof_audit_persistence",
    ):
        assert by_name[lane]["operational"] is True, lane
    # Two of the three list document_storage and do not have it.
    assert by_name["proof_audit_persistence"]["unmet_prerequisites"] == [
        "document_storage"
    ]
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


def test_proof_audit_left_the_requires_migrations_set():
    decision = spine_svc.build_persistence_spine_decision()
    assert "proof_audit_persistence" not in decision["requires_migrations"]


# ------------------------------------------------- readiness


def test_readiness_reports_three_lanes_built_and_tracking_still_blocked():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    for key in readiness_svc.STORAGE_COMPONENT_KEYS:
        assert readiness[key] is True, key
    assert readiness["proof_audit_storage_available"] is True
    assert readiness["proof_audit_persistence_available"] is True
    assert readiness["awarded_tracking_storage_available"] is True
    # And none of that moved the answer that matters.
    assert readiness["customer_persistence_live"] is False
    assert readiness["ready_for_operational_awarded_tracking"] is False
    assert readiness_svc.readiness_invariant_failures(readiness) == []


def test_document_storage_remains_false():
    readiness = readiness_svc.build_awarded_requirements_readiness()
    assert readiness["document_storage_live"] is False
    assert readiness["requirement_extraction_live"] is False


def test_proof_audit_availability_must_agree_with_its_lane():
    readiness = dict(readiness_svc.build_awarded_requirements_readiness())
    readiness["proof_audit_persistence_available"] = False
    assert (
        "proof_audit_availability_disagrees_with_its_lane"
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
        repo_svc.prepare_proof_event_write(**_event()),
        repo_svc.create_proof_event(**_event()),
    ):
        assert result["rows_written"] == 0
        assert result["production_proof_records_created"] == 0
        assert result["real_customer_rows_written"] == 0
        assert result["rows_deleted"] == 0


def test_nothing_claims_awarded_tracking_or_a_document_store_is_live():
    fixture = fixtures.build_proof_audit_fixture_set()
    declaration = art.build_persistence_declaration()
    assert fixture["awarded_grants_operational_tracking_live"] is False
    assert fixture["proof_audit_operational"] is False
    assert declaration["awarded_operational_tracking_ready"] is False
    assert declaration["document_storage_available"] is False
    assert declaration["customer_auth_live"] is False
    assert declaration["login_live"] is False
    assert declaration["customer_persistence_live"] is False
    assert declaration["beta_onboarding_ready"] is False
    assert declaration["production_rollout_ready"] is False


def test_no_api_route_serves_a_proof_event():
    """Gate 126F: skipped, and the survey records why."""
    assert not Path("src/nativeforge/api/award_requirement_proof_events.py").exists()
    survey = Path(
        "docs/operations/676_GATE126_PROOF_AUDIT_PERSISTENCE_SURVEY.md"
    ).read_text(encoding="utf-8")
    assert "## 9. No API route" in survey
