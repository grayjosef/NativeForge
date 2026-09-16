"""Gate 160: the raw payload persistence spine.

Every defect this gate found in its own work has a test here, named for what it
would have shipped:

  - the metadata filter called the secret scanner with the WRONG KEYWORD, so
    every call raised, the exception was caught, and EVERY allowlisted header
    was refused with a plausible-looking reason. A filter that refuses
    everything passes every refusal test and is useless.
  - `get_payload(include_body=True)` returned the body through `_json_safe`,
    which turned `bytes` into a lossy Python repr string. The hash verified and
    what the caller received could not be decoded back.
  - the provenance check compared a STRING organization id against a typed
    `sa.Uuid` column, so it reported "no such job" about a job it had just
    created. A provenance check that always answers no is as useless as one
    that always answers yes, and rather more convincing.

The restart proof is not here. Proving bytes outlive the process that wrote
them needs a second process, and a test that commits into the demo org would
leave rows behind on every run. The verifier does it:
scripts/verify_nativeforge_source_raw_payload_persistence.sh, phases A and B.
"""

from __future__ import annotations

import ast
import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.repositories.source_collection_job_repository import enqueue_job
from nativeforge.repositories.source_collection_raw_payload_repository import (
    ACTIVE,
    ARCHIVED,
    BODY_STORAGE_MODES,
    MAX_PAYLOAD_BYTES,
    MODE_DATABASE,
    PAYLOAD_STATUSES,
    PAYLOADS,
    RETENTION_POLICIES,
    RETENTION_UNKNOWN,
    archive_payload,
    count_payloads,
    get_payload,
    list_payloads,
    persist_payload,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_collection_attempt_identity_service import (
    FIRST_ATTEMPT,
    UNKNOWN_COLLECTOR_VERSION,
    attempt_identity_invariant_failures,
    build_attempt_id,
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_artifact_gate160_service import (
    ARTIFACT_DIR,
    ARTIFACT_FILES,
    build_raw_payload_artifacts,
    raw_payload_artifact_invariant_failures,
    write_raw_payload_artifacts,
)
from nativeforge.services.source_raw_payload_hash_service import (
    HASH_ALGORITHM,
    as_bytes,
    describe_encoding,
    hash_invariant_failures,
    hash_payload,
    verify_payload,
)
from nativeforge.services.source_raw_payload_health_service import (
    CONDITIONS,
    build_raw_payload_health,
    detect_object_store_configured,
    raw_payload_health_invariant_failures,
)
from nativeforge.services.source_raw_payload_persistence_service import (
    fingerprint_url,
    persist_raw_payload,
    persistence_invariant_failures,
)
from nativeforge.services.source_raw_payload_replay_service import (
    replay_invariant_failures,
    replay_payload,
)
from nativeforge.services.source_response_metadata_filter_service import (
    ALLOWED_RESPONSE_HEADERS,
    CREDENTIAL_HEADERS,
    KEPT,
    MAX_HEADER_VALUE_LENGTH,
    REFUSED_CREDENTIAL,
    REFUSED_UNRECOGNISED,
    classify_header,
    filter_response_metadata,
    metadata_filter_invariant_failures,
    normalize_header_name,
)
from tests import session_org_helper as soh

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

T0 = "2026-09-16T12:00:00Z"

MIGRATION = REPO_ROOT / "alembic/versions/0046_source_collection_raw_payloads.py"

#: Deliberately not valid UTF-8, with a null byte. A store that round-trips
#: only text would pass every test written with a JSON fixture.
BINARY_BODY = b'{"id":"A"}\xff\xfe\x00 tail \x80\x81'
JSON_BODY = b'{"opportunities":[{"id":"ABC-123"}]}'

SAFE_HEADERS = {"Content-Type": "application/json", "ETag": 'W/"v1"'}

GATE_160_MODULES = (
    "src/nativeforge/services/source_collection_attempt_identity_service.py",
    "src/nativeforge/services/source_raw_payload_hash_service.py",
    "src/nativeforge/services/source_response_metadata_filter_service.py",
    "src/nativeforge/services/source_raw_payload_persistence_service.py",
    "src/nativeforge/services/source_raw_payload_replay_service.py",
    "src/nativeforge/services/source_raw_payload_health_service.py",
    "src/nativeforge/services/source_raw_payload_artifact_gate160_service.py",
    "src/nativeforge/repositories/source_collection_raw_payload_repository.py",
    "src/nativeforge/api/source_raw_payload_routes.py",
)


@pytest.fixture
def db_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(DEMO, "demo")
    with SessionLocal() as session:
        yield session
        # Rolled back, so no test in this file leaves a row behind.
        session.rollback()


@pytest.fixture
def connection(db_session):
    return db_session.connection()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _called_name_paths(path: Path) -> set[str]:
    """Dotted paths of every call whose callee is a plain name or attribute.

    `hashlib.sha256(x)` -> "hashlib.sha256"
    `body_hash(x)`      -> "body_hash"
    `str(x).strip()`    -> nothing, because the base is a Call

    That last exclusion is the point: unparsing the callee of a chained call
    yields text containing the receiver's variable names, and matching against
    it finds identifiers rather than calls.
    """

    def dotted(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = dotted(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    tree = ast.parse(Path(path).read_text())
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            rendered = dotted(node.func)
            if rendered:
                paths.add(rendered)
                paths.add(rendered.rsplit(".", 1)[-1])
    return paths


def _imported_names(path: Path) -> set[str]:
    """Every name this module actually imports, from the AST.

    Several Gate 160 modules discuss the things they must NOT import, in
    prose, to explain why. A text search matches the explanation; this does
    not.
    """
    tree = ast.parse(Path(path).read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _load_migration_module():
    """Import migration 0046 as a module, so its constants can be read."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("g160_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _identity(tag: str, attempt: int = 1) -> dict:
    return build_attempt_identity(
        job_id=f"{tag}-job", source_id=f"{tag}-src", attempt_number=attempt
    )


def _write(connection, tag: str, body: bytes, attempt: int = 1, **kwargs) -> dict:
    return persist_raw_payload(
        connection=connection,
        organization_id=DEMO,
        job_id=f"{tag}-job",
        source_id=f"{tag}-src",
        attempt_number=attempt,
        body=body,
        response_headers=kwargs.pop("response_headers", SAFE_HEADERS),
        received_at=T0,
        **kwargs,
    )


# ------------------------------------------------------ 160C the migration


def test_the_migration_exists_and_pins_0045_as_its_parent():
    body = MIGRATION.read_text()
    assert 'revision: str = "0046"' in body
    assert 'down_revision: str | Sequence[str] | None = "0045"' in body


def test_the_migration_caps_the_payload_size():
    """Compare the constants, not the source text.

    The migration builds its CHECK with an f-string, so the file contains
    `{MAX_PAYLOAD_BYTES}` and never the numeral. An earlier version of this
    test searched for the number and failed for a reason unrelated to whether
    the cap exists.
    """
    module = _load_migration_module()
    assert module.MAX_PAYLOAD_BYTES == MAX_PAYLOAD_BYTES
    # And the constraint really is built from it.
    body = MIGRATION.read_text()
    assert "payload_size_bytes <= {MAX_PAYLOAD_BYTES}" in body
    assert "ck_nf_source_collection_raw_payloads_size_bounded" in body


def test_the_migration_refuses_a_row_claiming_a_fetch():
    body = MIGRATION.read_text()
    assert "collector_invoked = 0" in body
    assert "live_fetch_performed = 0" in body


def test_the_migration_stores_no_credential_and_no_url():
    body = MIGRATION.read_text().lower()
    for forbidden in (
        'sa.column("authorization"',
        'sa.column("cookie"',
        'sa.column("set_cookie"',
        'sa.column("api_key"',
        'sa.column("access_token"',
        'sa.column("request_url"',
        'sa.column("source_url"',
    ):
        assert forbidden not in body
    # A fingerprint instead.
    assert 'sa.column("source_url_fingerprint"' in body


def test_the_migration_creates_no_execution_proof_column():
    """Gate 158 left `completed` unreachable. Gate 160 does not change that."""
    body = MIGRATION.read_text().lower()
    assert "execution_proof" not in body
    assert "jobs_completed" not in body


def test_the_migration_requires_bytes_when_the_mode_says_database():
    body = MIGRATION.read_text()
    assert "db_mode_has_bytes" in body


def test_the_attempt_index_is_unique_and_the_hash_index_is_not():
    """Two attempts may legitimately retrieve identical bytes."""
    body = MIGRATION.read_text()
    assert "ux_nf_source_collection_raw_payloads_attempt" in body
    assert "ix_nf_source_collection_raw_payloads_hash" in body
    # The unique one names both columns; the hash one is a plain index.
    attempt_block = body[body.index("ux_nf_source_collection_raw_payloads_attempt") :]
    assert "unique=True" in attempt_block[:400]


# -------------------------------------------------- 160B attempt identity


def test_the_same_attempt_is_always_the_same_id():
    first = build_attempt_identity(job_id="j", source_id="s", attempt_number=1)
    again = build_attempt_identity(job_id="j", source_id="s", attempt_number=1)
    assert first["attempt_id"] == again["attempt_id"]
    assert first["determinism_proof"]["matches"] is True
    assert attempt_identity_invariant_failures(first) == []


def test_a_retry_is_a_different_attempt():
    """Or attempt 2 would overwrite attempt 1's evidence."""
    first = build_attempt_identity(job_id="j", source_id="s", attempt_number=1)
    retry = build_attempt_identity(job_id="j", source_id="s", attempt_number=2)
    assert first["attempt_id"] != retry["attempt_id"]
    assert first["next_attempt_id"] == retry["attempt_id"]


def test_a_different_collector_version_is_a_different_attempt():
    first = build_attempt_identity(job_id="j", source_id="s", attempt_number=1)
    upgraded = build_attempt_identity(
        job_id="j", source_id="s", attempt_number=1, collector_version="v2"
    )
    assert first["attempt_id"] != upgraded["attempt_id"]


def test_an_attempt_id_is_not_a_job_id():
    identity = build_attempt_identity(job_id="j", source_id="s")
    assert identity["is_a_collection_job_id"] is False
    assert identity["attempt_id"] != identity["job_id"]


def test_the_identity_module_never_imports_the_job_digest():
    """Parsed, not scanned.

    The module's docstring says it never imports `build_job_id`, so a text
    search matches the sentence ruling it out - the ninth occurrence of that
    defect in this campaign.
    """
    imported = _imported_names(
        REPO_ROOT
        / "src/nativeforge/services/source_collection_attempt_identity_service.py"
    )
    assert "build_job_id" not in imported
    assert "build_idempotency_key" not in imported


def test_the_attempt_id_does_not_depend_on_a_uuid_or_a_clock():
    identity = build_attempt_identity(job_id="j", source_id="s")
    for forbidden in ("random_uuid", "pid", "worker_id", "wall_clock"):
        assert forbidden in identity["not_derived_from"]
    assert identity["attempt_id"] == build_attempt_id(
        job_id="j",
        source_id="s",
        attempt_number=FIRST_ATTEMPT,
        collector_version=UNKNOWN_COLLECTOR_VERSION,
    )


@pytest.mark.parametrize("bad", [0, -1, None, "x", 10_000])
def test_an_attempt_number_outside_the_range_is_refused(bad):
    identity = build_attempt_identity(job_id="j", source_id="s", attempt_number=bad)
    assert identity["usable"] is False
    assert identity["attempt_id"] is None
    assert attempt_identity_invariant_failures(identity) == []


def test_a_missing_job_id_yields_no_attempt_id():
    identity = build_attempt_identity(job_id="", source_id="s")
    assert identity["usable"] is False
    assert "no_job_id_supplied" in identity["blocked_reasons"]


# ---------------------------------------------------------- 160E hashing


def test_the_same_bytes_hash_the_same():
    assert (
        hash_payload(body=BINARY_BODY)["payload_sha256"]
        == hash_payload(body=BINARY_BODY)["payload_sha256"]
    )


def test_one_changed_byte_changes_the_hash():
    assert (
        hash_payload(body=BINARY_BODY)["payload_sha256"]
        != hash_payload(body=BINARY_BODY[:-1] + b"X")["payload_sha256"]
    )


def test_a_reserialized_structure_is_not_the_same_evidence():
    """THE rule: never hash a reserialized structure."""
    reserialized = json.dumps(json.loads(JSON_BODY.decode())).encode()
    assert (
        hash_payload(body=JSON_BODY)["payload_sha256"]
        != hash_payload(body=reserialized)["payload_sha256"]
    )


def test_the_hash_service_composes_gate_97c():
    """Parsed, not scanned.

    The docstring says the module contains no `hashlib` call, so a text search
    matches the sentence ruling it out.
    """
    path = REPO_ROOT / "src/nativeforge/services/source_raw_payload_hash_service.py"
    imported = _imported_names(path)
    # The digest has ONE home: Gate 97C's body_hash.
    assert "body_hash" in imported
    assert "hashlib" not in imported

    # Dotted NAME paths only. ast.unparse renders the whole callee expression
    # including its receiver, so `str(expected_sha256 or "").strip().lower`
    # contains the parameter name and a substring search matches it - which is
    # what the first version of this assertion did.
    called = _called_name_paths(path)
    assert "hashlib.sha256" not in called, sorted(called)
    assert "sha256" not in called, sorted(called)
    # Falsifiable: the scan does find the call that IS there.
    assert "body_hash" in called, sorted(called)


def test_non_utf8_bytes_are_hashable_and_not_text():
    result = hash_payload(body=BINARY_BODY)
    assert result["usable"] is True
    assert result["encoding"]["decodes_as_utf8"] is False
    assert result["encoding"]["is_text"] is False
    assert hash_invariant_failures(result) == []


def test_text_is_encoded_once_and_the_encoding_is_recorded():
    assert as_bytes("hello") == b"hello"
    assert describe_encoding(b"hello")["is_text"] is True


def test_a_dict_is_not_an_acceptable_body():
    """Accepting one would mean serializing it, and that is not the response."""
    result = hash_payload(body={"not": "bytes"})
    assert result["usable"] is False
    assert "body_is_not_bytes_or_text" in result["blocked_reasons"]


def test_an_oversize_body_is_refused_not_truncated():
    result = hash_payload(body=b"x" * (MAX_PAYLOAD_BYTES + 1))
    assert result["usable"] is False
    assert result["within_size_limit"] is False
    assert any("exceeds_max_bytes" in r for r in result["blocked_reasons"])
    # It still HAS a hash - hashable and storable are different questions.
    assert len(result["payload_sha256"]) == 64


def test_a_body_exactly_at_the_limit_is_accepted():
    """The permitting branch. A limit that refuses everything is a wall."""
    result = hash_payload(body=b"y" * MAX_PAYLOAD_BYTES)
    assert result["usable"] is True
    assert result["within_size_limit"] is True


def test_verification_catches_a_wrong_hash():
    good = verify_payload(
        body=JSON_BODY, expected_sha256=hash_payload(body=JSON_BODY)["payload_sha256"]
    )
    bad = verify_payload(body=JSON_BODY, expected_sha256="0" * 64)
    assert good["hash_verified"] is True
    assert bad["hash_verified"] is False
    assert "stored_bytes_do_not_match_the_recorded_hash" in bad["blocked_reasons"]


def test_the_algorithm_is_sha256():
    assert hash_payload(body=b"x")["algorithm"] == HASH_ALGORITHM == "sha256"


# ------------------------------------------------- 160F the metadata filter


def test_the_four_required_headers_are_refused():
    for name in ("Authorization", "Cookie", "Set-Cookie", "X-API-Key"):
        decision = classify_header(name, "anything")
        assert decision["decision"] == REFUSED_CREDENTIAL, name


def test_a_header_nobody_has_classified_is_refused():
    """The whole argument for an allowlist."""
    assert (
        classify_header("X-Acme-Session", "v")["decision"] == REFUSED_UNRECOGNISED
    )


def test_a_safe_header_SURVIVES():
    """The defect: the filter refused everything for one commit.

    The secret scanner was called with the wrong keyword, every call raised,
    the exception was caught, and every allowlisted header was refused with a
    plausible reason. Only asserting that a safe header survives catches it.
    """
    result = filter_response_metadata(
        headers={
            "Content-Type": "application/json",
            "ETag": 'W/"v1"',
            "Cache-Control": "public, max-age=300",
            "Retry-After": "120",
            "Authorization": "Bearer nope",
        }
    )
    assert set(result["safe_headers"]) == {
        "content-type",
        "etag",
        "cache-control",
        "retry-after",
    }
    assert result["safe_header_count"] == 4
    assert metadata_filter_invariant_failures(result) == []


def test_the_allowlist_and_the_credential_set_do_not_overlap():
    assert ALLOWED_RESPONSE_HEADERS & CREDENTIAL_HEADERS == set()


def test_header_names_are_normalized_before_deciding():
    assert normalize_header_name("  Content-TYPE  ") == "content-type"
    assert classify_header("CONTENT-TYPE", "application/json")["decision"] == KEPT


def test_a_credential_inside_an_allowed_header_is_refused_not_redacted():
    sneaky = classify_header(
        "Cache-Control",
        "private, token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturehere",
    )
    assert sneaky["decision"] != KEPT
    # A redacted value would be neither the truth nor absent.
    assert "REDACTED" not in str(sneaky)


@pytest.mark.parametrize(
    ("name", "expected_kept"),
    [
        # A naive substring scan gets all three of these wrong.
        ("X-RateLimit-Remaining", True),
        ("X-Cache-Key", False),
        ("X-Acme-Session", False),
    ],
)
def test_substring_traps_a_naive_scan_would_get_wrong(name, expected_kept):
    decision = classify_header(name, "123")
    assert (decision["decision"] == KEPT) is expected_kept


def test_an_oversize_header_value_is_refused():
    decision = classify_header("ETag", "x" * (MAX_HEADER_VALUE_LENGTH + 1))
    assert decision["decision"] != KEPT


def test_too_many_headers_refuses_the_whole_response():
    result = filter_response_metadata(headers={f"X-H{i}": "v" for i in range(100)})
    assert result["usable"] is False
    assert result["safe_header_count"] == 0


def test_refused_header_values_are_never_reported():
    result = filter_response_metadata(
        headers={"Authorization": "Bearer super-secret-value-here"}
    )
    assert "super-secret-value-here" not in json.dumps(result)
    # Names only.
    assert result["refused_header_names"] == ["authorization"]


def test_the_invariant_checker_catches_a_kept_credential():
    assert any(
        "kept_a_credential_header" in failure
        for failure in metadata_filter_invariant_failures(
            {"safe_headers": {"authorization": "Bearer x"}, "decisions": []}
        )
    )


# ------------------------------------------------------ 160D the repository


def test_a_payload_persists_and_reads_back(connection):
    tag = "t160a"
    written = _write(connection, tag, BINARY_BODY)
    assert written["persisted"] is True
    assert written["write_hash_verified"] is True
    assert written["readback_hash_verified"] is True
    assert persistence_invariant_failures(written) == []


def test_the_exact_bytes_round_trip_including_non_utf8(connection):
    """The defect: the body came back as a lossy Python repr string."""
    tag = "t160b"
    written = _write(connection, tag, BINARY_BODY)
    read = get_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id=written["attempt_id"],
        include_body=True,
    )
    # Raw bytes, attached outside the JSON envelope.
    assert read["body_bytes"] == BINARY_BODY
    # And base64 inside it, which round-trips.
    assert base64.b64decode(read["payload"]["body_base64"]) == BINARY_BODY
    assert read["payload"]["body_encoding"] == "base64"


def test_the_same_attempt_with_identical_bytes_is_idempotent(connection):
    tag = "t160c"
    first = _write(connection, tag, JSON_BODY)
    again = _write(connection, tag, JSON_BODY)
    assert first["persisted"] is True
    assert again["persisted"] is False
    assert again["deduplicated"] is True
    assert again["blocked_reasons"] == []


def test_the_same_attempt_with_different_bytes_is_refused(connection):
    """Overwriting would destroy the evidence that they disagreed."""
    tag = "t160d"
    _write(connection, tag, JSON_BODY)
    conflict = _write(connection, tag, JSON_BODY + b"different")
    assert conflict["persisted"] is False
    assert any(
        "already_stored_different_bytes" in reason
        for reason in conflict["blocked_reasons"]
    )


def test_a_retry_stores_its_own_evidence(connection):
    tag = "t160e"
    first = _write(connection, tag, JSON_BODY, attempt=1)
    retry = _write(connection, tag, JSON_BODY + b" v2", attempt=2)
    assert first["persisted"] is True
    assert retry["persisted"] is True
    assert first["payload_sha256"] != retry["payload_sha256"]
    listed = list_payloads(
        connection=connection, organization_id=DEMO, job_id=f"{tag}-job"
    )
    assert listed["payload_count"] == 2


def test_two_attempts_may_share_identical_bytes(connection):
    """A source that has not changed is normal, not an error."""
    tag = "t160f"
    _write(connection, tag, JSON_BODY, attempt=1)
    second = _write(connection, tag, JSON_BODY, attempt=2)
    assert second["persisted"] is True
    same_hash = list_payloads(
        connection=connection,
        organization_id=DEMO,
        payload_sha256=second["payload_sha256"],
    )
    assert same_hash["payload_count"] == 2


def test_a_declared_hash_that_does_not_match_is_refused(connection):
    result = persist_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id="t160-liar",
        job_id="j",
        source_id="s",
        body=JSON_BODY,
        declared_sha256="0" * 64,
        received_at=T0,
    )
    assert result["stored"] is False
    assert any(
        "declared_hash_does_not_match" in reason
        for reason in result["blocked_reasons"]
    )


def test_an_oversize_payload_is_refused_by_the_repository(connection):
    tag = "t160g"
    result = _write(connection, tag, b"x" * (MAX_PAYLOAD_BYTES + 1))
    assert result["persisted"] is False
    assert any("exceeds_max_bytes" in r for r in result["blocked_reasons"])


def test_the_database_refuses_an_oversize_row(connection):
    """The CHECK is real, not only a service-level guard."""
    tag = "t160h"
    _write(connection, tag, JSON_BODY)
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "UPDATE nf_source_collection_raw_payloads "
                    "SET payload_size_bytes = 99999999"
                )
            )


def test_the_database_refuses_a_row_claiming_a_collector(connection):
    tag = "t160i"
    _write(connection, tag, JSON_BODY)
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "UPDATE nf_source_collection_raw_payloads "
                    "SET collector_invoked = 1"
                )
            )


def test_the_repository_refuses_unsafe_metadata(connection):
    """A caller that skipped the filter cannot write through this door."""
    result = persist_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id="t160-unsafe",
        job_id="j",
        source_id="s",
        body=JSON_BODY,
        received_at=T0,
        safe_response_metadata={"authorization": "Bearer x"},
    )
    assert result["stored"] is False
    assert any(
        "credential_header" in reason for reason in result["blocked_reasons"]
    )


def test_the_real_organization_is_refused_by_name(connection):
    result = persist_payload(
        connection=connection,
        organization_id=REAL_ORG,
        attempt_id="never",
        job_id="j",
        source_id="s",
        body=b"x",
        received_at=T0,
    )
    assert result["stored"] is False
    assert "real_organization_refused_by_name" in result["blocked_reasons"]


def test_the_url_is_fingerprinted_never_stored(connection):
    tag = "t160j"
    secret_url = "https://example.gov/api?api_key=SUPERSECRET123"
    _write(connection, tag, JSON_BODY, source_url=secret_url)
    row = (
        connection.execute(
            sa.select(PAYLOADS).where(PAYLOADS.c.job_id == f"{tag}-job")
        )
        .mappings()
        .first()
    )
    assert "SUPERSECRET123" not in str(dict(row))
    assert row["source_url_fingerprint"] == fingerprint_url(secret_url)
    assert len(row["source_url_fingerprint"]) == 64


def test_the_default_retention_policy_is_unknown(connection):
    """Nobody has approved one. Picking retain_90_days would invent it."""
    tag = "t160k"
    written = _write(connection, tag, JSON_BODY)
    read = get_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert read["payload"]["retention_policy"] == RETENTION_UNKNOWN
    assert read["payload"]["retention_is_unknown"] is True


def test_archive_keeps_a_payload_readable(connection):
    tag = "t160l"
    written = _write(connection, tag, JSON_BODY)
    archived = archive_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id=written["attempt_id"],
        now=T0,
    )
    assert archived["archived"] is True
    assert archived["payload"]["payload_status"] == ARCHIVED
    assert archived["payload"]["archived_at"] is not None

    read = get_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id=written["attempt_id"],
        include_body=True,
    )
    assert read["hash_verified"] is True
    assert read["body_bytes"] == JSON_BODY


def test_nothing_in_this_gate_deletes():
    """Deletion needs an approved retention policy and none exists."""
    module = (
        REPO_ROOT
        / "src/nativeforge/repositories/source_collection_raw_payload_repository.py"
    ).read_text()
    tree = ast.parse(module)
    # Parsed, not scanned: the docstrings discuss deletion to explain its
    # absence.
    deletes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and "delete" in ast.unparse(node.func).lower()
    ]
    assert deletes == [], [ast.unparse(node) for node in deletes]


def test_the_counts_report_every_bucket(connection):
    counts = count_payloads(connection=connection, organization_id=DEMO)
    assert set(counts["by_status"]) == set(PAYLOAD_STATUSES)
    assert set(counts["by_storage_mode"]) == set(BODY_STORAGE_MODES)
    assert counts["rows_claiming_a_collector"] == 0
    assert counts["rows_claiming_a_live_fetch"] == 0
    assert raw_payload_invariant_failures(counts) == []


def test_a_listing_never_carries_a_body(connection):
    tag = "t160m"
    _write(connection, tag, JSON_BODY)
    listed = list_payloads(
        connection=connection, organization_id=DEMO, job_id=f"{tag}-job"
    )
    for payload in listed["payloads"]:
        assert "body_base64" not in payload
        assert "body_bytes" not in payload


def test_the_storage_mode_is_the_database(connection):
    tag = "t160n"
    written = _write(connection, tag, JSON_BODY)
    read = get_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert read["payload"]["body_storage_mode"] == MODE_DATABASE
    assert read["payload"]["payload_status"] == ACTIVE


# ------------------------------------------------------------ 160H replay


def test_replay_returns_the_exact_bytes(connection):
    tag = "t160o"
    written = _write(connection, tag, BINARY_BODY)
    played = replay_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert played["replayable"] is True
    assert played["hash_verified"] is True
    assert base64.b64decode(played["body_base64"]) == BINARY_BODY
    assert replay_invariant_failures(played) == []


def test_replay_resolves_provenance_by_looking(connection):
    """The defect: this compared a string id against a typed Uuid column."""
    tag = "t160p"
    enqueue_job(
        connection=connection,
        organization_id=DEMO,
        job_id=f"{tag}-job",
        idempotency_key=f"{tag}-job",
        source_id=f"{tag}-src",
        now=T0,
        created_by_runtime="verifier_fixture",
    )
    written = _write(connection, tag, JSON_BODY)
    played = replay_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert played["linked_job_found"] is True
    assert played["provenance"]["job_id"] == f"{tag}-job"
    assert played["provenance"]["source_id"] == f"{tag}-src"


def test_a_payload_pointing_at_no_job_reports_the_link_as_missing(connection):
    """The falsifying case: the check LOOKS rather than trusting the column."""
    tag = "t160q"
    written = _write(connection, tag, JSON_BODY)
    played = replay_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert played["linked_job_found"] is False


def test_a_tampered_body_fails_replay_and_returns_no_bytes(connection):
    tag = "t160r"
    written = _write(connection, tag, JSON_BODY)
    connection.execute(
        sa.text(
            "UPDATE nf_source_collection_raw_payloads SET body_bytes = :body "
            "WHERE attempt_id = :attempt"
        ),
        {"body": b"tampered", "attempt": written["attempt_id"]},
    )
    played = replay_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert played["hash_verified"] is False
    assert played["replayable"] is False
    # THE invariant: no bytes at all, not bytes with a warning beside them.
    assert played["body_base64"] is None
    assert replay_invariant_failures(played) == []


def test_the_invariant_checker_catches_a_body_returned_unverified():
    assert (
        "returned_a_body_without_verifying_the_hash"
        in replay_invariant_failures(
            {"body_base64": "abc", "hash_verified": False, "replayable": False}
        )
    )


def test_cross_organization_replay_finds_nothing(connection):
    tag = "t160s"
    written = _write(connection, tag, JSON_BODY)
    played = replay_payload(
        connection=connection, organization_id=OTHER, attempt_id=written["attempt_id"]
    )
    assert played["replayable"] is False
    assert played["body_base64"] is None


def test_an_archived_payload_is_still_replayable(connection):
    tag = "t160t"
    written = _write(connection, tag, JSON_BODY)
    archive_payload(
        connection=connection,
        organization_id=DEMO,
        attempt_id=written["attempt_id"],
        now=T0,
    )
    played = replay_payload(
        connection=connection, organization_id=DEMO, attempt_id=written["attempt_id"]
    )
    assert played["archived"] is True
    assert played["readable"] is True
    assert played["replayable"] is True


# ------------------------------------------------------------ 160K health


def test_a_fully_evidenced_lane_goes_green():
    health = build_raw_payload_health(
        table_exists=True,
        write_result={"write_hash_verified": True, "readback_hash_verified": True},
        replay_result={"hash_verified": True},
        tamper_result={
            "hash_verified": False,
            "replayable": False,
            "body_base64": None,
        },
        conflict_result={
            "persisted": False,
            "blocked_reasons": ["this_attempt_already_stored_different_bytes:x"],
        },
        metadata_result={
            "safe_headers": {"content-type": "application/json"},
            "refused_header_names": [
                "authorization",
                "cookie",
                "set-cookie",
                "x-api-key",
            ],
        },
        oversize_result={
            "persisted": False,
            "blocked_reasons": ["payload_exceeds_max_bytes:1>0"],
        },
        archived_replay_result={"archived": True, "replayable": True},
        counts={
            "by_status": dict.fromkeys(PAYLOAD_STATUSES, 0),
            "total": 0,
            "rows_claiming_a_collector": 0,
            "rows_claiming_a_live_fetch": 0,
            "rows_over_the_size_limit": 0,
        },
        bytes_round_tripped=True,
    )
    assert health["raw_payload_persistence_ready"] is True
    assert health["blockers"] == []
    assert raw_payload_health_invariant_failures(health) == []


def test_a_filter_that_kept_nothing_closes_the_lane():
    """The condition that catches the wrong-keyword defect."""
    health = build_raw_payload_health(
        metadata_result={
            "safe_headers": {},
            "refused_header_names": [
                "authorization",
                "cookie",
                "set-cookie",
                "x-api-key",
                "content-type",
            ],
        }
    )
    assert health["conditions"]["safe_headers_survive"] is False


def test_a_tamper_that_returned_bytes_does_not_count_as_detected():
    health = build_raw_payload_health(
        tamper_result={
            "hash_verified": False,
            "replayable": False,
            "body_base64": "abc",
        }
    )
    assert health["conditions"]["tamper_detected"] is False


def test_a_row_claiming_a_collector_closes_the_lane():
    health = build_raw_payload_health(
        counts={
            "by_status": {},
            "total": 1,
            "rows_claiming_a_collector": 1,
            "rows_claiming_a_live_fetch": 0,
            "rows_over_the_size_limit": 0,
        }
    )
    assert health["raw_payload_persistence_ready"] is False
    assert any("claims_a_collector" in b for b in health["blockers"])


def test_ready_alongside_blockers_is_an_invariant_failure():
    assert "ready_alongside_blockers" in raw_payload_health_invariant_failures(
        {
            "raw_payload_persistence_ready": True,
            "blockers": ["x"],
            "conditions": {},
            "ready_does_not_mean": ["y"],
        }
    )


def test_every_condition_carries_evidence():
    health = build_raw_payload_health()
    for condition in CONDITIONS:
        assert health["condition_evidence"].get(condition, "").strip()


def test_the_object_store_is_measured_not_declared():
    """Read from Gate 97C's own config, so it changes if one is configured."""
    assert detect_object_store_configured() is False
    module = (
        REPO_ROOT / "src/nativeforge/services/source_raw_payload_health_service.py"
    ).read_text()
    assert "build_client_config" in module


def test_the_health_service_opens_no_connection():
    module = (
        REPO_ROOT / "src/nativeforge/services/source_raw_payload_health_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "sa.insert", "sa.update"):
        assert forbidden not in module


def test_the_lane_names_what_ready_does_not_mean():
    health = build_raw_payload_health()
    assert "a source was contacted" in health["ready_does_not_mean"]
    assert "production raw payload storage is available" in health[
        "ready_does_not_mean"
    ]


# ------------------------------------------------------------ 160L routes


@pytest.mark.parametrize("path", ["health", ""])
def test_the_read_routes_answer(client, path):
    soh.ensure_org(DEMO, "demo")
    url = f"/v1/nf/demo/orgs/{DEMO}/raw-payloads"
    if path:
        url += f"/{path}"
    assert client.get(url, headers=soh.session_headers(DEMO)).status_code == 200


def test_the_routes_need_a_session(client):
    soh.ensure_org(DEMO, "demo")
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/raw-payloads/health"
    ).status_code in (401, 403)


def test_another_organization_gets_a_404_not_a_403(client):
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    assert (
        client.get(
            f"/v1/nf/demo/orgs/{OTHER}/raw-payloads/health",
            headers=soh.session_headers(DEMO),
        ).status_code
        == 404
    )


def test_the_smoke_route_persists_nothing(client):
    soh.ensure_org(DEMO, "demo")
    response = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/raw-payloads/smoke",
        headers=soh.session_headers(DEMO),
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rows_after"] == body["rows_before"]
    assert body["nothing_persisted"] is True
    # And it was not a no-op.
    assert body["the_savepoint_actually_held_rows"] is True
    assert body["write_hash_verified"] is True
    assert body["readback_hash_verified"] is True
    assert body["invariant_failures"] == []
    assert body["object_store_configured"] is False
    assert body["source_monitoring_live"] is False


def test_the_smoke_route_accepts_no_caller_body(client):
    """A route storing caller bytes would be an upload endpoint."""
    soh.ensure_org(DEMO, "demo")
    body = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/raw-payloads/smoke",
        headers=soh.session_headers(DEMO),
        json={"body": "malicious", "url": "https://evil.example/"},
    ).json()
    assert body["route_accepts_no_caller_body"] is True
    assert body["route_fetches_no_url"] is True
    assert body["body_was_synthetic_not_fetched"] is True


def test_the_smoke_route_refuses_the_unsafe_headers(client):
    soh.ensure_org(DEMO, "demo")
    body = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/raw-payloads/smoke",
        headers=soh.session_headers(DEMO),
        json={},
    ).json()
    assert "authorization" in body["headers_refused"]
    assert "set-cookie" in body["headers_refused"]
    # And kept the safe ones.
    assert "content-type" in body["safe_headers_kept"]


def test_the_health_route_leaves_no_row_behind(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/raw-payloads/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["health_probe_rolled_back"] is True
    assert body["health_probe_rows_left_behind"] == 0


def test_every_route_write_is_inside_a_savepoint():
    module = (
        REPO_ROOT / "src/nativeforge/api/source_raw_payload_routes.py"
    ).read_text()
    assert module.count("begin_nested()") == 2
    assert module.count("savepoint.rollback()") == 2


# -------------------------------------------------------- 160O artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = write_raw_payload_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(ARTIFACT_FILES)
    assert raw_payload_artifact_invariant_failures(result) == []


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    for name, body in build_raw_payload_artifacts().items():
        on_disk = (REPO_ROOT / ARTIFACT_DIR / name).read_text()
        assert on_disk == body, f"{name} is stale; run .git/regen2.py"


def test_the_artifact_writer_opens_no_database():
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_raw_payload_artifact_gate160_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "get_settings"):
        assert forbidden not in module


def test_the_artifacts_carry_no_secret_shape():
    for body in build_raw_payload_artifacts().values():
        assert "GOCSPX-" not in body
        assert "nf_session=" not in body
        assert "BEGIN PRIVATE KEY" not in body


def test_the_monitoring_artifact_records_every_forbidden_persistence():
    status = json.loads(
        build_raw_payload_artifacts()["source_monitoring_status.json"]
    )
    for field in (
        "authorization_persisted",
        "cookie_persisted",
        "set_cookie_persisted",
        "api_keys_persisted",
        "request_url_persisted",
        "customer_data_persisted",
        "creates_execution_proof",
        "source_monitoring_live",
    ):
        assert status[field] is False, field
    assert status["object_store_configured"] is False
    assert status["approved_source_count"] == 0


# ---------------------------------------------- the verifier contract


def test_the_verifier_exists_and_is_executable():
    script = (
        REPO_ROOT / "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
    )
    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_the_verifier_is_registered():
    from nativeforge.services.readiness_verifier_registry_service import (
        build_verifier_registry,
    )

    registry = build_verifier_registry()
    assert "source_raw_payload_persistence" in registry["verifier_names"]
    entry = next(
        e
        for e in registry["verifiers"]
        if e["verifier"] == "source_raw_payload_persistence"
    )
    assert entry["lane"] == "raw_payload_persistence_ready"
    assert entry["gate"] == "160"


def test_the_verifier_proves_the_restart_in_a_separate_process():
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
    ).read_text()
    assert "scripts/_g160_phase_a.py" in body
    assert "scripts/_g160_phase_b.py" in body


def test_the_verifier_cleans_up_after_the_final_write():
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
    ).read_text()
    cleanup = body.index("_g160_phase_cleanup.py")
    for phase in ("_g160_phase_a.py", "_g160_phase_b.py", "_g160_phase_health.py"):
        assert body.index(phase) < cleanup, f"{phase} runs after cleanup"


def test_the_verifier_fails_a_cleanup_that_deleted_nothing():
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
    ).read_text()
    assert "cleanup_had_something_to_clean" in body
    assert "a cleanup that deletes nothing is untested" in body


@pytest.mark.parametrize(
    "phase",
    [
        "_g160_phase_a.py",
        "_g160_phase_b.py",
        "_g160_phase_health.py",
        "_g160_phase_cleanup.py",
    ],
)
def test_every_phase_script_compiles(phase):
    path = REPO_ROOT / "scripts" / phase
    assert path.exists()
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# ------------------------------------------------------ the standing boundary


@pytest.mark.parametrize("module", GATE_160_MODULES)
def test_no_gate_160_module_imports_an_http_client(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("import requests", "import httpx", "urllib.request", "aiohttp"):
        assert forbidden not in body, f"{module} reaches the network"


@pytest.mark.parametrize("module", GATE_160_MODULES)
def test_no_gate_160_module_imports_an_object_store_sdk(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("import boto3", "botocore", "minio", "google.cloud.storage"):
        assert forbidden not in body, f"{module} imports an SDK"


@pytest.mark.parametrize("module", GATE_160_MODULES)
def test_no_gate_160_module_sends_email(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("smtplib", "sendgrid", "send_email"):
        assert forbidden not in body


def test_no_gate_160_module_creates_an_execution_proof():
    """Gate 158 left `completed` unreachable. Gate 160 does not change that."""
    for module in GATE_160_MODULES:
        body = (REPO_ROOT / module).read_text()
        tree = ast.parse(body)
        assigned = {
            keyword.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg
        }
        assert "execution_proof_ref" not in assigned, module


def test_the_gate_does_not_widen_the_gate_96_metadata_table():
    """Gate 96C's contract: that table holds metadata, never a body.

    Checked by what the migration CREATES, not by scanning its text - the
    docstring discusses nf_raw_source_payloads at length to explain why a
    separate table exists, so a text search matches the explanation.
    """
    module = _load_migration_module()
    assert module.PAYLOADS == "nf_source_collection_raw_payloads"

    tree = ast.parse(MIGRATION.read_text())
    # Every table this migration touches, by name, from the actual calls.
    touched = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            rendered = ast.unparse(node.func)
            if rendered in ("op.create_table", "op.drop_table", "op.add_column"):
                touched.add(ast.unparse(node.args[0]) if node.args else "?")
    assert touched <= {"PAYLOADS"}, touched


def test_the_new_table_is_not_the_gate_96_table():
    from nativeforge.repositories.source_collection_raw_payload_repository import (
        TABLE_NAME,
    )

    assert TABLE_NAME == "nf_source_collection_raw_payloads"
    assert TABLE_NAME != "nf_raw_source_payloads"


def test_retention_policies_compose_the_existing_vocabulary():
    from nativeforge.services.raw_payload_store_contract_service import (
        RETENTION_POLICIES as EXISTING,
    )

    # Every existing policy is accepted, plus the honest default.
    assert set(EXISTING) <= set(RETENTION_POLICIES)
    assert RETENTION_UNKNOWN in RETENTION_POLICIES
