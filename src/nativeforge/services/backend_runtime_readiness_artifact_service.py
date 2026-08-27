"""Backend runtime readiness artifacts (Gate 101F).

Writes five files to `artifacts/backend_runtime_readiness/` describing the
backend runtime boundary, the health and readiness contracts, and the systemd
unit template.

## The health contract is a shape, not a sample

`/backend/health` returns a live `git_sha`, a live `source_dirty`, and a
timestamp. Embedding a real response would make the committed artifact disagree
with a fresh generation on the very next commit - the sha changes, and
`source_dirty` flips from true to false the moment the tree is clean.

So the artifact carries the contract's **field list, vocabulary and rules**, plus
one worked example built from fixed reference values and labelled
`example_only: true`. The example's sha is forty zeroes, which is not a commit
anyone will mistake for one.

The readiness contract has no clock in it and is captured live.

## Seven declarations, on every file and every CSV row

```text
backend_runtime_contract_available  true
persistent_backend_live             false
source_monitoring_live              false
collectors_live                     0
live_fetch_performed                false
live_source_coverage                false
customer_auth_live                  false
```

The first is the only true one, and it is the one that would be misread. It
means a loopback unit *template* is checked into the repository. It does not mean
a backend is running, it does not mean one is installed, and the six lines
beneath it are what say so.

## The systemd contract records that nothing was enabled

`backend_systemd_unit_contract.json` carries the template's ExecStart lines, the
fact that it binds loopback only, and `installed: false` / `enabled: false`.
Those two are not detections of the host - this service never inspects systemd -
they are statements that **this gate did not install or enable anything**, which
is the claim a reader needs.

## The writer refuses rather than annotates

`artifact_claim_failures` runs first and the writer raises instead of emitting a
file whose declarations disagree with the contracts behind them. It also refuses
a template that does not bind loopback only, because a unit binding `0.0.0.0` on
this host would be published through the Cloudflare tunnel that is already
running.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.backend_health_readiness_service import (
    HEALTH_FIELDS,
    HEALTH_STATUSES,
    READINESS_FIELDS,
    SERVICE_NAME,
    build_backend_health,
    build_backend_readiness,
    health_invariant_failures,
    readiness_invariant_failures,
)
from nativeforge.services.backend_runtime_contract_service import (
    HEALTHCHECK_PATH,
    LOOPBACK_HOSTS,
    READINESS_PATH,
    RUNTIME_MODES,
    SYSTEMD_UNIT_RELATIVE_PATH,
    backend_runtime_invariant_failures,
    build_backend_runtime_contract,
    detect_systemd_unit_template,
)

SCHEMA_VERSION = "nf_backend_runtime_readiness_artifact_v1"

ARTIFACT_DIR = "artifacts/backend_runtime_readiness"

READINESS_JSON_NAME = "backend_runtime_readiness.json"
READINESS_CSV_NAME = "backend_runtime_readiness.csv"
HEALTH_CONTRACT_NAME = "backend_health_contract.json"
SYSTEMD_CONTRACT_NAME = "backend_systemd_unit_contract.json"
SUMMARY_NAME = "backend_runtime_readiness_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    READINESS_JSON_NAME,
    READINESS_CSV_NAME,
    HEALTH_CONTRACT_NAME,
    SYSTEMD_CONTRACT_NAME,
    SUMMARY_NAME,
)

DECLARATION_KEYS: tuple[str, ...] = (
    "backend_runtime_contract_available",
    "persistent_backend_live",
    "source_monitoring_live",
    "collectors_live",
    "live_fetch_performed",
    "live_source_coverage",
    "customer_auth_live",
)

# The five that must be False. `collectors_live` is an integer that must be 0,
# and the first is legitimately true.
FALSE_DECLARATION_KEYS: tuple[str, ...] = (
    "persistent_backend_live",
    "source_monitoring_live",
    "live_fetch_performed",
    "live_source_coverage",
    "customer_auth_live",
)

READINESS_CSV_COLUMNS: tuple[str, ...] = (
    "fact",
    "value",
    "owner",
    "blocks_monitoring",
    "runtime_mode",
    *DECLARATION_KEYS,
)

# Fixed reference values for the worked health example. Forty zeroes is not a
# commit anyone will mistake for one.
REFERENCE_GIT_SHA = "0" * 40
REFERENCE_TIMESTAMP = "2026-01-01T12:00:00+00:00"
REFERENCE_RUNTIME_MODE = "loopback_backend_contract"


class BackendRuntimeArtifactError(RuntimeError):
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


def build_health_contract_shape() -> dict[str, Any]:
    """The contract's shape and rules, plus one fixed worked example."""
    example = build_backend_health(
        now=REFERENCE_TIMESTAMP,
        git_sha=REFERENCE_GIT_SHA,
        source_dirty=False,
        runtime_mode=REFERENCE_RUNTIME_MODE,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "path": HEALTHCHECK_PATH,
            "readiness_path": READINESS_PATH,
            "service": SERVICE_NAME,
            "fields": list(HEALTH_FIELDS),
            "statuses": sorted(HEALTH_STATUSES),
            "readiness_fields": list(READINESS_FIELDS),
            # Why this is not `/health`.
            "distinct_from_static_stamp": True,
            "static_stamp_note": (
                "the Vite preview serves a static /health from the build stamp "
                "that answers ok whether or not a backend exists"
            ),
            "health_claims_production_readiness": False,
            "carries_secrets": False,
            "example_only": True,
            "example": example,
            "example_git_sha_is_a_placeholder": True,
            "fabricated": False,
        }
    )


def build_systemd_contract(*, repo_root: Path | None = None) -> dict[str, Any]:
    """What the unit template says, and what this gate did not do with it."""
    unit = detect_systemd_unit_template(repo_root=repo_root)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "path": SYSTEMD_UNIT_RELATIVE_PATH,
            "template_present": bool(unit["available"]),
            "binds_loopback_only": bool(unit["binds_loopback_only"]),
            "exec_start_lines": unit.get("exec_start_lines", []),
            "loopback_hosts": sorted(LOOPBACK_HOSTS),
            "healthcheck_path": HEALTHCHECK_PATH,
            "readiness_path": READINESS_PATH,
            # Not detections of the host. Statements about what this gate did.
            "installed_by_this_gate": False,
            "enabled_by_this_gate": False,
            "installed": False,
            "enabled": False,
            "restart_policy": "on-failure, RestartSec=5, StartLimitBurst=5/300s",
            "carries_secrets": False,
            "environment_file_optional": True,
            "fabricated": False,
        }
    )


def build_backend_readiness_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the five artifacts are rendered from.

    `repo_root` here is **what to inspect**, not where to write. The writer
    keeps the two apart: these artifacts describe *this repository's* systemd
    template and runtime, and they describe it the same way whether they are
    written into the repo or into a temp directory for a determinism check.

    Conflating the two made a determinism run inspect an empty temp directory,
    find no template, and correctly refuse to write - a real refusal triggered
    by the wrong question being asked.
    """
    contract = build_backend_runtime_contract(repo_root=repo_root)
    readiness = build_backend_readiness(repo_root=repo_root)
    health_contract = build_health_contract_shape()
    systemd_contract = build_systemd_contract(repo_root=repo_root)

    declarations = {
        "backend_runtime_contract_available": bool(
            contract["backend_runtime_contract_available"]
        ),
        "persistent_backend_live": bool(contract["persistent_backend_live"]),
        "source_monitoring_live": bool(readiness["source_monitoring_live"]),
        "collectors_live": int(readiness["collectors_live"]),
        "live_fetch_performed": bool(contract["live_fetch_performed"]),
        "live_source_coverage": bool(contract["live_source_coverage"]),
        "customer_auth_live": bool(readiness["customer_auth_live"]),
    }

    # One row per fact a reader needs, each attributed to the service that owns
    # it. `database_ready` is deliberately excluded: it is a property of the
    # host at a moment, and baking it into a committed artifact would make the
    # file disagree with a fresh generation on a machine with no database.
    facts = [
        (
            "backend_runtime_contract_available",
            declarations["backend_runtime_contract_available"],
            "gate 101B",
            False,
        ),
        (
            "persistent_backend_live",
            declarations["persistent_backend_live"],
            "gate 101B",
            True,
        ),
        (
            "lifespan_hook_available",
            contract["lifespan_hook_available"],
            "gate 101B",
            True,
        ),
        (
            "systemd_unit_installed",
            contract["systemd_unit_installed"],
            "gate 101B",
            True,
        ),
        ("loopback_only", contract["loopback_only"], "gate 101B", False),
        (
            "production_raw_payload_store_available",
            readiness["production_raw_payload_store_available"],
            "gate 96/97",
            True,
        ),
        (
            "background_worker_available",
            readiness["background_worker_available"],
            "gate 98E",
            True,
        ),
        (
            "source_monitoring_live",
            declarations["source_monitoring_live"],
            "gate 98E",
            False,
        ),
        (
            "ready_to_start_monitoring",
            readiness["ready_to_start_monitoring"],
            "gate 98E",
            False,
        ),
        ("customer_auth_live", declarations["customer_auth_live"], "gate 101C", False),
        ("production_rollout", readiness["production_rollout"], "gate 101C", False),
    ]

    rows = [
        {
            "fact": name,
            "value": value,
            "owner": owner,
            "blocks_monitoring": blocks,
            "runtime_mode": contract["runtime_mode"],
            **declarations,
        }
        for name, value, owner, blocks in facts
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "contract": contract,
            "readiness": readiness,
            "health_contract": health_contract,
            "systemd_contract": systemd_contract,
            "rows": rows,
            "declarations": declarations,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    """Reasons to refuse to write. Empty means the bundle may be rendered."""
    fails: list[str] = []

    contract = bundle.get("contract") or {}
    readiness = bundle.get("readiness") or {}
    health_contract = bundle.get("health_contract") or {}
    systemd_contract = bundle.get("systemd_contract") or {}
    declarations = bundle.get("declarations") or {}

    fails.extend(
        f"contract_invariant:{f}" for f in backend_runtime_invariant_failures(contract)
    )
    fails.extend(
        f"readiness_invariant:{f}" for f in readiness_invariant_failures(readiness)
    )
    fails.extend(
        f"health_invariant:{f}"
        for f in health_invariant_failures(health_contract.get("example") or {})
    )

    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
    for key in FALSE_DECLARATION_KEYS:
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")
    if declarations.get("collectors_live") != 0:
        fails.append("declaration_reported_live_collectors")

    # The one true declaration must be backed by the template it describes.
    if declarations.get("backend_runtime_contract_available") != contract.get(
        "backend_runtime_contract_available"
    ):
        fails.append("declaration_disagrees_with_contract:contract_available")

    # Loopback. A unit binding a public interface on this host would be
    # published through the tunnel that is already running.
    if not systemd_contract.get("binds_loopback_only"):
        fails.append("systemd_template_does_not_bind_loopback_only")
    if not contract.get("loopback_only"):
        fails.append("backend_host_is_not_loopback")

    # Nothing was installed or enabled by this gate, and the artifact says so.
    for key in ("installed_by_this_gate", "enabled_by_this_gate"):
        if systemd_contract.get(key) is not False:
            fails.append(f"systemd_contract_claimed:{key}")

    # The health example must be a placeholder, not a real commit.
    example = health_contract.get("example") or {}
    if example.get("git_sha") != REFERENCE_GIT_SHA:
        fails.append("health_example_is_not_the_reference_placeholder")
    if health_contract.get("example_only") is not True:
        fails.append("health_contract_not_marked_example_only")
    if health_contract.get("health_claims_production_readiness") is not False:
        fails.append("health_contract_claimed_production_readiness")

    if contract.get("runtime_mode") not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")

    # No secret may appear in any rendered body.
    rendered = json.dumps(bundle, sort_keys=True).lower() + summary_text.lower()
    for marker in (
        "-----begin",
        "postgresql://",
        "bearer ",
        "api_key=",
        "password=",
    ):
        if marker in rendered:
            fails.append(f"artifact_carries_a_secret_marker:{marker.strip()}")

    # The summary must state every declaration in words.
    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")
    if "runtime_mode" not in lowered:
        fails.append("summary_omits_runtime_mode")

    return sorted(set(fails))


def render_readiness_summary(bundle: dict[str, Any]) -> str:
    contract = bundle["contract"]
    readiness = bundle["readiness"]
    systemd_contract = bundle["systemd_contract"]
    declarations = bundle["declarations"]

    lines: list[str] = []
    lines.append("# Backend runtime readiness")
    lines.append("")
    lines.append(
        "Generated by `backend_runtime_readiness_artifact_service`. No backend "
        "process was started, no systemd unit was installed or enabled, and no "
        "request was made."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        value = declarations[key]
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key:<38}{rendered}")
    lines.append(f"{'runtime_mode':<38}{contract['runtime_mode']}")
    lines.append("```")
    lines.append("")
    lines.append(
        "`backend_runtime_contract_available` is the only true line above, and "
        "it is the one that would be misread. It means a loopback unit "
        "*template* is checked into the repository. It does not mean a backend "
        "is running, and it does not mean one is installed."
    )
    lines.append("")
    lines.append("## Backend runtime")
    lines.append("")
    lines.append("| Fact | Value |")
    lines.append("| --- | --- |")
    for key in (
        "runtime_mode",
        "backend_runtime_available",
        "persistent_backend_live",
        "loopback_only",
        "lifespan_hook_available",
        "systemd_unit_available",
        "systemd_unit_installed",
        "systemd_unit_enabled",
    ):
        lines.append(f"| `{key}` | {str(contract[key]).lower()} |")
    lines.append(f"| `host` | {contract['host']} |")
    lines.append(f"| `port` | {contract['port']} |")
    lines.append(f"| `healthcheck_path` | `{contract['healthcheck_path']}` |")
    lines.append("")
    lines.append("## What blocks a persistent backend")
    lines.append("")
    for reason in contract["blocked_reasons"]:
        lines.append(f"- `{reason}`")
    lines.append("")
    lines.append("## What must happen next")
    lines.append("")
    for index, action in enumerate(contract["next_required_actions"], 1):
        lines.append(f"{index}. `{action['action']}` — {action['why']}")
    lines.append("")
    lines.append("## Readiness")
    lines.append("")
    lines.append("| Fact | Value | Owner |")
    lines.append("| --- | --- | --- |")
    for row in bundle["rows"]:
        lines.append(
            f"| `{row['fact']}` | {str(row['value']).lower()} | {row['owner']} |"
        )
    lines.append("")
    lines.append(
        "`database_ready` is not in this table on purpose: it is a property of "
        "the host at a moment, and committing it would make this file disagree "
        "with a fresh generation on a machine with no database. The live "
        "endpoint reports it."
    )
    lines.append("")
    lines.append("## Systemd")
    lines.append("")
    lines.append(
        f"Template at `{systemd_contract['path']}`, binding loopback only. "
        "**Not installed and not enabled by this gate.** Installing it is a "
        "host decision; nothing in the repository does it."
    )
    lines.append("")
    lines.append("## What this is not")
    lines.append("")
    lines.append(
        "A backend runtime is a process that answers HTTP. It is not collectors "
        "being live, not a scheduler running, not customer auth, and not "
        "production rollout. "
        f"`ready_to_start_monitoring` is "
        f"{str(readiness['ready_to_start_monitoring']).lower()}."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_backend_runtime_artifacts(
    *,
    repo_root: Any = None,
    detect_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all five files, or refuse and write none.

    `repo_root` is where the files go. `detect_root` is what gets inspected, and
    it defaults to the real repository rather than following `repo_root` - so a
    determinism check writing into a temp directory still describes this
    repository's template, which is what the artifact is about.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    inspect_root = (
        Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]
    )
    bundle = build_backend_readiness_bundle(repo_root=inspect_root)
    summary_text = render_readiness_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise BackendRuntimeArtifactError(
            "refusing to write backend runtime artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]
    runtime_mode = bundle["contract"]["runtime_mode"]

    (out_dir / READINESS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "contract": bundle["contract"],
                # `database_ready` is stripped: a host property has no place in
                # a committed artifact that must match a fresh generation.
                "readiness": {
                    k: v
                    for k, v in bundle["readiness"].items()
                    if k != "database_ready"
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / READINESS_CSV_NAME).write_text(
        _rows_to_csv(bundle["rows"], READINESS_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / HEALTH_CONTRACT_NAME).write_text(
        json.dumps(
            {**declarations, "runtime_mode": runtime_mode, **bundle["health_contract"]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / SYSTEMD_CONTRACT_NAME).write_text(
        json.dumps(
            {
                **declarations,
                "runtime_mode": runtime_mode,
                **bundle["systemd_contract"],
            },
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
            "runtime_mode": runtime_mode,
            "systemd_unit_installed_by_this_gate": False,
            "systemd_unit_enabled_by_this_gate": False,
            "claim_failures": [],
            "fabricated": False,
        }
    )
