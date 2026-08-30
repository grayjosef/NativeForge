"""Gate 123: tenant beta profile persistence.

A repository for how a tenant wants NativeForge to behave — which is a different
object from who the Tribe is when a form is submitted.

One thing must stay true: **nothing here infers a fact about a real government.**

The tests are grouped by what they would catch:

```text
anchor       a label treated as an RLS authority
inference    a state derived from an address, or a recognition status guessed
lifecycle    a DELETE where an archive belongs
liveness     a repository existing being read as beta onboarding starting
```
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import customer_persistence_capability_service as cap_svc
from nativeforge.services import tenant_beta_profile_service as beta_svc
from nativeforge.services import tenant_beta_readiness_service as beta_readiness
from nativeforge.services import tenant_profile_persistence_artifact_service as art
from nativeforge.services import (
    tenant_profile_persistence_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    tenant_profile_persistence_validation_service as val_svc,
)
from nativeforge.services import tenant_profile_repository_service as repo_svc

ORG = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"
IDENTITY = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def profiles_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.TENANT_BETA_PROFILES.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


def _profile(**overrides):
    kwargs = dict(fixtures.SC_PROFILE)
    kwargs.update(overrides)
    return kwargs


# ------------------------------------------------- the anchor


def test_organization_id_is_required():
    result = repo_svc.prepare_profile_write(**_profile(organization_id=None))
    assert result["storage_allowed"] is False
    assert "profile_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_organization_id_must_be_uuid_shaped():
    """Every RLS policy casts to ::uuid, so anything else cannot be scoped."""
    result = repo_svc.prepare_profile_write(
        **_profile(organization_id="nf-demo-org-profile-114")
    )
    assert result["storage_allowed"] is False
    assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_tenant_id_is_a_label_only():
    result = repo_svc.prepare_profile_write(**_profile())
    assert result["storage_allowed"] is True
    assert result["tenant_id_label"] == fixtures.DEMO_TENANT_LABEL
    assert result["rls_anchor"] == "organization_id"
    # Required, and never the anchor.
    missing = repo_svc.prepare_profile_write(**_profile(tenant_id_label=None))
    assert missing["storage_allowed"] is False
    assert "profile_without_a_tenant_label" in missing["blocked_reasons"]


def test_customer_org_id_is_a_label_only():
    result = repo_svc.prepare_profile_write(**_profile())
    assert result["customer_org_id_label"] == fixtures.DEMO_CUSTOMER_ORG_LABEL
    assert result["rls_anchor"] == "organization_id"
    # Optional: a tenant may have no customer-org label and still be stored.
    without = repo_svc.prepare_profile_write(**_profile(customer_org_id_label=None))
    assert without["storage_allowed"] is True


def test_organization_profile_id_is_refused_as_an_anchor():
    """Gates 110-113: a real value from a real column in the wrong space."""
    result = repo_svc.prepare_profile_write(
        **_profile(), organization_profile_id="nf-demo-fixture-org-profile"
    )
    assert result["storage_allowed"] is False
    assert (
        "organization_profile_id_is_not_an_organization_id_anchor"
        in result["blocked_reasons"]
    )


def test_a_read_is_anchored_on_organization_id(profiles_db):
    repo_svc.upsert_tenant_profile(connection=profiles_db, now=NOW, **_profile())
    other = repo_svc.get_tenant_profile(
        connection=profiles_db, organization_id=str(uuid.uuid4())
    )
    assert other["rows_read"] == 0
    assert "no_tenant_profile_for_this_organization" in other["blocked_reasons"]

    unanchored = repo_svc.get_tenant_profile(connection=profiles_db)
    assert unanchored["rows_read"] == 0
    assert (
        "read_without_a_uuid_shaped_organization_id_anchor"
        in unanchored["blocked_reasons"]
    )


# ------------------------------------------------- inference


def test_an_unknown_recognition_status_stays_unknown():
    result = repo_svc.prepare_profile_write(
        **_profile(
            recognition_status="unknown",
            recognition_status_fact_status="unknown",
        )
    )
    assert result["recognition_status"] == "unknown"
    assert result["human_review_required"] is True
    assert result["storage_allowed"] is True
    assert repo_svc.profile_repository_invariant_failures(result) == []


def test_an_unknown_recognition_status_cannot_claim_an_established_fact():
    result = repo_svc.prepare_profile_write(
        **_profile(
            recognition_status="unknown",
            recognition_status_fact_status="verified",
        )
    )
    assert result["storage_allowed"] is False
    assert (
        "unknown_recognition_status_cannot_carry_an_established_fact_status"
        in result["blocked_reasons"]
    )


def test_the_database_refuses_an_unknown_status_claimed_as_verified(profiles_db):
    """The CHECK is what catches the case this module gets wrong."""
    with pytest.raises(sa.exc.IntegrityError):
        profiles_db.execute(
            sa.insert(repo_svc.TENANT_BETA_PROFILES).values(
                id=uuid.uuid4(),
                organization_id=uuid.UUID(ORG),
                tenant_id_label="t",
                customer_org_id_label=None,
                recognition_status="unknown",
                recognition_status_fact_status="verified",
                operating_states=[],
                operating_states_fact_status="unknown",
                service_area=None,
                applicant_classes=[],
                applicant_classes_fact_status="unknown",
                programs=[],
                departments=[],
                priority_topics=[],
                excluded_topics=[],
                source_watchlist_preferences=[],
                digest_frequency="weekly",
                routing_rules=[],
                custom_alerts=[],
                profile_status="draft",
                created_by_identity_id=None,
                updated_by_identity_id=None,
                archived_at=None,
                is_demo=True,
                human_review_required=True,
                blocked_reasons=[],
                created_at=NOW,
                updated_at=NOW,
            )
        )


def test_missing_operating_states_blocks_state_source_matching():
    result = repo_svc.prepare_profile_write(
        **_profile(operating_states=[], service_area=None)
    )
    assert result["storage_allowed"] is False
    assert (
        "no_operating_states_so_state_matching_is_refused" in result["blocked_reasons"]
    )


def test_operating_states_drives_state_source_matching():
    validation = val_svc.validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="tenant_supplied",
        operating_states=["SC"],
        operating_states_fact_status="tenant_supplied",
        applicant_classes=["state_recognized_tribe"],
        applicant_classes_fact_status="tenant_supplied",
        priority_topics=["housing"],
        digest_frequency="weekly",
        routing_rules=["grants_admin"],
        source_watchlist_preferences=["sc_state_portal"],
    )
    assert validation["state_source_matching_enabled"] is True
    sc = val_svc.matches_state_source(validation=validation, source_state="SC")
    nc = val_svc.matches_state_source(validation=validation, source_state="NC")
    assert sc["matched"] is True
    assert nc["matched"] is False
    assert sc["decided_by"] == "operating_states"
    assert val_svc.validation_invariant_failures(validation) == []


def test_a_mailing_address_does_not_override_operating_states():
    """The case this whole gate turns on."""
    validation = val_svc.validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="tenant_supplied",
        operating_states=[],
        service_area="1 Main Street, Columbia, South Carolina",
        applicant_classes=["state_recognized_tribe"],
        applicant_classes_fact_status="tenant_supplied",
        digest_frequency="weekly",
        routing_rules=["grants_admin"],
    )
    assert validation["state_source_matching_enabled"] is False
    assert validation["operating_states"] == []

    match = val_svc.matches_state_source(validation=validation, source_state="SC")
    assert match["matched"] is False
    assert match["mailing_address_considered"] is False
    assert match["service_area_considered"] is False
    assert "state_source_matching_disabled_for_this_profile" in match["blocked_reasons"]


def test_operating_states_cannot_be_a_delimited_string():
    """A state produced by splitting on a comma is the prohibited inference."""
    result = repo_svc.prepare_profile_write(**_profile(operating_states="SC,NC"))
    assert result["storage_allowed"] is False
    assert (
        "operating_states_must_be_a_list_not_a_delimited_string"
        in result["blocked_reasons"]
    )


def test_a_service_area_without_states_is_refused_rather_than_parsed():
    result = repo_svc.prepare_profile_write(
        **_profile(operating_states=[], service_area="Columbia, South Carolina")
    )
    assert result["storage_allowed"] is False
    assert (
        "service_area_present_without_operating_states_and_none_is_inferred"
        in result["blocked_reasons"]
    )


def test_nothing_reports_an_inference():
    result = repo_svc.prepare_profile_write(**_profile())
    assert result["operating_states_inferred_from_address"] is False
    assert result["recognition_status_inferred"] is False

    validation = val_svc.validate_tenant_profile()
    for flag in (
        "mailing_address_considered",
        "recognition_status_inferred",
        "operating_states_inferred",
        "applicant_class_inferred",
        "priorities_inferred",
    ):
        assert validation[flag] is False, flag


def test_the_prohibited_inferences_are_bridged_not_restated():
    bridged = {item["inference"] for item in repo_svc.prohibited_inferences()}
    declared = {name for name, _ in beta_svc.INFERENCE_PROHIBITED}
    assert bridged == declared
    assert "operating_state_from_mailing_address" in bridged


def test_a_demo_fixture_fact_is_never_actionable():
    """Gate 103's rule: a demo value must not drive a real decision."""
    assert "demo_fixture" not in beta_svc.ACTIONABLE_FACT_STATUSES
    validation = val_svc.validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="demo_fixture",
        operating_states=["SC"],
        operating_states_fact_status="demo_fixture",
        applicant_classes=["state_recognized_tribe"],
        applicant_classes_fact_status="demo_fixture",
        priority_topics=["housing"],
        digest_frequency="weekly",
        routing_rules=["grants_admin"],
        source_watchlist_preferences=["sc_state_portal"],
    )
    assert validation["recognition_status_known"] is False
    assert validation["state_source_matching_enabled"] is False
    assert validation["profile_ready_for_matching"] is False


def test_the_validation_ready_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    validation = val_svc.validate_tenant_profile(
        recognition_status="state_recognized",
        recognition_status_fact_status="verified",
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
    assert validation["profile_ready_for_matching"] is True
    assert validation["human_review_required"] is False
    assert validation["blocked_reasons"] == []
    assert val_svc.validation_invariant_failures(validation) == []


# ------------------------------------------------- production write gates


def test_a_production_write_requires_customer_auth_live():
    result = repo_svc.prepare_profile_write(
        **_profile(is_demo=False), verified_operational_binding=True
    )
    assert result["production_write_allowed"] is False
    assert (
        "production_profile_write_requires_live_customer_auth"
        in result["blocked_reasons"]
    )


def test_a_production_write_requires_a_verified_operational_binding():
    result = repo_svc.prepare_profile_write(
        **_profile(is_demo=False), customer_auth_live=True
    )
    assert result["production_write_allowed"] is False
    assert (
        "production_profile_write_requires_a_verified_operational_binding"
        in result["blocked_reasons"]
    )


def test_the_production_branch_is_reachable_with_both_supplied():
    result = repo_svc.prepare_profile_write(
        **_profile(
            is_demo=False,
            recognition_status_fact_status="tenant_supplied",
            operating_states_fact_status="tenant_supplied",
            applicant_classes_fact_status="tenant_supplied",
        ),
        customer_auth_live=True,
        verified_operational_binding=True,
    )
    assert result["storage_allowed"] is True
    assert result["production_write_allowed"] is True
    assert result["blocked_reasons"] == []
    assert repo_svc.profile_repository_invariant_failures(result) == []


def test_a_demo_fixture_never_claims_a_production_write():
    forged = dict(repo_svc.prepare_profile_write(**_profile()))
    forged["production_write_allowed"] = True
    fails = repo_svc.profile_repository_invariant_failures(forged)
    assert "a_demo_fixture_claimed_a_production_write" in fails


# ------------------------------------------------- lifecycle


def test_archive_retains_the_profile(profiles_db):
    repo_svc.upsert_tenant_profile(connection=profiles_db, now=NOW, **_profile())
    archived = repo_svc.archive_tenant_profile(
        connection=profiles_db,
        organization_id=ORG,
        archived_by_identity_id=IDENTITY,
        now=NOW,
    )
    assert archived["write_performed"] is True
    assert archived["rows_deleted"] == 0

    remaining = profiles_db.execute(
        sa.select(sa.func.count()).select_from(repo_svc.TENANT_BETA_PROFILES)
    ).scalar()
    assert remaining == 1

    listing = repo_svc.list_tenant_profiles(connection=profiles_db, organization_id=ORG)
    assert listing["rows_read"] == 1
    assert listing["archived_count"] == 1


def test_an_archived_profile_stops_being_the_live_one(profiles_db):
    repo_svc.upsert_tenant_profile(connection=profiles_db, now=NOW, **_profile())
    repo_svc.archive_tenant_profile(
        connection=profiles_db,
        organization_id=ORG,
        archived_by_identity_id=IDENTITY,
        now=NOW,
    )
    live = repo_svc.get_tenant_profile(connection=profiles_db, organization_id=ORG)
    assert live["rows_read"] == 0


def test_upsert_archives_the_previous_profile_rather_than_replacing_it(
    profiles_db,
):
    repo_svc.upsert_tenant_profile(connection=profiles_db, now=NOW, **_profile())
    repo_svc.upsert_tenant_profile(
        connection=profiles_db, now=NOW, **_profile(priority_topics=["water"])
    )
    listing = repo_svc.list_tenant_profiles(connection=profiles_db, organization_id=ORG)
    assert listing["rows_read"] == 2
    assert listing["archived_count"] == 1


def test_nothing_in_the_repository_deletes():
    """Parsed, not grepped.

    A substring search finds `sa.delete` in the docstring that explains there
    is no delete path - the same substring-versus-meaning confusion this
    campaign has hit six times. An AST walk sees calls and not prose.
    """
    import ast

    source = Path(
        "src/nativeforge/services/tenant_profile_repository_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    deleting_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "delete"
    ]
    assert deleting_calls == []

    # And the prose that tripped the substring version is still there, so this
    # test would have caught a real delete rather than the explanation of one.
    assert "sa.delete" in source


def test_the_core_table_matches_the_migration_columns():
    migration = Path("alembic/versions/0031_nf_tenant_beta_profiles.py").read_text(
        encoding="utf-8"
    )
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.TENANT_BETA_PROFILES.columns}
    assert mapped == declared


def test_the_core_table_matches_the_migration_check_constraints():
    """Gate 119C's defect: a Core table weaker than the migrated one."""
    migration = Path("alembic/versions/0031_nf_tenant_beta_profiles.py").read_text(
        encoding="utf-8"
    )
    declared = set(re.findall(r'name="(ck_nf_tenant_beta_\w+)"', migration))
    mapped = {
        c.name
        for c in repo_svc.TENANT_BETA_PROFILES.constraints
        if c.name and str(c.name).startswith("ck_nf_tenant_beta")
    }
    assert mapped == declared
    assert len(mapped) == 8


def test_the_migration_restates_gate_103s_vocabularies_exactly():
    """A CHECK constraint cannot import Python, so a test holds them together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mig0031", "alembic/versions/0031_nf_tenant_beta_profiles.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.RECOGNITION_STATUSES) == set(beta_svc.RECOGNITION_STATUSES)
    assert set(module.DIGEST_FREQUENCIES) == set(beta_svc.DIGEST_FREQUENCIES)
    assert set(module.FACT_STATUSES) == set(beta_svc.FACT_STATUSES)


# ------------------------------------------------- readiness


def test_a_repository_does_not_make_beta_onboarding_live():
    readiness = beta_readiness.build_tenant_beta_readiness()
    assert readiness["tenant_beta_profile_repository_available"] is True
    assert readiness["tenant_beta_profile_validation_available"] is True
    assert readiness["tenant_beta_profiles_stored"] == 0
    assert readiness["ready_for_beta_onboarding"] is False
    assert readiness["customer_auth_live"] is False


def test_customer_persistence_stays_false():
    matrix = cap_svc.build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "tenant_profile_persistence"
    )
    assert lane["tenant_beta_profile_repository_available"] is True
    assert lane["tenant_beta_profile_table"] == "nf_tenant_beta_profiles"
    # A second repository does not make the lane operational.
    assert lane["operational"] is False


# ------------------------------------------------- the fixture set


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_tenant_profile_fixture_set()
    assert fixture["case_count"] == 10
    assert fixture["profile_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.tenant_profile_fixture_invariant_failures(fixture) == []


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_profile_cases(
        [{"case": "valid_sc_tribal_tenant_profile"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 9


def test_no_fixture_case_permits_a_production_write():
    fixture = fixtures.build_tenant_profile_fixture_set()
    assert fixture["production_write_count"] == 0
    assert fixture["production_tenant_profiles_created"] == 0
    assert fixture["real_customer_data_written"] == 0
    assert fixture["actual_customer_auth_live"] is False
    for row in fixture["cases"]:
        assert row["production_write_allowed"] is False
        assert row["rows_deleted"] == 0


def test_the_address_case_matches_no_state():
    fixture = fixtures.build_tenant_profile_fixture_set()
    case = next(
        r
        for r in fixture["cases"]
        if r["case"] == "mailing_address_does_not_override_operating_state"
    )
    assert case["sc_source_matched"] is False


def test_the_fixture_set_is_deterministic():
    first = fixtures.build_tenant_profile_fixture_set()
    second = fixtures.build_tenant_profile_fixture_set()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------- the artifacts


def _artifact(name: str) -> str:
    return (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_persistence_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_the_written_set_is_four_files_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_persistence_artifacts(repo_root=tmp)
    assert result["file_count"] == 4
    assert result["credential_fields_found"] == []
    assert result["claimed_inferences_found"] == []
    assert result["configured_secret_values_found"] == []
    assert art.persistence_artifact_invariant_failures(result) == []


def test_the_inference_scanner_can_actually_fire():
    """A scanner that cannot fail proves nothing about the files it passed."""
    planted = {"nested": {"recognition_status_inferred": True}}
    assert art.scan_for_claimed_inferences(planted) == [
        "claimed_inference:recognition_status_inferred"
    ]
    assert art.scan_for_claimed_inferences({"recognition_status_inferred": False}) == []


def test_no_artifact_carries_real_tenant_data():
    for path in Path(art.ARTIFACT_DIR).iterdir():
        text = path.read_text(encoding="utf-8")
        for forbidden in art.FORBIDDEN_VALUE_FIELDS:
            assert f'"{forbidden}":' not in text, f"{forbidden} in {path.name}"


def test_the_writer_refuses_a_claimed_inference(monkeypatch):
    monkeypatch.setattr(
        art,
        "scan_for_claimed_inferences",
        lambda payload: ["claimed_inference:operating_states_inferred"],
    )
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="refusing to write"):
            art.write_persistence_artifacts(repo_root=tmp)
        assert not (Path(tmp) / art.ARTIFACT_DIR).exists()


def test_the_declaration_refuses_every_liveness_claim():
    declaration = art.build_persistence_declaration()
    for claim in (
        "tenant_profile_operational",
        "customer_auth_live",
        "login_live",
        "verified_operational_binding",
        "customer_persistence_live",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "operating_states_inferred_from_address",
        "recognition_status_inferred",
    ):
        assert declaration[claim] is False, claim
    for count in (
        "production_tenant_profiles_created",
        "real_customer_data_written",
        "rows_deleted",
        "rows_in_the_application_database",
    ):
        assert declaration[count] == 0, count
    assert declaration["missing_auth_gates"]
    assert declaration["tenant_beta_profiles_stored"] == 0


def test_the_validation_matrix_has_a_row_per_case():
    import csv as csv_module
    import io as io_module

    text = _artifact("tenant_profile_validation_matrix.csv")
    rows = list(csv_module.DictReader(io_module.StringIO(text)))
    assert list(rows[0]) == list(art.MATRIX_COLUMNS)
    assert len(rows) == len(art.build_validation_cases())
    # The address case reaches no state matching.
    address = next(
        r for r in rows if r["case"] == "service_area_without_operating_states"
    )
    assert address["state_source_matching_enabled"] == "false"
    assert address["profile_ready_for_matching"] == "false"


def test_the_summary_names_the_address_rule():
    text = _artifact("tenant_profile_persistence_readiness_summary.md")
    assert "operating_states" in text
    assert "South Carolina" in text
    assert "customer_auth_live" in text
