"""Gate 166: source authorization derives from governed data, not from code.

Hermetic. No database, no network. Every branch of the authority classifier is
reachable from a dict, which is the point: Gate 162G established that an
unreachable permitted branch makes every refusal around it unfalsifiable, and
an authority model whose states can only be reached by writing rows is a model
nobody can test the edges of.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from nativeforge.services import source_live_warrant_service as warrant
from nativeforge.services.source_attribution_contract_service import (
    ATTRIBUTION_CONTRACTS,
    contract_for_adapter,
    verify_recorded_notice,
)
from nativeforge.services.source_authority_service import (
    ACTIVATED,
    AUTHORITY_LADDER,
    BLOCKED,
    LIVE_OPTED_IN,
    REGISTERED,
    REQUIRED_DECISION_KINDS,
    RETIRED,
    REVIEW_REQUIRED,
    REVIEWED,
    SOURCE_AUTHORITY_STATES,
    UNREGISTERED,
    authority_invariant_failures,
    classify_source_authority,
    derive_authorized_source_ids,
)
from nativeforge.services.source_authority_sweep_service import (
    SWEEP_BUCKETS,
    sweep_invariant_failures,
)
from nativeforge.services.source_definition_service import (
    FIELD_CLASSIFICATION,
    build_source_definition,
    definition_invariant_failures,
    derive_activation_state,
    describe_field_classification,
)
from nativeforge.services.source_fleet_fact_scope_service import (
    FLEET_FACTS,
    describe_scope,
    fleet_fact_scope,
    in_fleet_scope,
    scope_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def signed(**overrides):
    """A complete, signed governance fact set. The positive control."""
    base = {
        "decisions": {
            kind: {
                "decision": "approved",
                "guard_status": "NOT_APPLICABLE",
                "reviewed_by": "MAYHEM",
                "reviewed_at": "2026-09-17T20:43:27Z",
                "signed_and_approved": True,
            }
            for kind in REQUIRED_DECISION_KINDS
        },
        "activation": {
            "approved_by": "MAYHEM",
            "approved_at": "2026-09-17T20:43:27Z",
            "disabled_at": None,
            "signed": True,
            "disabled": False,
        },
    }
    base.update(overrides)
    return base


# ------------------------------------------------- the constant is gone


def test_the_warrant_module_no_longer_holds_an_authorization_allowlist():
    """The whole point of the gate, checked structurally.

    By attribute, not by grepping the file: a comment explaining why the
    constant was removed contains its name, and a text search would read the
    explanation as the thing it explains.
    """
    assert not hasattr(warrant, "AUTHORIZED_SOURCE_IDS")


def test_no_module_in_the_authority_path_defines_a_source_id_allowlist():
    """A frozenset of source ids anywhere in the authority path is the defect.

    AST, so a docstring quoting an id is not mistaken for a constant holding
    one.
    """
    offenders = []
    for name in (
        "source_authority_service",
        "source_authority_sweep_service",
        "source_live_warrant_service",
        "source_definition_service",
        "source_fleet_fact_scope_service",
    ):
        path = REPO / "src" / "nativeforge" / "services" / f"{name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for literal in ast.walk(node.value):
                if isinstance(literal, ast.Constant) and isinstance(
                    literal.value, str
                ):
                    if literal.value.startswith("nf-seed-"):
                        offenders.append(f"{name}:{literal.lineno}")
    assert offenders == [], offenders


def test_the_warrant_reports_where_its_authority_came_from():
    source = inspect.getsource(warrant.evaluate_live_request)
    assert "authorization_derived_from_persisted_decisions" in source
    assert "authorization_derived_from_source_code_constant" in source


# --------------------------------------------------------- the ladder


def test_a_fully_signed_source_reaches_live_opted_in():
    verdict = classify_source_authority(
        source_id="nf166.t.complete", registered=True, governance=signed()
    )
    assert verdict["state"] == LIVE_OPTED_IN
    assert verdict["governance_complete"] is True
    assert verdict["reasons"] == []
    assert authority_invariant_failures(verdict) == []


def test_any_source_id_can_reach_authorization_the_factory_unlock():
    """No identifier is privileged. This is what Gate 166 exists to make true."""
    for source_id in ("nf166.t.alpha", "some-other-source", "nf-seed-2026-fed-001"):
        verdict = classify_source_authority(
            source_id=source_id, registered=True, governance=signed()
        )
        assert verdict["governance_complete"] is True, source_id


@pytest.mark.parametrize("withheld", REQUIRED_DECISION_KINDS)
def test_withholding_any_one_decision_refuses(withheld):
    facts = signed()
    facts["decisions"].pop(withheld)
    verdict = classify_source_authority(
        source_id="nf166.t.partial", registered=True, governance=facts
    )
    assert verdict["governance_complete"] is False
    assert verdict["state"] != LIVE_OPTED_IN


def test_an_unsigned_approval_is_not_an_approval():
    facts = signed()
    for kind in facts["decisions"]:
        facts["decisions"][kind]["signed_and_approved"] = False
    verdict = classify_source_authority(
        source_id="nf166.t.unsigned", registered=True, governance=facts
    )
    assert verdict["state"] == REGISTERED
    assert verdict["governance_complete"] is False


def test_an_unsigned_activation_stops_the_ladder_at_reviewed():
    facts = signed()
    facts["activation"] = {"signed": False, "disabled": False}
    verdict = classify_source_authority(
        source_id="nf166.t.noactivation", registered=True, governance=facts
    )
    assert verdict["state"] == REVIEWED
    assert "activation_is_not_signed" in verdict["reasons"]


def test_activated_but_not_opted_in():
    facts = signed()
    facts["decisions"].pop("live_fetch")
    verdict = classify_source_authority(
        source_id="nf166.t.activated", registered=True, governance=facts
    )
    assert verdict["state"] == ACTIVATED
    assert verdict["governance_complete"] is False


def test_a_catalog_row_alone_is_only_registered():
    """Presence in the CSV is not authorization. The 177 live here."""
    verdict = classify_source_authority(
        source_id="nf166.t.bare", registered=True, governance={}
    )
    assert verdict["state"] == REGISTERED
    assert verdict["governance_complete"] is False


def test_no_catalog_row_is_unregistered():
    verdict = classify_source_authority(
        source_id="nf166.t.unknown", registered=False, governance=signed()
    )
    assert verdict["state"] == UNREGISTERED
    assert verdict["governance_complete"] is False


# ------------------------------------------------- the terminal states


def test_retired_beats_a_complete_ladder():
    """Checked BEFORE the rungs. Walking them would report live_opted_in."""
    facts = signed()
    facts["activation"] = dict(facts["activation"])
    facts["activation"]["disabled"] = True
    facts["activation"]["disabled_at"] = "2026-09-19T00:00:00Z"
    verdict = classify_source_authority(
        source_id="nf166.t.retired", registered=True, governance=facts
    )
    assert verdict["state"] == RETIRED
    assert verdict["governance_complete"] is False
    assert verdict["highest_rung"] is None
    assert authority_invariant_failures(verdict) == []


def test_an_explicit_denial_is_blocked_not_merely_unfinished():
    facts = signed()
    facts["decisions"]["terms"]["decision"] = "denied"
    facts["decisions"]["terms"]["signed_and_approved"] = False
    verdict = classify_source_authority(
        source_id="nf166.t.denied", registered=True, governance=facts
    )
    assert verdict["state"] == BLOCKED
    assert any("denied" in reason for reason in verdict["reasons"])


@pytest.mark.parametrize("guard", ["HUMAN_REVIEW_ONLY", "TERMS_REVIEW_REQUIRED"])
def test_a_terms_guard_that_demands_a_human_is_review_required(guard):
    facts = signed()
    facts["decisions"]["terms"]["guard_status"] = guard
    verdict = classify_source_authority(
        source_id="nf166.t.review", registered=True, governance=facts
    )
    assert verdict["state"] == REVIEW_REQUIRED


def test_every_state_names_a_reason_when_it_refuses():
    """A refusal that names nothing is the defect Gate 163 kept finding."""
    for facts, registered in (
        ({}, True),
        (signed(), False),
    ):
        verdict = classify_source_authority(
            source_id="nf166.t.x", registered=registered, governance=facts
        )
        if not verdict["governance_complete"]:
            assert verdict["reasons"], verdict


def test_every_return_path_states_governance_complete():
    """Absent, the invariant checks that read it are unfalsifiable.

    The first draft omitted it on four early returns, so a retired source
    could never have been caught reporting governance complete.
    """
    cases = [
        ({}, True, "nf166.t.a"),
        (signed(), False, "nf166.t.b"),
        (signed(), True, "nf166.t.c"),
        ({}, True, ""),
    ]
    retired = signed()
    retired["activation"] = {"signed": True, "disabled": True}
    cases.append((retired, True, "nf166.t.d"))
    for facts, registered, source_id in cases:
        verdict = classify_source_authority(
            source_id=source_id, registered=registered, governance=facts
        )
        assert "governance_complete" in verdict, verdict


# ------------------------------------------------------- the invariants


def test_the_invariant_catches_a_forged_complete_verdict():
    verdict = classify_source_authority(
        source_id="nf166.t.forge", registered=True, governance={}
    )
    verdict["governance_complete"] = True
    assert authority_invariant_failures(verdict)


def test_the_invariant_catches_a_retired_source_claiming_completion():
    facts = signed()
    facts["activation"] = {"signed": True, "disabled": True}
    verdict = classify_source_authority(
        source_id="nf166.t.rf", registered=True, governance=facts
    )
    verdict["governance_complete"] = True
    assert "retired_source_reported_governance_complete" in (
        authority_invariant_failures(verdict)
    )


def test_states_and_ladder_are_consistent():
    assert set(AUTHORITY_LADDER) <= set(SOURCE_AUTHORITY_STATES)
    assert set(SWEEP_BUCKETS) <= set(SOURCE_AUTHORITY_STATES)


def test_derive_without_a_connection_authorizes_nothing():
    assert derive_authorized_source_ids(connection=None) == frozenset()


# --------------------------------------------------- the fleet scope


def test_outside_a_scope_nothing_is_reused():
    assert in_fleet_scope() is False
    report = describe_scope()
    assert report["scope_open"] is False
    assert report["total_computations"] == 0


def test_a_scope_computes_each_fleet_fact_once():
    calls = {"n": 0}

    from nativeforge.services import source_fleet_fact_scope_service as scope_mod

    with fleet_fact_scope(organization_id="org-a", reason="test") as scope:
        for _ in range(50):
            scope_mod._scoped(
                "execution_health",
                lambda: calls.__setitem__("n", calls["n"] + 1) or {"v": 1},
                connection="conn",
                organization_id="org-a",
            )
        report = describe_scope(scope)

    assert calls["n"] == 1
    assert report["computations"]["execution_health"] == 1
    assert scope_invariant_failures(report) == []


def test_a_scope_opened_for_another_organization_is_bypassed_not_answered():
    """A mismatch must cost time, never correctness."""
    calls = {"n": 0}

    from nativeforge.services import source_fleet_fact_scope_service as scope_mod

    with fleet_fact_scope(organization_id="org-a", reason="test") as scope:
        for _ in range(5):
            scope_mod._scoped(
                "execution_health",
                lambda: calls.__setitem__("n", calls["n"] + 1) or {"v": 1},
                connection="conn",
                organization_id="org-b",
            )
        report = describe_scope(scope)

    assert calls["n"] == 5, "another tenant's fleet facts were reused"
    assert report["bypasses"]["execution_health"] == 5
    assert report["computations"]["execution_health"] == 0


def test_a_different_connection_is_a_different_key():
    calls = {"n": 0}

    from nativeforge.services import source_fleet_fact_scope_service as scope_mod

    with fleet_fact_scope(organization_id="org-a"):
        for conn in ("conn-1", "conn-2"):
            scope_mod._scoped(
                "execution_health",
                lambda: calls.__setitem__("n", calls["n"] + 1) or {"v": 1},
                connection=conn,
                organization_id="org-a",
            )

    assert calls["n"] == 2


def test_leaving_a_scope_discards_it():
    with fleet_fact_scope(organization_id="org-a"):
        assert in_fleet_scope() is True
    assert in_fleet_scope() is False


def test_the_scope_invariant_refuses_a_recomputed_fleet_fact():
    fake = {
        "scope_open": True,
        "computations": dict.fromkeys(FLEET_FACTS, 0) | {"execution_health": 4},
        "total_computations": 4,
    }
    failures = scope_invariant_failures(fake)
    assert any("computed_more_than_once" in f for f in failures)


# ----------------------------------------------------------- the sweep


def test_the_sweep_invariant_reads_a_legitimate_zero_as_zero():
    """`or -1` would call an unauthorized fleet a broken report.

    The first draft did exactly that and failed all four synthetic scales -
    a fleet of registered-only sources is the normal case.
    """
    report = {
        "counts_by_state": dict.fromkeys(SWEEP_BUCKETS, 0) | {"registered": 10},
        "evaluated_sources": 10,
        "authorized_for_live": 0,
        "fleet_facts": {"computations": {"execution_health": 1}},
        "authority_is_data_derived": True,
    }
    assert sweep_invariant_failures(report) == []


def test_the_sweep_invariant_catches_buckets_that_do_not_total():
    report = {
        "counts_by_state": dict.fromkeys(SWEEP_BUCKETS, 0) | {"registered": 9},
        "evaluated_sources": 10,
        "authorized_for_live": 0,
        "fleet_facts": {"computations": {}},
        "authority_is_data_derived": True,
    }
    assert any(
        "buckets_do_not_total" in f for f in sweep_invariant_failures(report)
    )


def test_the_sweep_invariant_catches_a_recomputed_fleet_fact():
    report = {
        "counts_by_state": dict.fromkeys(SWEEP_BUCKETS, 0) | {"registered": 10},
        "evaluated_sources": 10,
        "authorized_for_live": 0,
        "fleet_facts": {"computations": {"execution_health": 10}},
        "authority_is_data_derived": True,
    }
    assert any(
        "fleet_fact_recomputed" in f for f in sweep_invariant_failures(report)
    )


# ------------------------------------------------- the source contract


def test_activation_state_derives_from_signatures_not_a_label():
    assert derive_activation_state(None) == "activation_absent"
    assert derive_activation_state({}) == "activation_absent"
    assert (
        derive_activation_state({"disabled_at": "2026-01-01"}) == "activation_revoked"
    )
    assert (
        derive_activation_state(
            {"activation_approved_by": "X", "activation_approved_at": "T"}
        )
        == "activation_allowed"
    )
    # A row nobody signed is unknown, not denied.
    assert derive_activation_state({"activation_approved_by": "X"}) == (
        "activation_unknown"
    )


def test_a_revoked_activation_is_never_reported_as_allowed():
    """The label may say anything; the signature columns decide."""
    assert (
        derive_activation_state(
            {
                "activation_approved_by": "X",
                "activation_approved_at": "T",
                "disabled_at": "2026-09-19",
            }
        )
        == "activation_revoked"
    )


def test_an_unknown_source_projects_and_names_what_is_missing():
    definition = build_source_definition(source_id="nf166.t.nothing")
    assert definition["source_id"] == "nf166.t.nothing"
    assert definition["usable_by_an_adapter"] is False
    assert set(definition["missing_fields"]) >= {"source_name", "endpoint"}
    assert definition_invariant_failures(definition) == []


def test_the_contract_does_not_name_the_store_that_answered():
    """An adapter must not learn which table a field came from."""
    definition = build_source_definition(source_id="nf166.t.nothing")
    for key in definition:
        if key in ("stores_present", "schema_version"):
            continue
        assert "nf_" not in key, key


def test_every_projected_field_is_classified():
    described = describe_field_classification()
    assert described["consolidation_performed"] is False
    assert len(described["fields"]) == len(FIELD_CLASSIFICATION)
    for _field, meta in described["fields"].items():
        assert meta["classification"]
        assert meta["store"]


def test_the_duplicated_status_column_is_classified_as_duplicated():
    """It disagrees with the signed columns in the live data."""
    assert FIELD_CLASSIFICATION["source_status"][0] == "DUPLICATED"


# ------------------------------------------------------- attribution


def test_attribution_is_resolved_by_adapter_key_not_by_publisher_import():
    source = inspect.getsource(
        __import__(
            "nativeforge.services.source_authorization_fact_resolver_service",
            fromlist=["_resolve_attribution"],
        )._resolve_attribution
    )
    assert "grants_gov_attribution_service" not in source
    assert "adapter_key" in source


def test_an_adapter_with_no_declared_contract_does_not_pass():
    verdict = verify_recorded_notice(adapter_key="nf166.t.no_contract", notice="x")
    assert verdict["result"] == "no_contract_declared"
    assert verdict["attribution_is_customer_visible"] is False


def test_a_missing_notice_does_not_pass():
    key = sorted(ATTRIBUTION_CONTRACTS)[0]
    verdict = verify_recorded_notice(adapter_key=key, notice=None)
    assert verdict["result"] == "missing"
    assert verdict["attribution_is_customer_visible"] is False


def test_an_edited_notice_does_not_pass():
    """Verbatim means verbatim. One character and it returns to missing.

    The required text is resolved through the contract's own
    `text_constant`, not through a constant this test guesses the name of.
    Guessing `ATTRIBUTION_TEXT` worked while one adapter existed; Gate 171
    added two whose module serves both and therefore cannot use that name
    for either.
    """
    key = sorted(ATTRIBUTION_CONTRACTS)[0]
    contract = contract_for_adapter(key)
    module = __import__(contract["module"], fromlist=[contract["text_constant"]])
    good = getattr(module, contract["text_constant"])

    passing = verify_recorded_notice(adapter_key=key, notice=good)
    assert passing["attribution_is_customer_visible"] is True

    edited = verify_recorded_notice(adapter_key=key, notice=good + ".")
    assert edited["attribution_is_customer_visible"] is False


# ------------------------------------------ the corpus is not authority


def test_the_seed_loader_permits_growth_and_refuses_shrinkage():
    from nativeforge.services import source_ingestion_seed_loader_service as loader

    source = inspect.getsource(loader.load_source_seed_rows)
    assert "len(rows) < EXPECTED_ROW_COUNT" in source
    assert "len(rows) != EXPECTED_ROW_COUNT" not in source
