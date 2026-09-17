"""Gate 162: authorization that comes from records, not from callers.

Three kinds of test, and no substring-only safety assertion anywhere.

1. **Structural.** The resolver's parameter list is parsed, not described. The
   route surface is read from the served OpenAPI document. "No parameter can
   assert a fact" is a property of a signature, so a signature is what gets
   inspected.

2. **Falsifiability.** A fully recorded SYNTHETIC fact set must reach
   `approved`. Without that, "every real source is refused" proves nothing -
   the boundary could refuse unconditionally and no test could tell.

3. **The distinctions this gate turns on.** Missing is not denied. A ready
   runtime is not permission. Authorization complete is not a permitted
   request. Each is two fields, and each test reads both.
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import json
import os
import pathlib
import subprocess
import sys
import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.db.session import SessionLocal
from nativeforge.main import create_app
from nativeforge.repositories.source_authorization_decision_repository import (
    APPROVED,
    DECISIONS_TABLE,
    HUMAN_REVIEW,
    TERMS,
    count_decisions,
    get_decision,
    record_decision,
)
from nativeforge.services import (
    source_authorization_artifact_gate162_service as art,
)
from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
)
from nativeforge.services.source_activation_packet_service import (
    activation_packet_invariant_failures,
    build_activation_packet,
)
from nativeforge.services.source_allowlist_projection_service import (
    allowlist_projection_invariant_failures,
    project_allowlist,
    project_source,
)
from nativeforge.services.source_authorization_fact_model_service import (
    FACT_DENIED,
    FACT_MISSING,
    FACT_NAMES,
    FACT_RECORDED,
    FACT_STALE,
    PERMITTING_FACT_STATUSES,
    build_fact,
    describe_fact_model,
    fact_invariant_failures,
)
from nativeforge.services.source_authorization_fact_resolver_service import (
    AUTHORIZING_STRENGTHS,
    STRENGTH_BY_FACT,
    resolve_source_authorization_facts,
    resolver_invariant_failures,
)
from nativeforge.services.source_authorization_fixture_registry_service import (
    FIXTURE_PREFIX,
    FIXTURE_ROWS,
    PERMITTABLE_FIXTURE,
    UNDECIDED_FIXTURE,
    describe_fixture_registry,
    fixture_evidence_fingerprint,
    fixture_registry_invariant_failures,
    is_fixture_source,
)
from nativeforge.services.source_live_authorization_service import (
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_MISSING_FACT,
    STATUS_NEEDS_REVIEW,
    authorization_invariant_failures,
    authorize_source_for_live_access,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    evaluate_registry,
    load_registry_rows,
)
from nativeforge.services.source_runtime_readiness_fact_service import (
    LANE_NAMES,
    REQUIRED_FOR_COLLECTION,
    REQUIRED_FOR_MONITORING,
    build_runtime_readiness_facts,
    runtime_readiness_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
REAL = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
T0 = dt.datetime(2026, 9, 17, tzinfo=dt.UTC)
LATER = dt.datetime(2027, 9, 17, tzinfo=dt.UTC)
EXPIRED = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

ARTIFACT_ID = "nf162-test-activation"

ACTIVE_SOURCES = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_name", sa.Text()),
    sa.Column("source_type", sa.Text()),
    sa.Column("source_lane", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("update_frequency", sa.Text()),
    sa.Column("source_health_status", sa.Text()),
    sa.Column("activation_approved_by", sa.Text()),
    sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
    sa.Column("activation_approval_artifact_id", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)


@pytest.fixture
def connection():
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            sa.delete(DECISIONS_TABLE).where(
                DECISIONS_TABLE.c.source_id.like(f"{FIXTURE_PREFIX}%")
            )
        )
        session.execute(
            sa.delete(ACTIVE_SOURCES).where(
                ACTIVE_SOURCES.c.activation_approval_artifact_id == ARTIFACT_ID
            )
        )
        session.commit()
        session.close()


def _decide(session, source_id, kind, **kw):
    base = {
        "connection": session,
        "organization_id": DEMO,
        "source_id": source_id,
        "decision_kind": kind,
        "fact_status": "synthetic_fixture",
        "now": T0,
    }
    base.update(kw)
    return record_decision(**base)


def _activate(session, source_id, *, signer="operator:nf162-test"):
    row = FIXTURE_ROWS[source_id]
    session.execute(
        sa.insert(ACTIVE_SOURCES).values(
            id=uuid.uuid4(),
            organization_id=DEMO,
            source_name=row["source_name"],
            source_type="fixture",
            source_lane="fixture",
            source_url_or_search_target=row["source_url"],
            collection_method="hermetic_fixture",
            update_frequency="manual",
            source_health_status="healthy",
            activation_approved_by=signer,
            activation_approved_at=T0,
            activation_approval_artifact_id=ARTIFACT_ID,
            created_at=T0,
            updated_at=T0,
        )
    )


def _decide_everything(session, source_id):
    for kind, guard in (
        (TERMS, "NO_REVIEW_REQUIRED"),
        (HUMAN_REVIEW, "NOT_APPLICABLE"),
    ):
        _decide(
            session,
            source_id,
            kind,
            decision="approved",
            guard_status=guard,
            reviewed_by="reviewer:nf162-test",
            reviewed_at=T0,
            review_authority="nf162_test",
            evidence_fingerprint=fixture_evidence_fingerprint(source_id),
            expires_at=LATER,
        )
    _activate(session, source_id)


def _authorize(session, source_id):
    return authorize_source_for_live_access(
        connection=session, organization_id=DEMO, source_id=source_id, now=T0
    )


# ------------------------------------------------- the guard fact mapping


def test_every_guard_status_input_is_modelled():
    """Parsed from the guard's own signature, not from a list kept in step."""
    guard_params = set(inspect.signature(build_live_network_decision).parameters)
    wanted = {p for p in guard_params if p.endswith("_status")}
    model = describe_fact_model()
    mapped = {
        spec["guard_input"] for spec in model["facts"] if spec.get("guard_input")
    }
    assert wanted, "the guard declares no status inputs"
    assert wanted <= mapped, sorted(wanted - mapped)


def test_the_model_reads_the_guards_vocabularies_rather_than_restating_them():
    """A second copy of a vocabulary is a second thing to drift."""
    from nativeforge.services import live_network_guard_service as guard

    model = describe_fact_model()
    terms = next(s for s in model["facts"] if s["fact_name"] == "terms_status")
    assert set(terms["vocabulary"]) == set(guard.ALL_TERMS_STATUSES)
    assert set(terms["permitting"]) == set(guard.TERMS_NON_BLOCKING)

    activation = next(
        s for s in model["facts"] if s["fact_name"] == "activation_status"
    )
    assert set(activation["vocabulary"]) == set(guard.ACTIVATION_STATUSES)
    assert set(activation["permitting"]) == set(guard.ACTIVATION_SATISFYING)


def test_exactly_one_fact_status_permits():
    assert len(PERMITTING_FACT_STATUSES) == 1
    assert FACT_RECORDED in PERMITTING_FACT_STATUSES
    assert len(FACT_NAMES) == 11


# --------------------------------------------- missing is not denied


def test_missing_is_not_the_same_as_denied(connection):
    """Opposite problems, same effect on permission. A boolean cannot tell."""
    missing = build_fact(
        fact_name="terms_status", record_exists=False, now=T0
    )
    assert missing["fact_status"] == FACT_MISSING
    assert missing["value"] is None
    assert "Nobody has decided" in missing["refusal_meaning"]

    denied = build_fact(
        fact_name="terms_status",
        value="TERMS_REVIEW_REQUIRED",
        record_exists=True,
        decision_verdict="denied",
        recorded_by="reviewer:nf162-test",
        recorded_at=T0,
        now=T0,
    )
    assert denied["fact_status"] == FACT_DENIED
    assert "says no" in denied["refusal_meaning"]

    assert missing["refusal_meaning"] != denied["refusal_meaning"]
    assert not missing["permits"] and not denied["permits"]


def test_a_reviewers_verdict_outranks_the_guard_value():
    """A `denied` decision naturally carries a guard status reading as review.

    Deriving status from the guard value alone reported a human's refusal as
    "waiting on a human" - about a source a human had already refused.
    """
    fact = build_fact(
        fact_name="terms_status",
        value="TERMS_REVIEW_REQUIRED",
        record_exists=True,
        decision_verdict="denied",
        recorded_by="reviewer:nf162-test",
        recorded_at=T0,
        now=T0,
    )
    assert fact["fact_status"] == FACT_DENIED, "the verdict was overridden"
    assert fact["decision_verdict"] == "denied"


def test_an_expired_affirmative_answer_is_stale_not_permitting():
    fact = build_fact(
        fact_name="terms_status",
        value="NO_REVIEW_REQUIRED",
        record_exists=True,
        decision_verdict="approved",
        recorded_by="reviewer:nf162-test",
        recorded_at=EXPIRED,
        expires_at=EXPIRED,
        now=T0,
    )
    assert fact["fact_status"] == FACT_STALE
    assert not fact["permits"]
    assert "expired" in fact["refusal_meaning"]


def test_a_permitting_decision_without_attribution_fails_its_invariant():
    """An approval nobody signed is not evidence."""
    fact = build_fact(
        fact_name="terms_status",
        value="NO_REVIEW_REQUIRED",
        record_exists=True,
        decision_verdict="approved",
        now=T0,
    )
    fails = fact_invariant_failures(fact)
    assert "a_permitting_decision_with_no_recorded_by:terms_status" in fails
    assert "a_permitting_decision_with_no_recorded_at:terms_status" in fails


# ------------------------------------------------------ persistence


def test_the_database_refuses_an_unsigned_approval(connection):
    for kind in (TERMS, HUMAN_REVIEW):
        result = _decide(
            connection,
            f"{FIXTURE_PREFIX}unsigned",
            kind,
            decision="approved",
            guard_status=(
                "NO_REVIEW_REQUIRED" if kind == TERMS else "NOT_APPLICABLE"
            ),
            evidence_fingerprint="a" * 64,
        )
        assert result["recorded"] is False, kind
        assert (
            "an_approval_needs_reviewed_by_and_reviewed_at"
            in result["blocked_reasons"]
        )


def test_the_database_refuses_an_approval_with_no_evidence(connection):
    result = _decide(
        connection,
        f"{FIXTURE_PREFIX}noevidence",
        TERMS,
        decision="approved",
        guard_status="NO_REVIEW_REQUIRED",
        reviewed_by="reviewer:nf162-test",
        reviewed_at=T0,
    )
    assert result["recorded"] is False
    assert (
        "an_approval_needs_an_evidence_fingerprint" in result["blocked_reasons"]
    )


def test_a_terms_approval_cannot_carry_a_blocking_guard_status(connection):
    result = _decide(
        connection,
        f"{FIXTURE_PREFIX}contradiction",
        TERMS,
        decision="approved",
        guard_status="TERMS_REVIEW_REQUIRED",
        reviewed_by="reviewer:nf162-test",
        reviewed_at=T0,
        evidence_fingerprint="a" * 64,
    )
    assert result["recorded"] is False
    assert any(
        "blocking_guard_status" in reason for reason in result["blocked_reasons"]
    )


def test_the_real_organization_cannot_receive_a_decision(connection):
    result = record_decision(
        connection=connection,
        organization_id=REAL,
        source_id=f"{FIXTURE_PREFIX}realorg",
        decision_kind=TERMS,
        decision="needs_review",
        guard_status="TERMS_REVIEW_REQUIRED",
        now=T0,
    )
    assert result["recorded"] is False
    assert "real_organization_refused_by_name" in result["blocked_reasons"]


def test_both_decision_kinds_persist_independently_for_one_source(connection):
    """One table, two questions. Neither answer overwrites the other."""
    _decide(
        connection,
        UNDECIDED_FIXTURE,
        TERMS,
        decision="needs_review",
        guard_status="TERMS_REVIEW_REQUIRED",
    )
    _decide(
        connection,
        UNDECIDED_FIXTURE,
        HUMAN_REVIEW,
        decision="denied",
        guard_status="NOT_APPLICABLE",
        reviewed_by="reviewer:nf162-test",
        reviewed_at=T0,
    )

    terms = get_decision(
        connection=connection,
        organization_id=DEMO,
        source_id=UNDECIDED_FIXTURE,
        decision_kind=TERMS,
    )
    human = get_decision(
        connection=connection,
        organization_id=DEMO,
        source_id=UNDECIDED_FIXTURE,
        decision_kind=HUMAN_REVIEW,
    )
    assert terms["decision"]["decision"] == "needs_review"
    assert human["decision"]["decision"] == "denied"
    assert terms["decision"]["decision_kind"] == TERMS
    assert human["decision"]["decision_kind"] == HUMAN_REVIEW


def test_a_decision_kind_is_required_and_not_defaulted(connection):
    """A default would record a terms answer under the review question."""
    result = record_decision(
        connection=connection,
        organization_id=DEMO,
        source_id=UNDECIDED_FIXTURE,
        decision="unknown",
        guard_status="UNKNOWN",
        now=T0,
    )
    assert result["recorded"] is False
    assert any(
        "decision_kind_outside_vocabulary" in reason
        for reason in result["blocked_reasons"]
    )


def test_get_decision_reports_absence_rather_than_inventing_unknown(connection):
    """A repository that defaults destroys the distinction before it is seen."""
    found = get_decision(
        connection=connection,
        organization_id=DEMO,
        source_id=UNDECIDED_FIXTURE,
        decision_kind=TERMS,
    )
    assert found["record_exists"] is False
    assert found["decision"] is None


# ---------------------------------------------------- the resolver


def test_the_resolver_signature_cannot_assert_a_fact():
    """Structural. A parameter that does not exist cannot be misused."""
    params = sorted(
        inspect.signature(resolve_source_authorization_facts).parameters
    )
    assert params == ["connection", "now", "organization_id", "source_id"]

    fact_shaped = ("status", "approved", "allow", "permit", "override", "fact")
    assert not [
        p for p in params if any(word in p.lower() for word in fact_shaped)
    ]


def test_the_resolver_has_no_kwargs_escape_hatch():
    """`**overrides` would reintroduce everything the signature forbids."""
    source = inspect.getsource(resolve_source_authorization_facts)
    tree = ast.parse(source.strip())
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert function.args.kwarg is None, "the resolver accepts **kwargs"
    assert function.args.vararg is None, "the resolver accepts *args"


def test_only_a_recorded_decision_can_authorize():
    assert AUTHORIZING_STRENGTHS == frozenset({"recorded_decision"})
    for name in ("runtime_status", "source_registered", "collector_status",
                 "rate_limit_status", "user_agent_status"):
        assert STRENGTH_BY_FACT[name] not in AUTHORIZING_STRENGTHS, name


def test_a_queued_job_and_an_execution_proof_are_not_authorization_facts():
    """The strongest form of "these do not authorize": they are not facts."""
    assert not [n for n in FACT_NAMES if "job" in n]
    assert not [n for n in FACT_NAMES if "proof" in n]
    assert not [n for n in FACT_NAMES if "adapter" in n]


def test_every_real_source_resolves_and_none_is_authorized(connection):
    registry = load_registry_rows()
    assert len(registry) == 177

    authorized = []
    for source_id in sorted(registry):
        result = _authorize(connection, source_id)
        assert result["authorization_status"], source_id
        assert not authorization_invariant_failures(result), source_id
        if result["authorized"]:
            authorized.append(source_id)

    assert authorized == []


def test_a_real_sources_robots_fact_stays_unresolvable(connection):
    """Answering it needs the live fetch we want permission for."""
    real = sorted(load_registry_rows())[0]
    resolution = resolve_source_authorization_facts(
        connection=connection, organization_id=DEMO, source_id=real, now=T0
    )
    robots = resolution["resolved_facts"]["robots_status"]
    assert robots["fact_status"] == FACT_MISSING
    assert "robots.txt" in robots["unresolvable_because"]
    assert not resolver_invariant_failures(resolution)


# ------------------------------------------------ runtime derivation


def test_runtime_readiness_composes_the_six_gate_lanes(connection):
    facts = build_runtime_readiness_facts(
        connection=connection, organization_id=DEMO
    )
    assert len(LANE_NAMES) == 6
    assert set(facts["lanes"]) == set(LANE_NAMES)
    assert facts["lanes_observed"] == 6
    assert not runtime_readiness_invariant_failures(facts)


def test_runtime_readiness_is_not_derived_from_module_existence():
    """Parsed. A file on disk is not a runtime.

    Asserted by checking the derivation READS each lane's health function
    rather than testing for a path or an import.
    """
    from nativeforge.services import source_runtime_readiness_fact_service as mod

    tree = ast.parse(inspect.getsource(mod))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    # It imports by name at call time and invokes the health function via
    # getattr, so `exists` / `is_file` must appear nowhere.
    assert "exists" not in called
    assert "is_file" not in called
    assert "glob" not in called


def test_the_stale_background_worker_derivation_is_no_longer_read():
    """AST, not a substring: the module's docstring names the field it fixed."""
    from nativeforge.services import source_runtime_readiness_fact_service as mod

    tree = ast.parse(inspect.getsource(mod))
    read: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if isinstance(node.slice.value, str):
                read.add(node.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            read.add(node.args[0].value)
    assert "background_worker_available" not in read


def test_monitoring_requires_strictly_more_than_collection():
    assert set(REQUIRED_FOR_COLLECTION) < set(REQUIRED_FOR_MONITORING)
    assert "scheduler_runtime_ready" not in REQUIRED_FOR_COLLECTION
    assert "orchestration_runtime_ready" not in REQUIRED_FOR_COLLECTION


def test_a_ready_runtime_authorizes_nothing(connection):
    facts = build_runtime_readiness_facts(
        connection=connection, organization_id=DEMO
    )
    assert facts["authorizes_nothing"] is True
    assert facts["not_implied"]
    assert any("not an approved source" in item for item in facts["not_implied"])


# --------------------------------------------- activation composition


def test_activation_is_read_from_the_existing_table(connection):
    """Composed, not duplicated. No second approval column was added."""
    resolution = resolve_source_authorization_facts(
        connection=connection,
        organization_id=DEMO,
        source_id=PERMITTABLE_FIXTURE,
        now=T0,
    )
    before = resolution["resolved_facts"]["activation_status"]
    assert before["fact_status"] == FACT_MISSING
    assert before["source_of_truth"] == (
        "nf_active_opportunity_sources.activation_approved_*"
    )

    _activate(connection, PERMITTABLE_FIXTURE)
    after = resolve_source_authorization_facts(
        connection=connection,
        organization_id=DEMO,
        source_id=PERMITTABLE_FIXTURE,
        now=T0,
    )["resolved_facts"]["activation_status"]
    assert after["fact_status"] == FACT_RECORDED
    assert after["value"] == "activation_allowed"
    assert after["recorded_by"] == "operator:nf162-test"


def test_an_unsigned_activation_row_reads_as_unknown_not_allowed(connection):
    row = FIXTURE_ROWS[PERMITTABLE_FIXTURE]
    connection.execute(
        sa.insert(ACTIVE_SOURCES).values(
            id=uuid.uuid4(),
            organization_id=DEMO,
            source_name=row["source_name"],
            source_type="fixture",
            source_lane="fixture",
            source_url_or_search_target=row["source_url"],
            collection_method="hermetic_fixture",
            update_frequency="manual",
            source_health_status="healthy",
            activation_approval_artifact_id=ARTIFACT_ID,
            created_at=T0,
            updated_at=T0,
        )
    )
    fact = resolve_source_authorization_facts(
        connection=connection,
        organization_id=DEMO,
        source_id=PERMITTABLE_FIXTURE,
        now=T0,
    )["resolved_facts"]["activation_status"]
    assert fact["value"] == "activation_unknown"
    assert not fact["permits"]


# ----------------------------------------- the forged-input bypass


def test_forged_guard_booleans_cannot_change_an_authorization(connection):
    real = sorted(load_registry_rows())[0]
    before = _authorize(connection, real)

    forged = build_live_network_decision(
        purpose="source_collection",
        target_url=load_registry_rows()[real]["source_url"],
        caller="an_attacker",
        source_id=real,
        method="GET",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        activation_status="activation_allowed",
        collector_status="active",
        robots_status="allowed",
        credential_status="not_required",
        rate_limit_status="policy_declared",
        user_agent_status="canonical",
        attribution_status="not_required",
    )
    # The low-level guard IS a pure function and answers what it was told.
    assert forged["allowed"] is True

    after = _authorize(connection, real)
    assert after["authorized"] is False
    assert after["authorization_status"] == before["authorization_status"]


def test_the_authorization_service_withholds_unresolved_guard_inputs(connection):
    """An unresolved fact contributes None, never a permitting default."""
    real = sorted(load_registry_rows())[0]
    decision = _authorize(connection, real)
    assert decision["guard_inputs_withheld"]
    assert decision["guard_allowed"] is False
    assert not authorization_invariant_failures(decision)


def test_the_checker_catches_a_guard_that_allowed_with_inputs_withheld():
    liar = {
        "authorization_status": STATUS_MISSING_FACT,
        "authorized": False,
        "refusal_reasons": ["terms_status:missing"],
        "guard_inputs_withheld": ["terms_status"],
        "guard_allowed": True,
        "resolution": {"resolved_facts": {}, "authorization_ready": False},
        "not_implied": ["x"],
    }
    fails = authorization_invariant_failures(liar)
    assert "the_guard_allowed_with_1_inputs_withheld" in fails


def test_the_checker_catches_denied_without_a_recorded_denial():
    liar = {
        "authorization_status": STATUS_DENIED,
        "authorized": False,
        "refusal_reasons": ["runtime_status:denied"],
        "denial_is_a_decision": False,
        "resolution": {"resolved_facts": {}, "authorization_ready": False},
        "not_implied": ["x"],
    }
    assert "denied_without_a_recorded_denial" in authorization_invariant_failures(
        liar
    )


# -------------------------------------- the synthetic permitted branch


def test_a_fully_recorded_synthetic_fact_set_reaches_approved(connection):
    """THE falsifiability test. Without it, refusals prove nothing."""
    _decide_everything(connection, PERMITTABLE_FIXTURE)
    decision = _authorize(connection, PERMITTABLE_FIXTURE)

    facts = decision["resolution"]["resolved_facts"]
    recorded = [n for n, f in facts.items() if f["fact_status"] == FACT_RECORDED]

    assert decision["authorized"] is True, decision["refusal_reasons"]
    assert decision["authorization_status"] == STATUS_APPROVED
    assert len(recorded) == 11
    assert not authorization_invariant_failures(decision)


def test_the_synthetic_approved_branch_still_cannot_use_a_live_transport(
    connection,
):
    """Authorization complete is NOT a permitted request."""
    _decide_everything(connection, PERMITTABLE_FIXTURE)
    decision = _authorize(connection, PERMITTABLE_FIXTURE)

    assert decision["authorized"] is True
    assert decision["guard_allowed"] is False
    assert (
        "live_fetch_not_opted_in"
        in decision["guard_decision"]["blocked_reasons"]
    )
    assert decision["live_transport_permitted"] is False


def test_an_undecided_fixture_is_refused_like_any_other_source(connection):
    """Being a fixture is not itself permission."""
    decision = _authorize(connection, UNDECIDED_FIXTURE)
    assert decision["authorized"] is False
    assert decision["authorization_status"] == STATUS_MISSING_FACT
    assert "terms_status:missing" in decision["blocking_decisions"]


def test_a_terms_denial_on_a_fixture_reports_as_a_decision(connection):
    _decide(
        connection,
        UNDECIDED_FIXTURE,
        TERMS,
        decision="denied",
        guard_status="TERMS_REVIEW_REQUIRED",
        reviewed_by="reviewer:nf162-test",
        reviewed_at=T0,
    )
    decision = _authorize(connection, UNDECIDED_FIXTURE)
    assert decision["authorization_status"] == STATUS_DENIED
    assert decision["denial_is_a_decision"] is True


def test_a_technical_shortfall_is_not_reported_as_a_denial(connection):
    """`collector_status=not_active` is nobody's decision."""
    real = sorted(load_registry_rows())[0]
    decision = _authorize(connection, real)
    assert decision["authorization_status"] != STATUS_DENIED
    assert decision["denial_is_a_decision"] is False
    assert decision["blocking_prerequisites"]


def test_needs_review_is_reported_distinctly(connection):
    _decide(
        connection,
        UNDECIDED_FIXTURE,
        TERMS,
        decision="needs_review",
        guard_status="TERMS_REVIEW_REQUIRED",
    )
    decision = _authorize(connection, UNDECIDED_FIXTURE)
    assert decision["authorization_status"] == STATUS_NEEDS_REVIEW
    assert decision["denial_is_a_decision"] is False


# ----------------------------------------------- the fixture registry


def test_the_fixture_prefix_is_reserved_and_shadows_nothing():
    shipped = load_registry_rows()
    described = describe_fixture_registry(shipped)
    assert described["prefix_is_reserved"] is True
    assert described["no_fixture_shadows_a_real_source"] is True
    assert not fixture_registry_invariant_failures(described)
    assert described["merged_count"] == len(shipped) + described["fixture_count"]


def test_a_fixture_needs_both_the_prefix_and_declared_membership():
    """Either alone is bypassable."""
    assert is_fixture_source(PERMITTABLE_FIXTURE) is True
    # Prefixed but undeclared.
    assert is_fixture_source(f"{FIXTURE_PREFIX}grants.gov") is False
    # Declared-looking but unprefixed.
    assert is_fixture_source("grants.gov") is False
    assert is_fixture_source("") is False


def test_no_real_registry_source_uses_the_fixture_prefix():
    assert not [
        key for key in load_registry_rows() if str(key).startswith(FIXTURE_PREFIX)
    ]


# ------------------------------------------------ allowlist projection


def test_the_allowlist_is_derived_and_stores_no_flag(connection):
    projection = project_allowlist(
        connection=connection, organization_id=DEMO, now=T0
    )
    assert projection["evaluated"] == 179
    assert projection["real_sources_allowlisted"] == 0
    assert projection["approved_source_count"] == 0
    assert not allowlist_projection_invariant_failures(projection)
    assert "computed from recorded facts" in projection["is_a_projection"]


def test_no_column_anywhere_stores_an_allowlist_boolean():
    """Measured against the schema, not asserted in prose."""
    from nativeforge.db.session import engine

    inspector = sa.inspect(engine)
    offenders = []
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            name = str(column["name"]).lower()
            words = set(name.split("_"))
            if "allowlisted" in words or "allowlist" in words:
                offenders.append(f"{table}.{column['name']}")
    assert offenders == [], offenders


def test_the_allowlist_becomes_reachable_for_a_decided_fixture(connection):
    """Falsifiable: the list can be populated, by a synthetic source only."""
    _decide_everything(connection, PERMITTABLE_FIXTURE)
    entry = project_source(
        connection=connection,
        organization_id=DEMO,
        source_id=PERMITTABLE_FIXTURE,
        now=T0,
    )
    assert entry["allowlisted"] is True
    assert entry["is_synthetic_fixture"] is True
    assert entry["live_transport_permitted"] is False

    projection = project_allowlist(
        connection=connection, organization_id=DEMO, now=T0
    )
    assert projection["synthetic_fixtures_allowlisted"] == 1
    assert projection["real_sources_allowlisted"] == 0
    assert not allowlist_projection_invariant_failures(projection)


def test_the_projection_checker_catches_an_allowlisted_real_source():
    liar = {
        "evaluated": 1,
        "allowlisted": 1,
        "allowlisted_source_ids": ["grants.gov"],
        "real_sources_allowlisted": 1,
        "approved_source_count": 1,
        "by_authorization_state": {"approved": 1},
        "projections": [
            {
                "source_id": "grants.gov",
                "allowlisted": True,
                "authorization_state": STATUS_APPROVED,
                "is_synthetic_fixture": False,
            }
        ],
        "is_a_projection": "x",
    }
    fails = allowlist_projection_invariant_failures(liar)
    assert "real_sources_allowlisted:1" in fails
    assert "a_real_source_is_allowlisted:grants.gov" in fails


# --------------------------------------------- the activation packet


def test_the_activation_packet_names_an_owner_for_every_blocker(connection):
    real = sorted(load_registry_rows())[0]
    packet = build_activation_packet(
        connection=connection, organization_id=DEMO, source_id=real, now=T0
    )
    assert packet["activatable"] is False
    assert packet["grants_nothing"] is True
    assert not activation_packet_invariant_failures(packet)

    for requirement in packet["requirements"]:
        if not requirement["satisfied"]:
            assert requirement["authority"], requirement["requirement"]


def test_the_packet_records_the_robots_first_ordering(connection):
    real = sorted(load_registry_rows())[0]
    packet = build_activation_packet(
        connection=connection, organization_id=DEMO, source_id=real, now=T0
    )
    sequence = packet["gate_163_sequence"]
    robots_step = next(i for i, s in enumerate(sequence) if "robots" in s)
    collection_step = next(
        i for i, s in enumerate(sequence) if "collection request" in s
    )
    assert robots_step < collection_step


def test_the_packet_checker_catches_a_blocker_with_no_owner():
    liar = {
        "requirements": [
            {"requirement": n, "satisfied": True, "is_a_human_decision": False}
            for n in FACT_NAMES
        ],
        "requirements_satisfied": len(FACT_NAMES),
        "unresolved_blockers": [],
        "activatable": True,
        "authorization_status": STATUS_APPROVED,
        "grants_nothing": True,
        "gate_163_sequence": ["x"],
    }
    liar["requirements"][0]["satisfied"] = False
    liar["requirements_satisfied"] = len(FACT_NAMES) - 1
    liar["unresolved_blockers"] = [FACT_NAMES[0]]
    liar["activatable"] = False
    liar["authorization_status"] = STATUS_MISSING_FACT
    fails = activation_packet_invariant_failures(liar)
    assert any("no_authority" in f for f in fails)


# ------------------------------------------------------- the routes


def _client():
    soh.ensure_org(DEMO, "demo")
    return TestClient(create_app())


def test_no_authorization_route_mutates_anything():
    """Read from the SERVED schema: no write verb on this surface."""
    spec = _client().get("/openapi.json").json()
    paths = {
        path: ops
        for path, ops in spec["paths"].items()
        if "source-authorization" in path
    }
    assert len(paths) >= 4
    for path, ops in paths.items():
        for method in ops:
            assert method.upper() == "GET", f"{method.upper()} {path}"


def test_no_authorization_route_accepts_a_fact_or_an_address():
    spec = _client().get("/openapi.json").json()
    paths = {
        path: ops
        for path, ops in spec["paths"].items()
        if "source-authorization" in path
    }
    forbidden = {
        "approved", "approve", "allow", "allowed", "permit", "permitted",
        "override", "fact", "terms", "activation", "robots", "credential",
        "attribution", "decision", "authorize", "url", "uri", "endpoint",
        "host", "address", "target", "callback", "redirect", "proxy",
    }
    for path, ops in paths.items():
        for method, operation in ops.items():
            assert not operation.get("requestBody"), f"{method} {path}"
            for parameter in operation.get("parameters") or []:
                words = set(
                    str(parameter["name"]).replace("-", "_").lower().split("_")
                )
                assert not (words & forbidden), (method, path, parameter["name"])


def test_the_authorization_routes_fail_closed_without_a_session():
    client = _client()
    for suffix in (
        "source-authorization/fact-model",
        "source-authorization/allowlist",
        "source-authorization/sources/grants.gov",
        "source-authorization/sources/grants.gov/requirements",
    ):
        response = client.get(f"/v1/nf/demo/orgs/{DEMO}/{suffix}")
        assert response.status_code >= 400, suffix


def test_a_forged_org_header_cannot_override_the_session_scope():
    client = _client()
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-authorization/allowlist",
        headers={"X-NF-Org-Id": str(REAL)},
    )
    assert response.status_code >= 400


def test_the_real_organization_is_refused_by_the_routes():
    client = _client()
    response = client.get(
        f"/v1/nf/demo/orgs/{REAL}/source-authorization/allowlist",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 404


def test_a_real_source_reads_as_refused_over_the_route():
    client = _client()
    real = sorted(load_registry_rows())[0]
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-authorization/sources/{real}",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json().get("data", response.json())
    assert body["authorized"] is False
    assert body["live_fetch_opted_in"] is False
    assert body["live_transport_permitted"] is False
    assert body["caller_can_supply_a_fact"] is False
    assert not body["invariant_failures"]


def test_the_allowlist_route_reports_zero_real_sources():
    client = _client()
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-authorization/allowlist",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json().get("data", response.json())
    assert body["real_sources_allowlisted"] == 0
    assert body["approved_source_count"] == 0
    assert not body["invariant_failures"]


# ----------------------------------------------------- the counts


def test_the_registry_blocked_counts_are_preserved():
    evaluated = evaluate_registry()
    assert evaluated["registry_row_count"] == 177
    assert evaluated["terms_blocked_count"] == 171
    assert evaluated["human_review_blocked_count"] == 6
    assert evaluated["activation_approved_count"] == 0
    assert evaluated["monitorable_count"] == 0


def test_no_real_source_has_a_decision_or_an_approval(connection):
    counts = count_decisions(connection=connection, organization_id=DEMO)
    assert counts["unsigned_approvals"] == 0

    real_ids = set(load_registry_rows())
    rows = connection.execute(
        sa.select(DECISIONS_TABLE.c.source_id, DECISIONS_TABLE.c.decision)
    ).all()
    assert not [r[0] for r in rows if r[0] in real_ids]
    assert not [
        r[0] for r in rows if r[0] in real_ids and r[1] == APPROVED
    ]


def test_no_execution_attempt_claims_a_live_call(connection):
    live = connection.execute(
        sa.text(
            "SELECT count(*) FROM nf_source_collection_execution_attempts "
            "WHERE transport_kind <> 'hermetic' OR live_source_call <> 0"
        )
    ).scalar()
    assert int(live or 0) == 0


# --------------------------------------------------- the artifacts


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_authorization_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_are_deterministic_across_processes():
    """A different hash seed, in a separate process.

    Comparing two calls in one process compares set iteration order against
    itself. PYTHONHASHSEED is what actually varies, so that is what varies.
    """
    script = (
        "import json;"
        "from nativeforge.services import "
        "source_authorization_artifact_gate162_service as art;"
        "print(json.dumps(art.build_authorization_artifacts()))"
    )
    bodies = []
    for seed in ("1", "424242"):
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        environment["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=environment,
            check=True,
        )
        bodies.append(json.loads(result.stdout))
    assert bodies[0] == bodies[1]
    assert bodies[0] == art.build_authorization_artifacts()


def test_every_declared_artifact_file_exists():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name in art.ARTIFACT_FILES:
        assert (directory / name).exists(), name
    assert len(art.ARTIFACT_FILES) == 12


def test_the_artifacts_carry_no_secret_shape():
    """The writer's own guard, exercised rather than trusted."""
    for name, body in art.build_authorization_artifacts().items():
        art._assert_no_forbidden_shape(name, body)


def test_the_artifacts_report_zero_real_approvals():
    files = art.build_authorization_artifacts()
    health = json.loads(files["source_authorization_health.json"])
    assert health["real_approved_sources"] == 0
    assert health["real_allowlisted_sources"] == 0
    assert health["approved_source_count"] == 0
    assert health["fabricated_caller_bypass_possible"] is False
    assert health["live_transport_enabled"] is False
    assert health["live_source_calls"] == 0
    assert health["source_monitoring_live"] is False
    assert health["second_activation_system_created"] is False


def test_the_permitted_branch_artifact_shows_a_reachable_approval():
    files = art.build_authorization_artifacts()
    branch = json.loads(files["synthetic_permitted_branch.json"])
    assert branch["all_facts_permit"] is True
    assert branch["facts_recorded"] == 11
    assert branch["authorization_status_would_be"] == STATUS_APPROVED
    assert branch["is_synthetic"] is True
    assert branch["live_fetch_opted_in"] is False
    assert branch["live_transport_permitted"] is False
    assert branch["authorization_complete_is_not_a_permitted_request"] is True
    assert branch["invariant_failures"] == []


def test_the_forged_input_artifact_shows_the_bypass_is_ineffective():
    files = art.build_authorization_artifacts()
    forged = json.loads(files["fabricated_input_refusal.json"])
    assert forged["the_low_level_guard_allowed_it"] is True
    assert forged["forged_guard_inputs_change_the_authorization"] is False
    assert forged["caller_supplied_facts_accepted"] == 0
    assert len(forged["what_a_forged_opinion_cannot_do"]) >= 4


def test_the_survey_artifact_records_what_was_not_rebuilt():
    files = art.build_authorization_artifacts()
    survey = json.loads(files["source_activation_survey.json"])
    assert survey["second_activation_system_created"] is False
    assert survey["what_already_existed"]["activation_approval_storage"] == (
        "nf_active_opportunity_sources.activation_approved_*"
    )
    assert "id spaces" in survey["why_discovery_review_items_was_not_reused"]
    assert sorted(survey["decision_kinds"]) == [HUMAN_REVIEW, TERMS]


# --------------------------------------------- no duplicate truth source


def test_the_decision_table_is_the_only_place_a_terms_answer_lives():
    """Measured against the schema.

    `legal_tos_review_required` on nf_active_opportunity_sources is a
    REQUIREMENT flag, not an answer, and it is allowed to remain. What must not
    exist is a second column recording the reviewer's verdict.
    """
    from nativeforge.db.session import engine

    inspector = sa.inspect(engine)
    verdict_columns = []
    for table in inspector.get_table_names():
        if table == "nf_source_authorization_decisions":
            continue
        for column in inspector.get_columns(table):
            words = set(str(column["name"]).lower().split("_"))
            if {"terms"} & words and {"decision", "approved", "verdict"} & words:
                verdict_columns.append(f"{table}.{column['name']}")
    assert verdict_columns == [], verdict_columns


def test_the_verifier_is_registered_exactly_once():
    from nativeforge.services import readiness_verifier_registry_service as reg

    names = [entry["verifier"] for entry in reg.VERIFIERS]
    assert names.count("source_authorization_boundary") == 1
    assert len(names) == len(set(names))
