"""Gate 163M: the execution attempt for the collection that already happened.

The first live collection persisted its bytes and recorded no attempt, because
the attempt repository refused every live attempt regardless of authorization -
an eighth copy of "nothing live has ever happened" that migration 0050 had
already relaxed on the database side. That refusal is now
authorization-aware, so the attempt can be recorded.

## Reconstructed, and verified against what was persisted

Same pattern the robots evidence used: every field comes from the persisted
payload row, and the hash is re-verified against it rather than trusted.

```text
raw_payload_sha256    from the row, and the body is re-hashed to confirm
bytes_received        from the row
source / job / auth   from the row
request_method        POST, from the gate's one request
```

## What is NOT reconstructed

`http_status` stays NULL. The dispatch returned it under `status_code` and the
runner read `response_status`, so it was never persisted - and recovering it
would need a second request, which this gate forbids. The response headers WERE
persisted and corroborate the byte count independently
(`content-length: 11131`), but a header is not a status line.

So it stays unknown. UNKNOWN stays UNKNOWN: writing 200 because the body says
`"errorcode": 0` would be inferring a transport fact from an application one,
and the whole campaign is about not doing that.

Dry-run by default. `--apply` writes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E402
    record_attempt,
)
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    get_payload,
)
from nativeforge.services.source_collection_transport_service import LIVE  # noqa: E402

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
JOB_ID = "gate163-first-live-collection"
API_URL = "https://api.grants.gov/v1/api/search2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        row = (
            session.execute(
                sa.text(
                    "SELECT attempt_id, source_id, job_id, payload_sha256, "
                    "payload_size_bytes, authorized_source_id, source_url_fingerprint, "
                    "received_at, response_status "
                    "FROM nf_source_collection_raw_payloads "
                    "WHERE job_id = :job AND live_fetch_performed = 1"
                ),
                {"job": JOB_ID},
            )
            .mappings()
            .first()
        )

        if row is None:
            print("REFUSED: no persisted live payload for this job")
            return 1

        # Re-verify rather than trust. The hash on the row is only evidence if
        # the bytes still hash to it.
        stored = get_payload(
            connection=session,
            organization_id=DEMO,
            attempt_id=row["attempt_id"],
            include_body=True,
        )
        body = stored.get("body_bytes") or b""
        recomputed = hashlib.sha256(body).hexdigest()
        verified = recomputed == row["payload_sha256"]

        print("=== Gate 163M execution proof for the first live collection")
        print(f"    attempt_id           {row['attempt_id']}")
        print(f"    source_id            {row['source_id']}")
        print(f"    job_id               {row['job_id']}")
        print(f"    authorized_source_id {row['authorized_source_id']}")
        print(f"    bytes                {row['payload_size_bytes']}")
        print(f"    sha256 on the row    {row['payload_sha256']}")
        print(f"    sha256 recomputed    {recomputed}")
        print(f"    hash verified        {verified}")
        print(f"    http_status on row   {row['response_status']!r}  (not captured)")
        print(f"    mode                 {'APPLY' if args.apply else 'DRY RUN'}")
        print()

        if not verified:
            print("REFUSED: the persisted bytes do not match the recorded hash")
            return 1
        if str(row["authorized_source_id"] or "") != SOURCE:
            print("REFUSED: the payload does not name the authorized source")
            return 1

        if not args.apply:
            print("Dry run only. Re-run with --apply to record the attempt.")
            return 0

        written = record_attempt(
            connection=session,
            organization_id=DEMO,
            attempt_id=row["attempt_id"],
            attempt_number=1,
            collector_version="grants_gov_search2_adapter",
            job_id=JOB_ID,
            source_id=SOURCE,
            started_at=row["received_at"],
            completed_at=row["received_at"],
            execution_status="response_persisted",
            transport_kind=LIVE,
            transport_outcome="response_received",
            # Deliberately absent: never captured, and a second request to
            # learn it is forbidden.
            http_status=None,
            bytes_received=int(row["payload_size_bytes"] or 0),
            refusal_reason="none",
            request_url_fingerprint=row["source_url_fingerprint"],
            request_method="POST",
            raw_payload_sha256=row["payload_sha256"],
            raw_payload_persisted=True,
            execution_proof_available=True,
            fact_status="tenant_supplied",
            authorized_source_id=SOURCE,
        )
        session.commit()

        if written.get("blocked_reasons"):
            print(f"REFUSED: {written['blocked_reasons']}")
            return 1

        print("RECORDED.")
        attempt = written.get("attempt") or {}
        for field in (
            "attempt_id",
            "source_id",
            "execution_status",
            "transport_kind",
            "transport_outcome",
            "http_status",
            "bytes_received",
            "raw_payload_sha256",
            "raw_payload_persisted",
            "execution_proof_available",
            "live_source_call",
            "authorized_source_id",
        ):
            print(f"    {field:<28} {attempt.get(field)!r}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
