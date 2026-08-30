"""Gate 114: the org-scoped customer persistence spine.

Four services and one recurring theme: **schema available is not operational.**

Gate 114A found three lanes answering "is customer persistence live?" three
different ways - two hard-coded constants and one module-existence proxy that
would have flipped to True for an empty file. These tests pin the single answer
that replaced them, and pin the seven conjuncts it requires.

The hardest thing to test here is the negative. Every capability is
non-operational and every guard case is refused, which is the honest state of
the system and also a trap: a contract that only ever says no is
indistinguishable from a constant. So several tests forge `customer_auth_live`
and assert the permitted branch is reachable - not as a claim that auth exists,
but so the refusals mean something.
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

from nativeforge.services import (
    customer_persistence_capability_service as capability_svc,
)
from nativeforge.services import (
    customer_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    customer_persistence_spine_decision_service as spine_svc,
)
from nativeforge.services import (
    org_scoped_customer_persistence_artifact_service as art,
)
from nativeforge.services import (
    org_scoped_customer_persistence_guard_service as guard,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ORG = "00000000-0000-4000-8000-000000000114"
PROFILE_ID = "nf-demo-org-profile-114"
DEMO_ORG = "nf-demo-org-114"


def _authed(capability: str) -> dict:
    """A capability with customer auth forged live.

    Used to isolate a conjunct other than auth. Auth is false everywhere in
    reality, and a case that auth also blocked could not prove which condition
    did the blocking.
    """
    return capability_svc.build_capability(capability, customer_auth_live=True)


# ------------------------------------------------- capabilities


def test_schema_available_does_not_imply_operational():
    """The sentence this whole gate exists to prevent somebody writing."""
    matrix = capability_svc.build_capability_matrix()
    assert matrix["schema_available_count"] > 0, "no lane has schema at all"
    assert matrix["operational_count"] == 0
    assert matrix["customer_persistence_live"] is False
    assert capability_svc.capability_matrix_invariant_failures(matrix) == []


def test_every_capability_is_covered_and_refused_with_a_reason():
    matrix = capability_svc.build_capability_matrix()
    assert len(matrix["rows"]) == len(capability_svc.CAPABILITIES)
    for row in matrix["rows"]:
        assert row["operational"] is False, row["capability"]
        assert row["blocked_reasons"], f"{row['capability']} refused silently"


def test_the_binding_store_schema_does_not_imply_customer_persistence_live():
    """Gate 113 created a table. Gate 120 added a repository. Neither is this."""
    binding = capability_svc.build_capability("identity_binding_persistence")
    assert binding["schema_available"] is True
    assert binding["rls_backed"] is True
    # Gate 120B built the repository this lane was missing, so the write path
    # is now complete. The lane is still not operational, and the reason has
    # changed rather than disappeared: it is auth, not a missing write path.
    assert binding["repository_available"] is True
    assert binding["write_path_available"] is True
    assert binding["operational"] is False
    assert "no_customer_auth_so_nobody_owns_the_row" in binding["blocked_reasons"]
    assert "no_repository_can_address_this_capability" not in binding["blocked_reasons"]

    matrix = capability_svc.build_capability_matrix()
    assert matrix["customer_persistence_live"] is False


def test_a_lane_with_a_full_write_path_is_still_blocked_by_auth():
    """tenant_profile has table, anchor, RLS, repository and contract."""
    profile = capability_svc.build_capability("tenant_profile_persistence")
    assert profile["write_path_available"] is True
    assert profile["operational"] is False
    assert profile["blocked_reasons"] == ["no_customer_auth_so_nobody_owns_the_row"]
    # Built but unusable is exactly what demo_only means.
    assert profile["demo_only"] is True


def test_the_operational_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable.

    Forging auth is not a claim that auth exists - `customer_auth_live` really
    is false. It is what makes `operational: False` a measurement rather than a
    constant.
    """
    profile = _authed("tenant_profile_persistence")
    assert profile["operational"] is True
    assert profile["demo_only"] is False
    assert profile["blocked_reasons"] == []
    assert capability_svc.capability_invariant_failures(profile) == []

    matrix = capability_svc.build_capability_matrix(customer_auth_live=True)
    assert matrix["customer_persistence_live"] is True
    # Two lanes as of Gate 120: identity_binding gained the repository it was
    # missing, so with auth forged it too has everything it needs. Both are
    # still false in the real environment, where auth is not forged.
    assert matrix["operational_capabilities"] == [
        "tenant_profile_persistence",
        "identity_binding_persistence",
    ]


def test_a_lane_with_no_table_never_becomes_operational_however_auth_moves():
    for name in (
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "tenant_digest_persistence",
        "document_library_persistence",
        "source_watchlist_persistence",
        "beta_onboarding_persistence",
    ):
        row = _authed(name)
        assert row["schema_available"] is False, name
        assert row["operational"] is False, name
        assert row["write_path_available"] is False, name


def test_capability_detection_reads_the_schema_rather_than_asserting_it():
    """Pointed at an empty tree, every lane reports absent."""
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp)
        facts = capability_svc.detect_schema_facts(
            models_path=empty / "absent.py", versions_dir=empty
        )
        assert facts == {}
        matrix = capability_svc.build_capability_matrix(
            schema_facts=facts, repositories_dir=empty
        )
        assert matrix["schema_available_count"] == 0
        assert capability_svc.capability_matrix_invariant_failures(matrix) == []


def test_an_unknown_capability_is_denied_and_named():
    row = capability_svc.build_capability("persist_everything_please")
    assert row["operational"] is False
    assert row["blocked_reasons"] == [
        "unknown_persistence_capability:persist_everything_please"
    ]


def test_the_anchor_vocabulary_is_bridged_from_the_binding_store():
    """Two copies of these names is how the layers come to disagree."""
    from nativeforge.services import tenant_customer_org_binding_store_service as store

    assert capability_svc.RLS_ANCHOR_COLUMN is store.RLS_ANCHOR_COLUMN
    assert capability_svc.FORBIDDEN_ANCHOR_NAMES is store.FORBIDDEN_ANCHOR_NAMES


def test_forged_capability_rows_fail_their_invariants():
    row = dict(capability_svc.build_capability("tenant_profile_persistence"))
    row["operational"] = True
    row["blocked_reasons"] = []
    fails = capability_svc.capability_invariant_failures(row)
    assert "operational_without_customer_auth" in fails

    row = dict(capability_svc.build_capability("tenant_profile_persistence"))
    row["write_path_available"] = True
    row["rls_backed"] = False
    assert "write_path_without_rls" in capability_svc.capability_invariant_failures(row)


# ------------------------------------------------- the guard


def test_organization_id_is_required_for_an_operational_write():
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["write_allowed"] is False
    assert "write_without_an_organization_id" in result["blocked_reasons"]


def test_tenant_id_alone_cannot_write_customer_data():
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        tenant_id="nf-demo-tenant-114",
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["write_allowed"] is False
    assert "tenant_id_is_not_a_write_authority" in result["blocked_reasons"]
    assert guard.persistence_guard_invariant_failures(result) == []


def test_customer_org_id_alone_cannot_write_customer_data():
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        customer_org_id="nf-demo-customer-org-114",
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["write_allowed"] is False
    assert "customer_org_id_is_not_a_write_authority" in result["blocked_reasons"]


def test_organization_profile_id_cannot_write_customer_data():
    """The near-miss: a real identifier from a real column, wrong identity space."""
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_profile_id=PROFILE_ID,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["write_allowed"] is False
    assert (
        "organization_profile_id_is_not_a_write_authority" in result["blocked_reasons"]
    )


def test_a_profile_id_is_refused_even_beside_a_valid_anchor():
    """Supplying one is refused on its own terms, not merely for lack of an anchor."""
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=ORG,
        organization_profile_id=PROFILE_ID,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["rls_compatible"] is True
    assert result["write_allowed"] is False
    assert (
        "organization_profile_id_is_not_a_write_authority" in result["blocked_reasons"]
    )


def test_a_verified_binding_alone_does_not_allow_a_write_without_auth():
    """Everything correct except the one thing missing everywhere."""
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=capability_svc.build_capability(
            "tenant_profile_persistence"
        ),
    )
    assert result["binding_present"] is True
    assert result["rls_compatible"] is True
    assert result["write_allowed"] is False
    assert result["blocked_reasons"] == ["customer_auth_not_live"]


def test_customer_auth_live_false_blocks_every_operational_write():
    for operation, capability in guard.OPERATION_CAPABILITIES.items():
        result = guard.evaluate_persistence_write(
            operation=operation,
            organization_id=ORG,
            auth_principal_status="authenticated_verified_org",
            binding_status="verified_binding",
            persistence_capability=capability_svc.build_capability(capability),
        )
        assert result["write_allowed"] is False, operation
        assert result["customer_auth_live"] is False, operation


def test_a_demo_fixture_write_is_demo_only_and_never_permitted():
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
        is_demo_fixture=True,
    )
    assert result["demo_only"] is True
    assert result["write_allowed"] is False
    assert "demo_fixture_write_is_never_operational" in result["blocked_reasons"]
    assert guard.persistence_guard_invariant_failures(result) == []


def test_a_demo_organization_cannot_anchor_a_write():
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=DEMO_ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["rls_compatible"] is False
    assert result["write_allowed"] is False


def test_a_write_to_a_lane_with_no_schema_is_refused():
    result = guard.evaluate_persistence_write(
        operation="write_awarded_grant",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("awarded_grants_persistence"),
    )
    assert result["write_allowed"] is False
    assert "no_schema_for:awarded_grants_persistence" in result["blocked_reasons"]


def test_an_unrecognised_operation_grants_neither_read_nor_write():
    """Unknown must never become permissive."""
    result = guard.evaluate_persistence_write(
        operation="write_whatever_i_like",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["operation"] == "unknown"
    assert result["write_allowed"] is False
    assert result["read_allowed"] is False
    assert "unrecognised_persistence_operation" in result["blocked_reasons"]


def test_the_permitted_branch_of_the_guard_is_reachable():
    """A guard that only ever denies is a constant, not a contract."""
    result = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    assert result["write_allowed"] is True
    assert result["blocked_reasons"] == []
    assert guard.persistence_guard_invariant_failures(result) == []


def test_forged_guard_results_fail_their_invariants():
    base = guard.evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=ORG,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=_authed("tenant_profile_persistence"),
    )
    forged = dict(base)
    forged["customer_auth_live"] = False
    assert (
        "write_permitted_without_customer_auth"
        in guard.persistence_guard_invariant_failures(forged)
    )

    forged = dict(base)
    forged["demo_only"] = True
    fails = guard.persistence_guard_invariant_failures(forged)
    assert "write_permitted_for_a_demo_fixture" in fails


# ------------------------------------------------- the spine


def test_the_spine_recommends_a_safe_next_order():
    decision = spine_svc.build_persistence_spine_decision()
    sequence = decision["recommended_sequence"]
    assert [entry["capability"] for entry in sequence] == [
        name for name, _, _ in spine_svc.SPINE_SEQUENCE
    ]
    assert sequence[0]["capability"] == "identity_binding_persistence"
    assert spine_svc.spine_decision_invariant_failures(decision) == []


def test_the_spine_names_auth_as_the_next_gate():
    """Every lane lists it, so nothing else unblocks more than one."""
    decision = spine_svc.build_persistence_spine_decision()
    assert decision["ready_to_build_next"] is None
    assert (
        decision["next_gate_recommendation"]["recommendation"]
        == "customer_authentication"
    )
    assert "no_customer_auth_so_no_lane_can_be_operated" in decision["blocked_reasons"]


def test_the_spine_recommends_nothing_operational():
    decision = spine_svc.build_persistence_spine_decision()
    assert decision["operational_digest_recommended"] is False
    assert decision["operational_awarded_recommended"] is False
    assert decision["beta_onboarding_recommended"] is False
    assert decision["customer_persistence_live"] is False


def test_the_sequence_moves_when_a_precondition_does():
    """Otherwise the order is a list, not a decision."""
    decision = spine_svc.build_persistence_spine_decision(
        capability_matrix=capability_svc.build_capability_matrix(
            customer_auth_live=True
        ),
        preconditions={
            "customer_auth": True,
            "document_storage": False,
            "email_delivery": False,
            "live_source_collection": False,
        },
    )
    # Gate 120 built the identity binding repository, so that lane is no longer
    # the next thing to build - it is built. The sequence moved on, which is
    # exactly what this test exists to observe.
    assert decision["ready_to_build_next"] == "awarded_grants_persistence"
    assert "identity_binding_persistence" not in decision["ready_to_build"]
    assert spine_svc.spine_decision_invariant_failures(decision) == []


def test_a_lane_operating_ahead_of_its_prerequisites_is_reported():
    """The capability model and the spine answer different questions.

    One says "can this be written", the other "should it be yet". They can
    disagree, and the decision must say so rather than suppress it.
    """
    # Gate 120 removed the *naturally occurring* instance of this disagreement:
    # tenant_profile was operational ahead of identity_binding, and identity
    # binding is now built. The disagreement is still possible, so it is forged
    # here rather than the test being deleted - a reporting path that only ever
    # fired by accident is one nobody has actually tested.
    matrix = capability_svc.build_capability_matrix(customer_auth_live=True)
    matrix = dict(matrix)
    matrix["rows"] = [
        (
            {**row, "operational": False}
            if row["capability"] == "identity_binding_persistence"
            else row
        )
        for row in matrix["rows"]
    ]

    decision = spine_svc.build_persistence_spine_decision(
        capability_matrix=matrix,
        preconditions={
            "customer_auth": True,
            "document_storage": False,
            "email_delivery": False,
            "live_source_collection": False,
        },
    )
    assert decision["capabilities_operational_out_of_sequence"] == [
        "tenant_profile_persistence"
    ]
    assert (
        "operational_ahead_of_its_prerequisites:tenant_profile_persistence"
        in decision["blocked_reasons"]
    )

    suppressed = dict(decision)
    suppressed["capabilities_operational_out_of_sequence"] = []
    assert (
        "operational_out_of_sequence_unreported:tenant_profile_persistence"
        in spine_svc.spine_decision_invariant_failures(suppressed)
    )


def test_the_three_ordering_constraints_are_enforced():
    decision = spine_svc.build_persistence_spine_decision()
    sequence = [dict(entry) for entry in decision["recommended_sequence"]]
    by_name = {entry["capability"]: entry for entry in sequence}

    # digest before auth + persistence + sources
    forged = dict(decision)
    forged["operational_digest_recommended"] = True
    fails = spine_svc.spine_decision_invariant_failures(forged)
    assert "digest_recommended_operational_without_sources" in fails

    # awarded before document persistence
    forged = dict(decision)
    forged["operational_awarded_recommended"] = True
    assert (
        "awarded_recommended_operational_without_document_persistence"
        in spine_svc.spine_decision_invariant_failures(forged)
    )

    # onboarding before auth + binding + tenant profile
    forged = dict(decision)
    forged["beta_onboarding_recommended"] = True
    fails = spine_svc.spine_decision_invariant_failures(forged)
    assert "onboarding_recommended_without:customer_auth" in fails
    assert "onboarding_recommended_without:identity_binding_persistence" in fails

    assert by_name["beta_onboarding_persistence"]["position"] == 8


def test_the_spine_requires_a_migration_for_every_empty_lane():
    decision = spine_svc.build_persistence_spine_decision()
    assert set(decision["requires_migrations"]) == {
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "tenant_digest_persistence",
        "document_library_persistence",
        "source_watchlist_persistence",
        "beta_onboarding_persistence",
    }


# ------------------------------------------------- readiness surfaces


def test_the_three_lanes_now_share_one_definition_of_persistence_live():
    """Gate 114A found three: two constants and a module-existence proxy."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    assert build_awarded_requirements_readiness()["customer_persistence_live"] is False
    assert build_digest_readiness()["customer_persistence_live"] is False
    assert build_tenant_beta_readiness()["customer_persistence_live"] is False


def test_awarded_operational_tracking_remains_false():
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )

    awarded = build_awarded_requirements_readiness()
    assert awarded["ready_for_operational_awarded_tracking"] is False
    assert awarded["source_coverage_claimed"] is False


def test_digest_operational_remains_false():
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    digest = build_digest_readiness()
    assert digest.get("ready_for_operational_digest") is False
    assert digest["source_monitoring_live"] is False


def test_beta_onboarding_remains_false():
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    beta = build_tenant_beta_readiness()
    assert beta["ready_for_beta_onboarding"] is False
    assert beta["customer_auth_live"] is False


def test_the_binding_store_readiness_points_at_the_spine():
    """A refusal that does not say what would lift it is a dead end."""
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
        readiness_invariant_failures,
    )

    readiness = build_binding_store_readiness()
    spine = readiness["persistence_spine_position"]
    assert spine["capability"] == "identity_binding_persistence"
    assert spine["position"] == 1
    assert spine["next_recommended"] == "customer_authentication"
    assert readiness_invariant_failures(readiness) == []

    stripped = dict(readiness)
    stripped["persistence_spine_position"] = {}
    assert "readiness_refused_without_a_spine_position" in readiness_invariant_failures(
        stripped
    )


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case_and_refuses_all_of_them():
    fixture = fixtures.build_persistence_demo_fixture_set()
    assert fixture["case_count"] == 9
    assert fixture["persistence_cases_missing"] == []
    assert fixture["write_allowed_count"] == 0
    assert fixture["refused_count"] == 9
    assert fixtures.persistence_demo_invariant_failures(fixture) == []


def test_the_fixture_set_writes_nothing():
    fixture = fixtures.build_persistence_demo_fixture_set()
    assert fixture["rows_written"] == 0
    assert fixture["real_db_rows_inserted"] is False
    assert fixture["real_customer_data"] is False
    assert fixture["production_write_claimed"] is False
    assert fixture["customer_persistence_live"] is False


def test_the_fixture_set_proves_its_refusals_are_falsifiable():
    """Nine denials with no reachable permission would prove nothing."""
    fixture = fixtures.build_persistence_demo_fixture_set()
    probe = fixture["reachability_probe"]
    assert probe["write_allowed"] is True
    assert probe["forged_condition"] == "customer_auth_live"
    assert probe["customer_auth_live_in_reality"] is False
    assert probe["this_is_a_probe_not_a_claim"] is True


def test_cases_that_forge_auth_declare_that_they_do():
    """An undeclared live-auth row is drift; a declared one isolates a conjunct."""
    fixture = fixtures.build_persistence_demo_fixture_set()
    assert fixture["cases_forging_customer_auth"]
    for row in fixture["rows"]:
        if row["customer_auth_live"]:
            assert row["forges_customer_auth"] is True, row["case"]

    forged = dict(fixture)
    forged["rows"] = [dict(fixture["rows"][1], forges_customer_auth=False)]
    fails = fixtures.persistence_demo_invariant_failures(forged)
    assert any("undeclared" in f for f in fails)


def test_the_demo_only_cases_are_demo_only():
    fixture = fixtures.build_persistence_demo_fixture_set()
    demo = [row for row in fixture["rows"] if row["demo_only"]]
    assert len(demo) == 3
    for row in demo:
        assert row["write_allowed"] is False, row["case"]


def test_a_dropped_case_is_reported_as_a_coverage_gap():
    short = fixtures.build_demo_persistence_cases()[:-1]
    covered = fixtures.measure_persistence_cases(short)
    assert fixtures.REQUIRED_PERSISTENCE_CASES - covered == {
        "missing_capability_schema"
    }


def test_the_fixture_set_notices_when_the_guard_changes_its_answer():
    fixture = dict(fixtures.build_persistence_demo_fixture_set())
    assert fixture["cases_disagreeing_with_expectation"] == []
    fixture["cases_disagreeing_with_expectation"] = ["tenant_id_only_write"]
    assert (
        "guard_disagreed_with_the_fixture:tenant_id_only_write"
        in fixtures.persistence_demo_invariant_failures(fixture)
    )


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_five_artifacts_exist():
    for name in (
        "customer_persistence_capability_matrix.csv",
        "org_scoped_customer_persistence_guard_matrix.csv",
        "customer_persistence_spine_decision.json",
        "customer_persistence_demo_fixtures.json",
        "customer_persistence_readiness_summary.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_persistence_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_regeneration_is_stable_across_repeated_runs():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        art.write_persistence_artifacts(repo_root=a)
        art.write_persistence_artifacts(repo_root=b)
        for path in (Path(a) / art.ARTIFACT_DIR).iterdir():
            other = Path(b) / art.ARTIFACT_DIR / path.name
            assert path.read_text(encoding="utf-8") == other.read_text(
                encoding="utf-8"
            ), path.name


def test_the_artifacts_state_every_required_claim():
    declaration = art.build_persistence_declaration()
    for claim, expected in art.REQUIRED_CLAIMS.items():
        assert declaration[claim] is expected, claim


def test_the_capability_matrix_artifact_reports_no_operational_lane():
    rows = list(
        csv.DictReader(
            io.StringIO(_artifact("customer_persistence_capability_matrix.csv"))
        )
    )
    assert len(rows) == len(capability_svc.CAPABILITIES)
    assert all(row["operational"] == "false" for row in rows)
    assert any(row["schema_available"] == "true" for row in rows)
    for row in rows:
        assert row["blocked_reasons"], row["capability"]


def test_the_guard_matrix_artifact_permits_no_write():
    rows = list(
        csv.DictReader(
            io.StringIO(_artifact("org_scoped_customer_persistence_guard_matrix.csv"))
        )
    )
    assert rows
    assert all(row["write_allowed"] == "false" for row in rows)
    for row in rows:
        assert row["blocked_reasons"], row["case"]


def test_the_spine_artifact_writes_nothing_and_changes_no_schema():
    payload = json.loads(_artifact("customer_persistence_spine_decision.json"))
    assert payload["rows_written"] == 0
    assert payload["schema_changed"] is False
    assert payload["customer_persistence_live"] is False
    assert payload["rls_anchor"] == "organization_id"


def test_the_demo_fixture_artifact_inserted_no_rows():
    payload = json.loads(_artifact("customer_persistence_demo_fixtures.json"))
    assert payload["rows_written"] == 0
    assert payload["real_db_rows_inserted"] is False
    assert payload["production_write_claimed"] is False
    assert payload["write_allowed_count"] == 0


def test_the_summary_separates_the_contract_from_the_capability():
    summary = _artifact("customer_persistence_readiness_summary.md")
    assert "Customer persistence is not live" in summary.replace("**", "")
    assert "Schema available is not operational" in summary
    assert "current_setting('app.current_org_id', true)::uuid" in summary
    for label in ("tenant_id", "customer_org_id", "organization_profile_id"):
        assert label in summary
    # The true claims and the refused claims are in separate blocks; listing
    # them together under one heading mislabelled the true half.
    assert "## What is true" in summary
    assert "## Claims this gate does not make" in summary


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_persistence_declaration())
    declaration["customer_persistence_live"] = True
    assert (
        "artifact_claim_wrong:customer_persistence_live"
        in art.persistence_artifact_invariant_failures(declaration)
    )

    declaration = dict(art.build_persistence_declaration())
    declaration["tenant_id_write_authority"] = True
    assert (
        "artifact_claim_wrong:tenant_id_write_authority"
        in art.persistence_artifact_invariant_failures(declaration)
    )
