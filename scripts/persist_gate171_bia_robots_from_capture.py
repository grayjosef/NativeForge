"""Persist the BIA robots evidence that WAS fetched, without re-fetching it.

The replacement request succeeded - HTTP 200, 2027 bytes - and the row insert
then failed on a CHECK constraint, because this table's fact_status vocabulary
is migration 0049's ('live_fetch', 'synthetic_fixture', 'demo_fixture',
'unknown') and not the identically-named tuple used by the tenant-profile
tables.

The response is gone from the process, but the facts it produced were printed
before the failure and are transcribed here VERBATIM from that run's log. No
value is recomputed, inferred or rounded, and nothing is fetched again.

## What is recorded, and what is not

```text
recorded      status, byte count, sha256, fetched_at, verdict, evaluated path
NOT recorded  the 2027 response bytes themselves
```

The body was held in memory and lost with the process. The robots evidence
contract does not require it - migration 0049 requires a fetch time and a
payload hash for an `allowed` verdict, and both are here - but Gate 163 kept
its robots body as a raw payload row and this one has none. That is a real
gap, and it is named in the Gate 171 report rather than left for a reader to
notice that BIA has a hash with nothing behind it.

Run once. Refuses if a row for this attempt already exists.
"""

from __future__ import annotations

import datetime as dt
import socket
import sys
import uuid

sys.path.insert(0, "src")

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("this script transcribes a capture; it fetches nothing")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

# ---- transcribed verbatim from the run log -------------------------
CAPTURE = {
    "host": "www.bia.gov",
    "source_id": "nf-seed-2026-fed-007",
    "url": "https://www.bia.gov/robots.txt",
    "http_status": 200,
    "transport_outcome": "response_received",
    "byte_count": 2027,
    "payload_sha256": (
        "773fb8d35bb9a39d35335ee6db8dc5c912d2aacbfb823152d9c61cd647dd902d"
    ),
    "fetched_at": "2026-09-22T00:32:13.328620+00:00",
    "evaluated_path": "/service/grants/ttgp/apply-ttgp-grant",
    "decision": "allowed",
    "rfc_class": "successful",
    "restricts_collection": False,
    "attempt_id": "gate171-robots-nf-seed-2026-fed-007-20260922T003213Z",
}

ROBOTS_TABLE = sa.Table(
    "nf_source_robots_evidence",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("is_demo", sa.Boolean()),
    sa.Column("host", sa.Text()),
    sa.Column("fetched_for_source_id", sa.Text()),
    sa.Column("fetched_at", sa.DateTime(timezone=True)),
    sa.Column("http_status", sa.Integer()),
    sa.Column("decision", sa.String(length=16)),
    sa.Column("evaluated_path", sa.Text()),
    sa.Column("user_agent_scope", sa.String(length=128)),
    sa.Column("payload_sha256", sa.String(length=64)),
    sa.Column("attempt_id", sa.Text()),
    sa.Column("evidence_ref", sa.String(length=512)),
    sa.Column("recheck_due_at", sa.DateTime(timezone=True)),
    sa.Column("fact_status", sa.String(length=32)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)


def main() -> int:
    fetched_at = dt.datetime.fromisoformat(str(CAPTURE["fetched_at"]))
    session = SessionLocal()
    try:
        existing = session.execute(
            sa.select(ROBOTS_TABLE.c.id).where(
                ROBOTS_TABLE.c.attempt_id == CAPTURE["attempt_id"]
            )
        ).first()
        if existing is not None:
            print("REFUSED: this attempt is already on file. Nothing written.")
            return 1

        session.execute(
            sa.insert(ROBOTS_TABLE).values(
                id=uuid.uuid4(),
                organization_id=DEMO_ORG,
                is_demo=True,
                host=CAPTURE["host"],
                fetched_for_source_id=CAPTURE["source_id"],
                fetched_at=fetched_at,
                http_status=CAPTURE["http_status"],
                decision=CAPTURE["decision"],
                evaluated_path=CAPTURE["evaluated_path"],
                user_agent_scope="*",
                payload_sha256=CAPTURE["payload_sha256"],
                attempt_id=CAPTURE["attempt_id"],
                evidence_ref=(
                    f"{CAPTURE['url']}#gate171-{CAPTURE['decision']}"
                    "-body-not-retained"
                ),
                recheck_due_at=None,
                fact_status="live_fetch",
                created_at=fetched_at,
                updated_at=fetched_at,
            )
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"WRITE FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        session.close()

    print("PERSISTED BIA robots evidence from the captured run")
    for key in (
        "host",
        "http_status",
        "byte_count",
        "payload_sha256",
        "decision",
        "restricts_collection",
        "fetched_at",
    ):
        print(f"  {key:<22} {CAPTURE[key]}")
    print("  response body            NOT RETAINED - lost with the process")
    print(f"  network attempts here    {_NETWORK['attempts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
