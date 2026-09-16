"""Gate 160M phase B: a SEPARATE process reads, replays, tampers and archives.

Nothing phase A held is in memory here. The bytes this process reads were
committed by a process that has since exited, which is what makes "the exact
response is replayable" a measurement rather than a session remembering itself.
"""

from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    archive_payload,
    count_payloads,
    get_payload,
    list_payloads,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_collection_attempt_identity_service import (  # noqa: E402
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
    replay_invariant_failures,
    replay_payload,
)

TAG = os.environ["NF_G160_TAG"]
ORG = os.environ["NF_G160_ORG"]
OTHER_ORG = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
T1 = "2026-09-16T13:00:00Z"

JOB_ID = f"{TAG}-job"
SOURCE_ID = f"{TAG}-src"

BODY = (
    b'{"opportunities":[{"id":"ABC-123","note":"'
    b"\xff\xfe binary \x00 tail \x80\x81"
    b'"}]}'
)

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}

first = build_attempt_identity(job_id=JOB_ID, source_id=SOURCE_ID, attempt_number=1)
retry = build_attempt_identity(job_id=JOB_ID, source_id=SOURCE_ID, attempt_number=2)

# ---- 2: the exact bytes, from a process that did not write them ----------
with engine.connect() as connection:
    read = get_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=first["attempt_id"],
        include_body=True,
    )
out["found_after_restart"] = read["payload"] is not None
out["bytes_identical_after_restart"] = read.get("body_bytes") == BODY
out["readback_hash_verified"] = read["hash_verified"]
out["readback_sha256"] = read.get("readback_sha256")
out["read_invariants"] = raw_payload_invariant_failures(read)

# ---- replay, with base64 round-trip and provenance ----------------------
with engine.connect() as connection:
    played = replay_payload(
        connection=connection, organization_id=ORG, attempt_id=first["attempt_id"]
    )
out["replayable"] = played["replayable"]
out["replay_hash_verified"] = played["hash_verified"]
out["base64_round_trips"] = (
    base64.b64decode(played["body_base64"] or "") == BODY
    if played["body_base64"]
    else False
)
# 9 and 10: provenance resolves by LOOKING, not by reading the column back.
out["linked_job_found"] = played["linked_job_found"]
out["linked_source_found"] = played["linked_source_found"]
out["provenance"] = played["provenance"]
out["replay_invariants"] = replay_invariant_failures(played)
out["safe_response_headers"] = sorted(played.get("safe_response_headers") or {})
out["retention_policy"] = played.get("retention_policy")
out["retention_is_unknown"] = played.get("retention_is_unknown")

# ---- cross-organization access finds nothing ----------------------------
with engine.connect() as connection:
    cross = replay_payload(
        connection=connection,
        organization_id=OTHER_ORG,
        attempt_id=first["attempt_id"],
    )
out["cross_org_replayable"] = cross["replayable"]
out["cross_org_blocked"] = cross["blocked_reasons"]

# ---- 11: an ARCHIVED payload stays readable -----------------------------
with engine.begin() as connection:
    archived = archive_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=retry["attempt_id"],
        now=T1,
    )
out["archived"] = archived["archived"]
out["archived_at"] = (archived.get("payload") or {}).get("archived_at")
with engine.connect() as connection:
    archived_replay = replay_payload(
        connection=connection, organization_id=ORG, attempt_id=retry["attempt_id"]
    )
out["archived_still_replayable"] = archived_replay["replayable"]
out["archived_readable"] = archived_replay["readable"]
out["archived_hash_verified"] = archived_replay["hash_verified"]
out["archived_replay_invariants"] = replay_invariant_failures(archived_replay)

# ---- 12: a TAMPERED body fails replay, and returns NO bytes -------------
#
# Bypasses the repository entirely. The only way to ask whether the readback
# check is real is to change the bytes underneath it.
with engine.begin() as connection:
    connection.execute(
        sa.text(
            "UPDATE nf_source_collection_raw_payloads SET body_bytes = :body "
            "WHERE attempt_id = :attempt"
        ),
        {"body": b"tampered-by-hand", "attempt": first["attempt_id"]},
    )
with engine.connect() as connection:
    tampered = replay_payload(
        connection=connection, organization_id=ORG, attempt_id=first["attempt_id"]
    )
out["tampered_replayable"] = tampered["replayable"]
out["tampered_hash_verified"] = tampered["hash_verified"]
# The one that matters: no bytes at all, not bytes with a warning beside them.
out["tampered_returned_a_body"] = tampered["body_base64"] is not None
out["tampered_blocked"] = tampered["blocked_reasons"]
out["tampered_invariants"] = replay_invariant_failures(tampered)

# ---- listing and counts -------------------------------------------------
with engine.connect() as connection:
    by_job = list_payloads(
        connection=connection, organization_id=ORG, job_id=JOB_ID
    )
    counts = count_payloads(connection=connection, organization_id=ORG)
out["payloads_for_this_job"] = by_job["payload_count"]
out["by_status"] = counts["by_status"]
out["by_storage_mode"] = counts["by_storage_mode"]
out["distinct_hashes"] = counts["distinct_hashes"]
out["total_bytes"] = counts["total_bytes"]
out["rows_claiming_a_collector"] = counts["rows_claiming_a_collector"]
out["rows_claiming_a_live_fetch"] = counts["rows_claiming_a_live_fetch"]

# ---- 19: the database refuses a row claiming a collector ----------------
try:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE nf_source_collection_raw_payloads SET collector_invoked = 1"
            )
        )
    out["database_refused_a_collector_claim"] = False
except Exception as exc:  # noqa: BLE001 - the refusal is the measurement
    out["database_refused_a_collector_claim"] = True
    out["database_refusal"] = type(exc).__name__

# ---- and one claiming a live fetch --------------------------------------
try:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE nf_source_collection_raw_payloads "
                "SET live_fetch_performed = 1"
            )
        )
    out["database_refused_a_live_fetch_claim"] = False
except Exception:  # noqa: BLE001
    out["database_refused_a_live_fetch_claim"] = True

# ---- and one over the size limit ----------------------------------------
try:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE nf_source_collection_raw_payloads "
                "SET payload_size_bytes = 99999999"
            )
        )
    out["database_refused_an_oversize_row"] = False
except Exception:  # noqa: BLE001
    out["database_refused_an_oversize_row"] = True

print(json.dumps(out))
