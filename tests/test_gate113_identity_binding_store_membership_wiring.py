"""Gate 113: identity binding store, and membership wired to organization_id.

Two things happen in this gate and the tests keep them apart on purpose.

The store is new: a table, a contract service, a readiness surface, fixtures and
artifacts. The membership wiring is a *fix*: ``lookup_membership`` took a
parameter named ``organization_profile_id`` and bound it to a UUID column, and
the tests that exercised it supplied ``"org-profile-1"`` — so the defect was
encoded in the test fixture as well as the code.

The tests below therefore assert two different kinds of thing: that the store
refuses what it should, and that a profile-shaped string can no longer reach a
UUID predicate without being named.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from nativeforge.services import identity_persistence_safety_guard_service as guard
from nativeforge.services import (
    postgres_membership_directory_service as pg,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_artifact_service as art,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_decision_service as decision_svc,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_readiness_service as readiness_svc,
)
from nativeforge.services import tenant_customer_org_binding_store_service as store
from nativeforge.services.membership_directory_service import (
    InMemoryMembershipDirectory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ORG = "00000000-0000-4000-8000-000000000113"
OTHER_ORG = "00000000-0000-4000-8000-000000000114"
VERIFIER = "00000000-0000-4000-8000-0000000001b1"
PROFILE_ID = "nf-demo-org-profile-113"
VERIFIED_AT = "2026-08-29T00:00:00Z"


def _verified_record(**overrides):
    record = {
        "organization_id": ORG,
        "tenant_id": "t-113",
        "customer_org_id": "c-113",
        "binding_status": "verified_binding",
        "binding_source": "admin_verified",
        "verified_by_identity_id": VERIFIER,
        "verified_at": VERIFIED_AT,
    }
    record.update(overrides)
    return store.build_binding_record(**record)


# ------------------------------------------------- the migration


def test_the_binding_migration_applies_and_reverses_on_a_real_database():
    """0029 up and down against SQLite, from an empty database.

    Run through alembic itself rather than by calling upgrade() directly, so a
    revision id that does not chain onto 0028 fails here rather than in a
    deployment.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "gate113.db"
        env = {
            "PATH": "/usr/bin:/bin",
            "DATABASE_URL": f"sqlite:///{db}",
            "HOME": tmp,
        }
        up = subprocess.run(
            [".venv/bin/alembic", "upgrade", "head"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert up.returncode == 0, up.stderr

        import sqlite3

        with sqlite3.connect(db) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert store.STORE_TABLE in tables
            # The whole point: the table exists and holds nothing.
            count = conn.execute(f"SELECT count(*) FROM {store.STORE_TABLE}").fetchone()
            assert count[0] == 0

        down = subprocess.run(
            [".venv/bin/alembic", "downgrade", "0028"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert down.returncode == 0, down.stderr

        with sqlite3.connect(db) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert store.STORE_TABLE not in tables


def test_the_migrations_check_constraints_match_the_service_vocabulary():
    """A CHECK constraint cannot import Python, so the two are written twice.

    This is the test that keeps them from drifting.
    """
    module: dict = {}
    path = (
        REPO_ROOT / "alembic" / "versions" / "0029_nf_tenant_customer_org_bindings.py"
    )
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module)

    from nativeforge.services.tenant_customer_org_identity_binding_service import (
        BINDING_SOURCES,
        BINDING_STATUSES,
    )

    assert set(module["BINDING_STATUSES"]) == set(BINDING_STATUSES)
    assert set(module["BINDING_SOURCES"]) == set(BINDING_SOURCES)


def test_the_labels_carry_no_foreign_key():
    """tenant_id and customer_org_id are text columns and nothing more.

    A foreign key on either would make it an identity space by accident, which
    is precisely what Gates 109-112 exist to prevent.
    """
    body = (
        REPO_ROOT / "alembic" / "versions" / "0029_nf_tenant_customer_org_bindings.py"
    ).read_text(encoding="utf-8")
    for label in ("tenant_id", "customer_org_id"):
        start = body.index(f'sa.Column("{label}"')
        # To the start of the next column, so the whole definition is in view.
        column = body[start : body.index("sa.Column(", start + 10)]
        assert "ForeignKey" not in column, f"{label} acquired a foreign key"
        assert "sa.Text()" in column, column

    # And the anchor does carry one, which is what makes it the anchor.
    anchor = body[body.index('sa.Column(\n            "organization_id"') :]
    anchor = anchor[: anchor.index("sa.Column(", 10)]
    assert 'sa.ForeignKey("organizations.id"' in anchor


# ------------------------------------------------- membership wiring


def test_lookup_membership_refuses_a_profile_shaped_organization():
    """The defect this gate fixes, stated as a test.

    A configured directory whose row source would answer anything is handed a
    profile-shaped value. It must never reach the query - against Postgres the
    ``::uuid`` cast would raise inside a request handler.
    """
    reached: list[dict] = []

    def row_source(sql, params):
        reached.append(params)
        return ({"id": "mem-1", "organization_id": ORG},)

    directory = pg.PostgresMembershipDirectory(
        row_source=row_source, database_url_present=True
    )
    # Both are required, and both are supplied here deliberately: an
    # unconfigured directory returns None before the predicate is reached, which
    # is one of the two masks that hid this defect until now.
    assert directory.configured

    refused = directory.lookup_membership(
        identity_id="id-1", organization_id="org-profile-1"
    )
    assert refused is None
    assert reached == [], "a profile-shaped value reached the organization_id query"

    allowed = directory.lookup_membership(identity_id="id-1", organization_id=ORG)
    assert allowed is not None
    assert reached and reached[0]["org"] == ORG


def test_lookup_membership_no_longer_accepts_the_old_parameter_name():
    """The rename is the fix; keeping the old name as an alias would preserve it."""
    directory = pg.PostgresMembershipDirectory(
        row_source=lambda sql, params: (), database_url_present=True
    )
    with pytest.raises(TypeError):
        directory.lookup_membership(
            identity_id="id-1", organization_profile_id="org-profile-1"
        )


def test_a_profile_id_supplied_to_the_resolver_is_named_not_coerced():
    identity = {"issuer": "iss", "subject": "sub", "verification_trusted": True}
    result = pg.resolve_persisted_membership(
        identity=identity, organization_profile_id="org-profile-1"
    )
    assert result["allowed"] is False
    assert (
        "organization_profile_id_is_not_an_organization_id"
        in result["blocked_reasons"]
    )
    assert result["organization_id"] is None


def test_a_uuid_under_the_deprecated_name_is_accepted_and_flagged():
    """An organization id wearing the wrong label is still an organization id.

    Refusing it outright would break callers for no safety gain; accepting it
    silently would hide that they are still using the old name.
    """
    identity = {"issuer": "iss", "subject": "sub", "verification_trusted": True}
    result = pg.resolve_persisted_membership(
        identity=identity, organization_profile_id=ORG
    )
    assert (
        "organization_supplied_under_the_deprecated_parameter"
        in result["blocked_reasons"]
    )
    assert result["organization_id"] == ORG


def test_the_audit_event_records_the_organization_that_reached_the_lookup():
    """An audit trail naming the wrong identity is this gate's own defect class."""
    identity = {"issuer": "iss", "subject": "sub", "verification_trusted": True}
    result = pg.resolve_persisted_membership(identity=identity, organization_id=ORG)
    event = result["audit_event"]
    assert event, "a denial produced no audit event"
    assert event["organization_id"] == ORG


def test_the_in_memory_directory_accepts_either_organization_key():
    """Profile keying is correct here: a dict, no UUID column, no RLS.

    Gate 113 added the ``organization_id`` name for vocabulary agreement, and
    changing the keying would have broken Gate 61 for no safety gain.
    """
    directory = InMemoryMembershipDirectory()
    directory.put(
        {
            "subject": "sub-1",
            "organization_profile_id": "org-aaaa",
            "state": "active",
            "role": "grant_lead",
            "membership_source": "org_owner_approved",
            "role_source": "membership_record",
        }
    )
    by_profile = directory.lookup(subject="sub-1", organization_profile_id="org-aaaa")
    by_org = directory.lookup(subject="sub-1", organization_id="org-aaaa")
    assert by_profile == by_org
    assert by_profile is not None


# ------------------------------------------------- the store


def test_only_organization_id_may_anchor_a_stored_binding():
    for name, value in (
        ("tenant_id", "t-113"),
        ("customer_org_id", "c-113"),
        ("organization_profile_id", PROFILE_ID),
    ):
        record = store.build_binding_record(
            **{name: value},
            binding_status="verified_binding",
            binding_source="admin_verified",
            verified_by_identity_id=VERIFIER,
            verified_at=VERIFIED_AT,
        )
        assert record["storage_allowed"] is False, name
        assert record["blocked_reasons"], f"{name} refused without a reason"
        assert record["rls_anchor"] == "organization_id"


def test_a_verified_binding_without_a_verifier_is_refused():
    record = _verified_record(verified_by_identity_id=None, verified_at=None)
    assert record["storage_allowed"] is False
    assert "verified_binding_without_a_verifier_identity" in record["blocked_reasons"]


def test_a_demo_binding_cannot_be_verified_however_it_is_labelled():
    """The adversarial case: demo and verified asked for at once.

    A demo row that carried a verifier would be a production verification living
    in the demo scope, and the schema's ck_nf_binding_demo_has_no_verifier
    refuses the same combination one layer down.
    """
    record = store.build_binding_record(
        organization_id=ORG,
        tenant_id="t-113",
        customer_org_id="c-113",
        binding_status="verified_binding",
        binding_source="admin_verified",
        verified_by_identity_id=VERIFIER,
        verified_at=VERIFIED_AT,
        is_demo=True,
        demo_label="nf-demo",
    )
    assert record["storage_allowed"] is False
    assert record["blocked_reasons"]


def test_revocation_preserves_the_record():
    revoked = store.revoke_binding(
        record=_verified_record(),
        revoked_by_identity_id=VERIFIER,
        revoked_at=VERIFIED_AT,
    )
    assert revoked["binding_status"] == "revoked"
    assert revoked["rows_deleted"] == 0
    assert revoked["history_preserved"] is True
    assert revoked["write_allowed"] is False


def test_a_profile_id_cannot_read_the_store():
    refused = store.read_bindings_for_organization(organization_id=PROFILE_ID)
    assert refused["read_allowed"] is False
    assert refused["blocked_reasons"]


def test_the_store_invariants_catch_a_forged_record():
    forged = dict(_verified_record())
    forged["rls_anchor"] = "tenant_id"
    assert store.binding_store_invariant_failures(forged)


# ------------------------------------------------- detected migration state


def test_the_migration_state_is_detected_not_declared():
    """It was a hard-coded ``migration_applied: False`` before this gate.

    That constant was accidentally correct while no migration and no database
    existed. It would have become a lie the moment 0029 landed.
    """
    live = decision_svc.build_binding_store_decision()
    assert live["migration_defined"] is True
    assert live["migration_revision"] == "0029"
    assert live["migration_applied"] is False

    with tempfile.TemporaryDirectory() as tmp:
        empty = decision_svc.build_binding_store_decision(versions_dir=Path(tmp))
        assert empty["migration_defined"] is False
        assert empty["migration_revision"] is None


def test_a_database_at_the_revision_reports_the_migration_applied():
    applied = decision_svc.build_binding_store_decision(database_revision="0029")
    assert applied["migration_applied"] is True

    behind = decision_svc.build_binding_store_decision(database_revision="0028")
    assert behind["migration_applied"] is False


def test_creating_the_table_permits_no_storage_by_itself():
    """The claim this gate must not let anybody make.

    Every precondition Gate 110 named is still unmet, and a CREATE TABLE
    addresses none of them: nobody can authenticate, so nobody can be a
    verifier; there is nowhere to persist; and no verified binding exists.
    """
    applied = decision_svc.build_binding_store_decision(database_revision="0029")
    assert applied["migration_applied"] is True
    assert applied["operational_binding_storage_allowed"] is False
    for reason in (
        "no_customer_auth_so_nobody_can_verify_a_binding",
        "no_customer_persistence_to_write_a_binding_into",
        "no_verified_binding_exists_to_store",
    ):
        assert reason in applied["blocked_reasons"]
    assert decision_svc.decision_invariant_failures(applied) == []


def test_two_migrations_creating_the_table_is_ambiguity_not_progress():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for name in ("0029_a.py", "0030_b.py"):
            (directory / name).write_text(
                f'op.create_table("{store.STORE_TABLE}")', encoding="utf-8"
            )
        result = decision_svc.build_binding_store_decision(versions_dir=directory)
        assert result["migration_defined"] is False
        assert (
            "multiple_migration_files_create_the_binding_table"
            in result["blocked_reasons"]
        )


def test_a_forged_decision_fails_its_invariants():
    forged = dict(decision_svc.build_binding_store_decision())
    forged["migration_applied"] = True
    forged["migration_defined"] = False
    assert (
        "migration_applied_without_a_defined_migration"
        in decision_svc.decision_invariant_failures(forged)
    )


# ------------------------------------------------- the persistence guard


def test_the_guard_distinguishes_a_stored_binding_from_an_asserted_one():
    from nativeforge.services.tenant_customer_org_identity_binding_service import (
        build_binding,
    )

    contract = build_binding(
        tenant_id="t-113",
        customer_org_id="c-113",
        binding_source="admin_verified",
        requested_status="verified_binding",
        verified_by="admin@example.invalid",
        verified_at="2026-02-01",
    )
    expected = {
        "binding_store_record": _verified_record(),
        "binding_contract_object": contract,
        "caller_asserted": {"binding_status": "verified_binding"},
        "absent": None,
    }
    for provenance, binding in expected.items():
        result = guard.evaluate_persistence_safety(
            operation="awarded_grants_persist",
            identity_name="customer_org_id",
            identity_value="c-113",
            binding=binding,
        )
        assert result["binding_provenance"] == provenance
        assert result["write_allowed"] is False, provenance


def test_a_caller_asserted_binding_is_named_as_such():
    result = guard.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="customer_org_id",
        identity_value="c-113",
        binding={"binding_status": "verified_binding"},
    )
    assert (
        "binding_asserted_by_the_caller_not_derived_or_stored"
        in result["blocked_reasons"]
    )


def test_a_binding_of_any_provenance_still_never_lets_a_label_write():
    for name, value in (("tenant_id", "t-113"), ("customer_org_id", "c-113")):
        result = guard.evaluate_persistence_safety(
            operation="awarded_grants_persist",
            identity_name=name,
            identity_value=value,
            binding=_verified_record(),
        )
        assert result["write_allowed"] is False, name
        assert guard.persistence_safety_invariant_failures(result) == []


def test_only_organization_id_writes_customer_data():
    result = guard.evaluate_persistence_safety(
        operation="awarded_grants_persist",
        identity_name="organization_id",
        identity_value=ORG,
        binding=_verified_record(),
    )
    assert result["write_allowed"] is True
    assert result["binding_provenance"] == "binding_store_record"
    assert guard.persistence_safety_invariant_failures(result) == []


def test_a_forged_provenance_fails_the_guard_invariants():
    result = dict(
        guard.evaluate_persistence_safety(
            operation="awarded_grants_persist",
            identity_name="organization_id",
            identity_value=ORG,
            binding=_verified_record(),
        )
    )
    result["binding_provenance"] = "trust_me"
    assert (
        "binding_provenance_out_of_vocabulary"
        in guard.persistence_safety_invariant_failures(result)
    )


# ------------------------------------------------- readiness


def test_readiness_separates_the_table_existing_from_the_table_being_writable():
    result = readiness_svc.build_binding_store_readiness()
    assert result["store_schema_available"] is True
    assert result["store_contract_available"] is True
    assert result["store_writable"] is False
    assert result["operational_binding_storage_ready"] is False
    assert (
        "no_database_has_applied_the_binding_store_migration"
        in result["blocked_reasons"]
    )
    assert readiness_svc.readiness_invariant_failures(result) == []


def test_readiness_never_reports_demo_storage_ready():
    result = readiness_svc.build_binding_store_readiness(database_revision="0029")
    assert result["store_writable"] is True
    assert result["demo_binding_storage_ready"] is False
    assert result["operational_binding_storage_ready"] is False
    assert readiness_svc.readiness_invariant_failures(result) == []


def test_forged_readiness_fails_its_invariants():
    forged = dict(readiness_svc.build_binding_store_readiness())
    forged["operational_binding_storage_ready"] = True
    fails = readiness_svc.readiness_invariant_failures(forged)
    assert "operational_ready_without:store_writable" in fails
    assert "operational_ready_without_anybody_who_could_verify" in fails


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_store_demo_fixture_set()
    assert fixture["case_count"] == 9
    assert fixture["store_cases_missing"] == []
    assert fixtures.store_demo_invariant_failures(fixture) == []


def test_a_missing_case_is_reported_as_a_coverage_gap():
    """The measurement takes its input, so a shrunken set is observable."""
    short = fixtures.build_demo_store_cases()[:-1]
    covered = fixtures.measure_store_cases(short)
    assert fixtures.REQUIRED_STORE_CASES - covered == {"revoked_binding"}


def test_exactly_one_fixture_case_is_operational():
    """Stored and operational are different columns, and this is why.

    Three cases are storable: the verified binding, a demo binding inside the
    demo scope, and a revoked binding kept for the audit trail. Only the first
    carries any authority.
    """
    fixture = fixtures.build_store_demo_fixture_set()
    assert fixture["storable_case_count"] == 3
    assert fixture["operational_case_count"] == 1
    operational = [row["case"] for row in fixture["rows"] if row["operational"]]
    assert operational == ["verified_binding_with_verifier"]


def test_the_demo_and_revoked_rows_are_stored_and_powerless():
    fixture = fixtures.build_store_demo_fixture_set()
    rows = {row["case"]: row for row in fixture["rows"]}

    demo = rows["demo_fixture_binding"]
    assert demo["storage_allowed"] is True
    assert demo["is_demo"] is True
    assert demo["operational"] is False

    revoked = rows["revoked_binding"]
    assert revoked["storage_allowed"] is True
    assert revoked["write_allowed"] is False
    assert revoked["operational"] is False


def test_the_fixture_set_notices_when_the_store_changes_its_answer():
    fixture = dict(fixtures.build_store_demo_fixture_set())
    assert fixture["cases_disagreeing_with_expectation"] == []
    fixture["cases_disagreeing_with_expectation"] = ["tenant_id_as_anchor"]
    assert (
        "store_disagreed_with_the_fixture:tenant_id_as_anchor"
        in fixtures.store_demo_invariant_failures(fixture)
    )


def test_the_fixture_set_stores_nothing():
    fixture = fixtures.build_store_demo_fixture_set()
    assert fixture["rows_written"] == 0
    assert fixture["persisted"] is False
    assert fixture["real_customer_data"] is False
    assert fixture["customer_persistence_live"] is False


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_five_artifacts_exist():
    for name in (
        "tenant_customer_org_binding_store_contract.json",
        "tenant_customer_org_binding_store_matrix.csv",
        "tenant_customer_org_binding_store_demo_fixtures.json",
        "membership_organization_id_wiring.csv",
        "tenant_customer_org_binding_store_readiness.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_committed_artifacts_match_fresh_generation():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_store_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            committed = _artifact(path.name)
            assert fresh == committed, f"committed artifact is stale: {path.name}"


def test_the_contract_artifact_claims_nothing_it_cannot_support():
    payload = json.loads(_artifact("tenant_customer_org_binding_store_contract.json"))
    assert payload["rows_in_table"] == 0
    assert payload["rls_anchor_column"] == "organization_id"
    for claim in (
        "customer_bindings_stored",
        "customer_auth_live",
        "customer_persistence_live",
        "tenant_id_is_rls_authority",
        "customer_org_id_is_rls_authority",
        "organization_profile_id_is_rls_authority",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "label_columns_have_foreign_keys",
    ):
        assert payload[claim] is False, claim


def test_the_matrix_shows_a_refusal_for_every_forbidden_anchor():
    rows = list(csv.DictReader(io.StringIO(_artifact(
        "tenant_customer_org_binding_store_matrix.csv"
    ))))
    by_case = {row["case"]: row for row in rows}
    for case in (
        "tenant_id_as_anchor",
        "customer_org_id_as_anchor",
        "organization_profile_id_as_anchor",
    ):
        assert by_case[case]["storage_allowed"] == "false"
        assert by_case[case]["blocked_reasons"], f"{case} refused without a reason"


def test_the_wiring_artifact_shows_the_rename():
    wiring = _artifact("membership_organization_id_wiring.csv")
    assert "lookup_membership,organization_id," in wiring
    assert "renamed_by_gate_113" in wiring
    assert "deprecated_by_gate_113" in wiring


def test_the_readiness_summary_leads_with_the_refusals():
    summary = _artifact("tenant_customer_org_binding_store_readiness.md")
    assert "It is empty" in summary
    assert "no database has applied it" in summary
    assert "current_setting('app.current_org_id', true)::uuid" in summary
    for reason in (
        "no_customer_auth_so_nobody_can_verify_a_binding",
        "no_customer_persistence_to_write_a_binding_into",
        "no_verified_binding_exists_to_store",
    ):
        assert reason in summary


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_store_declaration())
    declaration["customer_bindings_stored"] = True
    assert (
        "store_artifact_claimed:customer_bindings_stored"
        in art.store_artifact_invariant_failures(declaration)
    )
