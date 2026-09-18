"""Gate 163F: re-derive the robots verdict from stored evidence. No refetch.

## What this does and does not touch

```text
PRESERVED EXACTLY   the 403 status, the 42 bytes, the sha256, the fetch time
RE-DERIVED          only the verdict, by running the corrected RFC 9309
                    mapping over that same status and those same bytes
```

Nothing here rewrites history to pretend robots.txt returned 200. The stored
`http_status` stays 403 and the stored `payload_sha256` stays the digest
computed at fetch time — which is what proves the bytes this script persists
are byte-identical to the ones received.

## It also closes a gap

163E required the exact raw bytes be persisted through Gate 160. The preflight
runner hashed them and recorded the digest but never called the payload store,
so `nf_source_collection_raw_payloads` held zero rows for a fetch that really
happened. The bytes were reconstructed and verified against the stored digest
before being written, so this completes a persistence step rather than
inventing evidence.

## Why the correction moves in the permitting direction, safely

The verdict changes from `unreachable` (blocks) to `unavailable` (does not
restrict). That is the direction to be careful in, so:

- the raw evidence is untouched and independently re-verifiable by hash
- `restricts_collection` is recorded alongside the verdict, so the claim is
  explicit rather than inferred from a word
- and RFC 9309 section 2 still applies: robots rules are not a form of access
  authorization. `unavailable` means the robots protocol adds no restriction
  for this authority. It permits nothing on its own.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import sqlalchemy as sa  # noqa: E402
from run_gate163_robots_preflight import (  # noqa: E402
    ROBOTS_TABLE,
    derive_robots_verdict,
)

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_raw_payload_persistence_service import (  # noqa: E402,E501
    persist_raw_payload,
    persistence_invariant_failures,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE_ID = "nf-seed-2026-api-grants-gov-search2"

#: The exact bytes received from https://api.grants.gov/robots.txt on the
#: first live fetch. Verified against the digest recorded at fetch time before
#: anything is written.
STORED_BODY = b'{"message":"Missing Authentication Token"}'
STORED_SHA256 = "f249b63cb2fcb66b47e86f906c98f8fd912e82dd035b4e53d7e72fc1960cfd16"
STORED_STATUS = 403
ROBOTS_URL = "https://api.grants.gov/robots.txt"

session = SessionLocal()
try:
    row = session.execute(
        sa.select(ROBOTS_TABLE).where(
            sa.and_(
                ROBOTS_TABLE.c.organization_id == DEMO_ORG,
                ROBOTS_TABLE.c.host == "api.grants.gov",
            )
        )
    ).first()
    if row is None:
        print("no stored robots evidence - nothing to re-derive")
        raise SystemExit(1)

    stored = row._mapping
    print("=== stored evidence, as received")
    for key in (
        "host",
        "http_status",
        "decision",
        "payload_sha256",
        "evaluated_path",
        "fetched_at",
        "fact_status",
    ):
        print(f"  {key:20} {stored[key]}")

    # The bytes must match the digest recorded at fetch time, or they are not
    # the bytes that were received and nothing else in this script is valid.
    digest = hashlib.sha256(STORED_BODY).hexdigest()
    print()
    print(f"  recomputed sha256    {digest}")
    print(f"  matches stored       {digest == stored['payload_sha256']}")
    if digest != stored["payload_sha256"]:
        print("\nHASH MISMATCH - refusing to write anything")
        raise SystemExit(1)
    if int(stored["http_status"]) != STORED_STATUS:
        print(f"\nSTATUS MISMATCH - stored {stored['http_status']}")
        raise SystemExit(1)

    # ---- persist the bytes through Gate 160 --------------------------
    #
    # The gap 163E required closed. The warrant is required by migration
    # 0050's CHECK, so this row cannot be written without naming the source.
    attempt_id = str(stored["attempt_id"] or f"gate163-robots-{uuid.uuid4().hex[:12]}")
    persisted = persist_raw_payload(
        connection=session,
        organization_id=DEMO_ORG,
        job_id=attempt_id,
        source_id=SOURCE_ID,
        attempt_number=1,
        collector_version="gate163_robots_preflight",
        body=STORED_BODY,
        response_headers={"content-type": "application/json"},
        response_status=STORED_STATUS,
        source_url=ROBOTS_URL,
        received_at=stored["fetched_at"],
        fact_status="tenant_supplied",
        live_fetch_performed=True,
        authorized_source_id=SOURCE_ID,
    )
    failures = persistence_invariant_failures(persisted)
    print()
    print("=== Gate 160 persistence (closing the 163E gap)")
    print(f"  persisted            {persisted['persisted']}")
    print(f"  deduplicated         {persisted.get('deduplicated')}")
    print(f"  payload_sha256       {persisted.get('payload_sha256')}")
    print(f"  hash matches fetch   {persisted.get('payload_sha256') == digest}")
    print(f"  blocked              {persisted.get('blocked_reasons')}")
    print(f"  INVARIANTS           {failures if failures else 'clean'}")
    if not (persisted["persisted"] or persisted.get("deduplicated")):
        print("\nPAYLOAD NOT PERSISTED - stopping")
        raise SystemExit(1)

    # ---- re-derive the verdict ---------------------------------------
    verdict = derive_robots_verdict(
        status=STORED_STATUS,
        body=STORED_BODY,
        path=str(stored["evaluated_path"]),
    )
    print()
    print("=== re-derived verdict, from the SAME status and bytes")
    print(f"  previous decision    {stored['decision']}")
    print(f"  corrected decision   {verdict['decision']}")
    print(f"  rfc_class            {verdict['rfc_class']}")
    print(f"  restricts_collection {verdict['restricts_collection']}")

    now = dt.datetime.now(dt.UTC)
    session.execute(
        sa.update(ROBOTS_TABLE)
        .where(
            sa.and_(
                ROBOTS_TABLE.c.organization_id == DEMO_ORG,
                ROBOTS_TABLE.c.host == "api.grants.gov",
                ROBOTS_TABLE.c.evaluated_path == stored["evaluated_path"],
            )
        )
        .values(
            decision=verdict["decision"],
            # http_status, payload_sha256, fetched_at and attempt_id are NOT
            # touched. Only the derived verdict changes.
            evidence_ref=(
                f"{ROBOTS_URL}#rfc9309-{verdict['rfc_class']}-rederived"
            ),
            updated_at=now,
        )
    )
    session.commit()

    after = session.execute(
        sa.select(ROBOTS_TABLE).where(
            sa.and_(
                ROBOTS_TABLE.c.organization_id == DEMO_ORG,
                ROBOTS_TABLE.c.host == "api.grants.gov",
            )
        )
    ).first()._mapping

    print()
    print("=== evidence after correction")
    for key in ("http_status", "decision", "payload_sha256", "evidence_ref"):
        print(f"  {key:20} {after[key]}")
    print()
    print(
        json.dumps(
            {
                "raw_evidence_preserved": bool(
                    after["http_status"] == STORED_STATUS
                    and after["payload_sha256"] == STORED_SHA256
                ),
                "verdict_corrected": bool(after["decision"] == "unavailable"),
                "robots_restriction_blocks_collection": verdict[
                    "restricts_collection"
                ],
                "robots_authorizes_nothing": (
                    "RFC 9309 section 2: robots rules are not a form of access "
                    "authorization"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
finally:
    session.close()
