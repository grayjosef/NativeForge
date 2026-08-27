"""Source scheduler readiness artifacts (Gate 98G).

Writes five files to `artifacts/source_scheduler_readiness/`, describing what a
scheduler would consult and what is missing before one could run.

## Every file states the same four facts

An artifact gets copied out of its directory, pasted into a deck, and read six
months later by somebody who was not here. So each file carries the declarations
on its own rather than relying on a neighbouring README:

```text
scheduler_runtime_available   false
background_worker_available   false
source_monitoring_live        false
ready_to_start_monitoring     false
```

The CSV stamps them on every *row*, because a row is the unit that gets copied.

## The writer refuses rather than annotates

`artifact_claim_failures` checks the bundle before anything is written, and
`write_scheduler_readiness_artifacts` raises instead of writing a file whose
declarations disagree with the detection behind them. An artifact that says
"monitoring is not live" beside a bundle that detected a running scheduler is
worse than no artifact, because it would be believed.

## No payloads, no bodies, no secrets

These describe contracts and detection results. Gate 95's payload store root is
gitignored for a reason; nothing here touches it, and the check-run contract
contributes only its *shape*, never a record with an error message in it.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.source_check_run_contract_service import (
    CONTRACT_FIELDS,
    PROHIBITED_FIELD_NAMES,
    contract_shape,
)
from nativeforge.services.source_circuit_breaker_service import (
    CIRCUIT_STATUSES,
    DEFAULT_BREAKER_THRESHOLD,
    DEFAULT_COOLDOWN_SECONDS,
    MANUAL_OVERRIDE_STATUSES,
    SCHEDULING_PERMITTED_STATUSES,
    SINGLE_PROBE_STATUSES,
    evaluate_circuit,
)
from nativeforge.services.source_schedule_decision_service import (
    ENQUEUE_PERMITTED_STATUSES,
    REQUIREMENT_KEYS,
    SCHEDULE_STATUSES,
    evaluate_schedule,
    schedule_invariant_failures,
)
from nativeforge.services.source_scheduler_readiness_service import (
    COMPONENT_KEYS,
    RUNTIME_COMPONENT_KEYS,
    build_scheduler_readiness,
    scheduler_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_source_scheduler_readiness_artifact_v1"

ARTIFACT_DIR = "artifacts/source_scheduler_readiness"

READINESS_JSON_NAME = "scheduler_readiness.json"
COMPONENTS_CSV_NAME = "scheduler_readiness_components.csv"
BREAKER_JSON_NAME = "circuit_breaker_states.json"
CHECK_RUN_JSON_NAME = "source_check_run_contract.json"
SUMMARY_NAME = "scheduler_readiness_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    READINESS_JSON_NAME,
    COMPONENTS_CSV_NAME,
    BREAKER_JSON_NAME,
    CHECK_RUN_JSON_NAME,
    SUMMARY_NAME,
)

# The facts every file states, in this order.
#
# Gate 99D added `runtime_mode`. It has to travel with
# `scheduler_runtime_available`, which is now true: that line read on its own -
# in a copied CSV row, on a status page - would be taken for a production
# scheduler, and the mode is the only thing that says otherwise.
DECLARATION_KEYS: tuple[str, ...] = (
    "runtime_mode",
    "scheduler_runtime_available",
    "background_worker_available",
    "source_monitoring_live",
    "ready_to_start_monitoring",
)

# The declarations that are booleans and must be False. `runtime_mode` is a
# string and `scheduler_runtime_available` is legitimately True from Gate 99
# onward, so neither belongs in a "must be false" check.
FALSE_DECLARATION_KEYS: tuple[str, ...] = (
    "background_worker_available",
    "source_monitoring_live",
    "ready_to_start_monitoring",
)

COMPONENT_CSV_COLUMNS: tuple[str, ...] = (
    "component",
    "available",
    "kind",
    "detection_method",
    *DECLARATION_KEYS,
)

# A fixed clock. These artifacts must regenerate byte-identically, and a real
# `now` would change the cooldown arithmetic on every run.
_REFERENCE_NOW = "2026-01-01T12:00:00+00:00"
_RECENT_FAILURE = "2026-01-01T11:45:00+00:00"
_OLD_FAILURE = "2026-01-01T10:00:00+00:00"


class SchedulerReadinessArtifactError(RuntimeError):
    """Raised rather than write an artifact whose declarations are wrong."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rows_to_csv(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buffer.getvalue()


def build_breaker_state_table() -> dict[str, Any]:
    """Every circuit state, with a worked example reaching it."""
    threshold = DEFAULT_BREAKER_THRESHOLD
    scenarios = (
        ("closed", dict(consecutive_failure_count=0)),
        (
            "closed_below_threshold",
            dict(consecutive_failure_count=threshold - 1),
        ),
        (
            "open_cooldown_running",
            dict(
                consecutive_failure_count=threshold,
                last_failure_at=_RECENT_FAILURE,
            ),
        ),
        (
            "half_open_cooldown_elapsed",
            dict(
                consecutive_failure_count=threshold,
                last_failure_at=_OLD_FAILURE,
            ),
        ),
        (
            "open_cooldown_not_derivable",
            dict(consecutive_failure_count=threshold),
        ),
        (
            "manual_hold",
            dict(consecutive_failure_count=0, manual_override_status="hold"),
        ),
        (
            "unknown_failure_count_absent",
            dict(),
        ),
        (
            "unknown_override_unrecognised",
            dict(
                consecutive_failure_count=0,
                manual_override_status="something_nobody_defined",
            ),
        ),
    )

    rows = []
    for name, kwargs in scenarios:
        result = evaluate_circuit(
            source_id="example_source", now=_REFERENCE_NOW, **kwargs
        )
        rows.append(
            {
                "scenario": name,
                "circuit_status": result["circuit_status"],
                "permits_scheduling": result["permits_scheduling"],
                "single_probe_only": result["single_probe_only"],
                "blocked_reasons": result["blocked_reasons"],
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "circuit_statuses": sorted(CIRCUIT_STATUSES),
            "scheduling_permitted_statuses": sorted(SCHEDULING_PERMITTED_STATUSES),
            "single_probe_statuses": sorted(SINGLE_PROBE_STATUSES),
            "manual_override_statuses": sorted(MANUAL_OVERRIDE_STATUSES),
            "breaker_threshold": threshold,
            "cooldown_seconds": DEFAULT_COOLDOWN_SECONDS,
            "reference_now": _REFERENCE_NOW,
            "scenarios": rows,
            "probe_performed": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def build_schedule_decision_table() -> dict[str, Any]:
    """Every schedule status, with a worked example reaching it."""
    cleared = dict(
        next_check_due_at=_OLD_FAILURE,
        collector_status="active",
        activation_status="activation_allowed",
        monitoring_status="enabled",
        terms_status="NO_REVIEW_REQUIRED",
        human_review_status="not_required",
        circuit_status="closed",
        production_raw_payload_store_available=True,
    )
    scenarios = (
        ("nothing_supplied", {}),
        ("due_and_cleared", cleared),
        ("not_yet_due", {**cleared, "next_check_due_at": "2026-06-01T00:00:00+00:00"}),
        ("no_schedule_recorded", {**cleared, "next_check_due_at": None}),
        ("monitoring_disabled", {**cleared, "monitoring_status": "disabled"}),
        ("terms_review_required", {**cleared, "terms_status": "TERMS_REVIEW_REQUIRED"}),
        ("human_review_only", {**cleared, "terms_status": "HUMAN_REVIEW_ONLY"}),
        ("circuit_open", {**cleared, "circuit_status": "open"}),
        (
            "no_production_payload_store",
            {**cleared, "production_raw_payload_store_available": False},
        ),
    )

    rows = []
    for name, kwargs in scenarios:
        decision = evaluate_schedule(
            source_id="example_source", now=_REFERENCE_NOW, **kwargs
        )
        rows.append(
            {
                "scenario": name,
                "schedule_status": decision["schedule_status"],
                "due_for_check": decision["due_for_check"],
                "safe_to_enqueue": decision["safe_to_enqueue"],
                "safe_to_execute_now": decision["safe_to_execute_now"],
                "blocked_reasons": decision["blocked_reasons"],
                "invariant_failures": schedule_invariant_failures(decision),
            }
        )

    return _json_safe(
        {
            "schedule_statuses": sorted(SCHEDULE_STATUSES),
            "enqueue_permitted_statuses": sorted(ENQUEUE_PERMITTED_STATUSES),
            "requirement_keys": list(REQUIREMENT_KEYS),
            "reference_now": _REFERENCE_NOW,
            "scenarios": rows,
        }
    )


def build_readiness_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the five artifacts are rendered from."""
    readiness = build_scheduler_readiness(repo_root=repo_root)

    declarations = {key: readiness[key] for key in DECLARATION_KEYS}

    component_rows = []
    for key in COMPONENT_KEYS:
        record = readiness["components"][key]
        component_rows.append(
            {
                "component": key,
                "available": record["available"],
                # `dry_run_runtime` is a runtime in the narrow sense that code
                # runs, and Gate 99 labels it as one here so a reader is not
                # left wondering why a contract made `runtime_mode` move.
                "kind": "runtime"
                if key in RUNTIME_COMPONENT_KEYS | {"dry_run_runtime"}
                else "contract",
                "detection_method": record["detection_method"],
                **declarations,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "readiness": readiness,
            "declarations": declarations,
            "components": component_rows,
            "breaker": build_breaker_state_table(),
            "schedule": build_schedule_decision_table(),
            "check_run_contract": contract_shape(),
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    """Reasons to refuse to write. Empty means the bundle may be rendered."""
    fails: list[str] = []

    readiness = bundle.get("readiness") or {}
    fails.extend(scheduler_readiness_invariant_failures(readiness))

    declarations = bundle.get("declarations") or {}
    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
        elif declarations[key] != readiness.get(key):
            fails.append(f"declaration_disagrees_with_detection:{key}")

    # Each component row must match the detection it summarises.
    for row in bundle.get("components") or []:
        key = row.get("component")
        record = (readiness.get("components") or {}).get(key)
        if not isinstance(record, dict):
            fails.append(f"component_row_without_detection:{key}")
            continue
        if bool(row.get("available")) != bool(record.get("available")):
            fails.append(f"component_row_disagrees_with_detection:{key}")

    # Every decision scenario must satisfy its own invariants.
    for row in (bundle.get("schedule") or {}).get("scenarios") or []:
        if row.get("invariant_failures"):
            fails.append(f"schedule_scenario_violates_invariants:{row.get('scenario')}")
        if row.get("safe_to_execute_now"):
            fails.append(f"schedule_scenario_claimed_execution:{row.get('scenario')}")

    # No worked breaker example may report a probe.
    breaker = bundle.get("breaker") or {}
    for constant in ("probe_performed", "fetch_performed"):
        if breaker.get(constant) is not False:
            fails.append(f"breaker_table_claimed:{constant}")

    # The check-run contract must still forbid bodies.
    contract = bundle.get("check_run_contract") or {}
    if contract.get("response_body_stored") is not False:
        fails.append("check_run_contract_stores_a_response_body")
    if contract.get("payload_reference_style") != "id_only":
        fails.append("check_run_contract_references_payloads_by_content")
    for name in CONTRACT_FIELDS:
        if name in PROHIBITED_FIELD_NAMES:
            fails.append(f"contract_field_is_prohibited:{name}")

    # The summary must state every declaration in words.
    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")

    return sorted(set(fails))


def render_readiness_summary(bundle: dict[str, Any]) -> str:
    readiness = bundle["readiness"]
    declarations = bundle["declarations"]

    lines: list[str] = []
    lines.append("# Source scheduler readiness")
    lines.append("")
    lines.append(
        "Generated by `source_scheduler_readiness_artifact_service`. Every value "
        "below is detected by importing or inspecting the thing itself, not read "
        "from a declaration."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        value = declarations[key]
        # `runtime_mode` is a string. Coercing it through bool() would print
        # "true" for every mode including `none`, which is exactly the kind of
        # collapse this whole block exists to prevent.
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key:<32}{rendered}")
    lines.append("```")
    lines.append("")
    lines.append(
        "`scheduler_runtime_available` is true because `runtime_mode` is "
        f"`{readiness['runtime_mode']}` - an in-process queue builder that "
        "executes nothing. It is not a background worker, and it is not "
        "monitoring. `scheduler_package_installed` is "
        f"{str(readiness['scheduler_package_installed']).lower()}."
    )
    lines.append("")
    lines.append("## Components")
    lines.append("")
    lines.append("| Component | Kind | Present | Detected by |")
    lines.append("| --- | --- | --- | --- |")
    for row in bundle["components"]:
        present = "yes" if row["available"] else "no"
        lines.append(
            f"| `{row['component']}` | {row['kind']} | {present} | "
            f"{row['detection_method']} |"
        )
    lines.append("")

    missing = readiness["components_missing"]
    lines.append("## What is missing")
    lines.append("")
    if missing:
        for key in missing:
            lines.append(f"- `{key}`")
    else:
        lines.append("- nothing")
    lines.append("")
    lines.append(
        "The decision layer is present and the runtime is not. Having the "
        "services a scheduler would consult is not having a scheduler, in the "
        "same way that Gate 95's payload contract was not a payload store."
    )
    lines.append("")
    lines.append("## Circuit breaker")
    lines.append("")
    breaker = bundle["breaker"]
    lines.append(
        f"Threshold {breaker['breaker_threshold']} consecutive failures, "
        f"cooldown {breaker['cooldown_seconds']}s. A cooldown that elapses "
        "produces `half_open`, which permits one probe - not a resumption at "
        "full rate."
    )
    lines.append("")
    lines.append("| Scenario | Status | Permits scheduling |")
    lines.append("| --- | --- | --- |")
    for row in breaker["scenarios"]:
        permits = "yes" if row["permits_scheduling"] else "no"
        lines.append(
            f"| {row['scenario']} | `{row['circuit_status']}` | {permits} |"
        )
    lines.append("")
    lines.append("## Schedule decisions")
    lines.append("")
    lines.append("| Scenario | Status | Due | Safe to enqueue |")
    lines.append("| --- | --- | --- | --- |")
    for row in bundle["schedule"]["scenarios"]:
        due = "yes" if row["due_for_check"] else "no"
        enq = "yes" if row["safe_to_enqueue"] else "no"
        lines.append(
            f"| {row['scenario']} | `{row['schedule_status']}` | {due} | {enq} |"
        )
    lines.append("")
    lines.append(
        "`safe_to_execute_now` is false on every decision in this gate: nothing "
        "executes, so nothing may report that executing is safe."
    )
    lines.append("")
    lines.append("## Check-run contract")
    lines.append("")
    contract = bundle["check_run_contract"]
    lines.append(
        f"{len(contract['contract_fields'])} fields for `{contract['table']}`. "
        "Payloads are referenced by id, never by content, and the error message "
        f"is redacted to `{contract['redaction_placeholder']}` on the way in "
        "rather than trusted to have been redacted already."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_scheduler_readiness_artifacts(
    *,
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all five files, or refuse and write none."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    bundle = build_readiness_bundle(repo_root=root)
    summary_text = render_readiness_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise SchedulerReadinessArtifactError(
            "refusing to write scheduler readiness artifacts: "
            + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]

    (out_dir / READINESS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "readiness": bundle["readiness"],
                "schedule": bundle["schedule"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / COMPONENTS_CSV_NAME).write_text(
        _rows_to_csv(bundle["components"], COMPONENT_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / BREAKER_JSON_NAME).write_text(
        json.dumps(
            {**declarations, **bundle["breaker"]}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / CHECK_RUN_JSON_NAME).write_text(
        json.dumps(
            {**declarations, **bundle["check_run_contract"]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "components_missing": bundle["readiness"]["components_missing"],
            "live_fetch_performed": False,
            "collectors_active": False,
            "live_source_coverage": False,
            "claim_failures": [],
            "fabricated": False,
        }
    )
