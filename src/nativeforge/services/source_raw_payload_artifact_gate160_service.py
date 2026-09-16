"""Gate 160O artifacts: the raw payload spine, measured rather than described.

Ten files. Every number comes from calling the code it describes - the hashes
are computed, the header decisions are decided, the refusals are produced by
actually asking for them.

Nothing here opens a database. An artifact writer that needed a connection would
produce different files on different machines, and the suite compares these
against a fresh build.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.source_collection_raw_payload_repository import (
    BODY_STORAGE_MODES,
    MODE_DATABASE,
    PAYLOAD_STATUSES,
    RETENTION_POLICIES,
    RETENTION_UNKNOWN,
    TABLE_NAME,
    persist_payload,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_collection_attempt_identity_service import (
    ATTEMPT_VERSION,
    UNKNOWN_COLLECTOR_VERSION,
    attempt_identity_invariant_failures,
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_hash_service import (
    COMPOSED_FROM,
    HASH_ALGORITHM,
    MAX_PAYLOAD_BYTES,
    hash_invariant_failures,
    hash_payload,
    verify_payload,
)
from nativeforge.services.source_raw_payload_health_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    READY_DOES_NOT_MEAN,
    detect_object_store_configured,
)
from nativeforge.services.source_raw_payload_persistence_service import (
    COMPOSES,
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
    DECISIONS,
    MAX_HEADER_VALUE_LENGTH,
    classify_header,
    filter_response_metadata,
    metadata_filter_invariant_failures,
)

SCHEMA_VERSION = "nf_source_raw_payload_gate160_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_raw_payload_gate160"

SURVEY_FILE = "raw_payload_persistence_survey.json"
IDENTITY_FILE = "attempt_identity.json"
HASH_FILE = "payload_hash_smoke.json"
FILTER_FILE = "metadata_filter_smoke.json"
WRITE_FILE = "payload_write_readback.json"
TAMPER_FILE = "payload_tamper_refusal.json"
ARCHIVE_FILE = "payload_archive_smoke.json"
HEALTH_FILE = "payload_health.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_raw_payload_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    IDENTITY_FILE,
    HASH_FILE,
    FILTER_FILE,
    WRITE_FILE,
    TAMPER_FILE,
    ARCHIVE_FILE,
    HEALTH_FILE,
    MONITORING_FILE,
    BLOCKERS_FILE,
)

FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

MIGRATION = "0046"

#: A fixed synthetic body, so a rebuild is byte-identical.
FIXTURE_BODY = (
    b'{"synthetic":true,"note":"Gate 160 fixture. Not fetched from anywhere.",'
    b'"opportunities":[]}'
)

FIXTURE_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "ETag": 'W/"gate160-fixture"',
    "Cache-Control": "no-store",
    "Authorization": "Bearer this-must-be-refused",
    "Cookie": "this=must-be-refused",
    "Set-Cookie": "this=must-be-refused",
    "X-API-Key": "this-must-be-refused",
    "X-Acme-Session": "unclassified-header-must-be-refused",
    "Server": "nginx",
}


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": SURVEY_FILE,
        "migration": MIGRATION,
        "measured_before_building": {
            "nf_raw_source_payloads_exists": True,
            "nf_raw_source_payloads_rows": 0,
            "nf_raw_source_payloads_has_a_body_column": False,
            "raw_payload_ref_is_a_pointer": True,
            "object_store_endpoint": "",
            "object_store_bucket": "",
            "body_store_configured": False,
            "production_raw_payload_store_available": False,
            "compression_utilities_in_the_repo": 0,
            "response_header_filters_in_the_repo": 0,
        },
        "the_gap": (
            "response METADATA had a home and response BODIES did not. "
            "raw_payload_ref is a VARCHAR pointer to an object store that has "
            "no bucket, endpoint or credential, and Gate 96C's repository "
            "rejects store_body=True outright."
        ),
        "why_a_new_table": (
            "Gate 96C's docstring gives the reason a body does not belong in "
            "nf_raw_source_payloads - 'a table that sometimes holds bodies is "
            "a table whose size nobody can predict' - and Gate 160 does not "
            "get to overturn that by widening the same table."
        ),
        "why_not_a_second_object_store": (
            "Option B is already implemented by Gate 97C and blocked on "
            "configuration rather than on code. A second abstraction would "
            "produce two stores, one of them fake."
        ),
        "storage_mode_chosen": MODE_DATABASE,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "why_one_megabyte": (
            "Gate 141's object adapter allows 16 MiB, but that is an OBJECT "
            "adapter's limit and a database row is not an object. 1 MiB holds "
            "a synthetic fixture or a realistic API page and makes clear this "
            "is not the production path."
        ),
        "composed_not_rebuilt": {
            "body_hash": COMPOSED_FROM,
            "retention_policies": sorted(RETENTION_POLICIES),
            "secret_scan": "raw_payload_secret_scan_service, for header VALUES",
        },
    }


def _identity() -> dict[str, Any]:
    first = build_attempt_identity(job_id="job-a", source_id="src-a", attempt_number=1)
    same = build_attempt_identity(job_id="job-a", source_id="src-a", attempt_number=1)
    retry = build_attempt_identity(job_id="job-a", source_id="src-a", attempt_number=2)
    other_job = build_attempt_identity(
        job_id="job-b", source_id="src-a", attempt_number=1
    )
    other_collector = build_attempt_identity(
        job_id="job-a",
        source_id="src-a",
        attempt_number=1,
        collector_version="grants-gov-v2",
    )
    unusable = build_attempt_identity(job_id="", source_id="src-a")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": IDENTITY_FILE,
        "attempt_version": ATTEMPT_VERSION,
        "default_collector_version": UNKNOWN_COLLECTOR_VERSION,
        "measured": {
            "same_attempt_twice_is_the_same_id": (
                first["attempt_id"] == same["attempt_id"]
            ),
            "a_retry_is_a_DIFFERENT_attempt": (
                first["attempt_id"] != retry["attempt_id"]
            ),
            "a_different_job_is_a_different_attempt": (
                first["attempt_id"] != other_job["attempt_id"]
            ),
            "a_different_collector_is_a_different_attempt": (
                first["attempt_id"] != other_collector["attempt_id"]
            ),
            "an_attempt_id_is_not_a_job_id": first["is_a_collection_job_id"],
            "no_job_id_yields_no_attempt_id": unusable["attempt_id"] is None,
        },
        "invariant_failures": {
            "usable": attempt_identity_invariant_failures(first),
            "unusable": attempt_identity_invariant_failures(unusable),
        },
        "derived_from": first["derived_from"],
        "not_derived_from": first["not_derived_from"],
        "why_a_retry_must_differ": (
            "a job retried three times is one job and three attempts. If the "
            "ids collided, attempt 2 would overwrite attempt 1's evidence - "
            "and the whole point of a raw payload spine is that the bytes from "
            "two attempts are separately inspectable when they disagree."
        ),
        "why_collector_version_is_in_the_digest": (
            "when a collector changes, the bytes it produces for the same slot "
            "may legitimately differ. Without it the store would have to choose "
            "between refusing the new bytes and silently overwriting the old."
        ),
    }


def _hash_smoke() -> dict[str, Any]:
    a = hash_payload(body=FIXTURE_BODY)
    b = hash_payload(body=FIXTURE_BODY)
    one_byte = hash_payload(body=FIXTURE_BODY[:-1] + b"X")
    empty = hash_payload(body=b"")
    binary = hash_payload(body=b"\xff\xfe\x00 not utf-8 \x80")
    oversize = hash_payload(body=b"x" * (MAX_PAYLOAD_BYTES + 1))
    reserialized = json.dumps(json.loads(FIXTURE_BODY.decode())).encode()

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": HASH_FILE,
        "algorithm": HASH_ALGORITHM,
        "composed_from": COMPOSED_FROM,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "measured": {
            "same_bytes_same_hash": a["payload_sha256"] == b["payload_sha256"],
            "one_byte_changes_the_hash": (
                a["payload_sha256"] != one_byte["payload_sha256"]
            ),
            "a_reserialized_structure_hashes_differently": (
                hash_payload(body=reserialized)["payload_sha256"]
                != a["payload_sha256"]
            ),
            "empty_is_hashable": empty["usable"],
            "non_utf8_is_hashable": binary["usable"],
            "non_utf8_is_not_text": not binary["encoding"]["is_text"],
            "oversize_is_refused": not oversize["usable"],
            "readback_verifies": verify_payload(
                body=FIXTURE_BODY, expected_sha256=a["payload_sha256"]
            )["hash_verified"],
            "a_wrong_hash_is_refused": not verify_payload(
                body=FIXTURE_BODY, expected_sha256="0" * 64
            )["hash_verified"],
        },
        "fixture": {
            "size_bytes": a["payload_size_bytes"],
            "sha256": a["payload_sha256"],
            "encoding": a["encoding"],
        },
        "oversize_refusal": oversize["blocked_reasons"],
        "invariant_failures": hash_invariant_failures(a),
        "the_rule": (
            "never hash a reserialized structure. If a collector receives 412 "
            "bytes of JSON, the evidence hash is of those 412 bytes - not of "
            "json.dumps(json.loads(body)), which reorders keys and produces a "
            "digest that no longer identifies what arrived."
        ),
    }


def _filter_smoke() -> dict[str, Any]:
    result = filter_response_metadata(headers=FIXTURE_HEADERS)
    sneaky = classify_header(
        "Cache-Control", "private, token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    )
    normal = classify_header("Cache-Control", "public, max-age=300")
    oversize = classify_header("ETag", "x" * (MAX_HEADER_VALUE_LENGTH + 1))

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": FILTER_FILE,
        "policy": result["policy"],
        "allowlist": sorted(ALLOWED_RESPONSE_HEADERS),
        "known_credential_headers": sorted(CREDENTIAL_HEADERS),
        "decisions": list(DECISIONS),
        "max_header_value_length": MAX_HEADER_VALUE_LENGTH,
        "measured": {
            "headers_supplied": result["headers_supplied"],
            "kept": result["safe_header_count"],
            "refused": result["headers_refused"],
            "by_decision": result["by_decision"],
            # Names only, never values.
            "refused_names": result["refused_header_names"],
            "kept_names": sorted(result["safe_headers"]),
        },
        "the_four_required_refusals": {
            "authorization": result["refuses_authorization"],
            "cookie": result["refuses_cookie"],
            "set_cookie": result["refuses_set_cookie"],
            "api_key": result["refuses_api_key"],
        },
        "a_credential_inside_an_allowed_header": {
            "header": "cache-control",
            "decision": sneaky["decision"],
            "why": sneaky["why"],
        },
        "a_clean_allowed_header_survives": {
            "header": "cache-control",
            "decision": normal["decision"],
        },
        "an_oversize_value": oversize["decision"],
        "substring_traps_a_naive_scan_gets_wrong": {
            "x-ratelimit-remaining": classify_header(
                "X-RateLimit-Remaining", "4999"
            )["decision"],
            "x-cache-key": classify_header("X-Cache-Key", "abc")["decision"],
            "x-acme-session": classify_header("X-Acme-Session", "abc")["decision"],
        },
        "invariant_failures": metadata_filter_invariant_failures(result),
        "why_an_allowlist": (
            "a denylist keeps a header because nothing on a list of bad words "
            "matched it. A new provider invents X-Acme-Session, no pattern "
            "matches, and it is persisted forever. An allowlist refuses it by "
            "default, which is correct for a header nobody has looked at."
        ),
    }


def _write_readback() -> dict[str, Any]:
    """A write requested with NO connection. The refusal is the artifact."""
    refused = persist_raw_payload(
        connection=None,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        job_id="artifact-fixture-job",
        source_id="artifact-fixture-source",
        attempt_number=1,
        body=FIXTURE_BODY,
        response_headers=FIXTURE_HEADERS,
        received_at="2026-09-15T12:00:00Z",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": WRITE_FILE,
        "table": TABLE_NAME,
        "storage_mode": MODE_DATABASE,
        "composes": list(COMPOSES),
        "the_six_steps": [
            "validate the attempt identity",
            "filter the response metadata",
            "hash the EXACT bytes",
            "persist",
            "re-read through the store",
            "verify the readback hash",
        ],
        "a_write_without_a_connection": {
            "persisted": refused["persisted"],
            "blocked_reasons": refused["blocked_reasons"],
            "invariant_failures": persistence_invariant_failures(refused),
        },
        "url_handling": {
            "stored": "a sha256 fingerprint",
            "not_stored": "the URL",
            "why": (
                "query strings carry api keys. A fingerprint answers 'is this "
                "the same endpoint as last time' without storing what the "
                "endpoint was."
            ),
            "example_fingerprint_length": len(
                fingerprint_url("https://example.gov/api?k=v") or ""
            ),
        },
        "conflict_semantics": {
            "same_attempt_same_bytes": "idempotent, the existing row is returned",
            "same_attempt_different_bytes": "REFUSED, and both hashes named",
            "different_attempts_same_bytes": "allowed; the hash index shows the pair",
        },
        "why_a_conflict_is_refused": (
            "two different byte strings claiming to be the same attempt is a "
            "contradiction. Overwriting would destroy the evidence that they "
            "disagreed; skipping would silently keep whichever arrived first."
        ),
        "measured_by_the_verifier": (
            "the write, readback, conflict and idempotency cases all need a "
            "connection - "
            "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
        ),
    }


def _tamper_refusal() -> dict[str, Any]:
    """The refusal, argued from the hash service rather than a live row."""
    good = verify_payload(
        body=FIXTURE_BODY,
        expected_sha256=hash_payload(body=FIXTURE_BODY)["payload_sha256"],
    )
    tampered = verify_payload(
        body=b"tampered-by-hand",
        expected_sha256=hash_payload(body=FIXTURE_BODY)["payload_sha256"],
    )
    # A replay requested with no connection: the refusal is the artifact.
    no_connection = replay_payload(
        connection=None,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        attempt_id="artifact-fixture-attempt",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": TAMPER_FILE,
        "measured": {
            "untouched_bytes_verify": good["hash_verified"],
            "tampered_bytes_do_not": tampered["hash_verified"],
            "the_refusal": tampered["blocked_reasons"],
        },
        "replay_without_a_connection": {
            "replayable": no_connection["replayable"],
            "blocked_reasons": no_connection["blocked_reasons"],
            "invariant_failures": replay_invariant_failures(no_connection),
        },
        "the_order_that_matters": [
            "read the row",
            "re-hash the stored bytes",
            "compare with the recorded hash",
            "match -> return the bytes",
            "mismatch -> return NOTHING, and say why",
        ],
        "why_no_bytes_at_all": (
            "returning bytes and reporting hash_verified:false beside them "
            "would put the caller in the position of noticing, and a caller "
            "that forgets has replayed evidence that changed underneath the "
            "row."
        ),
        "cross_organization": (
            "every query is scoped to organization_id, so another "
            "organization's payload is NOT FOUND rather than found-and-refused. "
            "A refusal that has to compare two values is a refusal somebody "
            "can forget to write."
        ),
    }


def _archive_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": ARCHIVE_FILE,
        "payload_statuses": sorted(PAYLOAD_STATUSES),
        "body_storage_modes": sorted(BODY_STORAGE_MODES),
        "retention_policies": sorted(RETENTION_POLICIES),
        "default_retention_policy": RETENTION_UNKNOWN,
        "why_unknown_is_the_default": (
            "nobody has approved a retention policy for source evidence. "
            "Defaulting to retain_90_days would be inventing one. UNKNOWN "
            "stays UNKNOWN."
        ),
        "archive_is_not_deletion": (
            "archive is a lifecycle state. Nothing in this gate deletes, "
            "because deletion needs an approved policy and none exists."
        ),
        "an_archived_payload_is_still_replayable": True,
        "the_database_enforces": [
            "an archived row carries archived_at",
            "a live row does not",
        ],
        "measured_by_the_verifier": (
            "archiving needs a persisted row - "
            "scripts/verify_nativeforge_source_raw_payload_persistence.sh"
        ),
    }


def _health_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": HEALTH_FILE,
        "lane": "raw_payload_persistence_ready",
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "storage_mode": MODE_DATABASE,
        "max_payload_size_bytes": MAX_PAYLOAD_BYTES,
        "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
        "object_store_configured": detect_object_store_configured(),
        "object_store_is_measured_not_declared": (
            "read from s3_raw_payload_body_store_service.build_client_config, "
            "which reads the settings. A constant False would be correct today "
            "and wrong the day somebody configures one."
        ),
        "the_condition_that_catches_a_filter_refusing_everything": (
            "safe_headers_survive. Gate 160 called the secret scanner with the "
            "wrong keyword, every call raised, the exception was caught, and "
            "EVERY allowlisted header was refused with a plausible reason. "
            "Only asserting that a safe header survives catches it."
        ),
        "any_blocker_closes_the_lane": (
            "ready is all(conditions) and not blockers. Gate 154 shipped a "
            "ready that weighed only the conditions it expected to matter."
        ),
    }


def _monitoring_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": MONITORING_FILE,
        "source_monitoring_live": False,
        "approved_source_count": 0,
        "collectors_registered": 0,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "emails_sent": 0,
        "object_store_calls": 0,
        "object_store_configured": detect_object_store_configured(),
        "production_raw_payload_store_available": False,
        "jobs_completed": 0,
        "rows_with_execution_proof": 0,
        "creates_execution_proof": False,
        "what_gate_160_added": (
            "a durable, size-capped, hash-verified landing zone for response "
            "bytes in controlled_dev_demo, with replay and provenance"
        ),
        "what_it_did_not_add": [
            "a collector",
            "an approved source",
            "accepted source terms",
            "a configured object store",
            "production raw payload storage",
            "an execution proof",
            "a completed job",
            "live monitoring",
        ],
        "a_stored_payload_is_not_a_fetched_payload": True,
        "every_byte_in_the_store_was_supplied_by_a_caller": True,
        "authorization_persisted": False,
        "cookie_persisted": False,
        "set_cookie_persisted": False,
        "api_keys_persisted": False,
        "request_url_persisted": False,
        "customer_data_persisted": False,
    }


def _blockers_markdown() -> str:
    return """# Next: what still stands between a landing zone and a collection

Gate 160 built the raw payload spine. Bytes land, hash, verify, replay and carry
their provenance. None of them came from anywhere - every one was handed in by a
caller.

## What is now true

```text
exact bytes persist                   including non-UTF-8 bodies
the hash is verified twice            on write, and again on readback
a tampered body fails replay          and NO bytes are returned
a retry is separate evidence          attempt 2 never overwrites attempt 1
the same attempt cannot change bytes  refused, with both hashes named
credential headers cannot be stored   allowlist by header name
the URL is never stored               only a sha256 fingerprint
oversize bodies are refused           1 MiB, by the service AND the database
archive keeps a payload readable      nothing deletes
```

## What still blocks a collection

```text
1  a collector envelope      Gate 161. No code can fetch anything.
2  source allowlist boundary Gate 162. Zero sources are approved, and this is
                             where approval gets defined.
3  source terms              a HUMAN must read them. 171 sources.
4  human review              a HUMAN must look at each source.
```

Item 1 is the last purely-engineering blocker before the allowlist boundary.
Items 3 and 4 are not engineering, and a working landing zone does not make them
so - it means that when a human finally clears them, there is somewhere for the
first response to land that has already been proven.

## Two things this gate deliberately did not do

**It did not configure an object store.** Gate 97C's S3 body store is built,
content-addressed and hash-verifying, and it has no bucket. Adding a second
abstraction to claim one exists would have produced two stores, one of them
fake. `object_store_configured` is measured from Gate 97C's own config and stays
`false`.

**It did not define an execution proof.** Gate 158 left `completed` unreachable
because the gate that defines what an execution proof IS has not been written.
A stored payload is not one: these bytes were supplied, and a row proves the
spine works rather than that a source was contacted.

Defining it is the moment "a job finished" becomes a claim this system can make,
and it should cost a gate of its own. Gate 161 is the obvious candidate, since a
collector that actually fetched something would be the first thing with standing
to make that claim - but it should be a deliberate decision in that gate rather
than a corner of it.

## What the spine now makes askable

```text
what exactly did this source return       replay, byte-identical
did it change between attempts            two attempts, two hashes
which attempt produced this               attempt -> job -> source
has anything been altered since           the readback hash says so
how much evidence is stored               total_bytes, distinct_hashes
```

The last two are the ones that matter for an audit. Until this gate, neither
question had an answer, because there was nothing to ask it about.
"""


def build_raw_payload_artifacts() -> dict[str, str]:
    """Every artifact body, keyed by filename. Writes nothing."""
    files = {
        SURVEY_FILE: _json(_survey()),
        IDENTITY_FILE: _json(_identity()),
        HASH_FILE: _json(_hash_smoke()),
        FILTER_FILE: _json(_filter_smoke()),
        WRITE_FILE: _json(_write_readback()),
        TAMPER_FILE: _json(_tamper_refusal()),
        ARCHIVE_FILE: _json(_archive_smoke()),
        HEALTH_FILE: _json(_health_contract()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_raw_payload_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_raw_payload_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def raw_payload_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")

    return fails


#: Kept importable so the verifier can assert the repository refuses a body
#: without going through the envelope.
__all__ = [
    "ARTIFACT_DIR",
    "ARTIFACT_FILES",
    "FIXTURE_BODY",
    "FIXTURE_HEADERS",
    "build_raw_payload_artifacts",
    "persist_payload",
    "raw_payload_artifact_invariant_failures",
    "raw_payload_invariant_failures",
    "write_raw_payload_artifacts",
]
