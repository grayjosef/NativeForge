"""Gate 95 - raw payload store.

The store exists to answer the number Gates 87-89 measured: 185 corpus records,
18 with independent transport evidence. These tests hold the shape of the fix -
bytes kept, hashed, scanned, and refused promotion until all three are true.

Nothing here fetches. Every payload is constructed in the test or written to a
temp directory.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from nativeforge.services.local_raw_payload_store_service import (
    STORAGE_MODE,
    STORE_ROOT,
    LocalPayloadStoreError,
    body_hash,
    body_path_for,
    headers_hash,
    read_raw_payload,
    store_invariant_failures,
    store_raw_payload,
    verify_stored_payload,
)
from nativeforge.services.phase1_collector_activation_policy_service import (
    PHASE1_SOURCE_IDS,
    build_phase1_activation_matrix,
    default_phase1_preflights,
    policy_invariant_failures,
)
from nativeforge.services.raw_payload_evidence_model_service import (
    EVIDENCE_CRITICAL_FIELDS,
    PROMOTION_STATUSES,
    REQUIRED_FIELDS,
    SECRET_SCAN_SATISFYING,
    RawPayloadEvidenceError,
    build_payload_evidence,
    build_payload_id,
    evidence_invariant_failures,
    summarise_evidence,
)
from nativeforge.services.raw_payload_promotion_gate_service import (
    REQUIREMENT_KEYS,
    apply_promotion,
    evaluate_payload_promotion,
    promotion_invariant_failures,
)
from nativeforge.services.raw_payload_secret_scan_service import (
    FINDING_KINDS,
    REDACTION_PLACEHOLDER,
    redact_payload,
    scan_and_redact,
    scan_payload_for_secrets,
    secret_scan_invariant_failures,
)
from nativeforge.services.raw_payload_store_readiness_artifact_service import (
    ARTIFACT_DIR,
    CONTRACT_JSON_NAME,
    MATRIX_CSV_NAME,
    PATTERNS_JSON_NAME,
    REQUIRED_DECLARATIONS,
    SUMMARY_NAME,
    RawPayloadReadinessArtifactError,
    artifact_claim_failures,
    build_readiness_bundle,
    render_readiness_summary,
    write_readiness_artifacts,
)
from nativeforge.services.source_activation_preflight_service import (
    STORE_IMPLEMENTATION_SATISFYING,
    build_activation_preflight,
    detect_store_implementation,
    preflight_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

GATE95_SERVICES = (
    "raw_payload_evidence_model_service",
    "local_raw_payload_store_service",
    "raw_payload_secret_scan_service",
    "raw_payload_promotion_gate_service",
    "raw_payload_store_readiness_artifact_service",
)

# Constructed here, never read from a real credential. Shaped like an HS256 JWT
# because that is what Gate 89 found committed inside a recorded API response.
SYNTHETIC_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJzeW50aGV0aWMtdGVzdC1vbmx5In0"
    ".c3ludGhldGljX3NpZ25hdHVyZV9ub3RfcmVhbA"
)
SYNTHETIC_TOKEN = "synthetic_not_a_real_key_0123456789"

CLEAN_BODY = '{"opportunityNumber":"HHS-2026-IHS-01","title":"Tribal Health"}'
RETRIEVED_AT = "2026-08-27T05:30:00Z"


def _evidence(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        source_id="grants_gov_daily_extract",
        retrieved_at=RETRIEVED_AT,
        response_body_hash=body_hash(CLEAN_BODY),
        raw_payload_ref=body_path_for(body_hash(CLEAN_BODY)),
        request_fingerprint="GET extract 20260827",
        secret_scan_status="clean",
        redaction_status="not_required",
        terms_status="NO_REVIEW_REQUIRED",
        parser_status="not_started",
        created_from_fixture=True,
    )
    base.update(overrides)
    return build_payload_evidence(**base)


# --------------------------------------------------------------------------
# 95B - evidence model
# --------------------------------------------------------------------------


def test_evidence_model_requires_source_id() -> None:
    with pytest.raises(RawPayloadEvidenceError, match="source_id"):
        _evidence(source_id="")


def test_evidence_model_requires_retrieved_at() -> None:
    with pytest.raises(RawPayloadEvidenceError, match="retrieved_at"):
        _evidence(retrieved_at="")


def test_evidence_model_requires_response_body_hash() -> None:
    with pytest.raises(RawPayloadEvidenceError, match="response_body_hash"):
        _evidence(response_body_hash="")


def test_evidence_model_rejects_a_non_sha256_hash() -> None:
    with pytest.raises(RawPayloadEvidenceError):
        _evidence(response_body_hash="deadbeef")


def test_evidence_model_requires_raw_payload_ref() -> None:
    with pytest.raises(RawPayloadEvidenceError, match="raw_payload_ref"):
        _evidence(raw_payload_ref="")


def test_payload_id_is_deterministic() -> None:
    first = _evidence()
    second = _evidence()
    assert first["payload_id"] == second["payload_id"]
    assert first["payload_id"] == build_payload_id(
        source_id="grants_gov_daily_extract",
        request_fingerprint="GET extract 20260827",
        response_body_hash=body_hash(CLEAN_BODY),
    )


def test_payload_id_changes_with_the_body() -> None:
    """A different response is a different payload, not an overwrite."""
    other_hash = body_hash(CLEAN_BODY + " ")
    first = _evidence()
    second = _evidence(
        response_body_hash=other_hash, raw_payload_ref=body_path_for(other_hash)
    )
    assert first["payload_id"] != second["payload_id"]


def test_explicit_payload_id_is_respected() -> None:
    record = _evidence(payload_id="operator-supplied-id")
    assert record["payload_id"] == "operator-supplied-id"


def test_live_and_fixture_provenance_are_mutually_exclusive() -> None:
    with pytest.raises(RawPayloadEvidenceError, match="cannot both be true"):
        _evidence(created_from_fixture=True, created_from_live_fetch=True)


def test_unstated_provenance_is_blocked_not_assumed() -> None:
    record = _evidence(created_from_fixture=False, created_from_live_fetch=False)
    assert "provenance_unstated" in record["blocked_reasons"]


def test_every_record_starts_in_quarantine() -> None:
    """Promotion is a separate decision, never asserted at construction."""
    assert _evidence()["promotion_status"] == "quarantine"


def test_evidence_never_implies_coverage_or_monitoring() -> None:
    record = _evidence()
    assert record["implies_live_coverage"] is False
    assert record["implies_monitoring_active"] is False
    assert record["fetch_performed"] is False
    assert evidence_invariant_failures(record) == []


def test_evidence_model_has_all_declared_fields() -> None:
    record = _evidence()
    for field in REQUIRED_FIELDS:
        assert field in record, field
    for field in EVIDENCE_CRITICAL_FIELDS:
        assert field in REQUIRED_FIELDS


def test_unrecognised_status_resolves_to_the_blocking_member() -> None:
    record = _evidence(secret_scan_status="probably_fine")
    assert record["secret_scan_status"] == "pending"
    assert record["secret_scan_status"] not in SECRET_SCAN_SATISFYING


def test_evidence_summary_counts_provenance_separately() -> None:
    summary = summarise_evidence([_evidence(), _evidence()])
    assert summary["fixture_records"] == 2
    assert summary["live_fetch_records"] == 0
    assert summary["implies_live_coverage"] is False


# --------------------------------------------------------------------------
# 95C - local store
# --------------------------------------------------------------------------


def test_local_store_refuses_writes_by_default(tmp_path: Path) -> None:
    with pytest.raises(LocalPayloadStoreError, match="disabled"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body=CLEAN_BODY,
            repo_root=tmp_path,
        )


def test_local_store_writes_when_explicitly_enabled(tmp_path: Path) -> None:
    result = store_raw_payload(
        source_id="grants_gov_daily_extract",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        request_fingerprint="GET extract",
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    assert result["write_status"] == "written"
    assert store_invariant_failures(result) == []
    assert (tmp_path / STORE_ROOT / result["body_ref"]).exists()


def test_local_store_is_content_addressed(tmp_path: Path) -> None:
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    digest = result["response_body_hash"]
    assert digest in result["body_ref"]
    assert result["body_ref"] == f"bodies/{digest[:2]}/{digest}.bin"


def test_stored_body_re_derives_its_own_hash(tmp_path: Path) -> None:
    """This is the whole point: origin re-derivable, not merely asserted."""
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    check = verify_stored_payload(
        body_ref=result["body_ref"],
        expected_hash=result["response_body_hash"],
        repo_root=tmp_path,
    )
    assert check["present"] is True
    assert check["hash_matches"] is True
    stored = read_raw_payload(body_ref=result["body_ref"], repo_root=tmp_path)
    assert stored == CLEAN_BODY


def test_corrupted_body_fails_verification(tmp_path: Path) -> None:
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    stored_file = tmp_path / STORE_ROOT / result["body_ref"]
    stored_file.write_text("tampered", encoding="utf-8")
    check = verify_stored_payload(
        body_ref=result["body_ref"],
        expected_hash=result["response_body_hash"],
        repo_root=tmp_path,
    )
    assert check["hash_matches"] is False
    assert check["reason"] == "hash_mismatch"


def test_local_store_uses_the_supplied_retrieved_at_not_now(tmp_path: Path) -> None:
    result = store_raw_payload(
        source_id="s",
        retrieved_at="1999-01-01T00:00:00Z",
        body=CLEAN_BODY,
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    assert result["evidence"]["retrieved_at"] == "1999-01-01T00:00:00Z"
    assert result["retrieved_at_generated_by_store"] is False

    source = (
        REPO_ROOT / "src/nativeforge/services/local_raw_payload_store_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "now" not in called
    assert "utcnow" not in called


def test_local_store_refuses_customer_data_by_default(tmp_path: Path) -> None:
    with pytest.raises(LocalPayloadStoreError, match="customer data"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body=CLEAN_BODY,
            local_storage_enabled=True,
            contains_customer_data=True,
            created_from_fixture=True,
            repo_root=tmp_path,
        )


def test_local_store_accepts_customer_data_when_explicitly_allowed(
    tmp_path: Path,
) -> None:
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        local_storage_enabled=True,
        contains_customer_data=True,
        customer_data_allowed=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    assert result["customer_data_stored"] is True


def test_local_store_refuses_a_payload_with_secrets(tmp_path: Path) -> None:
    with pytest.raises(LocalPayloadStoreError, match="secret finding"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body='{"access_token":"' + SYNTHETIC_TOKEN + '"}',
            local_storage_enabled=True,
            created_from_fixture=True,
            repo_root=tmp_path,
        )


def test_local_store_accepts_a_redacted_body(tmp_path: Path) -> None:
    dirty = '{"access_token":"' + SYNTHETIC_TOKEN + '"}'
    redaction = redact_payload(body=dirty)
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=dirty,
        redacted_body=redaction["redacted_body"],
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    assert result["redaction_status"] == "completed"
    stored = read_raw_payload(body_ref=result["body_ref"], repo_root=tmp_path)
    assert SYNTHETIC_TOKEN not in (stored or "")
    assert REDACTION_PLACEHOLDER in (stored or "")


def test_local_store_refuses_a_still_dirty_redacted_body(tmp_path: Path) -> None:
    dirty = '{"access_token":"' + SYNTHETIC_TOKEN + '"}'
    with pytest.raises(LocalPayloadStoreError, match="still contains"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body=dirty,
            redacted_body=dirty,
            local_storage_enabled=True,
            created_from_fixture=True,
            repo_root=tmp_path,
        )


def test_local_store_refuses_a_live_payload_without_a_preflight(
    tmp_path: Path,
) -> None:
    with pytest.raises(LocalPayloadStoreError, match="activation preflight"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body=CLEAN_BODY,
            local_storage_enabled=True,
            created_from_live_fetch=True,
            repo_root=tmp_path,
        )


def test_local_store_refuses_a_live_payload_whose_preflight_failed(
    tmp_path: Path,
) -> None:
    with pytest.raises(LocalPayloadStoreError, match="did not pass"):
        store_raw_payload(
            source_id="s",
            retrieved_at=RETRIEVED_AT,
            body=CLEAN_BODY,
            local_storage_enabled=True,
            created_from_live_fetch=True,
            activation_preflight={
                "activation_allowed": False,
                "activation_status": "activation_blocked",
            },
            repo_root=tmp_path,
        )


def test_headers_are_hashed_never_stored(tmp_path: Path) -> None:
    """Authorization and Set-Cookie live in headers."""
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        headers={"Content-Type": "application/json"},
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    metadata = json.loads(
        (tmp_path / STORE_ROOT / result["metadata_ref"]).read_text(encoding="utf-8")
    )
    assert "response_headers" not in metadata
    assert len(metadata["response_headers_hash"]) == 64
    assert metadata["response_headers_hash"] == headers_hash(
        {"Content-Type": "application/json"}
    )


def test_local_store_never_claims_production_availability(tmp_path: Path) -> None:
    result = store_raw_payload(
        source_id="s",
        retrieved_at=RETRIEVED_AT,
        body=CLEAN_BODY,
        local_storage_enabled=True,
        created_from_fixture=True,
        repo_root=tmp_path,
    )
    assert result["local_raw_payload_store_available"] is True
    assert result["production_raw_payload_store_available"] is False
    assert result["storage_mode"] == STORAGE_MODE == "local_dev_only"


def test_local_store_does_not_fetch() -> None:
    source = (
        REPO_ROOT / "src/nativeforge/services/local_raw_payload_store_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"httpx", "requests", "socket", "aiohttp", "urllib3"})


def test_store_root_is_gitignored() -> None:
    """artifacts/ is not ignored wholesale; this directory must be.

    Rules, not substrings: the readiness directory's name appears in the
    explanatory comment above the rule, so a plain `in` check on the file text
    reports it as ignored when it is not.
    """
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    rules = {
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    }
    assert f"{STORE_ROOT}/" in rules
    # The readiness artifacts are committed, so they must NOT be ignored.
    assert f"{ARTIFACT_DIR}/" not in rules
    assert ARTIFACT_DIR not in rules


# --------------------------------------------------------------------------
# 95D - secret scan and redaction
# --------------------------------------------------------------------------


def test_jwt_is_detected_without_printing_the_value() -> None:
    result = scan_payload_for_secrets(body='{"t":"' + SYNTHETIC_JWT + '"}')
    assert result["scan_status"] == "findings_blocked"
    assert {f["kind"] for f in result["findings"]} == {"jwt_token"}
    assert SYNTHETIC_JWT not in json.dumps(result)
    assert secret_scan_invariant_failures(result) == []


def test_authorization_header_is_detected_without_printing_the_value() -> None:
    result = scan_payload_for_secrets(
        body="{}", headers={"Authorization": "Bearer " + SYNTHETIC_TOKEN}
    )
    assert result["finding_count"] >= 1
    assert SYNTHETIC_TOKEN not in json.dumps(result)
    assert any(f["location"].startswith("header:") for f in result["findings"])


@pytest.mark.parametrize(
    "body,expected_kind",
    [
        ('{"access_token":"' + SYNTHETIC_TOKEN + '"}', "access_token"),
        ('{"refresh_token":"' + SYNTHETIC_TOKEN + '"}', "refresh_token"),
        ('{"client_secret":"' + SYNTHETIC_TOKEN + '"}', "client_secret"),
        ('{"api_key":"' + SYNTHETIC_TOKEN + '"}', "api_key"),
        ('{"password":"' + SYNTHETIC_TOKEN + '"}', "password"),
        ("Authorization: Bearer " + SYNTHETIC_TOKEN, "bearer_token"),
        (
            "-----BEGIN RSA PRIVATE KEY-----\nsynthetic\n-----END RSA PRIVATE KEY-----",
            "private_key",
        ),
    ],
)
def test_each_secret_kind_is_detected(body: str, expected_kind: str) -> None:
    result = scan_payload_for_secrets(body=body)
    assert expected_kind in {f["kind"] for f in result["findings"]}
    assert SYNTHETIC_TOKEN not in json.dumps(result)


def test_finding_reports_kind_and_location_only() -> None:
    result = scan_payload_for_secrets(
        body='{"access_token":"' + SYNTHETIC_TOKEN + '"}'
    )
    finding = result["findings"][0]
    assert set(finding) == {"kind", "location", "match_length", "fingerprint"}
    assert len(finding["fingerprint"]) == 8
    assert finding["kind"] in FINDING_KINDS


def test_benign_values_are_not_flagged() -> None:
    """A scanner that flags `"password": "n/a"` buries the real findings."""
    for body in ('{"password":"n/a"}', '{"api_key":"none"}', '{"password":""}'):
        assert scan_payload_for_secrets(body=body)["clean"] is True


def test_clean_payload_scans_clean() -> None:
    result = scan_payload_for_secrets(body=CLEAN_BODY)
    assert result["clean"] is True
    assert result["scan_status"] == "clean"
    assert secret_scan_invariant_failures(result) == []


def test_bearer_token_is_redacted() -> None:
    result = redact_payload(body="Authorization: Bearer " + SYNTHETIC_TOKEN)
    assert SYNTHETIC_TOKEN not in result["redacted_body"]
    assert REDACTION_PLACEHOLDER in result["redacted_body"]
    assert "Bearer" in result["redacted_body"]


def test_access_token_is_redacted_preserving_structure() -> None:
    result = redact_payload(body='{"access_token":"' + SYNTHETIC_TOKEN + '"}')
    assert result["redacted_body"] == '{"access_token":"[REDACTED]"}'
    assert SYNTHETIC_TOKEN not in result["redacted_body"]


def test_redacted_hash_differs_from_the_original() -> None:
    result = redact_payload(body='{"access_token":"' + SYNTHETIC_TOKEN + '"}')
    assert result["original_body_hash"] != result["redacted_body_hash"]
    assert result["hash_changed"] is True
    assert secret_scan_invariant_failures(result) == []


def test_redaction_of_a_clean_body_is_not_required() -> None:
    result = redact_payload(body=CLEAN_BODY)
    assert result["redaction_status"] == "not_required"
    assert result["hash_changed"] is False


def test_scan_and_redact_rescans_rather_than_assuming() -> None:
    body = '{"access_token":"' + SYNTHETIC_TOKEN + '","t":"' + SYNTHETIC_JWT + '"}'
    result = scan_and_redact(body=body)
    assert result["initial_findings"] == 2
    assert result["residual_findings"] == 0
    assert result["safe_to_store"] is True
    assert SYNTHETIC_TOKEN not in result["redacted_body"]
    assert SYNTHETIC_JWT not in result["redacted_body"]


def test_scanner_finds_the_gate89_shape() -> None:
    """Gate 89 found a committed JWT inside a recorded Grants.gov response.

    The real fixture is NOT modified by this gate. This reconstructs its shape
    locally - a JWT nested in an opportunity payload - and proves the scanner
    would have caught it.
    """
    gate89_shape = json.dumps(
        {
            "data": {
                "id": 362648,
                "opportunityNumber": "SYNTHETIC-2026-01",
                "accessToken": SYNTHETIC_JWT,
            }
        }
    )
    result = scan_payload_for_secrets(body=gate89_shape)
    assert result["scan_status"] == "findings_blocked"
    assert "jwt_token" in {f["kind"] for f in result["findings"]}
    assert SYNTHETIC_JWT not in json.dumps(result)


def test_gate89_fixture_is_not_modified_by_this_gate() -> None:
    """It is the scanner's proving case, not its subject."""
    fixture = (
        REPO_ROOT / "fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json"
    )
    if not fixture.exists():
        pytest.skip("Gate 89 fixture not present in this tree")
    # Present and readable is all this asserts - mutating it needs its own
    # approved gate.
    assert fixture.stat().st_size > 0


# --------------------------------------------------------------------------
# 95E - promotion gate
# --------------------------------------------------------------------------


def test_clean_fixture_payload_promotes() -> None:
    decision = evaluate_payload_promotion(payload=_evidence())
    assert decision["can_promote"] is True
    assert decision["promotion_status"] == "evidence_ready"
    assert decision["evidence_ready"] is True
    assert promotion_invariant_failures(decision) == []


@pytest.mark.parametrize("scan_status", ["pending", "findings_blocked", "failed"])
def test_promotion_blocked_when_secret_scan_is_not_clean(scan_status: str) -> None:
    decision = evaluate_payload_promotion(
        payload=_evidence(secret_scan_status=scan_status)
    )
    assert decision["can_promote"] is False
    assert decision["evidence_ready"] is False
    assert any("secret_scan_not_clean" in r for r in decision["blocked_reasons"])


@pytest.mark.parametrize("redaction", ["pending", "failed"])
def test_promotion_blocked_when_redaction_is_unresolved(redaction: str) -> None:
    decision = evaluate_payload_promotion(
        payload=_evidence(redaction_status=redaction)
    )
    assert decision["can_promote"] is False
    assert any("redaction_not_resolved" in r for r in decision["blocked_reasons"])


def test_promotion_blocked_by_terms_review_required() -> None:
    decision = evaluate_payload_promotion(
        payload=_evidence(terms_status="TERMS_REVIEW_REQUIRED")
    )
    assert decision["can_promote"] is False
    assert decision["human_review_required"] is False


def test_promotion_blocked_by_human_review_only_and_quarantined_not_rejected() -> None:
    """Human review parks a payload. Rejecting it would lose the evidence."""
    decision = evaluate_payload_promotion(
        payload=_evidence(terms_status="HUMAN_REVIEW_ONLY")
    )
    assert decision["can_promote"] is False
    assert decision["human_review_required"] is True
    assert decision["promotion_status"] == "quarantine"
    assert decision["promotion_status"] != "rejected"
    assert promotion_invariant_failures(decision) == []


def test_promotion_blocked_by_unknown_terms() -> None:
    decision = evaluate_payload_promotion(payload=_evidence(terms_status="UNKNOWN"))
    assert decision["can_promote"] is False


@pytest.mark.parametrize(
    "parser", ["parse_failed", "parser_unavailable", "human_review_required"]
)
def test_promotion_blocked_by_a_failed_parse(parser: str) -> None:
    decision = evaluate_payload_promotion(payload=_evidence(parser_status=parser))
    assert decision["can_promote"] is False


def test_promotion_allows_a_parsed_payload() -> None:
    decision = evaluate_payload_promotion(payload=_evidence(parser_status="parsed"))
    assert decision["can_promote"] is True


def test_live_payload_requires_an_activation_preflight() -> None:
    live = _evidence(created_from_fixture=False, created_from_live_fetch=True)
    without = evaluate_payload_promotion(payload=live)
    assert without["can_promote"] is False
    assert "activation_preflight_absent" in without["blocked_reasons"]

    with_pass = evaluate_payload_promotion(
        payload=live,
        activation_preflight={
            "activation_allowed": True,
            "activation_status": "activation_allowed",
        },
    )
    assert with_pass["can_promote"] is True
    assert promotion_invariant_failures(with_pass) == []


def test_live_payload_blocked_by_a_failed_preflight() -> None:
    live = _evidence(created_from_fixture=False, created_from_live_fetch=True)
    decision = evaluate_payload_promotion(
        payload=live,
        activation_preflight={
            "activation_allowed": False,
            "activation_status": "activation_blocked",
        },
    )
    assert decision["can_promote"] is False


def test_every_promotion_requirement_is_accounted_for() -> None:
    decision = evaluate_payload_promotion(payload=_evidence())
    accounted = set(decision["requirements_satisfied"]) | set(
        decision["requirements_missing"]
    )
    assert accounted == set(REQUIREMENT_KEYS)


def test_promotion_gate_writes_nothing() -> None:
    decision = evaluate_payload_promotion(payload=_evidence())
    assert decision["promotion_performed"] is False
    assert decision["fetch_performed"] is False
    assert decision["implies_live_coverage"] is False


def test_apply_promotion_returns_a_copy_carrying_the_status() -> None:
    payload = _evidence()
    decision = evaluate_payload_promotion(payload=payload)
    promoted = apply_promotion(payload=payload, decision=decision)
    assert promoted["promotion_status"] == "evidence_ready"
    assert payload["promotion_status"] == "quarantine"
    assert promoted["promotion_status"] in PROMOTION_STATUSES


# --------------------------------------------------------------------------
# 95F - activation integration
# --------------------------------------------------------------------------


def test_store_implementation_is_detected_not_declared() -> None:
    assert detect_store_implementation() == "local_only"
    assert detect_store_implementation() in STORE_IMPLEMENTATION_SATISFYING


def test_preflight_reports_three_distinct_storage_facts() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    assert result["raw_payload_store_contract_available"] is True
    assert result["local_raw_payload_store_available"] is True
    assert result["production_raw_payload_store_available"] is False
    assert preflight_invariant_failures(result) == []


def test_preflight_never_claims_production_storage() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    lying = dict(result, production_raw_payload_store_available=True)
    assert "preflight_claimed_production_payload_storage" in (
        preflight_invariant_failures(lying)
    )


def test_missing_store_implementation_blocks_activation() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    pretend = dict(
        result,
        activation_allowed=True,
        activation_status="activation_allowed",
        raw_payload_store_implementation="none",
    )
    assert "activation_allowed_without_a_payload_store_implementation" in (
        preflight_invariant_failures(pretend)
    )


def test_phase1_collectors_remain_not_active() -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["collectors_active"] == 0
    assert matrix["monitors_active"] == 0
    for source in matrix["sources"]:
        assert source["collector_status"] == "not_active"
    assert policy_invariant_failures(matrix) == []


@pytest.mark.parametrize("source_id", list(PHASE1_SOURCE_IDS))
def test_may_fetch_and_schedule_remain_false(source_id: str) -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    source = next(s for s in matrix["sources"] if s["source_id"] == source_id)
    assert source["may_fetch_live_now"] is False
    assert source["may_schedule_monitor"] is False
    assert source["may_surface_customer_data"] is False


def test_phase1_matrix_reports_local_store_but_not_production() -> None:
    matrix = build_phase1_activation_matrix()
    assert matrix["raw_payload_store_contract_available"] is True
    assert matrix["local_raw_payload_store_available"] is True
    assert matrix["production_raw_payload_store_available"] is False


def test_phase1_matrix_may_not_claim_production_storage() -> None:
    """The protection is unchanged; Gate 97 renamed the failures.

    Gate 96 asserted `production_raw_payload_store_available is not False` - a
    constant, correct while nothing could configure a body store. Gate 97 makes
    configuration possible, so the invariant became a check on the derivation
    instead, and a faked flag is now caught by the component it lacks rather
    than by a blanket rule.
    """
    matrix = build_phase1_activation_matrix()
    lying = dict(matrix, production_raw_payload_store_available=True)
    failures = policy_invariant_failures(lying)
    assert failures, "a faked production flag must still be caught"
    assert "metadata_table_treated_as_production_storage" in failures
    assert "implementation_treated_as_a_configured_body_store" in failures


# --------------------------------------------------------------------------
# 95G - artifacts
# --------------------------------------------------------------------------

ARTIFACT_NAMES = (
    CONTRACT_JSON_NAME,
    MATRIX_CSV_NAME,
    PATTERNS_JSON_NAME,
    SUMMARY_NAME,
)


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
    if not (committed_dir / CONTRACT_JSON_NAME).exists():
        pytest.skip("readiness artifacts not generated in this tree")
    write_readiness_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        committed = (committed_dir / name).read_bytes()
        assert hashlib.sha256(committed).hexdigest() == hashlib.sha256(
            fresh
        ).hexdigest(), name


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_declares_the_six_facts(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("readiness artifacts not generated in this tree")

    keys = (
        "local_raw_payload_store_available",
        "production_raw_payload_store_available",
        "live_fetch_performed",
        "collectors_active",
        "source_monitoring_active",
        "live_source_coverage",
    )
    raw = path.read_text(encoding="utf-8")
    for key in keys:
        assert key in raw, f"{name} does not state {key}"

    expected = {
        "local_raw_payload_store_available": True,
        "production_raw_payload_store_available": False,
        "live_fetch_performed": False,
        "collectors_active": False,
        "source_monitoring_active": False,
        "live_source_coverage": False,
    }

    if name.endswith(".json"):
        payload = json.loads(raw)
        for key, value in expected.items():
            assert payload[key] is value, f"{name}: {key}"
    elif name.endswith(".csv"):
        import csv as _csv

        rows = list(_csv.DictReader(__import__("io").StringIO(raw)))
        assert rows
        for row in rows:
            for key, value in expected.items():
                assert row[key] == str(value), f"{name}: {key} is {row[key]!r}"
    else:
        lowered = raw.lower()
        for key, value in expected.items():
            assert f"{key}: {str(value).lower()}" in lowered, f"{name}: {key}"


def test_no_artifact_contains_a_secret_value() -> None:
    for name in ARTIFACT_NAMES:
        path = REPO_ROOT / ARTIFACT_DIR / name
        if not path.exists():
            pytest.skip("readiness artifacts not generated in this tree")
        text = path.read_text(encoding="utf-8")
        result = scan_payload_for_secrets(body=text)
        assert result["clean"] is True, (name, result["by_kind"])


def test_artifact_writer_refuses_a_banned_phrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nativeforge.services.raw_payload_store_readiness_artifact_service as mod

    monkeypatch.setattr(
        mod,
        "render_readiness_summary",
        lambda bundle: "production storage is live\n"
        + "\n".join(REQUIRED_DECLARATIONS),
    )
    with pytest.raises(RawPayloadReadinessArtifactError):
        mod.write_readiness_artifacts(repo_root=tmp_path)


def test_artifact_writer_refuses_a_missing_declaration() -> None:
    bundle = build_readiness_bundle()
    failures = artifact_claim_failures(bundle, "a summary that declares nothing")
    assert any(f.startswith("required_declaration_missing") for f in failures)


def test_bundle_invariants_all_hold() -> None:
    bundle = build_readiness_bundle()
    summary = render_readiness_summary(bundle)
    assert artifact_claim_failures(bundle, summary) == []


def test_promotion_matrix_is_produced_by_the_real_gate() -> None:
    """A hand-written table would drift from the code that enforces it."""
    bundle = build_readiness_bundle()
    promoting = [r for r in bundle["promotion_rows"] if r["can_promote"]]
    assert len(promoting) == 1
    assert promoting[0]["scenario"] == "clean fixture payload"


# --------------------------------------------------------------------------
# Cross-cutting
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", GATE95_SERVICES)
def test_gate95_services_import_no_network_library(module_name: str) -> None:
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib3",
        "ftplib",
        "smtplib",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


@pytest.mark.parametrize("module_name", GATE95_SERVICES)
def test_gate95_services_are_registered_with_the_gate94_scanner(
    module_name: str,
) -> None:
    """A new service must not be a new unguarded egress site."""
    from nativeforge.services.hermetic_network_enforcement_service import (
        scan_for_network_call_sites,
    )

    report = scan_for_network_call_sites(repo_root=REPO_ROOT)
    offenders = [
        f for f in report["findings"] if f.get("module") == module_name
    ]
    assert offenders == [], offenders


def test_gate95_outputs_are_json_serialisable() -> None:
    json.dumps(_evidence())
    json.dumps(evaluate_payload_promotion(payload=_evidence()))
    json.dumps(scan_payload_for_secrets(body=CLEAN_BODY))
    json.dumps(redact_payload(body=CLEAN_BODY))
    json.dumps(build_readiness_bundle())
