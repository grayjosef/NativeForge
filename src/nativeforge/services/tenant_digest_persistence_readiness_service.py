"""Gate 151F: may `tenant_digest_persistence_live` be true, and on what evidence?

## Derived from a round trip, not from the table existing

A table that exists proves a migration ran. This lane needs the digest to have
survived a write and come back with its hash intact, its counts agreeing, and a
cross-org read refused — six conditions, each supplied by something that
actually happened rather than asserted.

Gate 138 established the shape: `customer_persistence_live` is measured from a
real round trip and the row is read back by id rather than merely counted.

## Controlled dev/demo only

`production_digest_persistence` has no branch that returns true. Persisting a
real tenant's digest is `customer_operational_data` under Gate 148's
classification, and writing one needs a consent record, a beta scope approval,
live customer auth and a verified binding — none of which exists.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_digest_persistence_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Every condition, each proved by something that happened.
CONDITIONS: tuple[str, ...] = (
    "table_exists",
    "repository_round_trip",
    "payload_hash_stable",
    "counts_preserved",
    "honesty_fields_preserved",
    "cross_org_read_refused",
    "delivery_intent_references_a_persisted_digest",
)

#: Capabilities that must be false for this lane to mean what it says.
MUST_STAY_FALSE: tuple[str, ...] = (
    "email_delivery",
    "source_monitoring_live",
    "object_store_configured",
    "production_digest_persistence",
)

#: What each condition is proved by, so a reader can check rather than take.
CONDITION_EVIDENCE: dict[str, str] = {
    "table_exists": "migration 0042 applied and the table is inspectable",
    "repository_round_trip": "a digest was written and read back by its id",
    "payload_hash_stable": (
        "the stored sha256 equals a hash recomputed over the stored payload"
    ),
    "counts_preserved": (
        "items_total, visible, suppressed and unchanged came back agreeing"
    ),
    "honesty_fields_preserved": (
        "human review, unverified deadlines and unknown reporting burden "
        "survived the round trip"
    ),
    "cross_org_read_refused": (
        "a read for the same digest id under another organization returned "
        "nothing, with the same answer it gives for a digest that does not "
        "exist"
    ),
    "delivery_intent_references_a_persisted_digest": (
        "an intent's digest_id resolves to a stored record - the gap Gate 150 "
        "found, where 71 intents named digests that existed nowhere"
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_digest_persistence_readiness(
    *,
    table_exists: bool | None = None,
    repository_round_trip: bool | None = None,
    payload_hash_stable: bool | None = None,
    counts_preserved: bool | None = None,
    honesty_fields_preserved: bool | None = None,
    cross_org_read_refused: bool | None = None,
    delivery_intent_references_a_persisted_digest: bool | None = None,
    email_delivery: bool | None = None,
    source_monitoring_live: bool | None = None,
    object_store_configured: bool | None = None,
    live_source_calls: int | None = None,
    emails_sent: int | None = None,
    object_store_calls: int | None = None,
) -> dict[str, Any]:
    """Report the lane. `tenant_digest_persistence_live` is derived, not given."""
    measured = {
        "table_exists": bool(table_exists),
        "repository_round_trip": bool(repository_round_trip),
        "payload_hash_stable": bool(payload_hash_stable),
        "counts_preserved": bool(counts_preserved),
        "honesty_fields_preserved": bool(honesty_fields_preserved),
        "cross_org_read_refused": bool(cross_org_read_refused),
        "delivery_intent_references_a_persisted_digest": bool(
            delivery_intent_references_a_persisted_digest
        ),
    }

    capabilities = {
        "email_delivery": bool(email_delivery),
        "source_monitoring_live": bool(source_monitoring_live),
        "object_store_configured": bool(object_store_configured),
        "production_digest_persistence": False,
    }

    counters = {
        "live_source_calls": int(live_source_calls or 0),
        "emails_sent": int(emails_sent or 0),
        "object_store_calls": int(object_store_calls or 0),
    }

    missing = [name for name in CONDITIONS if not measured[name]]
    dishonest = [
        name for name in MUST_STAY_FALSE if capabilities.get(name)
    ]
    contacted = [name for name, value in counters.items() if value]

    blockers = sorted(
        {
            *(f"condition_not_met:{name}" for name in missing),
            *(f"must_be_false_but_is_true:{name}" for name in dishonest),
            *(f"something_was_contacted:{name}" for name in contacted),
        }
    )

    live = not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived. Never supplied.
            "tenant_digest_persistence_live": live,
            "production_digest_persistence": False,
            "production_is_never_computed": True,
            "conditions": list(CONDITIONS),
            "conditions_met": measured,
            "conditions_missing": missing,
            "condition_evidence": dict(CONDITION_EVIDENCE),
            "capabilities": capabilities,
            "counters": counters,
            "blockers": blockers,
            "what_this_does_not_mean": [
                "that any digest was sent",
                "that any live source was called",
                "that any real tenant's digest was stored",
                "that production digest persistence is available",
            ],
        }
    )


def readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    """Refuse a readiness result that claims the lane without the evidence."""
    fails: list[str] = []

    if readiness.get("tenant_digest_persistence_live"):
        if readiness.get("blockers"):
            fails.append("live_alongside_blockers")
        for name in CONDITIONS:
            if not (readiness.get("conditions_met") or {}).get(name):
                fails.append(f"live_without:{name}")
        capabilities = readiness.get("capabilities") or {}
        for name in MUST_STAY_FALSE:
            if capabilities.get(name):
                fails.append(f"live_alongside:{name}")
        counters = readiness.get("counters") or {}
        for name, value in counters.items():
            if value:
                fails.append(f"live_after_contacting:{name}")

    if readiness.get("production_digest_persistence"):
        fails.append("production_digest_persistence_became_true")

    missing_conditions = set(CONDITIONS) - set(readiness.get("conditions") or [])
    if missing_conditions:
        fails.append(f"condition_list_lost_entries:{sorted(missing_conditions)}")

    return sorted(set(fails))
