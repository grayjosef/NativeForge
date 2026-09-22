"""Gate 171H/I: ONE bounded collection for an approved source.

Generic. The adapter is resolved from the activation row's recorded binding,
so this script names no source and a fourth source needs no edit to it.

## It persists the bytes and STOPS

Normalization, canonical write, identity and change intelligence are a
SEPARATE offline step that reads the persisted payload. That split is not
tidiness: this gate has already lost one live response to a defect downstream
of the request, and a response that reaches disk before anything tries to
parse it cannot be lost by a parser.

```text
this script          request -> raw evidence -> attempt row -> stop
the offline step     persisted bytes -> normalize -> canonical -> change
```

## One request, no retry

`RETRY_POLICY` on every adapter is one attempt. A failure is recorded and the
run stops. The operator authorized one bounded request per source and a retry
is a second one.

## A refusal is not a response

`execute_request` returns a FLAT result with `dispatched`. An earlier script in
this gate read a `response` key that does not exist, got None, and reported
"no request was made" about a request that had already gone out. Nothing here
infers a status from a missing object: `dispatched` is read directly, and a
blocked dispatch records nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import json
import pathlib
import sys
import uuid

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    descriptor_failures,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402,E501
    LIVE,
    execute_request,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    WARRANT_SOURCE_COLLECTION,
)
from nativeforge.services.source_raw_payload_persistence_service import (  # noqa: E402,E501
    persist_raw_payload,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
APPROVAL_FILE = (
    REPO / "fixtures" / "source_authorization" / "gate171_operator_approval.json"
)
DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

#: Adapter modules live under one package and are named by their key. The
#: binding recorded on the activation names the key; this turns it into a
#: module. No mapping table, so a new adapter is a new file and a data row.
ADAPTER_PACKAGE = "nativeforge.services.source_adapters"

ACTIVE_SOURCES = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_name", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("activation_notes", sa.Text()),
    sa.Column("disabled_at", sa.DateTime(timezone=True)),
)


def approved_entry(source_id: str) -> dict | None:
    approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
    for entry in approval.get("approved_sources") or []:
        if str(entry.get("source_id")) == source_id:
            return entry
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    source_id = str(args.source_id or "").strip()
    handle = str(args.operator_handle or "").strip()
    blocked: list[str] = []

    entry = approved_entry(source_id)
    if entry is None:
        blocked.append(f"collection_not_authorized_for_seed:{source_id!r}")
    elif not entry.get("live_fetch_approved"):
        blocked.append(f"source_present_but_not_approved:{source_id!r}")
    elif int((entry.get("request_budget") or {}).get("bounded_collection", 0)) < 1:
        blocked.append("no_bounded_collection_request_in_this_source_budget")
    if not handle:
        blocked.append("no_operator_handle")

    session = SessionLocal()
    try:
        row = session.execute(
            sa.select(ACTIVE_SOURCES).where(
                sa.and_(
                    ACTIVE_SOURCES.c.organization_id == DEMO_ORG,
                    ACTIVE_SOURCES.c.source_id == source_id,
                )
            )
        ).mappings().first()
        if row is None:
            blocked.append(f"source_has_no_activation_row:{source_id}")
        elif row.get("disabled_at") is not None:
            blocked.append("source_is_disabled")

        adapter_key = str((row or {}).get("collection_method") or "")
        adapter = None
        if not adapter_key:
            blocked.append("activation_row_records_no_adapter_binding")
        else:
            try:
                adapter = importlib.import_module(f"{ADAPTER_PACKAGE}.{adapter_key}")
            except Exception as exc:  # noqa: BLE001
                blocked.append(f"adapter_not_importable:{adapter_key}:{exc}")

        descriptor = None
        if adapter is not None:
            # Bound from the activation row, not from the adapter's defaults.
            # A descriptor that supplies its own id and URL is a second source
            # of truth about which source this is.
            descriptor = adapter.build_descriptor(
                source_id=source_id,
                source_url=str((row or {}).get("source_url_or_search_target") or ""),
            )
            problems = descriptor_failures(descriptor)
            blocked.extend(problems)
            declared = str(descriptor.base_url)
            approved_url = str((entry or {}).get("source_url") or "")
            if approved_url and declared != approved_url:
                # The adapter's descriptor and the operator's approval must
                # name the same URL. A descriptor default that drifted from
                # what was approved is a different request.
                blocked.append(
                    f"descriptor_url_is_not_the_approved_url:{declared!r}"
                )

        packet = {
            "purpose": "gate171_bounded_collection",
            "source_id": source_id,
            "operator_handle": handle,
            "adapter_binding": adapter_key,
            "descriptor": descriptor.describe() if descriptor else None,
            "request_shape": dict(descriptor.request_shape) if descriptor else None,
            "max_requests_this_run": 1,
            "retry_policy": getattr(adapter, "RETRY_POLICY", None),
            "rate_limit_policy": getattr(adapter, "RATE_LIMIT_POLICY", None),
            "blocked_reasons": sorted(set(blocked)),
            "would_request": not blocked,
            "apply": bool(args.apply),
        }
        print(json.dumps(packet, indent=2, sort_keys=True, default=str))

        if blocked:
            print("\nREFUSED - no request made")
            return 1
        if not args.apply:
            print("\nDRY RUN - no network request made. Pass --apply to collect.")
            return 0

        cursor = PageCursor(
            max_pages=descriptor.max_pages, max_records=descriptor.max_records
        )
        request = adapter.build_request(
            descriptor=descriptor,
            # The activation row IS the authorization. Passing it satisfies
            # the adapter's refusal-without-authorization contract; the real
            # gate is the warrant the transport checks for itself below.
            authorization={"source_id": source_id, "activation": dict(row)},
            cursor=cursor,
        )

        try:
            transport = build_live_transport(
                authorized_source_id=source_id,
                authorized_url=request.url,
                warrant_kind=WARRANT_SOURCE_COLLECTION,
                connection=session,
                organization_id=DEMO_ORG,
                method=request.method,
                timeout_seconds=30.0,
            )
        except LiveTransportRefused as refused:
            print(f"\nTRANSPORT REFUSED: {refused.reasons}")
            print("No request made.")
            return 1

        started = dt.datetime.now(dt.UTC)
        result = execute_request(
            request=request,
            transport_kind=LIVE,
            transport=transport,
            policy={
                "live_transport_allowed": True,
                "authorized_source_id": source_id,
            },
        )
        blocked_reasons = list(result.get("blocked_reasons") or [])
        dispatched = bool(result.get("dispatched"))
        if blocked_reasons or not dispatched:
            print("\n=== NO REQUEST WAS MADE - the boundary refused to dispatch")
            print(f"  blocked_reasons      {blocked_reasons}")
            print(f"  dispatched           {dispatched}")
            print("  nothing is recorded. The request budget is UNSPENT.")
            return 1

        status = result.get("status_code")
        body = bytes(result.get("body_bytes") or b"")
        observed_sha = hashlib.sha256(body).hexdigest()
        received_at = dt.datetime.now(dt.UTC)

        print("\n=== the one request, as it happened")
        print(f"  method               {request.method}")
        print(f"  url                  {request.url}")
        print(f"  http_status          {status}")
        print(f"  transport_outcome    {result.get('outcome')}")
        print(f"  bytes                {len(body)}")
        print(f"  payload_sha256       {observed_sha}")
        print(f"  started_at           {started.isoformat()}")
        print(f"  received_at          {received_at.isoformat()}")
        headers = result.get("response_headers") or {}
        print(f"  content_type         {headers.get('content-type')}")

        # ---- persist BEFORE anything parses it ------------------------
        persisted = persist_raw_payload(
            connection=session,
            organization_id=DEMO_ORG,
            job_id=f"gate171-{source_id}",
            source_id=source_id,
            attempt_number=1,
            body=body,
            response_headers=result.get("response_headers") or {},
            response_status=status,
            source_url=request.url,
            received_at=received_at,
            fact_status="tenant_supplied",
            live_fetch_performed=True,
            collector_invoked=True,
            authorized_source_id=source_id,
        )
        session.commit()

        print()
        print(f"  persisted            {persisted.get('persisted')}")
        print(f"  blocked_reasons      {persisted.get('blocked_reasons') or 'none'}")
        print(f"  attempt_id           {persisted.get('attempt_id')}")
        print(f"  payload_sha256       {persisted.get('payload_sha256')}")
        print(f"  write_hash_verified  {persisted.get('write_hash_verified')}")
        print(
            "  sha matches observed "
            f"{persisted.get('payload_sha256') == observed_sha}"
        )

        if not persisted.get("persisted"):
            print("\nPERSISTENCE REFUSED. The response is not recorded. Stopping.")
            return 1

        print("\n  RAW EVIDENCE IS DURABLE. Nothing has parsed it yet.")
        print("  Next: the offline normalization step. No further request.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
