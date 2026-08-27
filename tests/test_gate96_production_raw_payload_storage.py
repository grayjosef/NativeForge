"""Gate 96 - production raw payload storage.

Alembic 0028 adds a metadata table. No body store exists. These tests hold the
distinction: a table existing is not production storage being live, and no
combination of inputs can make the derived flags say it is.

Nothing here fetches, activates a collector, or writes a response body.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from nativeforge.db.session import SessionLocal
from nativeforge.services.phase1_collector_activation_policy_service import (
    PHASE1_SOURCE_IDS,
    build_phase1_activation_matrix,
    default_phase1_preflights,
    policy_invariant_failures,
)
from nativeforge.services.production_raw_payload_repository_service import (
    TABLE_NAME,
    ProductionPayloadRepositoryError,
    build_repository_decision,
    detect_metadata_table,
    persist_payload_metadata,
    repository_invariant_failures,
)
from nativeforge.services.raw_payload_body_store_contract_service import (
    BODY_STORE_MODES,
    NON_PRODUCTION_MODES,
    PRODUCTION_CAPABLE_MODES,
    REQUIRED_GUARANTEES,
    REQUIRED_SETTINGS,
    body_store_invariant_failures,
    build_body_store_contract,
    detect_body_store_mode,
    mode_is_production_capable,
)
from nativeforge.services.raw_payload_evidence_model_service import (
    build_payload_evidence,
)
from nativeforge.services.raw_payload_production_readiness_artifact_service import (
    ARTIFACT_DIR,
    BODY_STORE_JSON_NAME,
    MIGRATION_PATH,
    READINESS_CSV_NAME,
    READINESS_JSON_NAME,
    REQUIRED_DECLARATIONS,
    SCHEMA_JSON_NAME,
    SUMMARY_NAME,
    ProductionReadinessArtifactError,
    artifact_claim_failures,
    build_readiness_bundle,
    read_migration_schema,
    render_readiness_summary,
    write_readiness_artifacts,
)
from nativeforge.services.raw_payload_production_readiness_service import (
    REQUIRED_COMPONENTS,
    build_production_readiness,
    production_readiness_invariant_failures,
)
from nativeforge.services.source_activation_preflight_service import (
    COLLECTION_INTENTS,
    INTENT_STORE_REQUIREMENT,
    build_activation_preflight,
    detect_store_implementation,
    preflight_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

BODY_HASH = "a" * 64
BODY_REF = f"bodies/aa/{BODY_HASH}.bin"
RETRIEVED_AT = "2026-08-27T05:30:00Z"

REQUIRED_COLUMNS = (
    "id", "payload_id", "source_id", "source_name", "source_type", "collector_id",
    "retrieved_at", "retrieval_method", "request_method", "request_url",
    "request_fingerprint", "canonical_url", "response_status",
    "response_headers_hash", "response_body_hash", "response_body_size_bytes",
    "content_type", "raw_payload_ref", "redaction_status", "secret_scan_status",
    "terms_status", "attribution_required", "parser_status", "promotion_status",
    "retention_policy", "created_from_live_fetch", "created_from_fixture",
    "blocked_reasons_json", "metadata_json", "created_at", "updated_at",
)

ALL_SATISFIED: dict[str, Any] = dict(
    terms_status="NO_REVIEW_REQUIRED",
    legal_review_status="not_required",
    credential_status="not_required",
    attribution_status="not_required",
    user_agent_status="not_required",
    rate_limit_status="policy_declared",
    storage_status="contract_satisfied",
    scheduler_status="policy_declared",
    monitoring_status="not_started",
)


def _evidence(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        source_id="grants_gov_daily_extract",
        retrieved_at=RETRIEVED_AT,
        response_body_hash=BODY_HASH,
        raw_payload_ref=BODY_REF,
        request_fingerprint="GET extract 20260827",
        secret_scan_status="clean",
        redaction_status="not_required",
        terms_status="NO_REVIEW_REQUIRED",
        parser_status="not_started",
        created_from_fixture=True,
    )
    base.update(overrides)
    return build_payload_evidence(**base)


def _insert_row(session: Any, **overrides: Any) -> None:
    row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "payload_id": f"p-{uuid.uuid4()}",
        "source_id": "s",
        "retrieved_at": "2026-08-27T00:00:00",
        "retrieval_method": "fixture",
        "request_method": "GET",
        "response_body_hash": BODY_HASH,
        "raw_payload_ref": BODY_REF,
        "redaction_status": "not_required",
        "secret_scan_status": "clean",
        "terms_status": "NO_REVIEW_REQUIRED",
        "parser_status": "not_started",
        "promotion_status": "quarantine",
        "retention_policy": "retain_indefinite",
        "created_from_live_fetch": 0,
        "created_from_fixture": 1,
    }
    row.update(overrides)
    columns = ", ".join(row)
    placeholders = ", ".join(f":{k}" for k in row)
    session.execute(
        text(f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"), row
    )


# --------------------------------------------------------------------------
# 96B - the migration
# --------------------------------------------------------------------------


def test_migration_0028_exists() -> None:
    path = REPO_ROOT / MIGRATION_PATH
    assert path.exists()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assigned = {
        node.target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert isinstance(assigned["revision"], ast.Constant)
    assert assigned["revision"].value == "0028"
    assert assigned["down_revision"].value == "0027"


def test_migration_applied_locally_and_table_exists() -> None:
    """conftest runs alembic upgrade head before collection."""
    with SessionLocal() as session:
        assert TABLE_NAME in inspect(session.get_bind()).get_table_names()


def test_table_has_every_required_column() -> None:
    with SessionLocal() as session:
        columns = {
            c["name"] for c in inspect(session.get_bind()).get_columns(TABLE_NAME)
        }
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    assert missing == [], missing


def test_table_stores_no_response_body_column() -> None:
    """A 78 MB Grants.gov extract is not a database row."""
    with SessionLocal() as session:
        columns = {
            c["name"] for c in inspect(session.get_bind()).get_columns(TABLE_NAME)
        }
    for forbidden in ("response_body", "raw_body", "body", "payload_body", "content"):
        assert forbidden not in columns
    assert "raw_payload_ref" in columns


def test_payload_id_is_unique() -> None:
    with SessionLocal() as session:
        uniques = inspect(session.get_bind()).get_unique_constraints(TABLE_NAME)
    names = {u["name"] for u in uniques}
    columns = [tuple(u["column_names"]) for u in uniques]
    assert "uq_nf_raw_source_payloads_payload_id" in names
    assert ("payload_id",) in columns


def test_payload_id_uniqueness_is_enforced() -> None:
    with SessionLocal() as session:
        shared = f"p-dup-{uuid.uuid4()}"
        _insert_row(session, payload_id=shared)
        with pytest.raises(IntegrityError):
            _insert_row(session, payload_id=shared)
        session.rollback()


@pytest.mark.parametrize(
    "index_name",
    [
        "ix_nf_raw_source_payloads_source_id",
        "ix_nf_raw_source_payloads_collector_id",
        "ix_nf_raw_source_payloads_retrieved_at",
        "ix_nf_raw_source_payloads_response_body_hash",
        "ix_nf_raw_source_payloads_promotion_status",
    ],
)
def test_required_index_exists(index_name: str) -> None:
    with SessionLocal() as session:
        indexes = {
            i["name"] for i in inspect(session.get_bind()).get_indexes(TABLE_NAME)
        }
    assert index_name in indexes


def test_check_constraint_prevents_live_and_fixture_both_true() -> None:
    """Gate 88's finding made unrepresentable at the storage layer."""
    with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            _insert_row(session, created_from_live_fetch=1, created_from_fixture=1)
        session.rollback()


def test_neither_provenance_is_permitted_at_the_db_layer() -> None:
    """The DB constraint is exclusivity; 'unstated' is caught by the model."""
    with SessionLocal() as session:
        _insert_row(session, created_from_live_fetch=0, created_from_fixture=0)
        session.rollback()


def test_promoted_row_requires_a_clean_scan_in_sql() -> None:
    """Enforced in the DB too - a row written around the service is the case
    a database constraint exists for."""
    with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            _insert_row(
                session,
                promotion_status="evidence_ready",
                secret_scan_status="findings_blocked",
            )
        session.rollback()


@pytest.mark.parametrize(
    "column,value",
    [
        ("redaction_status", "probably_fine"),
        ("secret_scan_status", "looks_ok"),
        ("parser_status", "sort_of_parsed"),
        ("promotion_status", "definitely_ready"),
        ("retention_policy", "forever_ish"),
    ],
)
def test_status_vocabularies_are_enforced_in_sql(column: str, value: str) -> None:
    with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            _insert_row(session, **{column: value})
        session.rollback()


def test_table_is_not_foreign_keyed_to_the_source_registry() -> None:
    """None of the 381 v2 registry rows is in nf_opportunity_sources yet, and
    evidence must outlive its registry entry."""
    with SessionLocal() as session:
        fks = inspect(session.get_bind()).get_foreign_keys(TABLE_NAME)
    referred = {fk.get("referred_table") for fk in fks}
    assert "nf_opportunity_sources" not in referred


# --------------------------------------------------------------------------
# 96C - the repository
# --------------------------------------------------------------------------


def test_repository_detects_the_metadata_table() -> None:
    assert detect_metadata_table() is True
    with SessionLocal() as session:
        assert detect_metadata_table(session) is True


def test_repository_writes_metadata_only() -> None:
    decision = build_repository_decision(payload=_evidence())
    assert decision["metadata_write_allowed"] is True
    assert decision["body_write_allowed"] is False
    assert decision["bodies_written"] == 0
    assert repository_invariant_failures(decision) == []


def test_repository_refuses_a_body_request() -> None:
    decision = build_repository_decision(payload=_evidence(), store_body=True)
    assert decision["metadata_write_allowed"] is False
    assert "repository_stores_metadata_only" in decision["blocked_reasons"]

    with pytest.raises(ProductionPayloadRepositoryError, match="metadata only"):
        persist_payload_metadata(payload=_evidence(), store_body=True)


def test_repository_refuses_findings_blocked() -> None:
    decision = build_repository_decision(
        payload=_evidence(secret_scan_status="findings_blocked")
    )
    assert decision["promotion_allowed"] is False
    assert any("secret_scan_not_clean" in r for r in decision["blocked_reasons"])


def test_repository_refuses_terms_review_required() -> None:
    decision = build_repository_decision(
        payload=_evidence(terms_status="TERMS_REVIEW_REQUIRED")
    )
    assert decision["promotion_allowed"] is False
    assert any("terms_status_blocks" in r for r in decision["blocked_reasons"])


def test_repository_refuses_human_review_only() -> None:
    decision = build_repository_decision(
        payload=_evidence(terms_status="HUMAN_REVIEW_ONLY")
    )
    assert decision["promotion_allowed"] is False
    assert decision["human_review_required"] is True
    assert repository_invariant_failures(decision) == []


def test_repository_refuses_evidence_ready_without_a_body_store() -> None:
    """A row saying evidence_ready asserts the bytes are retrievable."""
    decision = build_repository_decision(payload=_evidence())
    assert decision["production_body_store_available"] is False
    assert decision["promotion_allowed"] is False
    assert decision["resolved_promotion_status"] == "quarantine"
    assert "evidence_ready_requires_a_configured_body_store" in (
        decision["blocked_reasons"]
    )


def test_repository_defaults_to_dry_run() -> None:
    result = persist_payload_metadata(payload=_evidence())
    assert result["repository_status"] == "dry_run"
    assert result["rows_written"] == 0


def test_repository_writes_quarantined_metadata_when_asked() -> None:
    """Recording that a payload exists and is not yet usable is the point of
    quarantine."""
    payload = _evidence(payload_id=f"p-write-{uuid.uuid4()}")
    with SessionLocal() as session:
        result = persist_payload_metadata(
            payload=payload, session=session, dry_run=False
        )
        assert result["repository_status"] == "written"
        assert result["rows_written"] == 1
        assert result["bodies_written"] == 0

        stored = session.execute(
            text(
                f"SELECT promotion_status FROM {TABLE_NAME} WHERE payload_id = :p"
            ),
            {"p": payload["payload_id"]},
        ).scalar_one()
        assert stored == "quarantine"
        session.rollback()


def test_repository_never_claims_production_storage_live() -> None:
    decision = build_repository_decision(payload=_evidence())
    assert decision["production_storage_live"] is False
    assert decision["collector_activated"] is False
    assert decision["fetch_performed"] is False


def test_repository_invariant_catches_a_faked_promotion() -> None:
    decision = build_repository_decision(payload=_evidence())
    lying = dict(decision, promotion_allowed=True)
    fails = repository_invariant_failures(lying)
    assert "promotion_allowed_without_a_body_store" in fails


# --------------------------------------------------------------------------
# 96D - the body store contract
# --------------------------------------------------------------------------


def test_body_store_defaults_to_unconfigured() -> None:
    assert detect_body_store_mode() == "unconfigured"
    contract = build_body_store_contract()
    assert contract["body_store_configured"] is False
    assert body_store_invariant_failures(contract) == []


def test_body_store_modes_are_the_declared_four() -> None:
    """Gate 97 renamed object_store_required -> s3_compatible_configured.

    A mode should say what *is*, not what is *needed*: reading
    "mode: object_store_required" told you nothing about whether one existed.
    """
    assert BODY_STORE_MODES == frozenset(
        {
            "local_dev_ignored",
            "database_small_payload_only",
            "s3_compatible_configured",
            "unconfigured",
        }
    )
    assert "object_store_required" not in BODY_STORE_MODES


def test_only_s3_compatible_configured_is_production_capable() -> None:
    assert PRODUCTION_CAPABLE_MODES == frozenset({"s3_compatible_configured"})
    assert mode_is_production_capable("s3_compatible_configured") is True
    # The retired name must not still be production-capable by accident.
    assert mode_is_production_capable("object_store_required") is False
    for mode in NON_PRODUCTION_MODES:
        assert mode_is_production_capable(mode) is False


def test_local_dev_ignored_does_not_count_as_production() -> None:
    contract = build_body_store_contract(declared_mode="local_dev_ignored")
    assert contract["body_store_configured"] is False
    assert contract["local_dev_counts_as_production"] is False
    assert "local_dev_ignored" in contract["non_production_modes"]


def test_database_mode_is_not_allowed_for_production() -> None:
    contract = build_body_store_contract(declared_mode="database_small_payload_only")
    assert contract["body_store_configured"] is False
    assert contract["database_mode_allowed_for_production"] is False


def test_a_declared_mode_cannot_override_detection() -> None:
    """The caller says what it believes; the detector says what is true."""
    contract = build_body_store_contract(declared_mode="s3_compatible_configured")
    assert contract["detected_mode"] == "unconfigured"
    assert contract["body_store_configured"] is False
    assert any(
        "declared_mode_does_not_match_detected" in r
        for r in contract["blocked_reasons"]
    )


def test_unknown_declared_mode_falls_back_to_unconfigured() -> None:
    contract = build_body_store_contract(declared_mode="magic_bucket")
    assert contract["declared_mode"] == "unconfigured"


def test_object_store_is_required_for_collection() -> None:
    contract = build_body_store_contract()
    assert contract["object_store_required_for_collection"] is True


def test_body_store_names_what_is_missing() -> None:
    """Gate 97 replaced the installed-SDK check with a settings-value check.

    With an injected-client seam the client arrives at call time, so requiring
    one to be importable would mean body_store_configured could never be true
    however correctly an environment was configured.
    """
    contract = build_body_store_contract()
    assert set(contract["settings_missing"]) == set(REQUIRED_SETTINGS)
    assert contract["placeholder_settings"] == []
    assert contract["body_store_implementation_available"] is True
    assert contract["object_store_sdk_required"] is False
    assert any(
        r.startswith("object_store_settings_missing:")
        for r in contract["blocked_reasons"]
    )


def test_required_guarantees_are_all_four() -> None:
    contract = build_body_store_contract()
    assert contract["required_guarantees"] == list(REQUIRED_GUARANTEES)
    assert len(REQUIRED_GUARANTEES) == 4


def test_faked_body_store_configuration_fails_invariants() -> None:
    contract = build_body_store_contract()
    lying = dict(contract, body_store_configured=True)
    fails = body_store_invariant_failures(lying)
    assert "body_store_configured_disagrees_with_detected_mode" in fails
    assert "non_production_mode_reported_configured:unconfigured" in fails


def test_body_store_contract_stores_nothing() -> None:
    contract = build_body_store_contract()
    assert contract["bodies_stored"] == 0
    assert contract["fetch_performed"] is False


# --------------------------------------------------------------------------
# 96E - production readiness
# --------------------------------------------------------------------------


def test_readiness_reports_metadata_table_available() -> None:
    report = build_production_readiness()
    assert report["metadata_table_available"] is True
    assert report["secret_scan_available"] is True
    assert report["promotion_gate_available"] is True
    assert production_readiness_invariant_failures(report) == []


def test_readiness_reports_body_store_not_configured() -> None:
    report = build_production_readiness()
    assert report["body_store_configured"] is False
    assert report["components_missing"] == ["body_store_configured"]


def test_production_store_remains_unavailable() -> None:
    report = build_production_readiness()
    assert report["production_raw_payload_store_available"] is False
    assert report["production_storage_live"] is False


def test_availability_is_derived_from_every_component() -> None:
    report = build_production_readiness()
    present = set(report["components_present"])
    missing = set(report["components_missing"])
    assert present | missing == set(REQUIRED_COMPONENTS)
    assert not (present & missing)


def test_a_metadata_table_alone_is_not_production_storage() -> None:
    """The whole shape of this gate."""
    report = build_production_readiness()
    assert report["metadata_table_available"] is True
    assert report["production_raw_payload_store_available"] is False


def test_local_store_does_not_count_toward_production() -> None:
    report = build_production_readiness()
    assert report["local_raw_payload_store_available"] is True
    assert report["production_raw_payload_store_available"] is False
    lying = dict(report, production_raw_payload_store_available=True)
    assert "local_store_counted_toward_production_availability" in (
        production_readiness_invariant_failures(lying)
    )


def test_live_is_strictly_stronger_than_available() -> None:
    report = build_production_readiness()
    lying = dict(report, production_storage_live=True)
    fails = production_readiness_invariant_failures(lying)
    assert "live_without_being_available" in fails
    assert "live_with_no_active_collectors" in fails


def test_readiness_names_the_next_actions() -> None:
    report = build_production_readiness()
    assert report["next_required_actions"]
    joined = " ".join(report["next_required_actions"]).lower()
    assert "object store" in joined


def test_readiness_reports_no_monitoring_or_coverage() -> None:
    report = build_production_readiness()
    assert report["collectors_active"] == 0
    assert report["source_monitoring_active"] is False
    assert report["live_fetch_performed"] is False
    assert report["live_source_coverage"] is False


# --------------------------------------------------------------------------
# 96F - activation integration
# --------------------------------------------------------------------------


def test_collection_intents_are_the_declared_two() -> None:
    assert COLLECTION_INTENTS == frozenset({"dry_run", "live_collection"})
    assert INTENT_STORE_REQUIREMENT["live_collection"] == frozenset({"production"})


def test_dry_run_may_use_the_local_store() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        collection_intent="dry_run",
        **ALL_SATISFIED,
    )
    assert result["collection_intent"] == "dry_run"
    assert result["activation_allowed"] is True
    assert preflight_invariant_failures(result) == []


def test_live_collection_requires_the_production_store() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        collection_intent="live_collection",
        **ALL_SATISFIED,
    )
    assert result["activation_allowed"] is False
    assert "store_supports_collection_intent" in result["requirements_missing"]
    assert preflight_invariant_failures(result) == []


def test_unrecognised_intent_falls_back_to_the_lesser_capability() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        collection_intent="whatever",
        **ALL_SATISFIED,
    )
    assert result["collection_intent"] == "dry_run"


def test_live_collection_on_a_local_store_fails_invariants() -> None:
    result = build_activation_preflight(
        source_id="X", collector_type="public_api", **ALL_SATISFIED
    )
    lying = dict(
        result,
        collection_intent="live_collection",
        activation_allowed=True,
        activation_status="activation_allowed",
    )
    assert "live_collection_allowed_on_a_non_production_store" in (
        preflight_invariant_failures(lying)
    )


def test_preflight_distinguishes_local_from_production() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    assert result["local_raw_payload_store_available"] is True
    assert result["production_raw_payload_store_available"] is False
    assert detect_store_implementation() == "local_only"


def test_phase1_matrix_reports_the_table_without_claiming_production() -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["metadata_table_available"] is True
    assert matrix["local_raw_payload_store_available"] is True
    assert matrix["production_raw_payload_store_available"] is False
    assert matrix["live_collection_requires_production_store"] is True
    assert policy_invariant_failures(matrix) == []


def test_metadata_table_may_not_be_treated_as_production_storage() -> None:
    matrix = build_phase1_activation_matrix()
    lying = dict(matrix, production_raw_payload_store_available=True)
    fails = policy_invariant_failures(lying)
    assert "metadata_table_treated_as_production_storage" in fails


def test_phase1_collectors_remain_not_active() -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["collectors_active"] == 0
    assert matrix["monitors_active"] == 0
    for source in matrix["sources"]:
        assert source["collector_status"] == "not_active"


@pytest.mark.parametrize("source_id", list(PHASE1_SOURCE_IDS))
def test_may_fetch_and_schedule_remain_false(source_id: str) -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    source = next(s for s in matrix["sources"] if s["source_id"] == source_id)
    assert source["may_fetch_live_now"] is False
    assert source["may_schedule_monitor"] is False
    assert source["may_surface_customer_data"] is False


# --------------------------------------------------------------------------
# 96G - artifacts
# --------------------------------------------------------------------------

ARTIFACT_NAMES = (
    READINESS_JSON_NAME,
    READINESS_CSV_NAME,
    SCHEMA_JSON_NAME,
    BODY_STORE_JSON_NAME,
    SUMMARY_NAME,
)


def test_schema_artifact_is_read_from_the_migration() -> None:
    """Transcribed schemas drift. This one is parsed."""
    schema = read_migration_schema(repo_root=REPO_ROOT)
    assert schema["migration_present"] is True
    assert schema["table"] == TABLE_NAME
    assert schema["column_count"] == len(REQUIRED_COLUMNS)
    for column in REQUIRED_COLUMNS:
        assert column in schema["columns"], column
    assert len(schema["indexes"]) == 5
    assert schema["stores_response_body"] is False


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_readiness_artifacts(repo_root=first)
    write_readiness_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed_dir = REPO_ROOT / ARTIFACT_DIR
    if not (committed_dir / READINESS_JSON_NAME).exists():
        pytest.skip("readiness artifacts not generated in this tree")
    write_readiness_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        committed = (committed_dir / name).read_bytes()
        assert hashlib.sha256(committed).hexdigest() == hashlib.sha256(
            fresh
        ).hexdigest(), name


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_declares_the_eight_facts(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("readiness artifacts not generated in this tree")

    expected = {
        "metadata_table_available": True,
        "body_store_configured": False,
        "production_raw_payload_store_available": False,
        "production_storage_live": False,
        "live_fetch_performed": False,
        "collectors_active": False,
        "source_monitoring_active": False,
        "live_source_coverage": False,
    }
    raw = path.read_text(encoding="utf-8")
    for key in expected:
        assert key in raw, f"{name} does not state {key}"

    if name.endswith(".json"):
        payload = json.loads(raw)
        for key, value in expected.items():
            assert payload[key] is value, f"{name}: {key}"
    elif name.endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(raw)))
        assert rows
        for row in rows:
            for key, value in expected.items():
                assert row[key] == str(value), f"{name}: {key} is {row[key]!r}"
    else:
        lowered = raw.lower()
        for key, value in expected.items():
            assert f"{key}: {str(value).lower()}" in lowered, f"{name}: {key}"


def test_artifact_writer_refuses_a_banned_phrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nativeforge.services.raw_payload_production_readiness_artifact_service as mod

    monkeypatch.setattr(
        mod,
        "render_readiness_summary",
        lambda bundle: "production storage is live\n"
        + "\n".join(REQUIRED_DECLARATIONS),
    )
    with pytest.raises(ProductionReadinessArtifactError):
        mod.write_readiness_artifacts(repo_root=tmp_path)


def test_artifact_writer_refuses_a_missing_declaration() -> None:
    bundle = build_readiness_bundle(repo_root=REPO_ROOT)
    failures = artifact_claim_failures(bundle, "a summary that declares nothing")
    assert any(f.startswith("required_declaration_missing") for f in failures)


def test_bundle_invariants_all_hold() -> None:
    bundle = build_readiness_bundle(repo_root=REPO_ROOT)
    summary = render_readiness_summary(bundle)
    assert artifact_claim_failures(bundle, summary) == []


def test_no_artifact_contains_a_secret_value() -> None:
    from nativeforge.services.raw_payload_secret_scan_service import (
        scan_payload_for_secrets,
    )

    for name in ARTIFACT_NAMES:
        path = REPO_ROOT / ARTIFACT_DIR / name
        if not path.exists():
            pytest.skip("readiness artifacts not generated in this tree")
        result = scan_payload_for_secrets(body=path.read_text(encoding="utf-8"))
        assert result["clean"] is True, (name, result["by_kind"])


# --------------------------------------------------------------------------
# Cross-cutting
# --------------------------------------------------------------------------

GATE96_SERVICES = (
    "raw_payload_body_store_contract_service",
    "production_raw_payload_repository_service",
    "raw_payload_production_readiness_service",
    "raw_payload_production_readiness_artifact_service",
)


@pytest.mark.parametrize("module_name", GATE96_SERVICES)
def test_gate96_services_import_no_network_library(module_name: str) -> None:
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {"requests", "httpx", "aiohttp", "socket", "urllib3", "boto3"}
    assert not (imported & forbidden), sorted(imported & forbidden)


@pytest.mark.parametrize("module_name", GATE96_SERVICES)
def test_gate96_services_pass_the_gate94_scanner(module_name: str) -> None:
    from nativeforge.services.hermetic_network_enforcement_service import (
        scan_for_network_call_sites,
    )

    report = scan_for_network_call_sites(repo_root=REPO_ROOT)
    offenders = [f for f in report["findings"] if f.get("module") == module_name]
    assert offenders == [], offenders


def test_gate96_outputs_are_json_serialisable() -> None:
    json.dumps(build_body_store_contract())
    json.dumps(build_production_readiness())
    json.dumps(build_repository_decision(payload=_evidence()))
    json.dumps(read_migration_schema(repo_root=REPO_ROOT))
