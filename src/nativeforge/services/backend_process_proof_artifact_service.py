"""Backend process proof artifacts (Gate 102F).

Writes five files to `artifacts/backend_process_proof/`: the proof contract, the
lifespan hook contract, the install plan, and what this gate did to the host.

## Repository scope, not host scope

The single decision shaping these files: **a running process is not a property of
this repository.** It is a property of one machine at one moment, and it stops
being true when the service stops.

Committed artifacts are compared against a fresh generation by test, so anything
host-specific in them fails that comparison on any other machine — and on this
one, minutes later. So:

```text
recorded here          the contract, the plan, what this gate did
NOT recorded here      pid, observed_at, proof_id, live healthcheck result
```

`persistent_backend_live` in these files is therefore **false**, and it means
exactly one thing: *the committed contract carries no process proof.* A real
proof was captured during the run and appears in the gate report. Both facts are
true; they are answers to different questions, and `process_proof_captured_
during_run` sits beside the flag so neither can be read as the other.

## What this gate did to the host is a constant, not a detection

`installed_by_this_gate` and `enabled_by_this_gate` are module constants set from
what the run actually did after operator approval. They do not inspect systemd —
inspecting it would make them vary — and they stay true afterwards in the way a
changelog entry stays true. The operator approved *install and start, not enable*,
so the second is false and a test asserts the unit is in no `WantedBy` target.

## Eight declarations, on every file and every CSV row

```text
backend_unit_template_available  true
lifespan_hook_available          true
installed_by_this_gate           true   (operator-approved during the run)
enabled_by_this_gate             false  (operator declined enable)
persistent_backend_live          false  (no proof in the committed contract)
collectors_started               false
urls_fetched                     false
source_monitoring_live           false
live_source_coverage             false
```
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.backend_lifespan_hook_service import (
    ATTACH_PREREQUISITES,
    SCHEDULER_ATTACH_POINT,
    build_lifespan_hook_contract,
    lifespan_invariant_failures,
)
from nativeforge.services.backend_process_proof_service import (
    DEFAULT_UNIT_NAME,
    HEALTHCHECK_STATUSES,
    PROOF_FIELDS,
    PROOF_REQUIREMENT_KEYS,
    build_process_proof,
    proof_invariant_failures,
)
from nativeforge.services.backend_runtime_contract_service import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HEALTHCHECK_PATH,
    READINESS_PATH,
    SYSTEMD_UNIT_RELATIVE_PATH,
    backend_runtime_invariant_failures,
    build_backend_runtime_contract,
    detect_systemd_unit_template,
)

SCHEMA_VERSION = "nf_backend_process_proof_artifact_v1"

ARTIFACT_DIR = "artifacts/backend_process_proof"

PROOF_JSON_NAME = "backend_process_proof_readiness.json"
PROOF_CSV_NAME = "backend_process_proof_readiness.csv"
LIFESPAN_JSON_NAME = "backend_lifespan_hook_contract.json"
INSTALL_PLAN_NAME = "backend_unit_install_plan.md"
SUMMARY_NAME = "backend_process_proof_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    PROOF_JSON_NAME,
    PROOF_CSV_NAME,
    LIFESPAN_JSON_NAME,
    INSTALL_PLAN_NAME,
    SUMMARY_NAME,
)

# What this gate did to the host, after the operator was asked. Constants, not
# detections - see the module docstring.
INSTALLED_BY_THIS_GATE = True
ENABLED_BY_THIS_GATE = False
OPERATOR_APPROVAL = "install_and_start_without_enable"
PROCESS_PROOF_CAPTURED_DURING_RUN = True

DECLARATION_KEYS: tuple[str, ...] = (
    "backend_unit_template_available",
    "lifespan_hook_available",
    "installed_by_this_gate",
    "enabled_by_this_gate",
    "persistent_backend_live",
    "collectors_started",
    "urls_fetched",
    "source_monitoring_live",
    "live_source_coverage",
)

# The declarations that must be False in a committed artifact.
FALSE_DECLARATION_KEYS: tuple[str, ...] = (
    "enabled_by_this_gate",
    "persistent_backend_live",
    "collectors_started",
    "urls_fetched",
    "source_monitoring_live",
    "live_source_coverage",
)

PROOF_CSV_COLUMNS: tuple[str, ...] = (
    "requirement",
    "satisfied_in_committed_scope",
    "why",
    "owner",
    *DECLARATION_KEYS,
)

# A fixed worked example. The pid is 0-prefixed nonsense nobody will mistake for
# an observation, and the timestamp is fixed - both for the same reason the
# health contract uses a forty-zero sha.
REFERENCE_OBSERVED_AT = "2026-01-01T12:00:00+00:00"
REFERENCE_PID = 1

INSTALL_COMMANDS: tuple[str, ...] = (
    "mkdir -p ~/.config/systemd/user",
    "cp deploy/systemd/nativeforge-backend.service "
    "~/.config/systemd/user/nativeforge-backend.service",
    "systemctl --user daemon-reload",
    "systemctl --user start nativeforge-backend.service",
    "sleep 5",
    "systemctl --user status nativeforge-backend.service --no-pager",
    "curl -fsS http://127.0.0.1:8000/backend/health",
    "curl -fsS http://127.0.0.1:8000/backend/readiness",
)

UNINSTALL_COMMANDS: tuple[str, ...] = (
    "systemctl --user stop nativeforge-backend.service",
    "rm ~/.config/systemd/user/nativeforge-backend.service",
    "systemctl --user daemon-reload",
)


class ProcessProofArtifactError(RuntimeError):
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


def build_proof_contract_shape() -> dict[str, Any]:
    """The proof contract's shape and rules, plus one fixed worked example."""
    example = build_process_proof(
        observed_at=REFERENCE_OBSERVED_AT,
        unit_name=DEFAULT_UNIT_NAME,
        unit_installed=True,
        unit_enabled=False,
        unit_active=True,
        pid=REFERENCE_PID,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        healthcheck_status="ok",
        readiness_status="ok",
        git_sha=None,
        source_dirty=None,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fields": list(PROOF_FIELDS),
            "requirements": list(PROOF_REQUIREMENT_KEYS),
            "healthcheck_statuses": sorted(HEALTHCHECK_STATUSES),
            "healthcheck_path": HEALTHCHECK_PATH,
            "readiness_path": READINESS_PATH,
            "source_dirty_blocks_production_not_the_observation": True,
            "example_only": True,
            "example": example,
            "example_pid_is_a_placeholder": True,
            "fabricated": False,
        }
    )


def build_install_plan(*, repo_root: Path | None = None) -> dict[str, Any]:
    unit = detect_systemd_unit_template(repo_root=repo_root)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "template_path": SYSTEMD_UNIT_RELATIVE_PATH,
            "template_present": bool(unit["available"]),
            "binds_loopback_only": bool(unit["binds_loopback_only"]),
            "exec_start_lines": unit.get("exec_start_lines", []),
            "host": DEFAULT_HOST,
            "port": DEFAULT_PORT,
            "install_ready": bool(unit["available"])
            and bool(unit["binds_loopback_only"]),
            "install_commands": list(INSTALL_COMMANDS),
            "uninstall_commands": list(UNINSTALL_COMMANDS),
            "operator_approval": OPERATOR_APPROVAL,
            "installed_by_this_gate": INSTALLED_BY_THIS_GATE,
            "enabled_by_this_gate": ENABLED_BY_THIS_GATE,
            "enable_command_deliberately_omitted": True,
            "carries_secrets": False,
            "fabricated": False,
        }
    )


def build_process_proof_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the five artifacts are rendered from. Repository scope only."""
    contract = build_backend_runtime_contract(repo_root=repo_root)
    lifespan = build_lifespan_hook_contract()
    proof_contract = build_proof_contract_shape()
    install_plan = build_install_plan(repo_root=repo_root)

    declarations = {
        "backend_unit_template_available": bool(install_plan["template_present"]),
        "lifespan_hook_available": bool(lifespan["lifespan_hook_available"]),
        "installed_by_this_gate": INSTALLED_BY_THIS_GATE,
        "enabled_by_this_gate": ENABLED_BY_THIS_GATE,
        # Repository scope: the committed contract carries no proof. A real one
        # was captured during the run and is in the gate report.
        "persistent_backend_live": bool(contract["persistent_backend_live"]),
        "collectors_started": bool(lifespan["collectors_started"]),
        "urls_fetched": bool(lifespan["urls_fetched"]),
        "source_monitoring_live": bool(lifespan["source_monitoring_live"]),
        "live_source_coverage": bool(lifespan["live_source_coverage"]),
    }

    rows = [
        {
            "requirement": name,
            "satisfied_in_committed_scope": False,
            "why": why,
            "owner": "gate 102B",
            **declarations,
        }
        for name, why in (
            (
                "observed_at_present",
                "a dated observation, absent from a committed file",
            ),
            ("unit_active", "systemd reports the service running"),
            ("pid_present", "a process id was actually seen"),
            ("loopback_host", "127.0.0.1 or ::1 only"),
            ("healthcheck_ok", "/backend/health answered"),
        )
    ] + [
        {
            "requirement": f"attach_prerequisite:{name}",
            "satisfied_in_committed_scope": False,
            "why": why,
            "owner": "gate 102C",
            **declarations,
        }
        for name, why in ATTACH_PREREQUISITES
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": contract,
            "lifespan": lifespan,
            "proof_contract": proof_contract,
            "install_plan": install_plan,
            "rows": rows,
            "declarations": declarations,
            "process_proof_captured_during_run": PROCESS_PROOF_CAPTURED_DURING_RUN,
            "process_proof_committed": False,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    """Reasons to refuse to write. Empty means the bundle may be rendered."""
    fails: list[str] = []

    contract = bundle.get("contract") or {}
    lifespan = bundle.get("lifespan") or {}
    proof_contract = bundle.get("proof_contract") or {}
    install_plan = bundle.get("install_plan") or {}
    declarations = bundle.get("declarations") or {}

    fails.extend(
        f"contract_invariant:{f}" for f in backend_runtime_invariant_failures(contract)
    )
    fails.extend(
        f"lifespan_invariant:{f}" for f in lifespan_invariant_failures(lifespan)
    )
    fails.extend(
        f"proof_invariant:{f}"
        for f in proof_invariant_failures(proof_contract.get("example") or {})
    )

    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
    for key in FALSE_DECLARATION_KEYS:
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")

    # The operator declined `enable`, and the artifact must keep saying so.
    if declarations.get("enabled_by_this_gate") is not False:
        fails.append("artifact_claimed_the_unit_was_enabled")
    if install_plan.get("enable_command_deliberately_omitted") is not True:
        fails.append("install_plan_does_not_record_the_omitted_enable")
    commands = install_plan.get("install_commands") or []
    if any("enable" in command for command in commands):
        fails.append("install_plan_contains_an_enable_command")

    # Loopback, the one mistake that would matter.
    if not install_plan.get("binds_loopback_only"):
        fails.append("install_plan_does_not_bind_loopback_only")
    if not contract.get("loopback_only"):
        fails.append("backend_host_is_not_loopback")

    # Host-specific values may not reach a committed artifact.
    example = proof_contract.get("example") or {}
    if example.get("observed_at") != REFERENCE_OBSERVED_AT:
        fails.append("proof_example_is_not_the_reference_observation")
    if example.get("pid") != REFERENCE_PID:
        fails.append("proof_example_pid_is_not_the_placeholder")
    if proof_contract.get("example_only") is not True:
        fails.append("proof_contract_not_marked_example_only")
    if bundle.get("process_proof_committed") is not False:
        fails.append("a_live_process_proof_reached_a_committed_artifact")

    # No secret may appear in any rendered body.
    rendered = json.dumps(bundle, sort_keys=True).lower() + summary_text.lower()
    for marker in ("-----begin", "postgresql://", "bearer ", "api_key=", "password="):
        if marker in rendered:
            fails.append(f"artifact_carries_a_secret_marker:{marker.strip()}")

    # The summary must state every declaration in words.
    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")
    if SCHEDULER_ATTACH_POINT not in summary_text:
        fails.append("summary_omits_the_attach_point")

    return sorted(set(fails))


def render_install_plan(bundle: dict[str, Any]) -> str:
    plan = bundle["install_plan"]
    lines: list[str] = []
    lines.append("# Backend unit install plan")
    lines.append("")
    lines.append(
        f"Template: `{plan['template_path']}` — present, binding "
        f"`{plan['host']}:{plan['port']}` and nothing else."
    )
    lines.append("")
    lines.append("## What this gate did")
    lines.append("")
    lines.append("```text")
    lines.append(f"operator_approval        {plan['operator_approval']}")
    lines.append(
        f"installed_by_this_gate   {str(plan['installed_by_this_gate']).lower()}"
    )
    lines.append(
        f"enabled_by_this_gate     {str(plan['enabled_by_this_gate']).lower()}"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "The operator was asked before anything touched the host and chose "
        "**install and start, without enable**. `systemctl --user enable` was "
        "not run and does not appear in the commands below, so the service "
        "**will not come back after a reboot**. That is deliberate: it keeps a "
        "loopback development backend trivially reversible."
    )
    lines.append("")
    lines.append("## Install")
    lines.append("")
    lines.append("```bash")
    for command in plan["install_commands"]:
        lines.append(command)
    lines.append("```")
    lines.append("")
    lines.append("## Remove")
    lines.append("")
    lines.append("```bash")
    for command in plan["uninstall_commands"]:
        lines.append(command)
    lines.append("```")
    lines.append("")
    lines.append("## Why loopback")
    lines.append("")
    lines.append(
        "A Cloudflare tunnel is already running on this host. A backend bound "
        "to `0.0.0.0` would be published through it. Every `ExecStart` binds "
        "`127.0.0.1`, a test parses the unit to prove it, and the writer "
        "refuses to emit this plan for a template that does not."
    )
    lines.append("")
    lines.append("No credential appears in the unit or in these commands.")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_summary(bundle: dict[str, Any]) -> str:
    declarations = bundle["declarations"]
    lifespan = bundle["lifespan"]
    contract = bundle["contract"]

    lines: list[str] = []
    lines.append("# Backend process proof and lifespan hook")
    lines.append("")
    lines.append(
        "Generated by `backend_process_proof_artifact_service`. These files "
        "describe the repository's contracts and what this gate did to the "
        "host. They do not describe whether a process is running right now."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        value = declarations[key]
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key:<34}{rendered}")
    lines.append(
        f"{'runtime_mode':<34}{contract['runtime_mode']}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Why persistent_backend_live is false here")
    lines.append("")
    lines.append(
        "A running process is a property of one machine at one moment, not of "
        "this repository. Committed artifacts are compared against a fresh "
        "generation by test, so a pid or an observation timestamp in this file "
        "would fail that comparison on any other machine — and on this one, "
        "minutes later."
    )
    lines.append("")
    lines.append(
        "So the flag above means exactly one thing: **the committed contract "
        "carries no process proof.** A real proof "
        f"{'was' if bundle['process_proof_captured_during_run'] else 'was not'} "
        "captured during the run and appears in the gate report. Both are true; "
        "they answer different questions."
    )
    lines.append("")
    lines.append("## The lifespan hook")
    lines.append("")
    lines.append(
        f"Attach point: `{SCHEDULER_ATTACH_POINT}`. It fires on startup and "
        "shutdown and starts nothing."
    )
    lines.append("")
    lines.append("| Fact | Value |")
    lines.append("| --- | --- |")
    for key in (
        "lifespan_hook_available",
        "scheduler_attached",
        "collectors_started",
        "urls_fetched",
        "source_monitoring_live",
    ):
        lines.append(f"| `{key}` | {str(lifespan[key]).lower()} |")
    lines.append("")
    lines.append(
        "Having somewhere for a scheduler to attach is a prerequisite for "
        "attaching one. It is not attaching one. Before the hook existed, \"no "
        "scheduler runs at startup\" was true because startup did not exist; it "
        "is now true because startup ran and deliberately started nothing, "
        "which is a claim a test can check."
    )
    lines.append("")
    lines.append("## What must be true before anything attaches")
    lines.append("")
    for item in lifespan["attach_prerequisites"]:
        lines.append(f"- `{item['requirement']}` — {item['owner']}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_process_proof_artifacts(
    *,
    repo_root: Any = None,
    detect_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all five files, or refuse and write none.

    `repo_root` is where the files go; `detect_root` is what gets inspected and
    defaults to the real repository — the separation Gate 101 had to introduce
    after an output directory was mistaken for an inspection root.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    inspect_root = (
        Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]
    )
    bundle = build_process_proof_bundle(repo_root=inspect_root)
    summary_text = render_summary(bundle)
    install_plan_text = render_install_plan(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise ProcessProofArtifactError(
            "refusing to write process proof artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]
    runtime_mode = bundle["contract"]["runtime_mode"]

    (out_dir / PROOF_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "process_proof_captured_during_run": bundle[
                    "process_proof_captured_during_run"
                ],
                "process_proof_committed": False,
                "proof_contract": bundle["proof_contract"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / PROOF_CSV_NAME).write_text(
        _rows_to_csv(bundle["rows"], PROOF_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / LIFESPAN_JSON_NAME).write_text(
        json.dumps(
            {**declarations, "runtime_mode": runtime_mode, **bundle["lifespan"]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / INSTALL_PLAN_NAME).write_text(install_plan_text, encoding="utf-8")
    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "runtime_mode": runtime_mode,
            "operator_approval": OPERATOR_APPROVAL,
            "process_proof_committed": False,
            "claim_failures": [],
            "fabricated": False,
        }
    )
