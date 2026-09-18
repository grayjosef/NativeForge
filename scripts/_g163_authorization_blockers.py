"""Exactly what stands between the recorded decisions and an allowlisted source.

Reads. Writes nothing, fabricates nothing, permits nothing.
"""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402
    resolve_source_authorization_facts,
)
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    COLLECTION_REQUIRED_FACTS,
    PREFLIGHT_REQUIRED_FACTS,
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
API_URL = "https://api.grants.gov/v1/api/search2"

session = SessionLocal()

print("=== the eleven facts")
resolution = resolve_source_authorization_facts(
    connection=session, organization_id=DEMO, source_id=SOURCE
)
for name, fact in sorted((resolution.get("resolved_facts") or {}).items()):
    print(
        f"  {name:<22} value={str(fact.get('value')):<16} "
        f"status={fact.get('fact_status')}"
    )
    if fact.get("unresolvable_because"):
        print(f"      unresolvable: {str(fact['unresolvable_because'])[:110]}")

print()
print("=== authorization")
result = authorize_source_for_live_access(
    connection=session, organization_id=DEMO, source_id=SOURCE
)
print(f"  authorized            {result.get('authorized')}")
print(f"  authorization_status  {result.get('authorization_status')}")
for key in ("blocking_reasons", "refusal_reasons", "blockers", "unmet"):
    if result.get(key):
        print(f"  {key}:")
        for item in result[key]:
            print(f"      - {item}")

print()
print("=== what the WARRANT requires (a different list)")
print(f"  preflight:  {list(PREFLIGHT_REQUIRED_FACTS)}")
print(f"  collection: {list(COLLECTION_REQUIRED_FACTS)}")

decision = evaluate_live_request(
    warrant_kind=WARRANT_SOURCE_COLLECTION,
    authorized_source_id=SOURCE,
    request_url=API_URL,
    method="POST",
    connection=session,
    organization_id=DEMO,
)
print()
print("=== the warrant, for the collection request")
print(f"  permitted             {decision.get('permitted')}")
print(f"  refusal_reasons       {json.dumps(decision.get('refusal_reasons'))}")

session.close()
