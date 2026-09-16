"""Gate 160M: the lane, with the evidence a request cannot produce.

The health route supplies no evidence for `tamper_detected` or
`archived_still_readable`, because a request cannot tamper with a row it has
just rolled back and archiving one would leave a fixture behind. It reports
those red and names this script.

This is the script. It has committed rows, a clock it can move and permission to
corrupt its own fixtures, so it can hand the health service the two the route
could not - and the lane goes green HERE while staying red THERE, which is the
honest arrangement.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    MAX_PAYLOAD_BYTES,
    archive_payload,
    count_payloads,
    get_payload,
)
from nativeforge.services.source_collection_attempt_identity_service import (  # noqa: E402
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_health_service import (  # noqa: E402
    build_raw_payload_health,
    raw_payload_health_invariant_failures,
)
from nativeforge.services.source_raw_payload_persistence_service import (  # noqa: E402
    persist_raw_payload,
)
from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
    replay_payload,
)

TAG = os.environ["NF_G160_TAG"] + "-h"
ORG = os.environ["NF_G160_ORG"]
T0 = "2026-09-16T14:00:00Z"

JOB_ID = f"{TAG}-job"
SOURCE_ID = f"{TAG}-src"

BODY = b'{"synthetic":true,"lane":"gate160"}'

HEADERS = {
    "Content-Type": "application/json",
    "ETag": 'W/"lane"',
    "Authorization": "Bearer must-be-refused",
    "Cookie": "must=be-refused",
    "Set-Cookie": "must=be-refused",
    "X-API-Key": "must-be-refused",
    "X-Acme-Session": "unclassified",
}

engine = sa.create_engine(get_settings().database_url)


def identity(attempt: int) -> dict:
    return build_attempt_identity(
        job_id=JOB_ID, source_id=SOURCE_ID, attempt_number=attempt
    )


def write(ident: dict, body: bytes) -> dict:
    with engine.begin() as connection:
        return persist_raw_payload(
            connection=connection,
            organization_id=ORG,
            job_id=ident["job_id"],
            source_id=ident["source_id"],
            attempt_number=ident["attempt_number"],
            body=body,
            response_headers=HEADERS,
            response_status=200,
            received_at=T0,
        )


# ---- the write, and its readback ----------------------------------------
written = write(identity(1), BODY)

with engine.connect() as connection:
    read = get_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=written["attempt_id"],
        include_body=True,
    )
round_tripped = read.get("body_bytes") == BODY

with engine.connect() as connection:
    replayed = replay_payload(
        connection=connection, organization_id=ORG, attempt_id=written["attempt_id"]
    )

# ---- the conflict refusal -----------------------------------------------
conflict = write(identity(1), BODY + b"different")

# ---- the oversize refusal -----------------------------------------------
oversize = write(identity(2), b"x" * (MAX_PAYLOAD_BYTES + 1))

# ---- archive, and prove it stays readable -------------------------------
archived_written = write(identity(3), BODY + b" third")
with engine.begin() as connection:
    archive_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=archived_written["attempt_id"],
        now=T0,
    )
with engine.connect() as connection:
    archived_replay = replay_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=archived_written["attempt_id"],
    )
archived_evidence = {
    **archived_replay,
    "archived": archived_replay.get("archived"),
}

# ---- tamper, on a payload this phase created ----------------------------
tamper_target = write(identity(4), BODY + b" fourth")
with engine.begin() as connection:
    connection.execute(
        sa.text(
            "UPDATE nf_source_collection_raw_payloads SET body_bytes = :body "
            "WHERE attempt_id = :attempt"
        ),
        {"body": b"tampered", "attempt": tamper_target["attempt_id"]},
    )
with engine.connect() as connection:
    tampered = replay_payload(
        connection=connection,
        organization_id=ORG,
        attempt_id=tamper_target["attempt_id"],
    )

with engine.connect() as connection:
    counts = count_payloads(connection=connection, organization_id=ORG)

health = build_raw_payload_health(
    table_exists=True,
    write_result=written,
    replay_result=replayed,
    tamper_result=tampered,
    conflict_result=conflict,
    metadata_result=written.get("metadata"),
    oversize_result=oversize,
    archived_replay_result=archived_evidence,
    counts=counts,
    bytes_round_tripped=round_tripped,
)

print(
    json.dumps(
        {
            "ready": health["raw_payload_persistence_ready"],
            "conditions": health["conditions"],
            "not_met": health["conditions_not_met"],
            "blockers": health["blockers"],
            "invariants": raw_payload_health_invariant_failures(health),
            "storage_mode": health["storage_mode"],
            "max_payload_size_bytes": health["max_payload_size_bytes"],
            "payloads_total": health["payloads_total"],
            "payloads_archived": health["payloads_archived"],
            "tamper_failures": health["tamper_failures"],
            "secret_header_refusals": health["secret_header_refusals"],
            "unrecognised_header_refusals": health["unrecognised_header_refusals"],
            "safe_headers_kept": health["safe_headers_kept"],
            "object_store_configured": health["object_store_configured"],
            "production_raw_payload_store_available": health[
                "production_raw_payload_store_available"
            ],
            "collectors_invoked": health["collectors_invoked"],
            "live_source_calls": health["live_source_calls"],
            "approved_source_count": health["approved_source_count"],
            "jobs_completed": health["jobs_completed"],
            "creates_execution_proof": health["creates_execution_proof"],
            "monitoring_live": health["source_monitoring_live"],
        }
    )
)
