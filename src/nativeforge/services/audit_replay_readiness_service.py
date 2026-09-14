"""Gate 152F: may `audit_replay_ready` be true, and on what evidence?

## Reporting a gap is a condition, not a failure

Six conditions, and the fourth is the one that distinguishes this lane from a
vanity check:

```text
legacy_gaps_reported     the 85 intents whose digest was never written are
                         counted and surfaced, NOT backfilled
```

A replay that quietly produced a digest for those intents would score better on
every other condition and be worthless. So "we know what we cannot prove" is
itself a condition, and a system that had silently filled the gaps would fail
this lane rather than pass it.

## Controlled dev/demo only

`production_audit_ready` has no branch that returns true. This lane means the
records this system wrote can be found, joined and checked against their own
hashes. It says nothing about legal standing, nothing about a real tenant, and
nothing about whether anybody read anything.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_audit_replay_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Every condition, each proved by something that happened.
CONDITIONS: tuple[str, ...] = (
    "tenant_digest_persistence_live",
    "digest_hash_verification_works",
    "delivery_intent_linkage_works",
    "legacy_gaps_reported",
    "evidence_ledger_generates",
    "cross_org_replay_refused",
)

#: Capabilities that must be false for this lane to mean what it says.
MUST_STAY_FALSE: tuple[str, ...] = (
    "email_delivery",
    "source_monitoring_live",
    "object_store_configured",
    "production_audit_ready",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "tenant_digest_persistence_live": (
        "Gate 151's lane; without a persisted digest there is nothing to replay"
    ),
    "digest_hash_verification_works": (
        "a stored payload hash equals one recomputed over the stored payload, "
        "and a tampered payload fails"
    ),
    "delivery_intent_linkage_works": (
        "an intent recorded with require_persisted_digest=True resolves to the "
        "digest record it names"
    ),
    "legacy_gaps_reported": (
        "the intents whose digest was never written are counted and surfaced "
        "as legacy_gap rather than backfilled. A replay that produced a digest "
        "for them would score better here and be worthless."
    ),
    "evidence_ledger_generates": (
        "one normalized entry per record, each carrying its status and what a "
        "replay still cannot say about it"
    ),
    "cross_org_replay_refused": (
        "a replay for another organization's record returns the same answer as "
        "one that does not exist"
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_audit_replay_readiness(
    *,
    tenant_digest_persistence_live: bool | None = None,
    digest_hash_verification_works: bool | None = None,
    delivery_intent_linkage_works: bool | None = None,
    legacy_gaps_reported: bool | None = None,
    evidence_ledger_generates: bool | None = None,
    cross_org_replay_refused: bool | None = None,
    legacy_gap_count: int | None = None,
    legacy_gaps_backfilled: bool | None = None,
    email_delivery: bool | None = None,
    source_monitoring_live: bool | None = None,
    object_store_configured: bool | None = None,
    live_source_calls: int | None = None,
    emails_sent: int | None = None,
    object_store_calls: int | None = None,
) -> dict[str, Any]:
    """Report the lane. `audit_replay_ready` is derived, never supplied."""
    measured = {
        "tenant_digest_persistence_live": bool(tenant_digest_persistence_live),
        "digest_hash_verification_works": bool(digest_hash_verification_works),
        "delivery_intent_linkage_works": bool(delivery_intent_linkage_works),
        "legacy_gaps_reported": bool(legacy_gaps_reported),
        "evidence_ledger_generates": bool(evidence_ledger_generates),
        "cross_org_replay_refused": bool(cross_org_replay_refused),
    }

    capabilities = {
        "email_delivery": bool(email_delivery),
        "source_monitoring_live": bool(source_monitoring_live),
        "object_store_configured": bool(object_store_configured),
        "production_audit_ready": False,
    }

    counters = {
        "live_source_calls": int(live_source_calls or 0),
        "emails_sent": int(emails_sent or 0),
        "object_store_calls": int(object_store_calls or 0),
    }

    missing = [name for name in CONDITIONS if not measured[name]]
    dishonest = [name for name in MUST_STAY_FALSE if capabilities.get(name)]
    contacted = [name for name, value in counters.items() if value]

    blockers = sorted(
        {
            *(f"condition_not_met:{name}" for name in missing),
            *(f"must_be_false_but_is_true:{name}" for name in dishonest),
            *(f"something_was_contacted:{name}" for name in contacted),
            # A backfill would clear the gaps and destroy the lane's meaning.
            *(["legacy_gaps_were_backfilled"] if legacy_gaps_backfilled else []),
        }
    )

    ready = not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived. Never supplied.
            "audit_replay_ready": ready,
            "production_audit_ready": False,
            "production_is_never_computed": True,
            "conditions": list(CONDITIONS),
            "conditions_met": measured,
            "conditions_missing": missing,
            "condition_evidence": dict(CONDITION_EVIDENCE),
            "capabilities": capabilities,
            "counters": counters,
            "legacy_gap_count": int(legacy_gap_count or 0),
            "legacy_gaps_backfilled": bool(legacy_gaps_backfilled),
            "reporting_a_gap_is_a_condition_not_a_failure": True,
            "blockers": blockers,
            "what_this_does_not_mean": [
                "that this would satisfy an auditor or a court",
                "that any digest was delivered",
                "that any tenant read anything",
                "that the legacy gaps were closed",
                "that any real tenant's evidence exists",
            ],
        }
    )


def readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    """Refuse a readiness result that claims the lane without the evidence."""
    fails: list[str] = []

    if readiness.get("audit_replay_ready"):
        if readiness.get("blockers"):
            fails.append("ready_alongside_blockers")
        for name in CONDITIONS:
            if not (readiness.get("conditions_met") or {}).get(name):
                fails.append(f"ready_without:{name}")
        capabilities = readiness.get("capabilities") or {}
        for name in MUST_STAY_FALSE:
            if capabilities.get(name):
                fails.append(f"ready_alongside:{name}")
        for name, value in (readiness.get("counters") or {}).items():
            if value:
                fails.append(f"ready_after_contacting:{name}")
        # The one that matters most: a lane that went green by hiding the gaps.
        if readiness.get("legacy_gaps_backfilled"):
            fails.append("ready_because_the_gaps_were_backfilled")

    if readiness.get("production_audit_ready"):
        fails.append("production_audit_ready_became_true")

    missing = set(CONDITIONS) - set(readiness.get("conditions") or [])
    if missing:
        fails.append(f"condition_list_lost_entries:{sorted(missing)}")

    return sorted(set(fails))
