"""Gate 163E/F: fetch robots.txt for the authorized source. One request.

## The robots-preflight warrant is NOT collection permission

Full authorization requires `robots_status`, and `robots_status` can only be
resolved by fetching robots.txt — which is itself a live request. A robots
fetch gated on full authorization could never happen.

So this is a separate, narrower warrant, and the distinction is enforced rather
than described:

```text
robots preflight                     collection
-------------------------------      ------------------------------
needs the THREE signed decisions     needs all ELEVEN facts
   terms, review, activation
one path: /robots.txt                the authorized endpoint
GET only                             the source's declared method
does NOT need live-fetch opt-in      DOES need live-fetch opt-in
authorizes nothing else              authorizes one bounded request
```

A preflight that permitted anything but `/robots.txt` would be collection
permission with a different name.

## The host relationship is RESOLVED, not assumed

robots.txt is per-authority — RFC 9309 scopes it to scheme, host and port. The
collection request targets `api.grants.gov`; `www.grants.gov` is a DIFFERENT
authority and its robots.txt does not govern the API host.

So this fetches the robots of the host the collection request will actually go
to, and records both hosts so the relationship is visible in the evidence
rather than assumed by a reader. If the two ever diverge, the record shows
which one was consulted.

## One request, and it is recorded whatever happens

A failure is persisted as evidence and the run stops. There is no retry: a
retry is a second request, and the first live request this repository has ever
made should not silently become two.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import uuid
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.live_source_transport_service import (  # noqa: E402
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402,E501
    resolve_source_authorization_facts,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402,E501
    LIVE,
    TransportRequest,
    execute_request,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

AUTHORIZED_SEED = "nf-seed-2026-api-grants-gov-search2"

#: The ONE path a preflight may request. Anything else is collection.
ROBOTS_PATH = "/robots.txt"

#: The three signed decisions a preflight requires. NOT all eleven facts.
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


#: RFC 9309 section 2.3.1. Each status class means something different, and
#: the first live fetch of this campaign landed in the gap the old mapping
#: missed.
#:
#: `unavailable` PERMITS - section 2.3.1.3, "crawlers MAY access any
#: resources". It is NOT `unreachable`, which section 2.3.1.4 says MUST be
#: treated as a complete disallow.
ROBOTS_VERDICT_PERMITS: frozenset[str] = frozenset(
    {"allowed", "absent", "unavailable"}
)


def derive_robots_verdict(*, status: Any, body: bytes, path: str) -> dict:
    """The verdict for one status and one body, per RFC 9309 section 2.3.1.

    PURE: status and bytes in, verdict out. That is what lets a verdict be
    RE-DERIVED from stored evidence without refetching, which is how the 4xx
    correction was applied to the 403 already on disk.
    """
    if status is None:
        # Network failure, DNS failure or timeout. Section 2.3.1.4.
        return {
            "decision": "unreachable",
            "rfc_class": "network_failure",
            "restricts_collection": True,
            "matched_group": None,
            "rules": [],
        }

    code = int(status)

    if 200 <= code < 300:
        parsed = parse_robots(body, path=path, agent="*")
        parsed["rfc_class"] = "successful"
        parsed["restricts_collection"] = parsed["decision"] == "disallowed"
        return parsed

    if 300 <= code < 400:
        # This transport follows no redirect by design: a redirect is a
        # different URL than the one authorized. Unfetched does not permit.
        return {
            "decision": "unreachable",
            "rfc_class": "redirect_not_followed",
            "restricts_collection": True,
            "matched_group": None,
            "rules": [],
        }

    if code == 404:
        # Definitively no file. Distinct from 4xx in general, where the file
        # could not be retrieved and we cannot say whether it exists.
        return {
            "decision": "absent",
            "rfc_class": "unavailable",
            "restricts_collection": False,
            "matched_group": None,
            "rules": [],
        }

    if 400 <= code < 500:
        # Section 2.3.1.3, "Unavailable". The robots protocol adds NO
        # restriction for this authority. It authorizes nothing - section 2
        # is explicit that robots rules are not a form of access
        # authorization.
        return {
            "decision": "unavailable",
            "rfc_class": "unavailable",
            "restricts_collection": False,
            "matched_group": None,
            "rules": [],
        }

    # 5xx. Section 2.3.1.4, "Unreachable" - a complete disallow.
    return {
        "decision": "unreachable",
        "rfc_class": "unreachable",
        "restricts_collection": True,
        "matched_group": None,
        "rules": [],
    }


def parse_robots(body: bytes, *, path: str, agent: str = "*") -> dict:
    """Minimal RFC 9309 evaluation for one path under the wildcard agent.

    Deliberately small and deliberately CONSERVATIVE: anything it cannot parse
    confidently returns `unparseable`, which does not permit. A robots parser
    that guesses is a robots parser that eventually guesses wrong in the
    permitting direction.
    """
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"decision": "unparseable", "matched_group": None, "rules": []}

    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    current_agents: list[str] = []
    current_rules: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if current_rules:
                groups.append((current_agents, current_rules))
                current_agents, current_rules = [], []
            current_agents.append(value.lower())
        elif field in {"allow", "disallow"}:
            current_rules.append((field, value))
    if current_agents or current_rules:
        groups.append((current_agents, current_rules))

    matched = None
    for agents, rules in groups:
        if agent.lower() in agents:
            matched = (agents, rules)
            break
    if matched is None:
        for agents, rules in groups:
            if "*" in agents:
                matched = (agents, rules)
                break

    if matched is None:
        # No group applies to us. RFC 9309: absent rules mean no restriction.
        return {"decision": "allowed", "matched_group": None, "rules": []}

    agents, rules = matched
    best: tuple[int, str] | None = None
    for field, value in rules:
        if value == "":
            # An empty Disallow permits everything; an empty Allow is a no-op.
            if field == "disallow":
                candidate = (0, "allow")
                if best is None or candidate[0] >= best[0]:
                    best = candidate
            continue
        if path.startswith(value):
            candidate = (len(value), "allow" if field == "allow" else "disallow")
            # Longest match wins; Allow wins ties.
            if (
                best is None
                or candidate[0] > best[0]
                or (candidate[0] == best[0] and candidate[1] == "allow")
            ):
                best = candidate

    decision = "allowed" if best is None or best[1] == "allow" else "disallowed"
    return {
        "decision": decision,
        "matched_group": agents,
        "rules": [f"{f}: {v}" for f, v in rules],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--operator-handle", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="without this, resolves and prints but makes NO network request",
    )
    args = parser.parse_args()

    blocked: list[str] = []
    source_id = str(args.source_id or "").strip()
    if source_id != AUTHORIZED_SEED:
        blocked.append(
            f"preflight_not_authorized_for_seed:{source_id!r}; "
            f"allowed={AUTHORIZED_SEED!r}"
        )
    if not str(args.operator_handle or "").strip():
        blocked.append("no_operator_handle")

    registry = load_registry_rows()
    row = registry.get(source_id)
    if row is None:
        blocked.append(f"source_not_in_registry:{source_id}")

    # ---- resolve the host relationship EXPLICITLY --------------------
    collection_url = str((row or {}).get("source_url") or "")
    collection_parts = urlsplit(collection_url)
    collection_host = (collection_parts.hostname or "").lower()
    collection_path = collection_parts.path or "/"

    # robots.txt is per-AUTHORITY. The robots that governs the collection
    # request is the one served by the host that request goes to.
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
            "RFC 9309 scopes robots.txt to a scheme/host/port authority. The "
            "robots governing a request is the one served by the host that "
            "request goes to. www.grants.gov is a DIFFERENT authority from "
            "api.grants.gov and its robots.txt does not govern the API host."
        ),
        "note": (
            "if these two hosts ever differ, this record shows which was "
            "consulted rather than leaving a reader to assume"
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

        # The preflight warrant: THREE signed decisions, not eleven facts.
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
            "authorizes_collection": False,
            "source_id": source_id,
            "operator_handle": str(args.operator_handle),
            "host_relationship": host_relationship,
            "preflight_required_facts": dict(preflight_facts),
            "request": {
                "method": "GET",
                "url": robots_url,
                "path": ROBOTS_PATH,
                "credentials": None,
                "follows_redirects": False,
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

        # ---- the request ------------------------------------------------
        #
        # A preflight authorization: approved for THIS source, scoped to the
        # robots path. `build_live_transport` checks source and host at
        # construction, so a transport that exists cannot be re-pointed.
        preflight_authorization = {
            "authorized": True,
            "source_id": source_id,
            "authorization_status": "robots_preflight",
        }
        try:
            transport = build_live_transport(
                authorized_source_id=source_id,
                authorization=preflight_authorization,
                authorized_url=robots_url,
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

        # A policy that permits LIVE for this named source. The boundary
        # re-checks; this is the warrant it checks against.
        policy = {
            "execution_allowed": True,
            "live_transport_allowed": True,
            "hermetic_transport_allowed": False,
            "authorized_source_id": source_id,
        }

        print(f"\n--- REQUESTING {robots_url}")
        result = execute_request(
            request=request,
            transport_kind=LIVE,
            transport=transport,
            policy=policy,
        )
        body = result.pop("body_bytes", b"") or b""

        print(f"  dispatched     {result['dispatched']}")
        print(f"  outcome        {result['outcome']}")
        print(f"  http_status    {result['status_code']}")
        print(f"  bytes          {result['bytes_received']}")
        print(f"  elapsed        {result['elapsed_seconds']:.3f}s")
        if result["blocked_reasons"]:
            print(f"  blocked        {result['blocked_reasons']}")

        if not result["dispatched"]:
            print("\nNOT DISPATCHED - stopping, no evidence to record")
            return 1

        digest = hashlib.sha256(body).hexdigest()
        print(f"  sha256         {digest}")
        print()
        print("--- body")
        print(body.decode("utf-8", errors="replace")[:600])

        verdict = derive_robots_verdict(
            status=result["status_code"], body=body, path=collection_path
        )
        status = result["status_code"]

        print()
        print(f"--- robots verdict for {collection_path}: {verdict['decision']}")
        print(f"    matched group: {verdict['matched_group']}")
        print(f"    rules:         {verdict['rules']}")

        now = dt.datetime.now(dt.UTC)
        session.execute(
            sa.delete(ROBOTS_TABLE).where(
                sa.and_(
                    ROBOTS_TABLE.c.organization_id == DEMO_ORG,
                    ROBOTS_TABLE.c.host == robots_host,
                    ROBOTS_TABLE.c.evaluated_path == collection_path,
                )
            )
        )
        session.execute(
            sa.insert(ROBOTS_TABLE).values(
                id=uuid.uuid4(),
                organization_id=DEMO_ORG,
                is_demo=True,
                host=robots_host,
                fetched_for_source_id=source_id,
                fetched_at=now,
                http_status=status,
                decision=verdict["decision"],
                evaluated_path=collection_path,
                user_agent_scope="*",
                payload_sha256=digest if body else None,
                attempt_id=f"gate163-robots-{uuid.uuid4().hex[:12]}",
                evidence_ref=robots_url,
                recheck_due_at=None,
                fact_status="live_fetch",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        print()
        print(f"RECORDED robots evidence for {robots_host}{collection_path}")
        print(f"  decision  {verdict['decision']}")
        print(f"  sha256    {digest}")
        return 0
    except Exception as exc:  # noqa: BLE001 - report honestly, do not retry
        session.rollback()
        print(f"\nPREFLIGHT FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
