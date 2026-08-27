"""Gate 97 - S3-compatible raw payload body store.

The write seam exists and every refusal path is exercised through an injected
fake client. No SDK is imported, no object store is contacted, no credential is
read, and nothing is configured.

The credential tests use synthetic values constructed in this file. None is a
real key, and each is asserted absent from every output it could reach.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from nativeforge.lib.settings import Settings, get_settings
from nativeforge.services.phase1_collector_activation_policy_service import (
    PHASE1_SOURCE_IDS,
    build_phase1_activation_matrix,
    default_phase1_preflights,
    policy_invariant_failures,
)
from nativeforge.services.production_raw_payload_repository_service import (
    build_repository_decision,
    repository_invariant_failures,
)
from nativeforge.services.raw_payload_body_store_contract_service import (
    BODY_STORE_MODES,
    OPTIONAL_SETTINGS,
    PRODUCTION_CAPABLE_MODES,
    REQUIRED_SETTINGS,
    body_store_invariant_failures,
    build_body_store_contract,
    detect_body_store_implementation,
    detect_body_store_mode,
)
from nativeforge.services.raw_payload_body_store_readiness_artifact_service import (
    ARTIFACT_DIR,
    MATRIX_CSV_NAME,
    REQUIRED_DECLARATIONS,
    S3_JSON_NAME,
    SETTINGS_JSON_NAME,
    SUMMARY_NAME,
    BodyStoreReadinessArtifactError,
    artifact_claim_failures,
    build_readiness_bundle,
    render_readiness_summary,
    write_readiness_artifacts,
)
from nativeforge.services.raw_payload_evidence_model_service import (
    build_payload_evidence,
)
from nativeforge.services.raw_payload_production_readiness_service import (
    REQUIRED_COMPONENTS,
    build_production_readiness,
    production_readiness_invariant_failures,
)
from nativeforge.services.raw_payload_secret_scan_service import (
    scan_payload_for_secrets,
)
from nativeforge.services.s3_raw_payload_body_store_service import (
    KEY_NAMESPACE,
    PLACEHOLDER_CREDENTIAL_VALUES,
    BodyStoreError,
    body_hash,
    build_client_config,
    is_placeholder_value,
    object_key_for,
    raw_payload_ref_for,
    store_body,
)
from nativeforge.services.s3_raw_payload_body_store_service import (
    body_store_invariant_failures as s3_invariant_failures,
)
from nativeforge.services.source_activation_preflight_service import (
    build_activation_preflight,
    preflight_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

BODY = '{"opportunityNumber":"HHS-2026-IHS-01","title":"Tribal Health"}'
DIGEST = body_hash(BODY)
BUCKET = "nf-raw-payloads-test"

# Synthetic throughout. Neither is a real credential, and both are asserted
# absent from every output they could reach.
SYNTHETIC_ACCESS_KEY = "AKIA0000SYNTHETIC0000"
SYNTHETIC_SECRET = "synthetic-secret-not-a-real-value-0123456789"

ENV_KEYS = (
    "RAW_PAYLOAD_OBJECT_STORE_ENDPOINT",
    "RAW_PAYLOAD_OBJECT_STORE_BUCKET",
    "RAW_PAYLOAD_OBJECT_STORE_REGION",
    "RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID",
    "RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY",
    "RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE",
)


class FakeObjectStoreClient:
    """Satisfies the one method the store calls. Reaches no network."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ETag": "fake-etag"}


class ExplodingClient:
    def put_object(self, **kwargs: Any) -> Any:
        raise RuntimeError(
            "https://bucket.example/key?X-Amz-Signature=synthetic-signature"
        )


@pytest.fixture(autouse=True)
def _clean_object_store_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    """No test inherits object-store settings from the developer's shell."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    values = {
        "RAW_PAYLOAD_OBJECT_STORE_ENDPOINT": "https://objects.internal.invalid",
        "RAW_PAYLOAD_OBJECT_STORE_BUCKET": BUCKET,
        "RAW_PAYLOAD_OBJECT_STORE_REGION": "us-east-2",
        "RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID": SYNTHETIC_ACCESS_KEY,
        "RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY": SYNTHETIC_SECRET,
    }
    values.update(overrides)
    for key, value in values.items():
        if value == "":
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _evidence(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        source_id="grants_gov_daily_extract",
        retrieved_at="2026-08-27T05:30:00Z",
        response_body_hash=DIGEST,
        raw_payload_ref=f"bodies/{DIGEST[:2]}/{DIGEST}.bin",
        request_fingerprint="GET extract",
        secret_scan_status="clean",
        redaction_status="not_required",
        terms_status="NO_REVIEW_REQUIRED",
        parser_status="not_started",
        created_from_fixture=True,
    )
    base.update(overrides)
    return build_payload_evidence(**base)


# --------------------------------------------------------------------------
# 97B - settings
# --------------------------------------------------------------------------


def test_settings_expose_all_six_object_store_fields() -> None:
    fields = set(Settings.model_fields)
    for name in (*REQUIRED_SETTINGS, *OPTIONAL_SETTINGS):
        assert name in fields, name


def test_missing_settings_mean_unconfigured() -> None:
    assert detect_body_store_mode() == "unconfigured"
    contract = build_body_store_contract()
    assert contract["body_store_configured"] is False
    assert set(contract["settings_missing"]) == set(REQUIRED_SETTINGS)
    assert body_store_invariant_failures(contract) == []


def test_blank_settings_mean_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    assert detect_body_store_mode() == "unconfigured"
    assert build_body_store_contract()["body_store_configured"] is False


def test_a_blank_boolean_setting_does_not_crash_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`FORCE_PATH_STYLE=` in a .env is "leave this alone", not a parse error.

    Without the before-validator, pydantic raises on a blank value and takes
    the whole Settings object - and therefore the app - down over an empty line
    in a config file.
    """
    monkeypatch.setenv("RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE", "")
    get_settings.cache_clear()
    assert get_settings().raw_payload_object_store_force_path_style is False

    monkeypatch.setenv("RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE", "true")
    get_settings.cache_clear()
    assert get_settings().raw_payload_object_store_force_path_style is True


def test_partial_settings_mean_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, RAW_PAYLOAD_OBJECT_STORE_REGION="")
    contract = build_body_store_contract()
    assert contract["body_store_configured"] is False
    assert "raw_payload_object_store_region" in contract["settings_missing"]


@pytest.mark.parametrize(
    "placeholder",
    ["AKIAIOSFODNN7EXAMPLE", "changeme", "your-secret-key", "minioadmin", "<key>"],
)
def test_placeholder_credentials_do_not_count(
    monkeypatch: pytest.MonkeyPatch, placeholder: str
) -> None:
    """AWS's own documentation key is not a production credential."""
    _configure(monkeypatch, RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID=placeholder)
    contract = build_body_store_contract()
    assert contract["body_store_configured"] is False
    assert "raw_payload_object_store_access_key_id" in (
        contract["placeholder_settings"]
    )
    assert body_store_invariant_failures(contract) == []


def test_placeholder_list_is_checked_case_insensitively() -> None:
    assert is_placeholder_value("AKIAIOSFODNN7EXAMPLE") is True
    assert is_placeholder_value("akiaiosfodnn7example") is True
    assert is_placeholder_value("") is True
    assert is_placeholder_value("   ") is True
    assert is_placeholder_value(SYNTHETIC_ACCESS_KEY) is False
    assert len(PLACEHOLDER_CREDENTIAL_VALUES) >= 15


def test_secret_never_appears_in_settings_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    settings = get_settings()
    assert SYNTHETIC_SECRET not in repr(settings)
    assert SYNTHETIC_SECRET not in str(
        settings.raw_payload_object_store_secret_access_key
    )
    assert "**********" in repr(settings.raw_payload_object_store_secret_access_key)


def test_secret_never_appears_in_readiness_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    for payload in (
        build_body_store_contract(),
        build_production_readiness(),
        build_client_config(),
        build_activation_preflight(source_id="X", collector_type="public_api"),
        build_phase1_activation_matrix(),
    ):
        serialised = json.dumps(payload)
        assert SYNTHETIC_SECRET not in serialised
        assert SYNTHETIC_ACCESS_KEY not in serialised


def test_client_config_reports_presence_not_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    config = build_client_config()
    assert config["credential_present"] is True
    assert config["secret_access_key_present"] is True
    assert "secret_access_key" not in config
    assert "credential" not in config
    assert SYNTHETIC_SECRET not in json.dumps(config)
    assert s3_invariant_failures(config) == []


def test_fully_configured_settings_report_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The detector must be able to say yes, or it is not a detector."""
    _configure(monkeypatch)
    assert detect_body_store_mode() == "s3_compatible_configured"
    contract = build_body_store_contract()
    assert contract["body_store_configured"] is True
    assert contract["settings_missing"] == []
    assert contract["placeholder_settings"] == []
    assert body_store_invariant_failures(contract) == []


# --------------------------------------------------------------------------
# 97C - the body store
# --------------------------------------------------------------------------


def test_body_store_implementation_exists() -> None:
    assert detect_body_store_implementation() is True


def test_object_key_is_content_addressed() -> None:
    key = object_key_for(DIGEST)
    assert key == f"{KEY_NAMESPACE}/{DIGEST[:2]}/{DIGEST[2:4]}/{DIGEST}.bin"
    assert DIGEST in key
    # Two levels of prefix: a million objects under one prefix is a hot shard.
    assert key.count("/") == 3


def test_object_key_rejects_a_non_sha256_hash() -> None:
    with pytest.raises(BodyStoreError, match="SHA-256"):
        object_key_for("deadbeef")


def test_ref_carries_the_bucket_and_the_hash() -> None:
    ref = raw_payload_ref_for(bucket=BUCKET, response_body_hash=DIGEST)
    assert ref.startswith(f"s3://{BUCKET}/")
    assert DIGEST in ref


def test_write_refused_by_default() -> None:
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=FakeObjectStoreClient(),
    )
    assert result["body_store_status"] == "refused"
    assert result["write_allowed"] is False
    assert result["raw_payload_ref"] is None
    assert result["bytes_written"] == 0
    assert "write_not_opted_in" in result["blocked_reasons"]
    assert s3_invariant_failures(result) == []


@pytest.mark.parametrize("scan", ["pending", "findings_blocked", "failed", None])
def test_write_refused_when_secret_scan_is_not_clean(scan: str | None) -> None:
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=FakeObjectStoreClient(),
        allow_write=True,
        secret_scan_status=scan,
    )
    assert result["body_store_status"] == "refused"
    assert any("secret_scan_not_clean" in r for r in result["blocked_reasons"])


def test_write_refused_on_hash_mismatch() -> None:
    """Content addressing means nothing if the hash is taken on trust."""
    client = FakeObjectStoreClient()
    result = store_body(
        body=BODY,
        response_body_hash=body_hash("entirely different bytes"),
        bucket=BUCKET,
        client=client,
        allow_write=True,
        secret_scan_status="clean",
    )
    assert result["body_store_status"] == "refused"
    assert "response_body_hash_does_not_match_body" in result["blocked_reasons"]
    assert client.calls == []


def test_write_refused_for_customer_data_by_default() -> None:
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=FakeObjectStoreClient(),
        allow_write=True,
        secret_scan_status="clean",
        contains_customer_data=True,
    )
    assert result["body_store_status"] == "refused"
    assert "customer_data_not_allowed" in result["blocked_reasons"]


def test_write_refused_without_a_bucket() -> None:
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket="",
        client=FakeObjectStoreClient(),
        allow_write=True,
        secret_scan_status="clean",
    )
    assert "bucket_not_configured" in result["blocked_reasons"]


def test_write_refused_without_a_client() -> None:
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=None,
        allow_write=True,
        secret_scan_status="clean",
    )
    assert "no_object_store_client_supplied" in result["blocked_reasons"]


def test_injected_fake_client_can_write_synthetic_bytes() -> None:
    client = FakeObjectStoreClient()
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=client,
        allow_write=True,
        secret_scan_status="clean",
        content_type="application/json",
    )
    assert result["body_store_status"] == "written"
    assert result["bytes_written"] == len(BODY.encode("utf-8"))
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["Bucket"] == BUCKET
    assert call["Key"] == object_key_for(DIGEST)
    assert isinstance(call["Body"], bytes)
    assert call["ContentType"] == "application/json"
    assert s3_invariant_failures(result) == []


def test_raw_payload_ref_returned_only_after_a_successful_write() -> None:
    refused = store_body(
        body=BODY, response_body_hash=DIGEST, bucket=BUCKET, client=None
    )
    assert refused["raw_payload_ref"] is None

    written = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=FakeObjectStoreClient(),
        allow_write=True,
        secret_scan_status="clean",
    )
    assert written["raw_payload_ref"] == raw_payload_ref_for(
        bucket=BUCKET, response_body_hash=DIGEST
    )


def test_client_exception_message_is_not_leaked() -> None:
    """A client's error text can carry a presigned URL or a header echo."""
    result = store_body(
        body=BODY,
        response_body_hash=DIGEST,
        bucket=BUCKET,
        client=ExplodingClient(),
        allow_write=True,
        secret_scan_status="clean",
    )
    assert result["body_store_status"] == "refused"
    assert result["blocked_reasons"] == ["object_store_write_failed:RuntimeError"]
    serialised = json.dumps(result)
    assert "X-Amz-Signature" not in serialised
    assert "synthetic-signature" not in serialised


def test_body_store_imports_no_sdk_and_no_network_library() -> None:
    """No dependency was added; uv.lock is untouched."""
    path = REPO_ROOT / "src/nativeforge/services/s3_raw_payload_body_store_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "boto3", "botocore", "minio", "s3fs", "aioboto3",
        "httpx", "requests", "aiohttp", "socket", "urllib3",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


def test_body_store_logs_nothing() -> None:
    """A log line is a copy. The store has no logger and no print."""
    path = REPO_ROOT / "src/nativeforge/services/s3_raw_payload_body_store_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    for forbidden in ("print", "info", "debug", "warning", "error", "exception"):
        assert forbidden not in called, forbidden


def test_no_object_store_sdk_in_the_dependency_set() -> None:
    for name in ("pyproject.toml", "uv.lock"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8").lower()
        for sdk in ("boto3", "botocore", "minio", "s3fs", "aioboto3"):
            assert sdk not in text, f"{name} references {sdk}"


# --------------------------------------------------------------------------
# 97D - readiness integration
# --------------------------------------------------------------------------


def test_modes_include_s3_compatible_configured() -> None:
    assert "s3_compatible_configured" in BODY_STORE_MODES
    assert PRODUCTION_CAPABLE_MODES == frozenset({"s3_compatible_configured"})


def test_implementation_and_configuration_are_separate_components() -> None:
    assert "body_store_implementation_available" in REQUIRED_COMPONENTS
    assert "body_store_configured" in REQUIRED_COMPONENTS
    report = build_production_readiness()
    assert report["body_store_implementation_available"] is True
    assert report["body_store_configured"] is False


def test_production_readiness_remains_false_in_the_test_environment() -> None:
    report = build_production_readiness()
    assert report["production_raw_payload_store_available"] is False
    assert report["production_storage_live"] is False
    assert report["components_missing"] == ["body_store_configured"]
    assert production_readiness_invariant_failures(report) == []


def test_configured_settings_alone_do_not_make_storage_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every component present is availability. Live needs a collector."""
    _configure(monkeypatch)
    report = build_production_readiness()
    assert report["body_store_configured"] is True
    assert report["production_raw_payload_store_available"] is True
    assert report["production_storage_live"] is False
    assert report["collectors_active"] == 0
    assert production_readiness_invariant_failures(report) == []


def test_readiness_cannot_be_available_without_an_implementation() -> None:
    report = build_production_readiness()
    lying = dict(
        report,
        production_raw_payload_store_available=True,
        body_store_implementation_available=False,
    )
    assert "available_without_a_body_store_implementation" in (
        production_readiness_invariant_failures(lying)
    )


def test_preflight_reports_both_body_store_facts() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    assert result["body_store_implementation_available"] is True
    assert result["body_store_configured"] is False
    assert preflight_invariant_failures(result) == []


def test_preflight_rejects_configured_without_an_implementation() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    lying = dict(
        result,
        body_store_configured=True,
        body_store_implementation_available=False,
    )
    assert "body_store_configured_without_an_implementation" in (
        preflight_invariant_failures(lying)
    )


def test_phase1_matrix_reports_both_facts_and_no_production() -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["body_store_implementation_available"] is True
    assert matrix["body_store_configured"] is False
    assert matrix["production_raw_payload_store_available"] is False
    assert policy_invariant_failures(matrix) == []


def test_implementation_may_not_stand_in_for_configuration() -> None:
    matrix = build_phase1_activation_matrix()
    lying = dict(matrix, production_raw_payload_store_available=True)
    fails = policy_invariant_failures(lying)
    assert "implementation_treated_as_a_configured_body_store" in fails


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


def test_collectors_remain_inactive_even_when_fully_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuring a body store does not start anything."""
    _configure(monkeypatch)
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["collectors_active"] == 0
    for source in matrix["sources"]:
        assert source["collector_status"] == "not_active"
        assert source["may_fetch_live_now"] is False
        assert source["may_schedule_monitor"] is False


# --------------------------------------------------------------------------
# 97E - repository integration
# --------------------------------------------------------------------------


def test_repository_accepts_a_body_store_ref() -> None:
    ref = raw_payload_ref_for(bucket=BUCKET, response_body_hash=DIGEST)
    decision = build_repository_decision(payload=_evidence(), body_store_ref=ref)
    assert decision["body_store_ref"] == ref
    assert decision["body_store_ref_supplied"] is True
    assert repository_invariant_failures(decision) == []


def test_repository_still_writes_metadata_only_with_a_ref() -> None:
    ref = raw_payload_ref_for(bucket=BUCKET, response_body_hash=DIGEST)
    decision = build_repository_decision(payload=_evidence(), body_store_ref=ref)
    assert decision["body_write_allowed"] is False
    assert decision["bodies_written"] == 0


def test_repository_refuses_a_live_payload_without_a_body_store_ref() -> None:
    live = _evidence(created_from_fixture=False, created_from_live_fetch=True)
    decision = build_repository_decision(
        payload=live,
        activation_preflight={
            "activation_allowed": True,
            "activation_status": "activation_allowed",
        },
    )
    assert decision["live_payload_missing_body_store_ref"] is True
    assert decision["promotion_allowed"] is False
    assert "live_payload_missing_body_store_ref" in decision["blocked_reasons"]


def test_fixture_payload_needs_no_body_store_ref() -> None:
    """Gate 95's local store holds it; nothing was fetched."""
    decision = build_repository_decision(payload=_evidence())
    assert decision["live_payload_missing_body_store_ref"] is False


def test_live_payload_with_ref_and_configured_store_can_promote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    ref = raw_payload_ref_for(bucket=BUCKET, response_body_hash=DIGEST)
    live = _evidence(created_from_fixture=False, created_from_live_fetch=True)
    decision = build_repository_decision(
        payload=live,
        body_store_ref=ref,
        activation_preflight={
            "activation_allowed": True,
            "activation_status": "activation_allowed",
        },
    )
    assert decision["production_body_store_available"] is True
    assert decision["promotion_allowed"] is True
    assert decision["resolved_promotion_status"] == "evidence_ready"
    assert repository_invariant_failures(decision) == []


def test_repository_invariant_catches_a_promoted_live_payload_without_a_ref() -> None:
    decision = build_repository_decision(payload=_evidence())
    lying = dict(
        decision,
        promotion_allowed=True,
        live_payload_missing_body_store_ref=True,
    )
    assert "live_payload_promoted_without_a_body_store_ref" in (
        repository_invariant_failures(lying)
    )


def test_repository_dry_run_needs_no_database() -> None:
    from nativeforge.services.production_raw_payload_repository_service import (
        persist_payload_metadata,
    )

    result = persist_payload_metadata(payload=_evidence())
    assert result["repository_status"] == "dry_run"
    assert result["rows_written"] == 0


# --------------------------------------------------------------------------
# 97F - artifacts
# --------------------------------------------------------------------------

ARTIFACT_NAMES = (SETTINGS_JSON_NAME, S3_JSON_NAME, MATRIX_CSV_NAME, SUMMARY_NAME)


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
    if not (committed_dir / SETTINGS_JSON_NAME).exists():
        pytest.skip("body store artifacts not generated in this tree")
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
        pytest.skip("body store artifacts not generated in this tree")

    expected = {
        "body_store_implementation_available": True,
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


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_no_artifact_contains_a_secret(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("body store artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    result = scan_payload_for_secrets(body=text)
    assert result["clean"] is True, (name, result["by_kind"])
    assert SYNTHETIC_SECRET not in text
    assert SYNTHETIC_ACCESS_KEY not in text


def test_artifacts_hold_no_secret_even_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case that actually matters: a configured environment."""
    _configure(monkeypatch)
    write_readiness_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        text = (tmp_path / ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert SYNTHETIC_SECRET not in text, name
        assert SYNTHETIC_ACCESS_KEY not in text, name
        assert scan_payload_for_secrets(body=text)["clean"] is True, name


def test_artifact_writer_refuses_a_banned_phrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nativeforge.services.raw_payload_body_store_readiness_artifact_service as mod

    monkeypatch.setattr(
        mod,
        "render_readiness_summary",
        lambda bundle: "the body store is configured\n"
        + "\n".join(REQUIRED_DECLARATIONS),
    )
    with pytest.raises(BodyStoreReadinessArtifactError):
        mod.write_readiness_artifacts(repo_root=tmp_path)


def test_artifact_writer_refuses_a_missing_declaration() -> None:
    bundle = build_readiness_bundle()
    failures = artifact_claim_failures(bundle, "a summary that declares nothing")
    assert any(f.startswith("required_declaration_missing") for f in failures)


def test_bundle_invariants_all_hold() -> None:
    bundle = build_readiness_bundle()
    summary = render_readiness_summary(bundle)
    assert artifact_claim_failures(bundle, summary) == []


def test_artifact_sample_write_was_actually_refused() -> None:
    """An artifact documenting a default-refuse store with a successful write
    would be documenting nothing."""
    bundle = build_readiness_bundle()
    assert bundle["refused_sample"]["body_store_status"] == "refused"
    assert bundle["refused_sample"]["blocked_reasons"]


def test_settings_artifact_lists_names_and_presence_only() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / SETTINGS_JSON_NAME
    if not path.exists():
        pytest.skip("body store artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["credential_values_rendered"] is False
    for row in payload["settings"]:
        assert set(row) == {
            "setting",
            "env_var",
            "required",
            "value_present",
            "is_secret",
        }


# --------------------------------------------------------------------------
# Cross-cutting
# --------------------------------------------------------------------------

GATE97_SERVICES = (
    "s3_raw_payload_body_store_service",
    "raw_payload_body_store_readiness_artifact_service",
)


@pytest.mark.parametrize("module_name", GATE97_SERVICES)
def test_gate97_services_pass_the_gate94_scanner(module_name: str) -> None:
    from nativeforge.services.hermetic_network_enforcement_service import (
        scan_for_network_call_sites,
    )

    report = scan_for_network_call_sites(repo_root=REPO_ROOT)
    offenders = [f for f in report["findings"] if f.get("module") == module_name]
    assert offenders == [], offenders


def test_no_object_store_was_contacted() -> None:
    """Every write path in this suite ran through an injected fake."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"boto3", "botocore", "minio", "httpx", "requests"})


def test_gate97_outputs_are_json_serialisable() -> None:
    json.dumps(build_body_store_contract())
    json.dumps(build_client_config())
    json.dumps(
        store_body(body=BODY, response_body_hash=DIGEST, bucket=BUCKET, client=None)
    )
    json.dumps(build_readiness_bundle())
