"""Gate 153F: may `operational_backup_restore_ready` be true, on what evidence?

## Why this module is not called `backup_restore_readiness_service`

Because that name is taken, by Gate 65, for the PRODUCTION lane - and the first
draft of this gate overwrote it. Same filename, same `SCHEMA_VERSION`, same
`build_backup_restore_readiness` function name. The two modules answer opposite
questions and one of them was silently gone.

That is the same confusion this gate exists to prevent, committed in the
filesystem rather than in prose, so the names are now distinct on purpose.

## The name this lane must not be confused with

```text
operational_backup_restore_ready
    this system can export its own controlled dev/demo operational state,
    load it into an isolated database, and still pass the Gate 152 replay

production_backup_ready     a managed instance, backup automation, PITR, and an
                            executed provider restore. None of those exist, and
                            nothing here computes this - it is a constant false.
```

`scripts/verify_nativeforge_backup_restore.sh` measures the second and returns
SKIP. It still does. This lane cannot make it pass and does not report on it.

## Refusing is a condition

Two of the eight conditions are refusals rather than capabilities:

```text
restore_into_source_refused   a restore whose target is the source is blocked
restore_into_live_refused     a target not declared isolated is blocked
```

Gate 134F's lesson was that a permitted branch nobody can reach makes a refusal
unfalsifiable. Both of these are reached by the verifier and by a test, which
run the refused call and assert the block, so the refusal is measured rather
than asserted.

## A preserved gap is a condition too

`legacy_gaps_preserved` fails if a restore reduced the legacy gap count. A
restore that invented a digest for an intent that never had one would score
better on the replay and be worthless, exactly as in Gate 152.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_operational_backup_restore_readiness_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Every condition, each proved by something that ran.
CONDITIONS: tuple[str, ...] = (
    "manifest_classified_by_meaning",
    "export_scoped_to_one_organization",
    "export_carries_a_hash_per_table",
    "restore_into_isolated_target_works",
    "restore_into_source_refused",
    "restore_into_live_refused",
    "restored_state_passes_the_gate_152_replay",
    "legacy_gaps_preserved",
)

#: Capabilities that must be false for this lane to mean what it says.
MUST_STAY_FALSE: tuple[str, ...] = (
    "email_delivery",
    "source_monitoring_live",
    "object_store_configured",
    "customer_data_backed_up",
    "production_backup_ready",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "manifest_classified_by_meaning": (
        "every included and excluded table carries a reason a person wrote. "
        "A name-matching pass flagged nf_org_memberships because a column is "
        "called `state` and that column holds 'active', so the name matcher "
        "survives only as a review hint."
    ),
    "export_scoped_to_one_organization": (
        "every manifest table is partitioned by organization_id, the real "
        "organization is refused by name, and a non-fixture row is counted "
        "rather than silently dropped"
    ),
    "export_carries_a_hash_per_table": (
        "a sha256 over the sorted serialised rows, so a restore can tell "
        "whether it received what was sent and row order cannot change it"
    ),
    "restore_into_isolated_target_works": (
        "the export loads into a freshly migrated temporary database and the "
        "row counts and per-table hashes come back equal"
    ),
    "restore_into_source_refused": (
        "a restore whose target URL equals the source URL is blocked before a "
        "row is written. The verifier runs this call and asserts the block."
    ),
    "restore_into_live_refused": (
        "a target not declared an isolated temporary database is blocked. The "
        "verifier runs this call too, so neither refusal is unfalsifiable."
    ),
    "restored_state_passes_the_gate_152_replay": (
        "audit_replay_service and evidence_ledger_service, unmodified, answer "
        "identically against the restored database and the source"
    ),
    "legacy_gaps_preserved": (
        "the legacy gap count is identical after a restore. A restore that "
        "reduced it would have invented a digest."
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_operational_restore_readiness(
    *,
    manifest_classified_by_meaning: bool | None = None,
    export_scoped_to_one_organization: bool | None = None,
    export_carries_a_hash_per_table: bool | None = None,
    restore_into_isolated_target_works: bool | None = None,
    restore_into_source_refused: bool | None = None,
    restore_into_live_refused: bool | None = None,
    restored_state_passes_the_gate_152_replay: bool | None = None,
    legacy_gaps_preserved: bool | None = None,
    source_legacy_gap_count: int | None = None,
    restored_legacy_gap_count: int | None = None,
    exported_row_count: int | None = None,
    restored_row_count: int | None = None,
    email_delivery: bool | None = None,
    source_monitoring_live: bool | None = None,
    object_store_configured: bool | None = None,
    customer_data_backed_up: bool | None = None,
    live_source_calls: int | None = None,
    emails_sent: int | None = None,
    object_store_calls: int | None = None,
    real_organization_rows_touched: int | None = None,
) -> dict[str, Any]:
    """Report the lane. The verdict is derived, never supplied."""
    measured = {
        "manifest_classified_by_meaning": bool(manifest_classified_by_meaning),
        "export_scoped_to_one_organization": bool(export_scoped_to_one_organization),
        "export_carries_a_hash_per_table": bool(export_carries_a_hash_per_table),
        "restore_into_isolated_target_works": bool(restore_into_isolated_target_works),
        "restore_into_source_refused": bool(restore_into_source_refused),
        "restore_into_live_refused": bool(restore_into_live_refused),
        "restored_state_passes_the_gate_152_replay": bool(
            restored_state_passes_the_gate_152_replay
        ),
        "legacy_gaps_preserved": bool(legacy_gaps_preserved),
    }

    capabilities = {
        "email_delivery": bool(email_delivery),
        "source_monitoring_live": bool(source_monitoring_live),
        "object_store_configured": bool(object_store_configured),
        "customer_data_backed_up": bool(customer_data_backed_up),
        # Constant. No branch computes it, because none of its prerequisites
        # exist: no managed instance, no automation, no PITR, no executed
        # provider restore.
        "production_backup_ready": False,
    }

    counters = {
        "live_source_calls": int(live_source_calls or 0),
        "emails_sent": int(emails_sent or 0),
        "object_store_calls": int(object_store_calls or 0),
        "real_organization_rows_touched": int(real_organization_rows_touched or 0),
    }

    source_gaps = int(source_legacy_gap_count or 0)
    restored_gaps = int(restored_legacy_gap_count or 0)

    missing = [name for name in CONDITIONS if not measured[name]]
    dishonest = [name for name in MUST_STAY_FALSE if capabilities.get(name)]
    contacted = [name for name, value in counters.items() if value]

    blockers = sorted(
        {
            *(f"condition_not_met:{name}" for name in missing),
            *(f"must_be_false_but_is_true:{name}" for name in dishonest),
            *(f"something_was_contacted:{name}" for name in contacted),
            # A restore that closed a gap invented a digest for it.
            *(
                ["legacy_gap_count_fell_across_the_restore"]
                if restored_gaps < source_gaps
                else []
            ),
        }
    )

    ready = not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived. Never supplied.
            "operational_backup_restore_ready": ready,
            "production_backup_ready": False,
            "production_is_never_computed": True,
            "production_backup_is_a_different_harness": (
                "scripts/verify_nativeforge_backup_restore.sh, which needs a "
                "managed instance and returns SKIP until one exists. This lane "
                "cannot make it pass and does not report on it."
            ),
            "conditions": list(CONDITIONS),
            "conditions_met": measured,
            "conditions_missing": missing,
            "condition_evidence": dict(CONDITION_EVIDENCE),
            "capabilities": capabilities,
            "counters": counters,
            "source_legacy_gap_count": source_gaps,
            "restored_legacy_gap_count": restored_gaps,
            "exported_row_count": int(exported_row_count or 0),
            "restored_row_count": int(restored_row_count or 0),
            "preserving_a_gap_is_a_condition_not_a_failure": True,
            "blockers": blockers,
            "remaining_blockers_for_production_backup": [
                "a managed database instance (procurement, not engineering)",
                "backup automation, which needs the instance first",
                "point-in-time recovery, which needs a provider that has it",
                "an executed provider restore, which needs all three",
            ],
            "what_this_does_not_mean": [
                "that production is backed up",
                "that any customer data was backed up; none exists",
                "that object storage was backed up; none is configured",
                "that an RPO or RTO is enforced by anything",
                "that a real organization was exported, restored or touched",
            ],
        }
    )


def operational_restore_readiness_invariant_failures(
    readiness: dict[str, Any],
) -> list[str]:
    """Refuse a readiness result that claims the lane without the evidence."""
    fails: list[str] = []

    if readiness.get("operational_backup_restore_ready"):
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
        if int(readiness.get("restored_legacy_gap_count") or 0) < int(
            readiness.get("source_legacy_gap_count") or 0
        ):
            fails.append("ready_while_the_legacy_gap_count_fell")

    if readiness.get("production_backup_ready"):
        fails.append("production_backup_ready_became_true")

    missing = set(CONDITIONS) - set(readiness.get("conditions") or [])
    if missing:
        fails.append(f"condition_list_lost_entries:{sorted(missing)}")

    return sorted(set(fails))
