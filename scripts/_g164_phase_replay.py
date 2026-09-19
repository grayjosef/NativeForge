"""Gate 164A/164C: replay the first live collection from persisted evidence.

Nothing is fetched. The question is whether the collection that happened can be
reconstructed from what was written down - bytes, hash, linkage, attribution
and the one normalized opportunity - by a process that has no memory of it and
no network.

## The restart proof is the point

164C asks for a FRESH connection, and the reason is specific: an ORM session
can hand back an object it is still holding, so a replay on the original
session can pass while the durable evidence is incomplete. So the original
session is closed before anything is read, and the replay uses a connection
opened afterwards.

The engine is disposed as well as the session closed. A pooled connection
survives `session.close()`, and reusing one would be the same shortcut wearing
a different name.

## HTTP status stays UNKNOWN

The transport status was never captured (doc 849, section 12). A replay that
produced one would be inventing it. `http_status_is_still_unknown` is asserted
as a POSITIVE property here: the gap is known, recorded, and must survive the
round trip rather than being quietly filled in.

## No network, proven rather than promised

`socket.socket` is replaced for the duration with one that raises. Asserting
"no network" by reading the code is a claim; making a socket impossible and
then doing the work is a measurement.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
COLLECTION_JOB = "gate163-first-live-collection"
EXPECTED_SHA = "eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712"
EXPECTED_BYTES = 11131
EXPECTED_OPPORTUNITY = "O-BJA-2026-172662"

out: dict[str, object] = {}
detail: list[str] = []


class NetworkAttempted(RuntimeError):
    """Raised if anything tries to open a socket during the replay."""


_REAL_SOCKET = socket.socket
network_attempts = {"count": 0}


def _refuse_socket(*args, **kwargs):  # noqa: ANN002, ANN003
    network_attempts["count"] += 1
    raise NetworkAttempted("the replay attempted to open a socket")


# ---- phase 1: read the identifiers, then let the session go -------------
from nativeforge.db.session import SessionLocal, engine  # noqa: E402

opening = SessionLocal()
row = (
    opening.execute(
        sa.text(
            "SELECT attempt_id FROM nf_source_collection_raw_payloads "
            "WHERE job_id = :job AND live_fetch_performed = 1"
        ),
        {"job": COLLECTION_JOB},
    )
    .mappings()
    .first()
)
attempt_id = None if row is None else str(row["attempt_id"])
out["the_collection_exists"] = attempt_id is not None
opening.close()

# Dispose the pool too. A pooled connection outlives `close()`, and reusing
# one would be the process-memory shortcut this phase exists to exclude.
engine.dispose()
out["original_session_closed_and_pool_disposed"] = True

if attempt_id is None:
    detail.append("no live collection payload found")
    out["detail"] = "; ".join(detail)
    print(json.dumps(out, sort_keys=True))
    raise SystemExit(0)

# ---- phase 2: a fresh connection, with no network possible --------------
socket.socket = _refuse_socket  # type: ignore[assignment]
try:
    from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E402,E501
        get_attempt,
    )
    from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
        replay_invariant_failures,
        replay_payload,
    )

    fresh = SessionLocal()
    try:
        replay = replay_payload(
            connection=fresh, organization_id=DEMO, attempt_id=attempt_id
        )
        detail.extend(replay_invariant_failures(replay))

        out["replay_hash_verified"] = bool(replay.get("hash_verified"))
        out["replayable"] = bool(replay.get("replayable"))

        body = base64.b64decode(replay.get("body_base64") or b"")
        out["exact_bytes_recovered"] = len(body) == EXPECTED_BYTES
        out["recovered_byte_count"] = len(body)

        recomputed = hashlib.sha256(body).hexdigest()
        out["sha256_recomputes"] = recomputed == EXPECTED_SHA
        out["recomputed_sha256"] = recomputed

        # ---- linkage that must survive the round trip ------------------
        payload = (
            fresh.execute(
                sa.text(
                    "SELECT source_id, authorized_source_id, "
                    "source_url_fingerprint, response_status, job_id "
                    "FROM nf_source_collection_raw_payloads "
                    "WHERE attempt_id = :a"
                ),
                {"a": attempt_id},
            )
            .mappings()
            .first()
        )
        out["source_id_survives"] = str(payload["source_id"]) == SOURCE
        out["authorized_source_id_survives"] = (
            str(payload["authorized_source_id"]) == SOURCE
        )
        out["request_fingerprint_survives"] = bool(
            str(payload["source_url_fingerprint"] or "").strip()
        )

        attempt = get_attempt(
            connection=fresh, organization_id=DEMO, attempt_id=attempt_id
        )
        record = attempt.get("attempt") or {}
        out["execution_attempt_linkage_survives"] = bool(
            record
            and str(record.get("source_id")) == SOURCE
            and str(record.get("authorized_source_id")) == SOURCE
            and record.get("raw_payload_sha256") == EXPECTED_SHA
            and record.get("execution_proof_available")
        )
        out["execution_proof_present"] = bool(record.get("execution_proof_available"))

        # The known gap, asserted as a property rather than tolerated.
        out["http_status_is_still_unknown"] = (
            payload["response_status"] is None and record.get("http_status") is None
        )

        # ---- attribution -----------------------------------------------
        from nativeforge.services.source_authorization_fact_resolver_service import (
            resolve_source_authorization_facts,
        )

        facts = (
            resolve_source_authorization_facts(
                connection=fresh, organization_id=DEMO, source_id=SOURCE
            ).get("resolved_facts")
            or {}
        )
        attribution = facts.get("attribution_status") or {}
        out["attribution_survives"] = (
            attribution.get("value") == "present_and_verbatim"
            and attribution.get("fact_status") == "recorded"
        )

        # ---- the normalized opportunity, reproduced from the bytes -----
        parsed = json.loads(body.decode("utf-8"))
        hits = list((parsed.get("data") or {}).get("oppHits") or [])
        first = hits[0] if hits else {}
        out["normalization_reproduced"] = (
            str(first.get("number") or "") == EXPECTED_OPPORTUNITY
        )
        out["reproduced_opportunity"] = str(first.get("number") or "")
        out["application_errorcode"] = parsed.get("errorcode")
        out["application_message"] = parsed.get("msg")
    finally:
        fresh.close()
except NetworkAttempted as exc:  # pragma: no cover - the refusal is the measure
    detail.append(str(exc))
finally:
    socket.socket = _REAL_SOCKET  # type: ignore[assignment]

out["network_calls_during_replay"] = network_attempts["count"]
out["replay_without_network"] = network_attempts["count"] == 0
out["fresh_connection_replay"] = True

for key in (
    "the_collection_exists",
    "original_session_closed_and_pool_disposed",
    "replay_hash_verified",
    "replayable",
    "exact_bytes_recovered",
    "sha256_recomputes",
    "source_id_survives",
    "authorized_source_id_survives",
    "request_fingerprint_survives",
    "execution_attempt_linkage_survives",
    "execution_proof_present",
    "http_status_is_still_unknown",
    "attribution_survives",
    "normalization_reproduced",
    "replay_without_network",
    "fresh_connection_replay",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
