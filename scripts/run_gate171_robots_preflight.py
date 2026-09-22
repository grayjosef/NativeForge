"""Gate 171G: robots preflight for an approved source. One request. No retry.

Same warrant shape as Gate 163's, and the same narrow one: the preflight needs
the three signed decisions, not the eleven collection facts, because
`robots_status` can only be resolved by fetching robots.txt and a robots fetch
gated on full authorization could never happen.

What differs is where the allowlist lives. Gate 163 held one seed as a module
constant; this reads the operator approval file, so a third and fourth source
cost a reviewed data change rather than a code edit. The check is no weaker: a
source id absent from that file is refused by name.

## One request, whatever happens

A failure is persisted as evidence and the run stops. There is no retry -
a retry is a second request, and the operator authorized exactly two per host.

## The verdict authorizes nothing

RFC 9309 section 2 is explicit that robots rules are not access authorization.
A permitting verdict removes one objection. It is not permission, and the
collection step checks the signed decisions again regardless.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import uuid
from urllib.parse import urlsplit

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.robots_verdict_service import (  # noqa: E402
    ROBOTS_VERDICT_PERMITS,
    derive_robots_verdict,
)
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402,E501
    resolve_source_authorization_facts,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402,E501
    LIVE,
    TransportRequest,
    execute_request,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    WARRANT_ROBOTS_PREFLIGHT,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
APPROVAL_FILE = (
    REPO / "fixtures" / "source_authorization" / "gate171_operator_approval.json"
)
DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

#: The ONE path a preflight may request. Anything else is collection.
ROBOTS_PATH = "/robots.txt"

PREFLIGHT_REQUIRED_FACTS = (
    "terms_status",
    "human_review_status",
    "activation_status",
)

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

    blocked: list[str] = []
    source_id = str(args.source_id or "").strip()
    handle = str(args.operator_handle or "").strip()

    entry = approved_entry(source_id)
    if entry is None:
        blocked.append(f"preflight_not_authorized_for_seed:{source_id!r}")
    elif not entry.get("live_fetch_approved"):
        blocked.append(f"source_present_but_not_approved:{source_id!r}")
    if not handle:
        blocked.append("no_operator_handle")

    registry = load_registry_rows()
    row = registry.get(source_id)
    if row is None:
        blocked.append(f"source_not_in_registry:{source_id}")

    collection_url = str((row or {}).get("source_url") or "")
    parts = urlsplit(collection_url)
    collection_host = (parts.hostname or "").lower()
    collection_path = parts.path or "/"
    robots_host = collection_host
    robots_url = f"https://{robots_host}{ROBOTS_PATH}"

    host_relationship = {
        "collection_url": collection_url,
        "collection_host": collection_host,
        "collection_path": collection_path,
        "robots_host": robots_host,
        "robots_url": robots_url,
        "same_authority": robots_host == collection_host,
        "why": (
            "RFC 9309 scopes robots.txt to a scheme/host/port authority, so "
            "the robots governing a request is the one served by the host "
            "that request goes to."
        ),
    }

    session = SessionLocal()
    try:
        resolution = resolve_source_authorization_facts(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            now=dt.datetime.now(dt.UTC),
        )
        facts = resolution.get("resolved_facts") or {}
        preflight_facts = {}
        for name in PREFLIGHT_REQUIRED_FACTS:
            fact = facts.get(name) or {}
            preflight_facts[name] = fact.get("fact_status")
            if fact.get("fact_status") != "recorded":
                blocked.append(f"preflight_requires:{name}:{fact.get('fact_status')}")
            if not fact.get("recorded_by"):
                blocked.append(f"preflight_requires_a_signer:{name}")

        packet = {
            "purpose": "robots_preflight",
            "gate": "171G",
            "authorizes_collection": False,
            "source_id": source_id,
            "operator_handle": handle,
            "host_relationship": host_relationship,
            "preflight_required_facts": dict(preflight_facts),
            "request": {
                "method": "GET",
                "url": robots_url,
                "path": ROBOTS_PATH,
                "credentials": None,
                "follows_redirects": False,
                "retries": 0,
            },
            "blocked_reasons": sorted(set(blocked)),
            "would_request": not blocked,
            "apply": bool(args.apply),
        }
        print(json.dumps(packet, indent=2, sort_keys=True))

        if blocked:
            print("\nREFUSED - no request made")
            return 1
        if not args.apply:
            print("\nDRY RUN - no network request made. Pass --apply to fetch.")
            return 0

        # No pre-validated authorization is handed in. `build_live_transport`
        # calls the warrant check ITSELF and refuses at construction, which is
        # what makes a bypass structurally impossible rather than discouraged.
        # Gate 163's own runner still passes an `authorization=` kwarg this
        # signature no longer accepts - it is stale against the API that
        # replaced it, and that staleness is why this gate did not copy it.
        try:
            transport = build_live_transport(
                authorized_source_id=source_id,
                authorized_url=robots_url,
                warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
                connection=session,
                organization_id=DEMO_ORG,
                method="GET",
                timeout_seconds=20.0,
            )
        except LiveTransportRefused as refused:
            print(f"\nTRANSPORT REFUSED: {refused.reasons}")
            return 1

        request = TransportRequest(
            method="GET",
            url=robots_url,
            headers={"accept": "text/plain"},
            timeout_seconds=20.0,
            body_bytes=None,
        )
        fetched_at = dt.datetime.now(dt.UTC)
        attempt_id = f"gate171-robots-{source_id}-{fetched_at:%Y%m%dT%H%M%SZ}"

        result = execute_request(
            request=request,
            transport_kind=LIVE,
            transport=transport,
            # The boundary asks which authorization permits a LIVE dispatch,
            # separately from the warrant the transport already checked at
            # construction. Omitting it does not fail loudly - it returns a
            # BLOCKED result with no response, which is how the first run of
            # this script came within one CHECK constraint of recording a
            # fabricated network failure.
            policy={
                "live_transport_allowed": True,
                "authorized_source_id": source_id,
            },
        )

        # A BLOCKED dispatch is not a fetch, and must never be derived into a
        # verdict. `status=None` from a refusal and `status=None` from a real
        # timeout are the same two bytes and completely different facts: the
        # second is evidence about the host, the first is evidence about this
        # script. Deriving the first produced `unreachable`, which under RFC
        # 9309 section 2.3.1.4 is a COMPLETE DISALLOW - a refusal by the
        # caller, about to be filed as a restriction by the publisher.
        # `execute_request` returns a FLAT result - dispatched / outcome /
        # status_code / body_bytes. There is no "response" object in it. An
        # earlier cut of this script read `result["response"]`, got None every
        # time, and reported "no request was made" about a dispatch that had
        # already happened. `dispatched` is the authoritative answer and is
        # read directly.
        blocked_reasons = list(result.get("blocked_reasons") or [])
        dispatched = bool(result.get("dispatched"))
        if blocked_reasons or not dispatched:
            print("\n=== NO REQUEST WAS MADE - the boundary refused to dispatch")
            print(f"  blocked_reasons      {blocked_reasons}")
            print(f"  dispatched           {dispatched}")
            print("  nothing is recorded: a refusal is not a robots verdict")
            print("  the request budget is UNSPENT")
            return 1

        status = result.get("status_code")
        body = bytes(result.get("body_bytes") or b"")
        outcome = result.get("outcome")
        digest = hashlib.sha256(body).hexdigest()

        verdict = derive_robots_verdict(
            status=status, body=body, path=collection_path
        )

        print("\n=== the one request, as it happened")
        print(f"  url                  {robots_url}")
        print(f"  http_status          {status}")
        print(f"  transport_outcome    {outcome}")
        print(f"  bytes                {len(body)}")
        print(f"  payload_sha256       {digest}")
        print(f"  fetched_at           {fetched_at.isoformat()}")
        print(f"  evaluated_path       {collection_path}")
        print(f"  decision             {verdict['decision']}")
        print(f"  rfc_class            {verdict.get('rfc_class')}")
        print(f"  restricts_collection {verdict.get('restricts_collection')}")
        print(f"  permits              {verdict['decision'] in ROBOTS_VERDICT_PERMITS}")

        session.execute(
            sa.insert(ROBOTS_TABLE).values(
                id=uuid.uuid4(),
                organization_id=DEMO_ORG,
                is_demo=True,
                host=robots_host,
                fetched_for_source_id=source_id,
                fetched_at=fetched_at,
                http_status=status,
                decision=str(verdict["decision"]),
                evaluated_path=collection_path,
                user_agent_scope="*",
                payload_sha256=digest,
                attempt_id=attempt_id,
                evidence_ref=f"{robots_url}#gate171-{verdict['decision']}",
                recheck_due_at=None,
                # THIS table's vocabulary is ('live_fetch', 'synthetic_
                # fixture', 'demo_fixture', 'unknown') - migration 0049 - and
                # it is NOT the FACT_STATUSES tuple used by the tenant-profile
                # tables, which is where `tenant_supplied` came from. Two
                # different vocabularies, both spelled FACT_STATUSES in their
                # own migration. A robots row written by a real fetch is
                # `live_fetch`, which also says how the fact was obtained.
                fact_status="live_fetch",
                created_at=fetched_at,
                updated_at=fetched_at,
            )
        )
        session.commit()
        print("\n  robots evidence persisted. This authorizes NOTHING further.")
        if verdict.get("restricts_collection"):
            print("  RESTRICTS COLLECTION - stop this source, do not work around it.")
            return 2
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
