"""Gate 110: org identity canonicalization.

Five identity names, one authority. Every row-level security policy reads
`organization_id = current_setting('app.current_org_id', true)::uuid`, so
`organization_id` is what the database enforces on and everything else is a label
until it resolves to one.

These tests hold three rules:

```text
tenant_id is never the RLS authority, whatever its value looks like
a label never persists customer data, even with a verified binding
a recommendation can be right while the migration stays unsafe to apply
```
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import (
    awarded_grants_requirements_readiness_service as awarded_readiness,
)
from nativeforge.services import identity_persistence_safety_guard_service as safety
from nativeforge.services import org_identity_canonicalization_artifact_service as art
from nativeforge.services import org_identity_role_contract_service as roles
from nativeforge.services import tenant_beta_readiness_service as beta_readiness
from nativeforge.services import (
    tenant_customer_org_binding_store_decision_service as store,
)
from nativeforge.services import (
    tenant_customer_org_identity_binding_service as binding,
)
from nativeforge.services import (
    tenant_nofo_digest_readiness_service as digest_readiness,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

UUID_VALUE = "11111111-2222-3333-4444-555555555555"
DEMO_TENANT = "nf-demo-tenant-01"


def _verified_binding():
    return binding.build_binding(
        tenant_id="t-gate110",
        customer_org_id="org-gate110",
        binding_source="admin_verified",
        requested_status="verified_binding",
        verified_by="admin@example.invalid",
        verified_at="2026-02-01",
    )


# ------------------------------------------------- the authority


def test_organization_id_is_the_rls_authority():
    row = roles.describe_identity_role(
        identity_name="organization_id", identity_value=UUID_VALUE
    )
    assert row["role"] == "rls_authority"
    assert row["authority_level"] == "authority"
    assert row["rls_allowed"] is True
    assert row["persistence_allowed"] is True
    assert roles.identity_role_invariant_failures(row) == []


def test_current_org_id_is_session_context_not_a_product_label():
    row = roles.describe_identity_role(
        identity_name="current_org_id", identity_value=UUID_VALUE
    )
    assert row["role"] == "rls_session_context"
    assert row["authority_level"] == "session_context"
    assert row["rls_allowed"] is True
    # Session context scopes a transaction; it is not a column to write into.
    assert row["persistence_allowed"] is False


def test_an_authority_name_with_a_non_uuid_value_gets_no_rls():
    """The name is necessary but not sufficient - the value must be castable.

    Every RLS policy casts to ::uuid, so a free-form value cannot match even
    under the right name.
    """
    row = roles.describe_identity_role(
        identity_name="organization_id", identity_value="not-a-uuid"
    )
    assert row["shape"] == "free_form"
    assert row["rls_allowed"] is False
    assert row["persistence_allowed"] is False
    assert "rls_requires_a_uuid_value:free_form" in row["blocked_reasons"]


def test_session_context_with_a_non_uuid_value_gets_no_rls():
    row = roles.describe_identity_role(
        identity_name="current_org_id", identity_value="not-a-uuid"
    )
    assert row["rls_allowed"] is False


def test_the_matrix_names_exactly_one_authority():
    matrix = roles.build_identity_role_matrix()
    assert matrix["organization_id_is_rls_authority"] is True
    assert matrix["rls_authority_names"] == ["organization_id"]
    assert matrix["names_allowing_rls"] == ["current_org_id", "organization_id"]


# ------------------------------------------------- tenant_id is never authority


def test_tenant_id_is_not_the_rls_authority():
    row = roles.describe_identity_role(
        identity_name="tenant_id", identity_value="t-anything"
    )
    assert row["role"] != "rls_authority"
    assert row["rls_allowed"] is False
    assert row["persistence_allowed"] is False
    assert row["requires_binding"] is True


def test_a_uuid_shaped_tenant_id_is_still_not_the_authority():
    """The name governs authority; the shape only governs whether a name may act."""
    row = roles.describe_identity_role(
        identity_name="tenant_id", identity_value=UUID_VALUE
    )
    assert row["shape"] == "uuid"
    assert row["rls_allowed"] is False
    assert row["persistence_allowed"] is False
    assert roles.identity_role_invariant_failures(row) == []


def test_a_tenant_id_permitted_rls_fails_its_invariants():
    forged = roles.describe_identity_role(
        identity_name="tenant_id", identity_value=UUID_VALUE
    )
    forged["rls_allowed"] = True
    forged["persistence_allowed"] = True
    failures = roles.identity_role_invariant_failures(forged)
    assert "tenant_id_permitted_rls" in failures
    assert "tenant_id_permitted_persistence" in failures


def test_demo_tenant_ids_are_never_rls_authority():
    row = roles.describe_identity_role(
        identity_name="tenant_id", identity_value=DEMO_TENANT
    )
    assert row["role"] == "demo_fixture_label"
    assert row["rls_allowed"] is False
    assert row["persistence_allowed"] is False
    assert "demo_identity_value" in row["blocked_reasons"]


def test_a_demo_organization_id_is_refused_too():
    """The demo check is on the value, so it catches an authority name as well."""
    row = roles.describe_identity_role(
        identity_name="organization_id", identity_value="nf-demo-org-01"
    )
    assert row["rls_allowed"] is False
    assert row["persistence_allowed"] is False
    assert "demo_identity_value" in row["blocked_reasons"]


# ------------------------------------------------- aliases and surfaces


def test_customer_org_id_is_not_automatically_a_foreign_key():
    row = roles.describe_identity_role(
        identity_name="customer_org_id", identity_value="org-real-1"
    )
    assert row["role"] == "customer_surface_alias"
    assert row["persistence_allowed"] is False
    assert row["requires_binding"] is True


def test_customer_org_id_treated_as_a_foreign_key_fails():
    forged = roles.describe_identity_role(
        identity_name="customer_org_id", identity_value="org-real-1"
    )
    forged["role"] = "db_foreign_key"
    forged["persistence_allowed"] = True
    forged["requires_binding"] = False
    failures = roles.identity_role_invariant_failures(forged)
    assert "customer_org_id_treated_as_a_foreign_key" in failures
    assert "customer_org_id_permitted_persistence_without_a_binding" in failures
    assert "customer_org_id_did_not_require_a_binding" in failures


def test_org_id_is_an_alias_only_when_its_value_is_a_uuid():
    as_uuid = roles.describe_identity_role(
        identity_name="org_id", identity_value=UUID_VALUE
    )
    assert as_uuid["authority_level"] == "alias_of_authority"
    assert as_uuid["persistence_allowed"] is True

    as_string = roles.describe_identity_role(
        identity_name="org_id", identity_value="operator-org-alpha"
    )
    assert as_string["authority_level"] == "label"
    assert as_string["persistence_allowed"] is False
    assert as_string["requires_binding"] is True
    assert "org_id_value_is_not_a_uuid:free_form" in as_string["blocked_reasons"]


def test_a_non_uuid_org_id_claiming_alias_authority_fails():
    forged = roles.describe_identity_role(
        identity_name="org_id", identity_value="operator-org-alpha"
    )
    forged["authority_level"] = "alias_of_authority"
    assert "non_uuid_org_id_claimed_alias_authority" in (
        roles.identity_role_invariant_failures(forged)
    )


def test_shape_is_read_from_the_value():
    assert roles.classify_identity_value_shape(UUID_VALUE) == "uuid"
    assert roles.classify_identity_value_shape("tn_c206946f01e50396") == (
        "gate51_derived"
    )
    assert roles.classify_identity_value_shape("anything-else") == "free_form"
    assert roles.classify_identity_value_shape("") == "absent"


# ------------------------------------------------- persistence safety


@pytest.mark.parametrize("operation", sorted(safety.CUSTOMER_DATA_OPERATIONS))
def test_tenant_id_alone_cannot_persist_any_customer_data(operation):
    result = safety.evaluate_persistence_safety(
        operation=operation, identity_name="tenant_id", identity_value="t-real-1"
    )
    assert result["write_allowed"] is False
    assert result["cross_tenant_risk"] is True
    assert safety.persistence_safety_invariant_failures(result) == []


def test_tenant_id_cannot_persist_awarded_grants_even_with_a_verified_binding():
    """The binding names the organization; the write must use that organization."""
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="tenant_id",
        identity_value="t-gate110",
        binding=_verified_binding(),
    )
    assert result["binding_present"] is True
    assert result["write_allowed"] is False
    assert any(
        "write_must_use_it" in reason for reason in result["blocked_reasons"]
    )


def test_tenant_id_cannot_persist_digest_records():
    result = safety.evaluate_persistence_safety(
        operation="tenant_digest_persist",
        identity_name="tenant_id",
        identity_value="t-real-1",
    )
    assert result["write_allowed"] is False


def test_tenant_id_cannot_persist_document_library_records():
    result = safety.evaluate_persistence_safety(
        operation="document_library_persist",
        identity_name="tenant_id",
        identity_value="t-real-1",
    )
    assert result["write_allowed"] is False


def test_customer_org_id_alone_cannot_persist_without_a_binding():
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value="org-real-1",
    )
    assert result["binding_required"] is True
    assert result["binding_present"] is False
    assert result["write_allowed"] is False
    # The reason is asserted, not just the outcome: the write gate and the
    # blocked reason are independent, and a refusal that cannot say why is
    # unreviewable.
    assert "binding_required_for:customer_org_id" in result["blocked_reasons"]


def test_the_guard_refuses_an_inconsistent_identity_role(monkeypatch):
    """Defence in depth, made observable.

    The guard re-checks shape and the binding requirement even though the role
    contract already implies both. Those conjuncts are unreachable while the
    contract is self-consistent, so a mutation removing either survives against
    real inputs. Forge an inconsistent role - persistence permitted on a
    free-form value that still needs a binding - and the guard must still refuse.
    """

    def _forged(*, identity_name, identity_value=None):
        return {
            "identity_name": "customer_org_id",
            "identity_value": identity_value,
            "role": "customer_surface_alias",
            "shape": "free_form",
            "authority_level": "label",
            "rls_allowed": False,
            "persistence_allowed": True,
            "product_surface_allowed": True,
            "demo_allowed": False,
            "derived_allowed": False,
            "requires_binding": True,
            "blocked_reasons": [],
        }

    monkeypatch.setattr(safety, "describe_identity_role", _forged)
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value="org-real-1",
    )
    assert result["rls_compatible"] is False, "shape check must hold on its own"
    assert result["write_allowed"] is False
    assert "binding_required_for:customer_org_id" in result["blocked_reasons"]


def test_the_guard_refuses_a_forged_role_that_drops_the_binding_requirement(
    monkeypatch,
):
    """The other half: shape is fine, but the binding gate must still bite."""

    def _forged(*, identity_name, identity_value=None):
        return {
            "identity_name": "customer_org_id",
            "identity_value": identity_value,
            "role": "customer_surface_alias",
            "shape": "uuid",
            "authority_level": "label",
            "rls_allowed": False,
            "persistence_allowed": True,
            "product_surface_allowed": True,
            "demo_allowed": False,
            "derived_allowed": False,
            "requires_binding": True,
            "blocked_reasons": [],
        }

    monkeypatch.setattr(safety, "describe_identity_role", _forged)
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value=UUID_VALUE,
    )
    assert result["rls_compatible"] is True
    assert result["binding_required"] is True
    assert result["write_allowed"] is False, (
        "an outstanding binding requirement must block even an RLS-compatible write"
    )


def test_a_satisfied_binding_still_does_not_let_a_label_carry_the_write(
    monkeypatch,
):
    """The narrowest case, and the one that isolates the binding conjunct.

    Forge a role that is RLS-compatible *and* requires a binding, then supply a
    verified binding. Every other guard falls silent - no blocked reasons, no
    shape problem - so `not binding_required` is the only thing left standing.

    The rule it holds: a binding says which organization the label corresponds
    to. The write must then use that organization's id. Writing under the label
    with the binding merely on file leaves a row RLS cannot see.
    """

    def _forged(*, identity_name, identity_value=None):
        return {
            "identity_name": "customer_org_id",
            "identity_value": identity_value,
            "role": "customer_surface_alias",
            "shape": "uuid",
            "authority_level": "label",
            "rls_allowed": False,
            "persistence_allowed": True,
            "product_surface_allowed": True,
            "demo_allowed": False,
            "derived_allowed": False,
            "requires_binding": True,
            "blocked_reasons": [],
        }

    monkeypatch.setattr(safety, "describe_identity_role", _forged)
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value=UUID_VALUE,
        binding=_verified_binding(),
    )
    assert result["binding_present"] is True
    assert result["rls_compatible"] is True
    assert result["blocked_reasons"] == []
    assert result["write_allowed"] is False, (
        "a label never carries the write, however well bound it is"
    )


def test_a_verified_binding_still_requires_an_organization_id_anchor():
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value="org-real-1",
        binding=_verified_binding(),
    )
    assert result["binding_present"] is True
    assert result["rls_compatible"] is False
    assert result["write_allowed"] is False


def test_org_id_cannot_persist_unless_it_is_a_uuid():
    as_string = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="org_id",
        identity_value="operator-org-alpha",
    )
    assert as_string["write_allowed"] is False

    as_uuid = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="org_id",
        identity_value=UUID_VALUE,
    )
    assert as_uuid["write_allowed"] is True
    assert as_uuid["rls_compatible"] is True


def test_organization_id_can_persist():
    """The permission path must be reachable, or every refusal proves nothing."""
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="organization_id",
        identity_value=UUID_VALUE,
    )
    assert result["write_allowed"] is True
    assert result["rls_compatible"] is True
    assert result["cross_tenant_risk"] is False
    assert safety.persistence_safety_invariant_failures(result) == []


def test_a_demo_organization_id_cannot_persist():
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="organization_id",
        identity_value="nf-demo-org-01",
    )
    assert result["write_allowed"] is False
    assert "demo_identity_cannot_persist_customer_data" in result["blocked_reasons"]


def test_an_unknown_persist_operation_is_refused():
    result = safety.evaluate_persistence_safety(
        operation="whatever",
        identity_name="organization_id",
        identity_value=UUID_VALUE,
    )
    assert result["operation"] == "unknown"
    assert result["write_allowed"] is False


def test_a_forged_tenant_id_write_fails_its_invariants():
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="tenant_id",
        identity_value="t-real-1",
    )
    forged = json.loads(json.dumps(result))
    forged["write_allowed"] = True
    failures = safety.persistence_safety_invariant_failures(forged)
    assert "tenant_id_permitted_a_customer_data_write" in failures
    assert "write_permitted_without_an_rls_compatible_identity" in failures


def test_the_safety_matrix_permits_no_label_write():
    matrix = safety.build_persistence_safety_matrix()
    assert matrix["tenant_id_writes_allowed"] == 0
    assert matrix["names_permitted_to_write"] == ["org_id", "organization_id"]
    assert matrix["rows_written"] == 0


def test_the_guard_writes_nothing():
    result = safety.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="organization_id",
        identity_value=UUID_VALUE,
    )
    assert result["rows_written"] == 0
    assert result["persisted"] is False
    assert result["live_fetch_performed"] is False


# ------------------------------------------------- the store decision


def test_the_binding_store_anchors_to_the_rls_authority():
    decision = store.build_binding_store_decision()
    assert decision["recommended_store"] == "new_identity_binding_table"
    assert decision["recommended_primary_key"] == "organization_id"
    assert "organizations.id" in decision["recommended_foreign_keys"]
    assert decision["rls_enforced_by"] == "organization_id"
    assert decision["binding_lookup_key"] == "organization_id"


def test_the_decision_applies_no_migration():
    decision = store.build_binding_store_decision()
    assert decision["requires_migration"] is True
    assert decision["migration_applied"] is False
    assert decision["schema_changed"] is False
    assert decision["rows_written"] == 0


def test_the_migration_is_not_safe_yet_and_says_why():
    decision = store.build_binding_store_decision()
    assert decision["migration_safe_now"] is False
    assert decision["operational_binding_storage_allowed"] is False
    assert "no_customer_auth_so_nobody_can_verify_a_binding" in (
        decision["blocked_reasons"]
    )
    assert store.decision_invariant_failures(decision) == []


def test_the_migration_can_become_safe():
    """A refusal that can never lift is a constant, not a decision."""
    decision = store.build_binding_store_decision(
        rls_authority_confirmed=True,
        customer_auth_live=True,
        customer_persistence_live=True,
        verified_binding_available=True,
        # Gate 113 created the binding table, which made "the decision permits
        # storing" and "there is a table to store into" separable facts. They
        # were one value while no such table could exist.
        database_revision="0029",
    )
    assert decision["migration_safe_now"] is True
    assert decision["migration_applied"] is True
    assert decision["operational_binding_storage_allowed"] is True
    assert store.decision_invariant_failures(decision) == []


def test_storage_is_refused_when_no_database_has_the_migration():
    """Every precondition met, but nothing has created the table."""
    decision = store.build_binding_store_decision(
        rls_authority_confirmed=True,
        customer_auth_live=True,
        customer_persistence_live=True,
        verified_binding_available=True,
    )
    assert decision["migration_defined"] is True
    assert decision["migration_applied"] is False
    assert decision["operational_binding_storage_allowed"] is False
    assert store.decision_invariant_failures(decision) == []


def test_no_store_is_recommended_without_an_rls_authority():
    decision = store.build_binding_store_decision(rls_authority_confirmed=False)
    assert decision["recommended_store"] == "unknown"
    assert decision["migration_safe_now"] is False


def test_a_store_keyed_on_a_label_fails_its_invariants():
    forged = store.build_binding_store_decision()
    forged["recommended_primary_key"] = "tenant_id"
    forged["binding_lookup_key"] = "tenant_id"
    failures = store.decision_invariant_failures(forged)
    assert "recommended_primary_key_is_a_label_not_an_authority:tenant_id" in failures
    assert "binding_lookup_key_is_a_label_not_an_authority:tenant_id" in failures


def test_demo_bindings_are_never_stored():
    decision = store.build_binding_store_decision()
    assert decision["demo_binding_storage_allowed"] is False


def test_migration_safety_is_derived_not_declared():
    """Tampered onto a blocked decision, where flipping it changes the answer."""
    forged = store.build_binding_store_decision()
    assert forged["migration_safe_now"] is False
    forged["migration_safe_now"] = True
    assert "migration_safe_now_disagrees_with_the_measurements" in (
        store.decision_invariant_failures(forged)
    )


def test_migration_safety_cannot_be_falsely_denied():
    """The inverse tamper is caught too, so the flag tracks the measurements."""
    forged = store.build_binding_store_decision(
        rls_authority_confirmed=True,
        customer_auth_live=True,
        customer_persistence_live=True,
        verified_binding_available=True,
    )
    assert forged["migration_safe_now"] is True
    forged["migration_safe_now"] = False
    assert "migration_safe_now_disagrees_with_the_measurements" in (
        store.decision_invariant_failures(forged)
    )


def test_operational_storage_cannot_outrun_migration_safety():
    forged = store.build_binding_store_decision()
    forged["operational_binding_storage_allowed"] = True
    assert "operational_storage_permitted_before_migration_is_safe" in (
        store.decision_invariant_failures(forged)
    )


# ------------------------------------------------- readiness


def test_operational_awarded_tracking_remains_false():
    result = awarded_readiness.build_awarded_requirements_readiness()
    assert result["ready_for_operational_awarded_tracking"] is False
    assert result["ready_for_demo_contract"] is True


def test_operational_digest_remains_false():
    result = digest_readiness.build_digest_readiness()
    assert result["ready_for_operational_digest"] is False
    assert result["ready_for_demo_preview"] is True


def test_beta_onboarding_remains_false():
    result = beta_readiness.build_tenant_beta_readiness()
    assert result["ready_for_beta_onboarding"] is False
    assert result["ready_for_demo"] is True
    assert result["customer_auth_live"] is False
    assert result["customer_persistence_live"] is False


# ------------------------------------------------- artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    art.write_canonicalization_artifacts(repo_root=tmp_path / "a")
    art.write_canonicalization_artifacts(repo_root=tmp_path / "b")
    for name in (
        "org_identity_role_contract.json",
        "org_identity_role_matrix.csv",
        "binding_store_decision.json",
        "identity_persistence_safety_matrix.csv",
        "org_identity_readiness_summary.md",
    ):
        first = (tmp_path / "a" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        second = (tmp_path / "b" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert first == second


def test_committed_artifacts_match_fresh_generation(tmp_path):
    art.write_canonicalization_artifacts(repo_root=tmp_path)
    for name in (
        "org_identity_role_contract.json",
        "org_identity_role_matrix.csv",
        "binding_store_decision.json",
        "identity_persistence_safety_matrix.csv",
        "org_identity_readiness_summary.md",
    ):
        fresh = (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_the_role_contract_artifact_states_the_required_facts():
    payload = json.loads(
        (
            REPO_ROOT / art.ARTIFACT_DIR / "org_identity_role_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["organization_id_is_rls_authority"] is True
    assert payload["binding_store_decision_available"] is True
    for key in (
        "tenant_id_is_rls_authority",
        "demo_tenant_ids_rls_allowed",
        "migration_applied",
        "customer_persistence_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        assert payload[key] is False


def test_the_role_matrix_artifact_grants_tenant_id_nothing():
    path = REPO_ROOT / art.ARTIFACT_DIR / "org_identity_role_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["identity_name"] == "tenant_id":
            assert row["rls_allowed"] == "false"
            assert row["persistence_allowed"] == "false"
            assert row["requires_binding"] == "true"


def test_the_safety_matrix_artifact_permits_only_the_authority_and_its_alias():
    path = REPO_ROOT / art.ARTIFACT_DIR / "identity_persistence_safety_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["write_allowed"] == "true":
            assert row["identity_name"] in {"organization_id", "org_id"}
            assert row["identity_shape"] == "uuid"
            assert row["rls_compatible"] == "true"


def test_the_store_decision_artifact_applies_nothing():
    payload = json.loads(
        (REPO_ROOT / art.ARTIFACT_DIR / "binding_store_decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["migration_applied"] is False
    assert payload["schema_changed"] is False
    assert payload["rows_written"] == 0
    assert payload["recommended_primary_key"] == "organization_id"


def test_the_summary_states_the_authority_and_the_refusals():
    text = (
        REPO_ROOT / art.ARTIFACT_DIR / "org_identity_readiness_summary.md"
    ).read_text(encoding="utf-8")
    assert "current_setting('app.current_org_id', true)::uuid" in text
    for line in (
        "tenant_id_is_rls_authority",
        "demo_tenant_ids_rls_allowed",
        "migration_applied",
        "customer_persistence_live",
        "beta_onboarding_ready",
    ):
        assert line in text


def test_artifact_invariants_pass():
    declaration = art.build_canonicalization_declaration()
    assert art.canonicalization_artifact_invariant_failures(declaration) == []
