"""Gate 163Z: exactly ONE bounded search2 request.

Dry-run by default: it resolves the authorization, builds the request, builds
the transport through the enforcement path and stops short of the socket.
`--apply` dispatches, once.

## One request, and the path it takes

```text
authorize_source_for_live_access(exercise_runtime=True)   approved
build_live_transport(warrant_kind=source_collection)      calls
                                                          assert_live_request_permitted
execute_request(transport_kind=LIVE, policy names the authorized source)
  -> the Gate 161 boundary, which refuses a live dispatch that names no
     authorization
  -> one POST, no redirect, no cookie, no credential, bounded timeout
```

`search_grants_gov_opportunities` is NOT used: it makes its own body from the
source name, and `fetch_grants_gov_opportunities_for_source` would follow the
search with a `fetchOpportunity` per hit. This dispatches one request and
parses the bytes itself.

## The query

```json
{"rows": 1, "oppStatuses": "posted|forecasted", "keyword": "tribal"}
```

`rows: 1` because one record proves the path. The adapter's own builder would
have used the source's display name - "Grants.gov Search2 API" - as the
keyword, which proves transport and finds nothing a Tribe could apply for.

## No job row

A one-shot operator-initiated collection persists an execution attempt, the
raw bytes and an execution proof. It does not invent a durable scheduler job:
`completed` is unreachable in the job store by design, and a job row created
only to satisfy readiness would make `nothing_collected` false for a
collection that never went through the queue.

## If it fails

The evidence is persisted and the script stops. No retry, at any level.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.source_collection_request_builder_service import (  # noqa: E402
    build_source_request,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402
    LIVE,
    execute_request,
)
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_fetch_opt_in_service import (  # noqa: E402
    is_live_fetch_opted_in,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)
from nativeforge.services.source_raw_payload_persistence_service import (  # noqa: E402
    persist_raw_payload,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
API_URL = "https://api.grants.gov/v1/api/search2"

#: Bounded, and deliberately Native-relevant. One row proves the path.
SEARCH_BODY: dict[str, object] = {
    "rows": 1,
    "oppStatuses": "posted|forecasted",
    "keyword": "tribal",
}

JOB_ID = "gate163-first-live-collection"
TIMEOUT_SECONDS = 20.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="dispatch the request")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        # ---- 1. authorization, with fresh runtime evidence -------------
        authorization = authorize_source_for_live_access(
            connection=session,
            organization_id=DEMO,
            source_id=SOURCE,
            purpose="source_collection",
            method="POST",
            exercise_runtime=True,
        )
        status = str(authorization.get("authorization_status") or "")
        opted_in = is_live_fetch_opted_in(
            connection=session, organization_id=DEMO, source_id=SOURCE
        )

        print("=== Gate 163Z first live search2 collection")
        print(f"    source_id            {SOURCE}")
        print(f"    url                  {API_URL}")
        print(f"    body                 {json.dumps(SEARCH_BODY, sort_keys=True)}")
        print(f"    authorization        {status}")
        print(f"    live_fetch_opted_in  {opted_in}")

        if status != "approved":
            print(f"REFUSED: authorization is {status}")
            print(f"    reasons {authorization.get('refusal_reasons')}")
            return 1
        if not opted_in:
            print("REFUSED: no live-fetch opt-in for this source")
            return 1

        # ---- 2. the warrant, for THIS request --------------------------
        warrant = evaluate_live_request(
            warrant_kind=WARRANT_SOURCE_COLLECTION,
            authorized_source_id=SOURCE,
            request_url=API_URL,
            method="POST",
            connection=session,
            organization_id=DEMO,
        )
        print(f"    warrant permitted    {warrant['permitted']}")
        if not warrant["permitted"]:
            print(f"REFUSED: {warrant['refusal_reasons']}")
            return 1

        # ---- 3. the request -------------------------------------------
        built = build_source_request(
            source_definition={
                "source_id": SOURCE,
                "endpoint": API_URL,
                "method": "POST",
                "body": json.dumps(SEARCH_BODY, sort_keys=True),
            },
            timeout_seconds=TIMEOUT_SECONDS,
        )
        if not built.get("usable"):
            print(f"REFUSED: request not usable: {built.get('blocked_reasons')}")
            return 1
        request = built["transport_request"]
        request.headers["content-type"] = "application/json"

        request_fingerprint = hashlib.sha256(
            f"POST {API_URL} {json.dumps(SEARCH_BODY, sort_keys=True)}".encode()
        ).hexdigest()
        print(f"    request fingerprint  {request_fingerprint}")

        # ---- 4. the transport, through the enforcement path ------------
        try:
            transport = build_live_transport(
                authorized_source_id=SOURCE,
                authorized_url=API_URL,
                warrant_kind=WARRANT_SOURCE_COLLECTION,
                connection=session,
                organization_id=DEMO,
                method="POST",
                timeout_seconds=TIMEOUT_SECONDS,
            )
        except LiveTransportRefused as refused:
            print(f"REFUSED BY THE GUARD: {refused.reasons}")
            return 1
        print(f"    transport warrant    {json.dumps(transport.warrant, default=str)}")

        if not args.apply:
            print()
            print("DRY RUN. Everything above resolved; no socket was opened.")
            print("Re-run with --apply to make the one request.")
            return 0

        # ---- 5. ONE dispatch ------------------------------------------
        print()
        print("DISPATCHING ONE REQUEST...")
        dispatched = execute_request(
            request=request,
            transport_kind=LIVE,
            transport=transport,
            policy={
                "execution_allowed": True,
                "live_transport_allowed": True,
                "hermetic_transport_allowed": False,
                "authorized_source_id": SOURCE,
            },
        )

        # `status_code` and `bytes_received`, which is what the boundary
        # returns at the top level. An earlier version read `response_status`
        # and `body_size_bytes`, so both printed None and the HTTP status
        # persisted as NULL.
        #
        # Worth being precise about which mistake each name was.
        # `response_status` does not exist in the result at all.
        # `body_size_bytes` DOES exist - nested under `request`, describing the
        # REQUEST body - so reading it at the top level found nothing while
        # looking like a plausible key. The second is the more instructive
        # error: a name that is real somewhere else in the same structure.
        status_code = dispatched.get("status_code")
        bytes_received = dispatched.get("bytes_received")

        print(f"    dispatched           {dispatched.get('dispatched')}")
        print(f"    outcome              {dispatched.get('outcome')}")
        print(f"    blocked_reasons      {dispatched.get('blocked_reasons') or 'none'}")
        print(f"    http status          {status_code}")
        print(f"    bytes                {bytes_received}")
        print(f"    elapsed              {dispatched.get('elapsed_seconds')}")

        body = dispatched.get("body_bytes")
        if isinstance(body, str):
            body = body.encode("utf-8")
        body = body or b""
        observed_sha = hashlib.sha256(body).hexdigest()
        print(f"    sha256               {observed_sha}")

        if not dispatched.get("dispatched"):
            print()
            print("THE REQUEST DID NOT COMPLETE. Persisting nothing further and")
            print("stopping. No retry.")
            return 1

        # ---- 6. persist the exact bytes, with the warrant --------------
        now = dt.datetime.now(dt.UTC)
        persisted = persist_raw_payload(
            connection=session,
            organization_id=DEMO,
            job_id=JOB_ID,
            source_id=SOURCE,
            attempt_number=1,
            body=body,
            response_headers=dispatched.get("response_headers") or {},
            response_status=status_code,
            source_url=API_URL,
            received_at=now,
            fact_status="tenant_supplied",
            live_fetch_performed=True,
            collector_invoked=True,
            authorized_source_id=SOURCE,
        )
        session.commit()

        print()
        print(f"    persisted            {persisted.get('persisted')}")
        print(f"    blocked_reasons      {persisted.get('blocked_reasons') or 'none'}")
        print(f"    attempt_id           {persisted.get('attempt_id')}")
        print(f"    payload_sha256       {persisted.get('payload_sha256')}")
        print(f"    write_hash_verified  {persisted.get('write_hash_verified')}")
        print(
            "    sha matches observed "
            f"{persisted.get('payload_sha256') == observed_sha}"
        )

        if not persisted.get("persisted"):
            print("PERSISTENCE REFUSED. The response is not recorded. Stopping.")
            return 1

        # ---- 7. what came back ----------------------------------------
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"    response not JSON    {type(exc).__name__}")
            parsed = None

        if isinstance(parsed, dict):
            print(f"    errorcode            {parsed.get('errorcode')}")
            print(f"    msg                  {parsed.get('msg')}")
            data = parsed.get("data") or {}
            hits = list(data.get("oppHits") or [])
            print(f"    hit_count            {len(hits)}")
            print(f"    total available      {data.get('hitCount')}")
            if hits:
                first = hits[0]
                print("    first opportunity:")
                for field in ("id", "number", "title", "agencyCode", "openDate"):
                    print(f"        {field:<14} {first.get(field)}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
