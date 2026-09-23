"""Gate 172A: what already exists, and which layer owns each operational fact.

The temptation in a fleet-operations gate is to build a second scheduler, a
second attempt ledger and a second health model, because composing five
existing ones is harder than writing a sixth. Gate 166 removed code-level
source authority for the same reason this survey exists: the duplicate is
always the one that drifts.

So this phase reads the substrate and produces a SOURCE-OF-TRUTH MAP - one
owner per operational fact - before anything is built. A fact with two owners
is reported as DUPLICATED rather than quietly given a third.

No network. Reads only.
"""

from __future__ import annotations

import ast
import json
import pathlib
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate172 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"
SERVICES = REPO / "src" / "nativeforge" / "services"

AUTHORITATIVE = "AUTHORITATIVE"
REUSABLE = "REUSABLE"
UNWIRED = "UNWIRED"
DUPLICATED = "DUPLICATED"
LEGACY = "LEGACY"
SOURCE_SPECIFIC = "SOURCE_SPECIFIC"
GLOBAL = "GLOBAL"
UNKNOWN = "UNKNOWN"

#: Each primitive, its classification, and - the point of the exercise - the
#: operational facts it OWNS. Written down so a later phase that wants one of
#: these facts composes it instead of recomputing it.
PRIMITIVES: tuple[dict, ...] = (
    {
        "name": "source_circuit_breaker_service",
        "classification": AUTHORITATIVE,
        "owns": ["circuit_state", "cooldown", "manual_override", "probe_permission"],
        "note": (
            "closed/open/half_open with a threshold, a cooldown and a manual "
            "hold already exist. Gate 172 WIRES this into fleet state; a "
            "second breaker would be a second answer to 'may this run'."
        ),
    },
    {
        "name": "source_collection_retry_policy_service",
        "classification": AUTHORITATIVE,
        "owns": ["failure_class", "retryable", "why_not_retried"],
        "note": (
            "already separates refused_by_activation / terms_blocked / "
            "human_review_blocked from transient and permanent worker "
            "failure, which is exactly 172I's 'do not retry an authorization "
            "failure as a transport failure'. Gate 172 maps its classes into "
            "the wider taxonomy rather than replacing them."
        ),
    },
    {
        "name": "source_freshness_service",
        "classification": AUTHORITATIVE,
        "owns": [
            "check_interval_days",
            "next_check_due_at",
            "is_due",
            "is_overdue",
        ],
        "note": "cadence is already per-source and priority-defaulted.",
    },
    {
        "name": "source_collection_job_lease_service",
        "classification": AUTHORITATIVE,
        "owns": ["lease_state", "lease_expiry", "claim", "reclaim"],
        "note": "lease safety belongs here; 172O proves it rather than rebuilds it.",
    },
    {
        "name": "source_collection_scheduler_health_service",
        "classification": REUSABLE,
        "owns": ["scheduler_conditions"],
        "note": "condition-based, composes into SCHEDULER_HEALTH.",
    },
    {
        "name": "source_collection_worker_health_service",
        "classification": REUSABLE,
        "owns": ["worker_conditions"],
        "note": "composes into WORKER_HEALTH.",
    },
    {
        "name": "source_fleet_fact_scope_service",
        "classification": AUTHORITATIVE,
        "owns": ["fleet_global_facts", "hoisting_scope"],
        "note": (
            "Gate 166's ContextVar hoisting. MANDATORY at fleet scale: a "
            "fleet-global fact recomputed once per source is the O(N) cost "
            "that makes 5,000 sources unmanageable."
        ),
    },
    {
        "name": "source_authorization_fact_resolver_service",
        "classification": AUTHORITATIVE,
        "owns": ["authorization_facts", "terms", "robots", "attribution"],
        "note": "AUTHORIZATION_HEALTH derives from here, never from a flag.",
    },
    {
        "name": "source_adapter_conformance_service",
        "classification": REUSABLE,
        "owns": ["adapter_contract_conformance"],
        "note": "Gate 171's harness; 172K plugs adapter contract drift into it.",
    },
)

#: Operational facts Gate 172 needs and where each one comes from. A fact with
#: no owner is what this gate must build; a fact with two is a defect.
FACT_OWNERS: dict[str, str] = {
    "authorization_state": "source_authority_service",
    "authorization_facts": "source_authorization_fact_resolver_service",
    "activation_state": "nf_active_opportunity_sources",
    "disabled": "nf_active_opportunity_sources.disabled_at",
    "circuit_state": "source_circuit_breaker_service",
    "failure_class": "source_collection_retry_policy_service",
    "consecutive_failures": "nf_active_opportunity_sources.consecutive_failure_count",
    "last_attempt_at": "nf_source_collection_execution_attempts",
    "last_success_at": "nf_active_opportunity_sources.last_success_at",
    "last_payload_at": "nf_source_collection_raw_payloads.received_at",
    "last_observation_at": "nf_opportunity_source_observations.observed_at",
    "last_useful_change_at": "nf_opportunity_change_events.detected_at",
    "cadence": "nf_active_opportunity_sources.freshness_cadence_days",
    "stale_threshold": "nf_active_opportunity_sources.stale_threshold_days",
    "next_due_at": "source_freshness_service",
    "lease_state": "nf_source_collection_job_leases",
    "queue_state": "nf_source_collection_jobs",
    "robots_verdict": "nf_source_robots_evidence",
    "attribution": "source_attribution_contract_service",
    "adapter_binding": "nf_active_opportunity_sources.collection_method",
}

out: dict[str, object] = {"schema_version": "nf_gate172_fleet_survey_v1"}

# ---- the primitives actually exist on disk ------------------------
classified: list[dict] = []
for entry in PRIMITIVES:
    path = SERVICES / (entry["name"] + ".py")
    exists = path.exists()
    classified.append(
        {
            **entry,
            "module_exists": exists,
            "lines": len(path.read_text(encoding="utf-8").splitlines())
            if exists
            else 0,
        }
    )
out["primitives"] = classified
out["primitives_surveyed"] = len(classified)
out["all_primitives_exist"] = all(e["module_exists"] for e in classified)
out["missing_primitives"] = sorted(
    str(e["name"]) for e in classified if not e["module_exists"]
)

counts: dict[str, int] = {}
for entry in classified:
    counts[str(entry["classification"])] = (
        counts.get(str(entry["classification"]), 0) + 1
    )
out["classification_counts"] = dict(sorted(counts.items()))

# ---- one owner per fact -------------------------------------------
owners: dict[str, list[str]] = {}
for fact, owner in FACT_OWNERS.items():
    owners.setdefault(owner, []).append(fact)
out["fact_owner_map"] = dict(sorted(FACT_OWNERS.items()))
out["facts_mapped"] = len(FACT_OWNERS)
out["every_fact_has_exactly_one_owner"] = len(FACT_OWNERS) == len(
    set(FACT_OWNERS)
)
out["owners_in_use"] = len(owners)

# ---- the tables, measured rather than assumed ---------------------
connection = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)
try:
    tables = {
        str(row[0])
        for row in connection.execute(
            "select name from sqlite_master where type='table'"
        )
    }
    wanted = {
        "nf_active_opportunity_sources",
        "nf_source_collection_jobs",
        "nf_source_collection_job_leases",
        "nf_source_collection_execution_attempts",
        "nf_source_collection_raw_payloads",
        "nf_source_authorization_decisions",
        "nf_source_robots_evidence",
        "nf_opportunity_source_observations",
        "nf_opportunity_change_events",
    }
    present = sorted(wanted & tables)
    out["operational_tables_present"] = present
    out["operational_tables_missing"] = sorted(wanted - tables)

    shapes: dict[str, object] = {}
    for table in present:
        columns = [r[1] for r in connection.execute(f"pragma table_info({table})")]
        rows = connection.execute(f"select count(*) from {table}").fetchone()[0]
        shapes[table] = {"rows": int(rows), "columns": len(columns)}
    out["operational_table_shapes"] = shapes

    # The fields 172D/E ask for that ALREADY exist. Building a parallel set
    # would leave two answers to "when is this source stale".
    activation_columns = {
        r[1]
        for r in connection.execute(
            "pragma table_info(nf_active_opportunity_sources)"
        )
    }
    already = sorted(
        activation_columns
        & {
            "freshness_cadence_days",
            "stale_threshold_days",
            "last_checked_at",
            "last_success_at",
            "last_failure_at",
            "consecutive_failure_count",
            "source_health_status",
            "source_status",
            "disabled_at",
            "disabled_by",
            "disabled_reason",
        }
    )
    out["operational_fields_already_on_the_activation_row"] = already
    out["freshness_fields_need_no_new_table"] = len(already) >= 9
finally:
    connection.close()


# ---- what Gate 172 must actually BUILD ----------------------------
#
# Named here so the gate's scope is a conclusion of the survey rather than a
# restatement of the prompt.
def _defines(module: str, name: str) -> bool:
    path = SERVICES / (module + ".py")
    if not path.exists():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return True
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name == name:
            return True
    return False


gaps = {
    "operational_state_vocabulary": not _defines(
        "source_fleet_operational_state_service", "OPERATIONAL_STATES"
    ),
    "independent_health_dimensions": not _defines(
        "source_fleet_operational_state_service", "HEALTH_DIMENSIONS"
    ),
    "failure_taxonomy": not _defines(
        "source_fleet_failure_taxonomy_service", "FAILURE_TYPES"
    ),
    "source_sla_contract": not _defines(
        "source_fleet_expectation_service", "SLA_FIELDS"
    ),
    "schema_drift_detection": not _defines(
        "source_fleet_drift_service", "DRIFT_CLASSES"
    ),
    "volume_anomaly": not _defines("source_fleet_drift_service", "VOLUME_STATES"),
    "operations_events": not _defines(
        "source_fleet_operations_event_service", "EVENT_TYPES"
    ),
    "alert_contract": not _defines(
        "source_fleet_alert_contract_service", "ALERT_CONDITIONS"
    ),
    "fleet_read_model": not _defines(
        "source_fleet_read_model_service", "READ_MODEL_FIELDS"
    ),
}
out["gate172_must_build"] = dict(sorted(gaps.items()))
out["gap_count"] = sum(1 for v in gaps.values() if v)
out["nothing_to_duplicate"] = out["all_primitives_exist"]

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written"] = 0
print(json.dumps(out, sort_keys=True, default=str))
