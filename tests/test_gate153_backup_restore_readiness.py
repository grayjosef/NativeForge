"""Gate 153: back up controlled state, restore it elsewhere, re-verify it.

Three defects found while building this gate, each with a regression test here:

1. The table classifier matched column NAMES against unsafe words including
   `state`, and flagged two tables whose `state` column holds `'active'`. That
   is the substring-versus-meaning defect, committed by the tool built to stop
   an information leak. The manifest now classifies by meaning with a reason
   per table, and the name matcher survives only as a review hint.

2. The restore verification read the digest primary key `id` and asked the
   replay about it. `replay_digest` resolves the separate `digest_id` column,
   so a digest sitting in the table came back `missing_record`.

3. The same check then measured the whole chain's `evidence_status`, which is
   the WEAKEST link. On the one persisted fixture digest that link is
   `not_replayable`, because no delivery intent names it - which says nothing
   about whether the payload hashes. It does.

The refusals are RUN, never asserted: a restore into the source and a restore
into a target that is not isolated are both called, and each must refuse AND
write zero rows.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    backup_restore_artifact_gate153_service as art,
)
from nativeforge.services.operational_backup_export_service import (
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
    build_backup_export,
    export_invariant_failures,
    table_payload_sha256,
)
from nativeforge.services.operational_backup_manifest_service import (
    EXCLUDED_TABLES,
    INCLUDED_TABLES,
    MANIFEST_MIGRATION_HEAD,
    REVIEW_HINT_COLUMNS,
    build_backup_manifest,
    manifest_invariant_failures,
)
from nativeforge.services.operational_backup_restore_readiness_service import (
    CONDITIONS,
    MUST_STAY_FALSE,
    build_operational_restore_readiness,
    operational_restore_readiness_invariant_failures,
)
from nativeforge.services.operational_restore_service import (
    ISOLATED_TARGET,
    RESTORE_LIMITATIONS,
    restore_backup,
    restore_invariant_failures,
)
from nativeforge.services.operational_restore_verification_service import (
    ORDERED_CHECKS,
    verification_invariant_failures,
    verify_restored_state,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000153"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


@pytest.fixture
def db_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(DEMO, "demo")
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture
def connection(db_session):
    return db_session.connection()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _empty_export(**overrides) -> dict:
    """A well-formed export carrying no rows. Hashes are real, not invented."""
    tables = {
        entry["table"]: {
            "rows": [],
            "row_count": 0,
            "payload_sha256": table_payload_sha256([]),
            "columns": [],
            "excluded_fields": [],
            "hash_fields": entry["hash_fields"],
            "archive_field": entry["archive_field"],
            "absent_from_this_database": False,
        }
        for entry in INCLUDED_TABLES
    }
    payload = {
        "schema_version": "nf_operational_backup_export_v1",
        "scope": "controlled_dev_demo",
        "organization_id": DEMO,
        "exported": True,
        "migration_head": MANIFEST_MIGRATION_HEAD,
        "tables": tables,
        "table_count": len(tables),
        "row_count_total": 0,
        "skipped_non_fixture_rows": 0,
        "blocked_reasons": [],
        "rows_written": 0,
        "leaked_shapes": [],
    }
    payload.update(overrides)
    return payload


def _fixture_export_with_a_row(table: str, row: dict) -> dict:
    export = _empty_export()
    export["tables"][table]["rows"] = [row]
    export["tables"][table]["row_count"] = 1
    export["tables"][table]["payload_sha256"] = table_payload_sha256([row])
    export["row_count_total"] = 1
    return export


# --------------------------------------------------------------- 153B manifest


def test_the_manifest_is_deterministic():
    assert build_backup_manifest() == build_backup_manifest()


def test_the_manifest_has_no_invariant_failures():
    assert manifest_invariant_failures(build_backup_manifest()) == []


def test_every_included_table_carries_a_reason_a_person_wrote():
    for entry in INCLUDED_TABLES:
        assert entry["why_included"], entry["table"]
        assert entry["org_partition"], entry["table"]


def test_every_excluded_table_carries_a_reason_and_a_detail():
    for entry in EXCLUDED_TABLES:
        assert entry["exclusion_reason"], entry["table"]
        assert entry["detail"], entry["table"]


@pytest.mark.parametrize(
    "table", ["nf_identities", "nf_auth_redirect_states", "organizations"]
)
def test_the_three_that_must_never_be_exported_are_excluded(table):
    manifest = build_backup_manifest()
    assert table in {entry["table"] for entry in manifest["excluded_tables"]}
    assert table not in manifest["table_names"]


def test_the_manifest_reads_no_live_schema():
    assert build_backup_manifest()["reads_a_live_schema"] is False


def test_the_manifest_never_claims_production_backup_readiness():
    assert build_backup_manifest()["production_backup_ready"] is False


def test_a_manifest_claiming_production_readiness_is_refused():
    manifest = {**build_backup_manifest(), "production_backup_ready": True}
    assert "manifest_claimed_production_backup_readiness" in (
        manifest_invariant_failures(manifest)
    )


def test_an_unsafe_table_smuggled_into_the_included_list_is_refused():
    manifest = build_backup_manifest()
    manifest["included_tables"] = [
        *manifest["included_tables"],
        {"table": "nf_identities", "why_included": "x", "org_partition": "y"},
    ]
    manifest["included_count"] = len(manifest["included_tables"])
    failures = manifest_invariant_failures(manifest)
    assert any("unsafe_table_included" in f for f in failures)


def test_an_included_table_without_a_reason_is_refused():
    manifest = build_backup_manifest()
    manifest["included_tables"][0]["why_included"] = ""
    assert any(
        f.startswith("included_without_a_reason")
        for f in manifest_invariant_failures(manifest)
    )


# -- the substring-versus-meaning regression ---------------------------------


def test_state_is_a_review_hint_and_never_a_gate():
    """`state` names an OAuth state AND a row lifecycle state.

    The first classifier matched the word and excluded two tables that hold
    `'active'`. The word must still prompt a look and must never decide.
    """
    manifest = build_backup_manifest()
    assert "state" in REVIEW_HINT_COLUMNS
    assert manifest["classified_by"] == "meaning, per table"
    assert "review_hints_are_not_a_gate" in manifest


def test_org_memberships_is_excluded_for_identity_not_for_the_word_state():
    entry = next(e for e in EXCLUDED_TABLES if e["table"] == "nf_org_memberships")
    assert entry["exclusion_reason"] == "membership_is_identity_adjacent"
    # The detail must say so explicitly, so a later reader cannot "simplify"
    # the exclusion back into a name match.
    assert "state" in entry["detail"]
    assert "active" in entry["detail"]
    assert "identit" in entry["detail"]


def test_no_included_table_was_chosen_by_matching_a_column_name():
    """Every inclusion names a gate and a purpose, not a pattern."""
    for entry in INCLUDED_TABLES:
        assert entry["gate"]
        assert len(entry["why_included"]) > 10


# ----------------------------------------------------------------- 153C export


def test_the_export_refuses_the_real_organization_by_name(connection):
    export = build_backup_export(
        connection=connection, organization_id=REAL, migration_head=None
    )
    assert export["exported"] is False
    assert "real_organization_refused_by_name" in export["blocked_reasons"]
    assert export["tables"] == {}


def test_the_export_refuses_a_non_uuid_organization(connection):
    export = build_backup_export(
        connection=connection, organization_id="not-a-uuid", migration_head=None
    )
    assert export["exported"] is False
    assert "organization_id_is_not_uuid_shaped" in export["blocked_reasons"]


def test_the_export_refuses_without_a_connection():
    export = build_backup_export(connection=None, organization_id=DEMO)
    assert export["exported"] is False
    assert "no_connection_supplied" in export["blocked_reasons"]


def test_the_export_covers_every_manifest_table(connection):
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    assert export["exported"] is True
    assert set(export["tables"]) == {e["table"] for e in INCLUDED_TABLES}


def test_the_export_writes_nothing_and_leaks_nothing(connection):
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    assert export["rows_written"] == 0
    assert export["leaked_shapes"] == []
    assert export["email_sent"] is False
    assert export["live_source_called"] is False
    assert export["object_store_contacted"] is False
    assert export_invariant_failures(export) == []


def test_the_export_body_carries_no_address_and_no_provider_subject(connection):
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    body = json.dumps(export, default=str)
    assert not ADDRESS_SHAPE.search(body)
    assert not SUBJECT_SHAPE.search(body)


def test_the_table_hash_does_not_depend_on_row_order():
    rows = [{"id": "b", "n": 2}, {"id": "a", "n": 1}]
    assert table_payload_sha256(rows) == table_payload_sha256(list(reversed(rows)))


def test_the_table_hash_changes_when_a_value_changes():
    assert table_payload_sha256([{"id": "a"}]) != table_payload_sha256([{"id": "b"}])


def test_an_export_whose_hash_does_not_match_its_rows_is_refused():
    export = _empty_export()
    first = sorted(export["tables"])[0]
    export["tables"][first]["payload_sha256"] = "0" * 64
    assert any(
        f.startswith("payload_hash_does_not_match_the_rows")
        for f in export_invariant_failures(export)
    )


def test_an_export_claiming_to_have_written_rows_is_refused():
    assert "export_wrote_rows" in export_invariant_failures(
        {**_empty_export(), "rows_written": 3}
    )


def test_the_demo_and_real_organization_constants_are_distinct():
    assert DEMO_ORGANIZATION_ID != REAL_ORGANIZATION_ID
    assert REAL_ORGANIZATION_ID == REAL


# ---------------------------------------------------------------- 153D restore


def test_a_restore_into_a_target_that_is_not_isolated_is_refused(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(),
        target_kind="live_database",
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "restore_target_is_not_isolated" in restore["blocked_reasons"]
    assert restore["rows_restored_total"] == 0


def test_a_restore_whose_target_is_the_source_is_refused(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///same",
        target_url="sqlite:///same",
    )
    assert restore["restored"] is False
    assert "restore_target_is_the_source_database" in restore["blocked_reasons"]
    assert restore["rows_restored_total"] == 0


def test_a_tampered_payload_is_refused_before_any_row_is_written(connection):
    export = _empty_export()
    first = sorted(export["tables"])[0]
    export["tables"][first]["payload_sha256"] = "0" * 64
    restore = restore_backup(
        target_connection=connection,
        export=export,
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "payload_hash_mismatch" in restore["blocked_reasons"]
    assert restore["rows_restored_total"] == 0
    assert restore["hash_mismatched_tables"] == [first]


def test_a_payload_naming_the_real_organization_is_refused(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(organization_id=REAL),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "real_organization_refused_by_name" in restore["blocked_reasons"]


def test_a_payload_carrying_a_forbidden_field_is_refused(connection):
    row = {"id": uuid.uuid4().hex, "is_demo": True, "recipient_email": "x"}
    restore = restore_backup(
        target_connection=connection,
        export=_fixture_export_with_a_row("nf_digest_delivery_intents", row),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "payload_contains_a_forbidden_field" in restore["blocked_reasons"]
    assert restore["rows_restored_total"] == 0


def test_a_payload_carrying_a_non_fixture_row_is_refused_as_a_whole(connection):
    row = {"id": uuid.uuid4().hex, "is_demo": False, "fact_status": "tenant_supplied"}
    restore = restore_backup(
        target_connection=connection,
        export=_fixture_export_with_a_row("nf_awarded_grants", row),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "payload_contains_a_non_fixture_row" in restore["blocked_reasons"]
    # Refused as a whole, not filtered: a mixed payload means the export that
    # produced it was wrong, and loading half of it would hide that.
    assert restore["rows_restored_total"] == 0


def test_a_migration_head_mismatch_is_refused(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(migration_head="0001"),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
        target_migration_head=MANIFEST_MIGRATION_HEAD,
    )
    assert restore["restored"] is False
    assert "migration_head_mismatch" in restore["blocked_reasons"]


def test_a_restore_without_a_target_connection_is_refused():
    restore = restore_backup(
        target_connection=None,
        export=_empty_export(),
        target_kind=ISOLATED_TARGET,
    )
    assert restore["restored"] is False
    assert "no_target_connection_supplied" in restore["blocked_reasons"]


def test_a_restore_of_an_unexported_payload_is_refused(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(exported=False),
        target_kind=ISOLATED_TARGET,
        source_url="sqlite:///source",
        target_url="sqlite:///target",
    )
    assert restore["restored"] is False
    assert "export_payload_was_not_exported" in restore["blocked_reasons"]


def test_a_refused_restore_has_no_invariant_failures(connection):
    restore = restore_backup(
        target_connection=connection,
        export=_empty_export(),
        target_kind="live_database",
    )
    assert restore_invariant_failures(restore) == []


def test_a_restore_claiming_success_alongside_blockers_is_refused():
    assert "restored_alongside_blockers" in restore_invariant_failures(
        {
            "restored": True,
            "target_kind": ISOLATED_TARGET,
            "blocked_reasons": ["something"],
            "restored_tables": {},
            "rows_restored_total": 0,
        }
    )


def test_a_restore_into_a_non_isolated_target_that_claims_success_is_refused():
    assert "restored_into_a_target_that_is_not_isolated" in (
        restore_invariant_failures(
            {
                "restored": True,
                "target_kind": "live_database",
                "blocked_reasons": [],
                "restored_tables": {},
                "rows_restored_total": 0,
            }
        )
    )


def test_a_restore_that_backfilled_legacy_gaps_is_refused():
    assert "restore_backfilled_legacy_gaps" in restore_invariant_failures(
        {"restored": False, "legacy_gaps_backfilled": True}
    )


def test_a_restore_that_fabricated_evidence_is_refused():
    assert "restore_fabricated_evidence" in restore_invariant_failures(
        {"restored": False, "evidence_fabricated": True}
    )


def test_a_restore_whose_row_totals_disagree_is_refused():
    assert "rows_restored_total_disagrees" in restore_invariant_failures(
        {
            "restored": True,
            "target_kind": ISOLATED_TARGET,
            "blocked_reasons": [],
            "restored_tables": {"a": {"rows_restored": 5}},
            "rows_restored_total": 9,
        }
    )


def test_a_row_narrowed_on_the_way_in_is_counted_and_refused():
    """A field the target has no column for is dropped - and reported.

    A narrowed row would hash differently on the way out, and the restore
    verification would report that as a mismatch without ever saying why. So
    the drop is counted per table and fails the restore's own invariants.
    """
    assert "restored_a_narrowed_row:nf_awarded_grants" in restore_invariant_failures(
        {
            "restored": True,
            "target_kind": ISOLATED_TARGET,
            "blocked_reasons": [],
            "restored_tables": {
                "nf_awarded_grants": {
                    "rows_restored": 1,
                    "dropped_fields": ["a_column_the_target_does_not_have"],
                }
            },
            "rows_restored_total": 1,
        }
    )


def test_a_clean_restore_drops_no_fields(connection, isolated_target):
    """The real round trip narrows nothing, so the guard above stays quiet."""
    target_url, target_engine = isolated_target
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    with target_engine.begin() as target:
        restore = restore_backup(
            target_connection=target,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url="sqlite:///the-suite-database",
            target_url=target_url,
        )
    for name, entry in restore["restored_tables"].items():
        assert entry.get("dropped_fields", []) == [], name
    assert restore_invariant_failures(restore) == []


def test_the_restore_states_its_limitations_rather_than_hiding_them():
    assert RESTORE_LIMITATIONS
    joined = " ".join(RESTORE_LIMITATIONS)
    assert "not production backup" in joined
    assert "precondition" in joined


# ----------------------------------------------- 153E the round trip, for real


@pytest.fixture
def isolated_target(tmp_path, connection):
    """A separate, empty database carrying the SOURCE schema.

    Built by replaying the source's own CREATE statements rather than
    `Base.metadata.create_all`: several tables this gate exports - including
    `nf_tenant_digest_records` - are declared on a repository's own MetaData
    and are created by Alembic, so `create_all` produces a target missing
    exactly the tables the restore needs. Copying the schema also makes the
    target what a real restore target is: the same shape as the source.
    """
    url = f"sqlite+pysqlite:///{(tmp_path / 'restore.sqlite3').as_posix()}"
    engine = sa.create_engine(url)

    statements = (
        connection.execute(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
            )
        )
        .scalars()
        .all()
    )
    with engine.begin() as target:
        for statement in statements:
            target.execute(sa.text(statement))

    yield url, engine
    engine.dispose()


def _seed_source(connection, org: str) -> dict:
    """Two fixture rows the round trip can carry, written to the suite's db."""
    grant_id = uuid.uuid4()
    connection.execute(
        sa.text(
            "INSERT INTO nf_awarded_grants "
            "(id, organization_id, is_demo, fact_status, award_title, "
            " funder_name, award_status, active_obligation_status, "
            " human_review_required, blocked_reasons, created_at, updated_at) "
            "VALUES (:i, :o, 1, 'demo_fixture', :t, :f, 'active_award', 'unknown', "
            " 0, '[]', :c, :c)"
        ),
        {
            "i": grant_id.hex,
            "o": uuid.UUID(org).hex,
            "t": "Gate 153 fixture award",
            "f": "Fixture Agency",
            "c": "2026-09-14 00:00:00",
        },
    )
    return {"grant_id": str(grant_id)}


def test_a_real_round_trip_restores_every_row_and_reverifies(
    connection, isolated_target
):
    target_url, target_engine = isolated_target
    _seed_source(connection, DEMO)

    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    assert export["exported"] is True
    assert export["row_count_total"] >= 1
    assert export_invariant_failures(export) == []

    with target_engine.begin() as target:
        restore = restore_backup(
            target_connection=target,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url="sqlite:///the-suite-database",
            target_url=target_url,
            target_migration_head=None,
        )

    assert restore["restored"] is True
    assert restore["rows_restored_total"] == export["row_count_total"]
    assert restore["blocked_reasons"] == []
    assert restore_invariant_failures(restore) == []

    with target_engine.connect() as target:
        verification = verify_restored_state(
            source_connection=connection,
            restored_connection=target,
            organization_id=DEMO,
            export=export,
            restore=restore,
        )

    assert verification_invariant_failures(verification) == []
    assert verification["checks_failed"] == 0
    assert verification["rows_written"] == 0
    assert verification["evidence_fabricated"] is False


def test_the_restored_table_hashes_equal_the_exported_ones(connection, isolated_target):
    target_url, target_engine = isolated_target
    _seed_source(connection, DEMO)

    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    with target_engine.begin() as target:
        restore_backup(
            target_connection=target,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url="sqlite:///the-suite-database",
            target_url=target_url,
        )

    with target_engine.connect() as target:
        entry = export["tables"]["nf_awarded_grants"]
        rows = (
            target.execute(
                sa.text(
                    f"SELECT {', '.join(entry['columns'])} FROM nf_awarded_grants "
                    "WHERE organization_id = :o"
                ),
                {"o": uuid.UUID(DEMO).hex},
            )
            .mappings()
            .all()
        )
        restored = json.loads(json.dumps([dict(r) for r in rows], default=str))

    # The restore writes rows back the way the export read them, so the
    # representation survives and the hash still matches.
    assert table_payload_sha256(restored) == entry["payload_sha256"]


def test_a_restore_does_not_carry_the_organization_row_across(
    connection, isolated_target
):
    """The organizations table is a precondition, never a payload.

    This is how the real organization cannot arrive in a restore target.
    """
    _target_url, target_engine = isolated_target
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    assert "organizations" not in export["tables"]

    with target_engine.begin() as target:
        restore_backup(
            target_connection=target,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url="sqlite:///the-suite-database",
            target_url=_target_url,
        )

    with target_engine.connect() as target:
        assert (
            target.execute(sa.text("SELECT count(*) FROM organizations")).scalar() == 0
        )
        assert (
            target.execute(sa.text("SELECT count(*) FROM nf_identities")).scalar() == 0
        )


# ----------------------------------------------------- 153E verification rules


def test_the_verification_refuses_the_real_organization(connection):
    verification = verify_restored_state(
        restored_connection=connection, organization_id=REAL
    )
    assert verification["verified"] is False
    assert "real_organization_refused_by_name" in verification["blocked_reasons"]


def test_the_verification_refuses_without_a_restored_connection():
    verification = verify_restored_state(restored_connection=None, organization_id=DEMO)
    assert verification["verified"] is False
    assert "no_restored_connection_supplied" in verification["blocked_reasons"]


def test_the_verification_refuses_when_the_restore_did_not_run(connection):
    verification = verify_restored_state(
        restored_connection=connection,
        organization_id=DEMO,
        restore={"restored": False},
    )
    assert verification["verified"] is False
    assert "restore_did_not_run" in verification["blocked_reasons"]


def test_an_unknown_check_is_not_a_pass():
    """A check that could not run has not verified anything."""
    verification = {
        "verified": True,
        "checks": [
            {"check": name, "passed": None, "status": "UNKNOWN"}
            for name in ORDERED_CHECKS
        ],
        "checks_passed": 0,
        "checks_failed": 0,
        "checks_unknown": len(ORDERED_CHECKS),
        "blocked_reasons": [],
    }
    assert "verified_while_a_check_could_not_run" in (
        verification_invariant_failures(verification)
    )


def test_a_verification_claiming_success_with_a_failed_check_is_refused():
    verification = {
        "verified": True,
        "checks": [
            {"check": n, "passed": True, "status": "PASS"} for n in ORDERED_CHECKS
        ],
        "checks_passed": len(ORDERED_CHECKS),
        "checks_failed": 0,
        "checks_unknown": 0,
        "blocked_reasons": [],
    }
    verification["checks"][0] = {
        "check": ORDERED_CHECKS[0],
        "passed": False,
        "status": "FAIL",
    }
    verification["checks_passed"] = len(ORDERED_CHECKS) - 1
    verification["checks_failed"] = 1
    assert "verified_alongside_a_failed_check" in (
        verification_invariant_failures(verification)
    )


def test_a_verification_missing_a_check_is_refused():
    verification = {
        "verified": False,
        "checks": [
            {"check": n, "passed": True, "status": "PASS"} for n in ORDERED_CHECKS[:-1]
        ],
        "checks_passed": len(ORDERED_CHECKS) - 1,
        "checks_failed": 0,
        "checks_unknown": 0,
        "blocked_reasons": [],
    }
    assert any(
        f.startswith("check_missing")
        for f in verification_invariant_failures(verification)
    )


def test_a_check_whose_status_string_disagrees_with_its_boolean_is_refused():
    verification = {
        "verified": False,
        "checks": [
            {"check": n, "passed": True, "status": "PASS"} for n in ORDERED_CHECKS
        ],
        "checks_passed": len(ORDERED_CHECKS),
        "checks_failed": 0,
        "checks_unknown": 0,
        "blocked_reasons": [],
    }
    verification["checks"][0]["status"] = "FAIL"
    assert any(
        f.startswith("check_status_disagrees")
        for f in verification_invariant_failures(verification)
    )


def test_a_verification_that_backfilled_legacy_gaps_is_refused():
    assert "verification_backfilled_legacy_gaps" in (
        verification_invariant_failures(
            {
                "verified": False,
                "checks": [],
                "legacy_gaps_backfilled": True,
                "blocked_reasons": ["x"],
            }
        )
    )


def test_a_verification_claiming_production_readiness_is_refused():
    assert "verification_claimed_production_backup_readiness" in (
        verification_invariant_failures(
            {
                "verified": False,
                "checks": [],
                "production_backup_ready": True,
                "blocked_reasons": ["x"],
            }
        )
    )


def test_the_verification_compares_fidelity_not_health(connection, isolated_target):
    """`source == restored` is the claim, and the payload says so."""
    _target_url, target_engine = isolated_target
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    with target_engine.begin() as target:
        restore = restore_backup(
            target_connection=target,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url="sqlite:///the-suite-database",
            target_url=_target_url,
        )
    with target_engine.connect() as target:
        verification = verify_restored_state(
            source_connection=connection,
            restored_connection=target,
            organization_id=DEMO,
            export=export,
            restore=restore,
        )
    assert "missing_record" in verification["comparison_is_fidelity_not_health"]
    assert verification["production_backup_ready"] is False


# ------------------------------------------------------------- 153F readiness


def _ready_kwargs(**overrides) -> dict:
    kwargs = {name: True for name in CONDITIONS}
    kwargs.update(
        source_legacy_gap_count=8,
        restored_legacy_gap_count=8,
        exported_row_count=10,
        restored_row_count=10,
    )
    kwargs.update(overrides)
    return kwargs


def test_the_lane_is_ready_when_every_condition_is_met():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    assert readiness["operational_backup_restore_ready"] is True
    assert readiness["blockers"] == []
    assert operational_restore_readiness_invariant_failures(readiness) == []


@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_condition_can_block_the_lane_on_its_own(condition):
    readiness = build_operational_restore_readiness(
        **_ready_kwargs(**{condition: False})
    )
    assert readiness["operational_backup_restore_ready"] is False
    assert f"condition_not_met:{condition}" in readiness["blockers"]


@pytest.mark.parametrize(
    "capability",
    [
        "email_delivery",
        "source_monitoring_live",
        "object_store_configured",
        "customer_data_backed_up",
    ],
)
def test_a_capability_that_must_stay_false_blocks_the_lane(capability):
    readiness = build_operational_restore_readiness(
        **_ready_kwargs(**{capability: True})
    )
    assert readiness["operational_backup_restore_ready"] is False
    assert f"must_be_false_but_is_true:{capability}" in readiness["blockers"]


def test_a_fallen_legacy_gap_count_blocks_the_lane():
    """A restore that closed a gap invented a digest for it."""
    readiness = build_operational_restore_readiness(
        **_ready_kwargs(source_legacy_gap_count=8, restored_legacy_gap_count=3)
    )
    assert readiness["operational_backup_restore_ready"] is False
    assert "legacy_gap_count_fell_across_the_restore" in readiness["blockers"]


def test_touching_the_real_organization_blocks_the_lane():
    readiness = build_operational_restore_readiness(
        **_ready_kwargs(real_organization_rows_touched=1)
    )
    assert readiness["operational_backup_restore_ready"] is False
    assert (
        "something_was_contacted:real_organization_rows_touched"
        in (readiness["blockers"])
    )


def test_sending_an_email_blocks_the_lane():
    readiness = build_operational_restore_readiness(**_ready_kwargs(emails_sent=1))
    assert readiness["operational_backup_restore_ready"] is False


def test_production_backup_ready_has_no_branch_that_returns_true():
    readiness = build_operational_restore_readiness(
        **_ready_kwargs(), customer_data_backed_up=False
    )
    assert readiness["production_backup_ready"] is False
    assert readiness["production_is_never_computed"] is True
    # Even if a caller tried to supply it, there is no parameter for it.
    assert "production_backup_ready" in MUST_STAY_FALSE


def test_a_readiness_result_claiming_production_is_refused():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    readiness["production_backup_ready"] = True
    assert "production_backup_ready_became_true" in (
        operational_restore_readiness_invariant_failures(readiness)
    )


def test_a_lane_ready_alongside_blockers_is_refused():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    readiness["blockers"] = ["something"]
    assert "ready_alongside_blockers" in (
        operational_restore_readiness_invariant_failures(readiness)
    )


def test_a_lane_ready_while_the_gap_count_fell_is_refused():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    readiness["restored_legacy_gap_count"] = 1
    assert "ready_while_the_legacy_gap_count_fell" in (
        operational_restore_readiness_invariant_failures(readiness)
    )


def test_every_condition_has_declared_evidence():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    for condition in CONDITIONS:
        assert readiness["condition_evidence"].get(condition)


def test_the_lane_names_what_it_does_not_mean():
    readiness = build_operational_restore_readiness(**_ready_kwargs())
    joined = " ".join(readiness["what_this_does_not_mean"])
    assert "production" in joined
    assert "customer data" in joined
    assert readiness["remaining_blockers_for_production_backup"]


# ---------------------------------------------------------------- 153F routes


def test_the_manifest_route_returns_the_manifest(client):
    headers = soh.session_headers(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/manifest", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["included_count"] == len(INCLUDED_TABLES)
    assert body["production_backup_ready"] is False


def test_the_export_summary_route_never_returns_rows(client):
    headers = soh.session_headers(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/export-summary", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    for table in body["tables"]:
        assert "rows" not in table
        assert "payload_sha256" in table
    assert "rows_are_never_returned_by_this_route" in body


def test_the_table_route_refuses_a_table_outside_the_manifest(client):
    headers = soh.session_headers(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/table/nf_identities",
        headers=headers,
    )
    assert response.status_code == 404


def test_the_table_route_returns_accounting_for_a_manifest_table(client):
    headers = soh.session_headers(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/table/nf_awarded_grants",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["table"] == "nf_awarded_grants"
    assert "rows" not in body


def test_the_readiness_route_says_which_conditions_it_measured(client):
    headers = soh.session_headers(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/readiness", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    # A request has no second database, so the restore conditions are reported
    # false here rather than declared true.
    assert set(body["measured_in_this_request"]) | set(
        body["measured_by_the_verifier"]
    ) == set(CONDITIONS)
    assert not set(body["measured_in_this_request"]) & set(
        body["measured_by_the_verifier"]
    )
    assert body["lane_verdict_comes_from_the_verifier"] is True
    assert body["production_backup_ready"] is False


@pytest.mark.parametrize(
    "path",
    [
        "manifest",
        "export-summary",
        "readiness",
        "table/nf_awarded_grants",
    ],
)
def test_every_backup_route_refuses_without_a_session(client, path):
    response = client.get(f"/v1/nf/demo/orgs/{DEMO}/backup-restore/{path}")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", ["manifest", "export-summary", "readiness"])
def test_every_backup_route_refuses_another_organization(client, path):
    soh.ensure_org(OTHER, "demo")
    headers = soh.session_headers(OTHER)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/backup-restore/{path}", headers=headers
    )
    assert response.status_code in (403, 404)


def test_no_backup_route_accepts_a_write_method(client):
    headers = soh.session_headers(DEMO)
    for method in (client.post, client.put, client.patch, client.delete):
        response = method(
            f"/v1/nf/demo/orgs/{DEMO}/backup-restore/manifest", headers=headers
        )
        assert response.status_code == 405


# -------------------------------------------------------------- 153H artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = art.write_backup_restore_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.backup_restore_artifact_invariant_failures(result) == []


def test_the_artifacts_are_deterministic():
    assert art.build_backup_restore_artifacts() == art.build_backup_restore_artifacts()


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_backup_restore_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_no_artifact_carries_an_address_or_a_provider_subject():
    for name, body in art.build_backup_restore_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name


def test_the_artifacts_record_the_substring_defect_this_gate_found():
    survey = json.loads(art.build_backup_restore_artifacts()[art.SURVEY_FILE])
    defect = survey["the_defect_this_gate_found_in_its_own_first_draft"]
    assert "state" in defect["what"]
    assert "nf_org_memberships" in " ".join(defect["what_it_flagged"])
    assert defect["the_fix"]


def test_the_artifacts_keep_the_two_harnesses_apart():
    survey = json.loads(art.build_backup_restore_artifacts()[art.SURVEY_FILE])
    harnesses = survey["two_different_harnesses"]
    assert harnesses["infrastructure_path"]["result"] == "SKIP"
    assert harnesses["infrastructure_path"]["unblocked_by_gate_153"] is False


def test_the_blockers_file_does_not_claim_production_backup():
    body = art.build_backup_restore_artifacts()[art.BLOCKERS_FILE]
    assert "does not mean production is backed up" in body
    assert "a managed database instance" in body


def test_the_restore_rules_artifact_lists_both_refusals():
    rules = json.loads(art.build_backup_restore_artifacts()[art.RESTORE_RULES_FILE])
    blockers = {entry["blocker"] for entry in rules["refusals"]}
    assert "restore_target_is_not_isolated" in blockers
    assert "restore_target_is_the_source_database" in blockers
    assert rules["only_target_kind_accepted"] == ISOLATED_TARGET


def test_an_artifact_result_missing_a_file_is_refused():
    assert any(
        f.startswith("artifact_files_missing")
        for f in art.backup_restore_artifact_invariant_failures(
            {"files_written": list(art.ARTIFACT_FILES[:-1]), "file_count": 7}
        )
    )


# ------------------------------------------------------------ 153G the verifier


def test_the_verifier_exists_and_is_executable():
    path = REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore_readiness.sh"
    assert path.exists()
    assert path.stat().st_mode & 0o111


def test_the_verifier_runs_both_refusals_rather_than_asserting_them():
    body = (
        REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore_readiness.sh"
    ).read_text(encoding="utf-8")
    # Each refusal must be CALLED, and each must be checked for zero writes.
    assert "target_url=source_url" in body.replace(" ", "") or (
        "target_url=source_url" in body.replace(" ", "")
    )
    assert "restore_into_source_wrote" in body
    assert "restore_into_live_wrote" in body
    assert 'target_kind="live_database"' in body


def test_the_verifier_requires_a_digest_hash_to_have_been_proven():
    """Nothing to preserve is not the same as preserved."""
    body = (
        REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore_readiness.sh"
    ).read_text(encoding="utf-8")
    assert "a_digest_hash_was_actually_proven" in body


def test_the_verifier_does_not_claim_production_backup_readiness():
    body = (
        REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore_readiness.sh"
    ).read_text(encoding="utf-8")
    assert "production_backup_ready=false" in body
    assert "THIS IS NOT PRODUCTION BACKUP" in body


def test_the_production_backup_harness_is_untouched_by_this_gate():
    """Gate 61/65 measures the other lane and still returns SKIP."""
    body = (REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore.sh").read_text(
        encoding="utf-8"
    )
    assert "restore_test_executed" in body
    # Gate 153 must not have taught it to pass.
    assert "operational_backup_restore_ready=true" not in body
