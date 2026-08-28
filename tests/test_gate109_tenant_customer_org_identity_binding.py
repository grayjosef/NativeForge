"""Gate 109: tenant / customer org identity binding.

Two identifiers meet on the awarded record, row-level security keys on the
organization, and nothing relates them. These tests hold the rule that closes
that gap:

```text
a binding is recorded, never computed
matching strings are not a binding, and neither are matching names
a demo binding is not production verification
```

The failure being prevented is concrete: bind the wrong pair and a Tribe sees
another Tribe's awarded grants.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import awarded_grant_record_service as awarded_record
from nativeforge.services import (
    awarded_grants_requirements_readiness_service as awarded_readiness,
)
from nativeforge.services import tenant_beta_readiness_service as beta_readiness
from nativeforge.services import (
    tenant_customer_org_demo_identity_fixture_service as fx,
)
from nativeforge.services import tenant_customer_org_identity_artifact_service as art
from nativeforge.services import (
    tenant_customer_org_identity_binding_service as binding,
)
from nativeforge.services import (
    tenant_customer_org_resolution_guard_service as guard,
)
from nativeforge.services import (
    tenant_nofo_digest_readiness_service as digest_readiness,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

TENANT = "t-gate109"
ORG = "org-gate109"


def _verified():
    return binding.build_binding(
        tenant_id=TENANT,
        customer_org_id=ORG,
        binding_source="admin_verified",
        requested_status="verified_binding",
        verified_by="admin@example.invalid",
        verified_at="2026-02-01",
    )


def _demo():
    return binding.build_binding(
        tenant_id="nf-demo-tenant-01",
        customer_org_id="nf-demo-org-01",
        binding_source="demo_fixture",
        demo_label=binding.DEMO_LABEL,
    )


def _pending():
    return binding.build_binding(
        tenant_id=TENANT, customer_org_id=ORG, binding_source="human_entered"
    )


def _unbound():
    return binding.build_binding(tenant_id=TENANT, binding_source="human_entered")


def _conflict():
    return binding.build_binding(
        tenant_id="same-value",
        customer_org_id="same-value",
        binding_source="admin_verified",
    )


def _revoked():
    return binding.build_binding(
        tenant_id=TENANT,
        customer_org_id=ORG,
        binding_source="admin_verified",
        revoked=True,
    )


# ------------------------------------------- no silent equivalence


def test_tenant_id_is_not_silently_equivalent_to_customer_org_id():
    """Two ids arriving together is not a statement that they belong together."""
    result = _pending()
    assert result["binding_status"] == "pending_review"
    assert result["is_production_verified"] is False
    assert result["identities_assumed_equivalent"] is False


def test_matching_strings_do_not_create_a_verified_binding():
    """One value cannot be two identity spaces at once."""
    result = _conflict()
    assert result["binding_status"] == "conflict"
    assert result["is_production_verified"] is False
    assert "tenant_id_and_customer_org_id_are_the_same_value" in (
        result["blocked_reasons"]
    )


def test_identical_identifiers_must_be_treated_as_a_conflict():
    forged = _conflict()
    forged["binding_status"] = "verified_binding"
    assert "identical_identifiers_not_treated_as_a_conflict" in (
        binding.binding_invariant_failures(forged)
    )


def test_matching_names_do_not_create_a_binding():
    """Similar-looking identifiers are still two different identity spaces."""
    result = binding.build_binding(
        tenant_id="acme-tribe",
        customer_org_id="acme-tribe-org",
        binding_source="human_entered",
    )
    assert result["binding_status"] == "pending_review"
    assert result["is_production_verified"] is False
    assert result["derived_from_matching_names"] is False


def test_system_inference_is_blocked_rather_than_performed():
    result = binding.build_binding(
        tenant_id=TENANT,
        customer_org_id=ORG,
        binding_source="system_inferred_blocked",
    )
    assert result["binding_status"] == "pending_review"
    assert "system_inference_is_not_a_binding" in result["blocked_reasons"]
    assert result["system_inferred"] is False


def test_no_binding_derives_one_identifier_from_the_other():
    for candidate in (_verified(), _demo(), _pending(), _unbound(), _conflict()):
        assert candidate["derived_from_matching_strings"] is False
        assert candidate["derived_from_matching_names"] is False
        assert candidate["identities_assumed_equivalent"] is False


# ------------------------------------------- verification requirements


def test_a_verified_binding_requires_both_ids_and_an_allowed_source():
    result = _verified()
    assert result["binding_status"] == "verified_binding"
    assert result["is_production_verified"] is True
    assert result["binding_source"] in binding.VERIFYING_SOURCES
    assert binding.binding_invariant_failures(result) == []


def test_a_source_that_cannot_verify_is_demoted_to_pending():
    """human_entered asserts; it does not check."""
    result = binding.build_binding(
        tenant_id=TENANT,
        customer_org_id=ORG,
        binding_source="human_entered",
        requested_status="verified_binding",
        verified_by="someone",
        verified_at="2026-02-01",
    )
    assert result["binding_status"] == "pending_review"
    assert any("source_cannot_verify" in r for r in result["blocked_reasons"])


def test_a_verified_binding_needs_an_actual_verifier():
    result = binding.build_binding(
        tenant_id=TENANT,
        customer_org_id=ORG,
        binding_source="admin_verified",
        requested_status="verified_binding",
    )
    assert result["binding_status"] == "pending_review"
    assert "verified_binding_without_a_verifier" in result["blocked_reasons"]


def test_a_forged_verified_binding_fails_its_invariants():
    forged = _pending()
    forged["binding_status"] = "verified_binding"
    forged["is_production_verified"] = True
    failures = binding.binding_invariant_failures(forged)
    assert "verified_binding_from_a_source_that_cannot_verify" in failures
    assert "verified_binding_without_a_verifier" in failures


def test_a_missing_identifier_leaves_the_pair_unbound():
    result = _unbound()
    assert result["binding_status"] == "unbound"
    assert "binding_without_a_customer_org_id" in result["blocked_reasons"]


# ------------------------------------------- demo bindings


def test_a_demo_binding_is_labelled():
    result = _demo()
    assert result["binding_status"] == "demo_fixture"
    assert result["demo_label"] == binding.DEMO_LABEL
    assert result["is_demo_binding"] is True


def test_an_unlabelled_demo_binding_is_refused():
    result = binding.build_binding(
        tenant_id="nf-demo-tenant-01",
        customer_org_id="nf-demo-org-01",
        binding_source="demo_fixture",
    )
    assert result["binding_status"] == "pending_review"
    assert "demo_binding_without_its_label" in result["blocked_reasons"]


def test_a_demo_binding_is_not_production_verification():
    result = _demo()
    assert result["is_production_verified"] is False
    assert result["binding_confidence"] == "demo_only"


def test_a_demo_binding_cannot_claim_production_verification():
    forged = _demo()
    forged["is_production_verified"] = True
    assert "demo_binding_claimed_production_verification" in (
        binding.binding_invariant_failures(forged)
    )


def test_the_gate51_tenant_id_shape_is_recorded_not_trusted():
    """A derived id is evidence about an org profile, not a verified binding."""
    from nativeforge.services.org_tenant_seat_model_service import make_tenant_id

    derived = make_tenant_id("org-profile-123")
    assert binding.classify_tenant_id_shape(derived) == "gate51_derived"
    assert binding.classify_tenant_id_shape("nf-demo-tenant-01") == "free_form"
    assert binding.classify_tenant_id_shape("") == "absent"

    # Carrying a derived shape does not by itself verify anything.
    asserted = binding.build_binding(
        tenant_id=derived, customer_org_id=ORG, binding_source="human_entered"
    )
    assert asserted["tenant_id_shape"] == "gate51_derived"
    assert asserted["binding_status"] == "pending_review"


# ------------------------------------------- the resolution guard


@pytest.mark.parametrize(
    "operation", sorted(guard.OPERATIONAL_OPERATIONS)
)
def test_unbound_blocks_every_operational_operation(operation):
    result = guard.evaluate_resolution(binding=_unbound(), operation=operation)
    assert result["resolution_allowed"] is False
    assert result["read_allowed"] is False
    assert result["write_allowed"] is False
    assert result["cross_tenant_risk"] is True
    assert guard.resolution_invariant_failures(result) == []


@pytest.mark.parametrize("operation", sorted(guard.WRITE_OPERATIONS))
def test_pending_review_blocks_every_write(operation):
    result = guard.evaluate_resolution(binding=_pending(), operation=operation)
    assert result["write_allowed"] is False
    assert "pending_review_binding_cannot_write" in result["blocked_reasons"]


def test_pending_review_permits_inspection():
    """Inspection is how a pending binding gets checked."""
    result = guard.evaluate_resolution(
        binding=_pending(), operation="awarded_grants_read"
    )
    assert result["read_allowed"] is True
    assert result["write_allowed"] is False


@pytest.mark.parametrize("operation", sorted(guard.OPERATIONAL_OPERATIONS))
def test_conflict_blocks_reads_and_writes(operation):
    result = guard.evaluate_resolution(binding=_conflict(), operation=operation)
    assert result["read_allowed"] is False
    assert result["write_allowed"] is False
    assert result["cross_tenant_risk"] is True


@pytest.mark.parametrize("operation", sorted(guard.OPERATIONAL_OPERATIONS))
def test_revoked_blocks_reads_and_writes(operation):
    result = guard.evaluate_resolution(binding=_revoked(), operation=operation)
    assert result["read_allowed"] is False
    assert result["write_allowed"] is False


def test_a_verified_binding_permits_operational_reads_and_writes():
    read = guard.evaluate_resolution(
        binding=_verified(), operation="awarded_grants_read"
    )
    write = guard.evaluate_resolution(
        binding=_verified(), operation="awarded_grants_write"
    )
    assert read["read_allowed"] is True
    assert write["write_allowed"] is True
    assert read["cross_tenant_risk"] is False
    assert write["cross_tenant_risk"] is False


def test_a_demo_binding_never_reaches_an_operational_surface():
    result = guard.evaluate_resolution(
        binding=_demo(), operation="awarded_grants_read", demo_context=False
    )
    assert result["read_allowed"] is False
    assert result["cross_tenant_risk"] is True
    assert "demo_binding_cannot_reach_an_operational_surface" in (
        result["blocked_reasons"]
    )


def test_a_demo_binding_works_in_a_demo_context():
    """The permission path must be reachable, or the refusals prove nothing."""
    result = guard.evaluate_resolution(
        binding=_demo(), operation="awarded_grants_read", demo_context=True
    )
    assert result["read_allowed"] is True
    assert result["cross_tenant_risk"] is False


def test_cross_tenant_risk_is_true_whenever_binding_is_absent_or_conflicting():
    for candidate in (_unbound(), _conflict(), _revoked(), _pending()):
        result = guard.evaluate_resolution(
            binding=candidate, operation="tenant_digest_read"
        )
        assert result["cross_tenant_risk"] is True
        assert result["human_review_required"] is True


def test_cross_tenant_risk_cannot_be_hidden():
    result = guard.evaluate_resolution(
        binding=_unbound(), operation="awarded_grants_read"
    )
    forged = json.loads(json.dumps(result))
    forged["cross_tenant_risk"] = False
    assert "cross_tenant_risk_disagrees_with_the_measurements" in (
        guard.resolution_invariant_failures(forged)
    )


def test_a_write_cannot_be_permitted_without_a_verified_binding():
    result = guard.evaluate_resolution(
        binding=_pending(), operation="awarded_grants_write"
    )
    forged = json.loads(json.dumps(result))
    forged["write_allowed"] = True
    failures = guard.resolution_invariant_failures(forged)
    assert "pending_review_binding_permitted_a_write" in failures
    assert "write_permitted_without_a_verified_binding" in failures


def test_an_unknown_operation_is_refused():
    result = guard.evaluate_resolution(binding=_verified(), operation="whatever")
    assert result["operation"] == "unknown"
    assert result["resolution_allowed"] is False
    assert "unrecognised_operation" in result["blocked_reasons"]


def test_the_guard_joins_nothing_and_fetches_nothing():
    result = guard.evaluate_resolution(
        binding=_verified(), operation="awarded_grants_read"
    )
    assert result["records_joined"] is False
    assert result["persisted"] is False
    assert result["live_fetch_performed"] is False


# ------------------------------------------- readiness deltas


def test_awarded_operational_readiness_requires_a_verified_binding():
    result = awarded_readiness.build_awarded_requirements_readiness()
    assert result["verified_operational_identity_binding"] is False
    assert result["ready_for_operational_awarded_tracking"] is False
    assert "verified_operational_identity_binding" in (
        result["missing_operational_components"]
    )


def test_awarded_demo_contract_remains_true():
    result = awarded_readiness.build_awarded_requirements_readiness()
    assert result["ready_for_demo_contract"] is True


def test_tenant_digest_operational_readiness_remains_false():
    result = digest_readiness.build_digest_readiness()
    assert result["ready_for_demo_preview"] is True
    assert result["ready_for_operational_digest"] is False
    assert result["verified_operational_identity_binding"] is False


def test_beta_onboarding_readiness_remains_false():
    result = beta_readiness.build_tenant_beta_readiness()
    assert result["ready_for_demo"] is True
    assert result["ready_for_beta_onboarding"] is False
    assert result["verified_operational_identity_binding"] is False
    assert result["customer_auth_live"] is False
    assert result["customer_persistence_live"] is False


def test_an_awarded_record_carries_its_binding_status():
    record = awarded_record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        binding_source="human_entered",
    )
    assert record["tenant_org_binding_status"] == "pending_review"
    assert record["operational_identity_binding_verified"] is False
    assert record["identity_binding"]["binding_status"] == "pending_review"
    assert awarded_record.award_record_invariant_failures(record) == []


def test_an_awarded_record_with_conflicting_ids_reports_conflict():
    record = awarded_record.build_awarded_grant_record(
        tenant_id="same", customer_org_id="same", source_opportunity_id="opp-1"
    )
    assert record["tenant_org_binding_status"] == "conflict"
    assert record["operational_identity_binding_verified"] is False


def test_an_awarded_record_cannot_claim_verification_it_does_not_have():
    record = awarded_record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        binding_source="human_entered",
    )
    forged = json.loads(json.dumps(record))
    forged["operational_identity_binding_verified"] = True
    assert "operational_binding_verification_disagrees_with_the_status" in (
        awarded_record.award_record_invariant_failures(forged)
    )


def test_an_awarded_record_binding_status_must_match_its_binding_record():
    record = awarded_record.build_awarded_grant_record(
        tenant_id=TENANT,
        customer_org_id=ORG,
        source_opportunity_id="opp-1",
        binding_source="human_entered",
    )
    forged = json.loads(json.dumps(record))
    forged["tenant_org_binding_status"] = "demo_fixture"
    assert "binding_status_disagrees_with_the_binding_record" in (
        awarded_record.award_record_invariant_failures(forged)
    )


# ------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_binding_case():
    fixture = fx.build_demo_identity_fixture_set()
    assert fixture["binding_cases_missing"] == []
    assert set(fixture["binding_cases_covered"]) == fx.REQUIRED_BINDING_CASES


def test_every_demo_binding_is_labelled():
    fixture = fx.build_demo_identity_fixture_set()
    assert fixture["fixture_label"] == fx.FIXTURE_LABEL
    for entry in fixture["bindings"]:
        assert entry["fixture_label"] == fx.FIXTURE_LABEL


def test_no_demo_binding_is_production_verified():
    fixture = fx.build_demo_identity_fixture_set()
    assert fixture["production_verified_bindings"] == 0
    for entry in fixture["bindings"]:
        assert entry["is_production_verified"] is False


def test_the_fixture_creates_no_real_records():
    fixture = fx.build_demo_identity_fixture_set()
    assert fixture["real_customer_data"] is False
    assert fixture["real_tenant_records_created"] is False
    assert fixture["real_customer_records_created"] is False
    assert fixture["identities_assumed_equivalent"] is False
    assert fx.demo_identity_invariant_failures(fixture) == []


def test_no_operational_write_is_permitted_anywhere_in_the_fixture():
    fixture = fx.build_demo_identity_fixture_set()
    matrix = fixture["operational_context_matrix"]
    assert matrix["writes_allowed"] == 0


def test_the_fixture_invariant_catches_a_demo_binding_reaching_operations():
    """The check must fire, or its silence proves nothing."""
    fixture = json.loads(json.dumps(fx.build_demo_identity_fixture_set()))
    row = next(
        r
        for r in fixture["operational_context_matrix"]["rows"]
        if r["binding_status"] == "demo_fixture"
    )
    row["read_allowed"] = True
    failures = fx.demo_identity_invariant_failures(fixture)
    assert any(
        f.startswith("demo_binding_permitted_operational_access") for f in failures
    )


def test_binding_case_coverage_is_measured_not_asserted():
    """Feed it a set missing cases and it must notice.

    The real fixture covers everything, so a function returning the full set
    would pass every other assertion here.
    """
    assert fx.measure_binding_cases([]) == set()
    partial = fx.measure_binding_cases(
        [{"binding_status": "unbound"}, {"binding_status": "conflict"}]
    )
    assert partial == {"unbound", "conflict"}
    assert "revoked" not in partial
    assert "demo_fixture" not in partial


def test_the_fixture_invariant_catches_a_missing_case():
    fixture = json.loads(json.dumps(fx.build_demo_identity_fixture_set()))
    fixture["binding_cases_missing"] = ["conflict"]
    assert "binding_case_not_covered:conflict" in (
        fx.demo_identity_invariant_failures(fixture)
    )


# ------------------------------------------- artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    art.write_identity_artifacts(repo_root=tmp_path / "a")
    art.write_identity_artifacts(repo_root=tmp_path / "b")
    for name in (
        "tenant_customer_org_identity_binding_contract.json",
        "tenant_customer_org_identity_matrix.csv",
        "tenant_customer_org_resolution_guard_matrix.csv",
        "tenant_customer_org_demo_bindings.json",
        "tenant_customer_org_readiness_summary.md",
    ):
        first = (tmp_path / "a" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        second = (tmp_path / "b" / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert first == second


def test_committed_artifacts_match_fresh_generation(tmp_path):
    art.write_identity_artifacts(repo_root=tmp_path)
    for name in (
        "tenant_customer_org_identity_binding_contract.json",
        "tenant_customer_org_identity_matrix.csv",
        "tenant_customer_org_resolution_guard_matrix.csv",
        "tenant_customer_org_demo_bindings.json",
        "tenant_customer_org_readiness_summary.md",
    ):
        fresh = (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_the_contract_artifact_states_the_required_facts():
    payload = json.loads(
        (
            REPO_ROOT
            / art.ARTIFACT_DIR
            / "tenant_customer_org_identity_binding_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["identity_binding_contract_available"] is True
    assert payload["demo_fixture_bindings_available"] is True
    for key in (
        "verified_operational_binding_available",
        "customer_persistence_live",
        "customer_auth_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        assert payload[key] is False


def test_the_guard_matrix_artifact_permits_no_operational_write():
    path = (
        REPO_ROOT
        / art.ARTIFACT_DIR
        / "tenant_customer_org_resolution_guard_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        if row["demo_context"] == "false":
            assert row["write_allowed"] == "false"


def test_the_identity_matrix_artifact_verifies_nothing():
    path = REPO_ROOT / art.ARTIFACT_DIR / "tenant_customer_org_identity_matrix.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        assert row["is_production_verified"] == "false"


def test_the_summary_states_no_derivation():
    text = (
        REPO_ROOT / art.ARTIFACT_DIR / "tenant_customer_org_readiness_summary.md"
    ).read_text(encoding="utf-8")
    for line in (
        "identities_assumed_equivalent",
        "tenant_id_derived_from_customer_org_id",
        "customer_org_id_derived_from_tenant_id",
        "beta_onboarding_ready",
        "operational_digest_ready",
    ):
        assert line in text


def test_artifact_invariants_pass():
    declaration = art.build_identity_declaration()
    assert art.identity_artifact_invariant_failures(declaration) == []
