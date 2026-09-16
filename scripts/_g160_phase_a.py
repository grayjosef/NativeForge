"""Gate 160M phase A: bytes land, and the store refuses what it must.

Commits, so phase B reads rows this process wrote and then exited.

A REAL Gate 158 job row is created first, so phase B's provenance check can
actually resolve `attempt -> job`. A linkage test against an id nobody created
would pass for the wrong reason - it would prove the column was populated, not
that it pointed at anything.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    enqueue_job,
)
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    MAX_PAYLOAD_BYTES,
    count_payloads,
    get_payload,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_collection_attempt_identity_service import (  # noqa: E402
    attempt_identity_invariant_failures,
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_hash_service import (  # noqa: E402
    hash_payload,
)
from nativeforge.services.source_raw_payload_persistence_service import (  # noqa: E402
    persist_raw_payload,
    persistence_invariant_failures,
)

TAG = os.environ["NF_G160_TAG"]
ORG = os.environ["NF_G160_ORG"]
T0 = "2026-09-16T12:00:00Z"

JOB_ID = f"{TAG}-job"
SOURCE_ID = f"{TAG}-src"

#: Deliberately NOT valid UTF-8, and containing a null byte. A store that
#: round-trips only text would pass every test written with a JSON fixture.
BODY = (
    b'{"opportunities":[{"id":"ABC-123","note":"'
    b"\xff\xfe binary \x00 tail \x80\x81"
    b'"}]}'
)

SAFE_AND_UNSAFE_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "ETag": 'W/"v1"',
    "Cache-Control": "no-store",
    "Authorization": "Bearer must-be-refused",
    "Cookie": "must=be-refused",
    "Set-Cookie": "must=be-refused",
    "X-API-Key": "must-be-refused",
    "X-Acme-Session": "unclassified-must-be-refused",
}

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def identity(attempt: int = 1) -> dict:
    return build_attempt_identity(
        job_id=JOB_ID, source_id=SOURCE_ID, attempt_number=attempt
    )


def write(ident: dict, body: bytes, **kwargs) -> dict:
    with engine.begin() as connection:
        return persist_raw_payload(
            connection=connection,
            organization_id=ORG,
            job_id=ident["job_id"],
            source_id=ident["source_id"],
            attempt_number=ident["attempt_number"],
            body=body,
            response_headers=SAFE_AND_UNSAFE_HEADERS,
            response_status=200,
            source_url="https://example.gov/api/grants?api_key=SUPERSECRET123",
            received_at=T0,
            **kwargs,
        )


# ---- a REAL job, so provenance can resolve later -------------------------
with engine.begin() as connection:
    job = enqueue_job(
        connection=connection,
        organization_id=ORG,
        job_id=JOB_ID,
        idempotency_key=JOB_ID,
        source_id=SOURCE_ID,
        now=T0,
        created_by_runtime="verifier_fixture",
    )
out["job_created"] = job["created"]

# ---- identity -------------------------------------------------------------
first = identity(1)
same = identity(1)
retry = identity(2)
out["same_attempt_same_id"] = first["attempt_id"] == same["attempt_id"]
out["retry_is_a_different_attempt"] = first["attempt_id"] != retry["attempt_id"]
out["attempt_id_is_not_the_job_id"] = first["attempt_id"] != JOB_ID
out["identity_invariants"] = attempt_identity_invariant_failures(first)
out["attempt_id"] = first["attempt_id"]
out["retry_attempt_id"] = retry["attempt_id"]

# ---- hashing --------------------------------------------------------------
a = hash_payload(body=BODY)
b = hash_payload(body=BODY)
changed = hash_payload(body=BODY[:-1] + b"X")
out["same_bytes_same_hash"] = a["payload_sha256"] == b["payload_sha256"]
out["one_byte_changes_the_hash"] = a["payload_sha256"] != changed["payload_sha256"]
out["fixture_sha256"] = a["payload_sha256"]
out["fixture_size"] = a["payload_size_bytes"]
out["fixture_is_not_utf8"] = not a["encoding"]["is_text"]

# ---- 1 to 4: persist, and verify both sides ------------------------------
written = write(first, BODY)
out["persisted"] = written["persisted"]
out["write_hash_verified"] = written["write_hash_verified"]
out["readback_hash_verified"] = written["readback_hash_verified"]
out["write_invariants"] = persistence_invariant_failures(written)
out["safe_headers_kept"] = sorted(written.get("metadata", {}).get("safe_headers", {}))
out["headers_refused"] = written.get("refused_header_names")

# ---- 13 to 17: the header allowlist, both directions ---------------------
refused = set(written.get("refused_header_names") or [])
kept = set(written.get("metadata", {}).get("safe_headers", {}))
out["authorization_refused"] = "authorization" in refused
out["cookie_refused"] = "cookie" in refused
out["set_cookie_refused"] = "set-cookie" in refused
out["api_key_refused"] = "x-api-key" in refused
out["unclassified_refused"] = "x-acme-session" in refused
# The condition that catches a filter refusing everything.
out["safe_headers_survived"] = sorted(kept)
out["a_safe_header_survived"] = "content-type" in kept

# ---- the URL was fingerprinted, never stored -----------------------------
with engine.connect() as connection:
    row = (
        connection.execute(
            sa.text(
                "SELECT source_url_fingerprint, response_header_metadata, "
                "body_storage_mode, retention_policy "
                "FROM nf_source_collection_raw_payloads WHERE attempt_id = :a"
            ),
            {"a": first["attempt_id"]},
        )
        .mappings()
        .first()
    )
fingerprint = str((row or {}).get("source_url_fingerprint") or "")
out["url_fingerprint_length"] = len(fingerprint)
out["the_secret_appears_in_the_row"] = "SUPERSECRET123" in str(dict(row or {}))
out["stored_header_names"] = sorted(
    json.loads((row or {}).get("response_header_metadata") or "{}")
)
out["body_storage_mode"] = (row or {}).get("body_storage_mode")
out["retention_policy"] = (row or {}).get("retention_policy")

# ---- 7: the same attempt with identical bytes is idempotent --------------
again = write(first, BODY)
out["idempotent_persisted"] = again["persisted"]
out["idempotent_deduplicated"] = again["deduplicated"]
out["idempotent_blocked"] = again["blocked_reasons"]

# ---- 8: the same attempt with DIFFERENT bytes is refused -----------------
conflict = write(first, BODY + b"different")
out["conflict_persisted"] = conflict["persisted"]
out["conflict_blocked"] = conflict["blocked_reasons"]
out["conflict_refused_for_the_right_reason"] = any(
    "already_stored_different_bytes" in reason
    for reason in (conflict["blocked_reasons"] or [])
)

# ---- a retry stores its own, separate evidence ---------------------------
retry_written = write(retry, BODY + b" attempt-2")
out["retry_persisted"] = retry_written["persisted"]
out["retry_sha256"] = retry_written["payload_sha256"]
out["retry_differs_from_first"] = (
    retry_written["payload_sha256"] != written["payload_sha256"]
)

# ---- 18: an oversize body is refused deterministically -------------------
oversize = write(identity(3), b"x" * (MAX_PAYLOAD_BYTES + 1))
out["oversize_persisted"] = oversize["persisted"]
out["oversize_blocked"] = oversize["blocked_reasons"]
out["max_payload_bytes"] = MAX_PAYLOAD_BYTES

# ---- a body exactly AT the limit is accepted -----------------------------
#
# The permitting branch. A limit that refused everything would pass the
# refusal test and be useless.
at_limit = write(identity(4), b"y" * MAX_PAYLOAD_BYTES)
out["at_limit_persisted"] = at_limit["persisted"]
out["at_limit_size"] = at_limit["payload_size_bytes"]

# ---- counts ---------------------------------------------------------------
with engine.connect() as connection:
    counts = count_payloads(connection=connection, organization_id=ORG)
    read_back = get_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=first["attempt_id"],
        include_body=True,
    )
out["payloads_total"] = counts["total"]
out["rows_claiming_a_collector"] = counts["rows_claiming_a_collector"]
out["rows_claiming_a_live_fetch"] = counts["rows_claiming_a_live_fetch"]
out["rows_over_the_size_limit"] = counts["rows_over_the_size_limit"]
out["count_invariants"] = raw_payload_invariant_failures(counts)
# 2: the exact bytes, in this same process.
out["bytes_identical_same_process"] = read_back.get("body_bytes") == BODY

print(json.dumps(out))
