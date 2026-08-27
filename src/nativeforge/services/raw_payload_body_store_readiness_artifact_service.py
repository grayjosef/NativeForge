"""Body store readiness artifacts (Gate 97F).

Writes to ``artifacts/raw_payload_body_store_readiness/``.

## No credential ever reaches an artifact

The settings contract artifact lists **names**, and for each one whether a value
is present. It carries no value, and there is no field it could carry one in — a
test parses every artifact with the Gate 95 secret scanner and asserts clean.

That is stricter than it needs to be for the current state (nothing is
configured, so there is nothing to leak) and exactly as strict as it needs to be
for the state after someone configures it, which is when a leak would matter.

## Two facts kept apart

Every artifact states ``body_store_implementation_available: true`` beside
``body_store_configured: false``. The seam exists; no environment configures it.
Collapsing those into one line is how "we built it" becomes "it is running".
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.phase1_collector_activation_policy_service import (
    build_phase1_activation_matrix,
    default_phase1_preflights,
    policy_invariant_failures,
)
from nativeforge.services.raw_payload_body_store_contract_service import (
    NON_PRODUCTION_MODES,
    OPTIONAL_SETTINGS,
    PRODUCTION_CAPABLE_MODES,
    REQUIRED_GUARANTEES,
    REQUIRED_SETTINGS,
    body_store_invariant_failures,
    build_body_store_contract,
)
from nativeforge.services.raw_payload_production_readiness_service import (
    REQUIRED_COMPONENTS,
    build_production_readiness,
    production_readiness_invariant_failures,
)
from nativeforge.services.s3_raw_payload_body_store_service import (
    KEY_NAMESPACE,
    PLACEHOLDER_CREDENTIAL_VALUES,
    body_hash,
    build_client_config,
    object_key_for,
    store_body,
)
from nativeforge.services.s3_raw_payload_body_store_service import (
    body_store_invariant_failures as s3_invariant_failures,
)

SCHEMA_VERSION = "nf_raw_payload_body_store_readiness_artifact_v1"

ARTIFACT_DIR = "artifacts/raw_payload_body_store_readiness"

SETTINGS_JSON_NAME = "body_store_settings_contract.json"
S3_JSON_NAME = "s3_body_store_contract.json"
MATRIX_CSV_NAME = "body_store_readiness_matrix.csv"
SUMMARY_NAME = "body_store_readiness_summary.md"

# The eight facts every artifact in this family states.
REQUIRED_DECLARATIONS: tuple[str, ...] = (
    "body_store_implementation_available: true",
    "body_store_configured: false",
    "production_raw_payload_store_available: false",
    "production_storage_live: false",
    "live_fetch_performed: false",
    "collectors_active: false",
    "source_monitoring_active: false",
    "live_source_coverage: false",
)

BANNED_PHRASES: tuple[str, ...] = (
    "body store is configured",
    "production storage is live",
    "production storage is ready",
    "object store contacted",
    "collectors active",
    "monitoring is active",
    "live coverage",
    "65% improvement",
    "improvement over",
)

# Setting names are safe to publish. Values are not, and none is read here.
SETTINGS_CSV_COLUMNS = [
    "setting",
    "env_var",
    "required",
    "value_present",
    "is_secret",
    "body_store_implementation_available",
    "body_store_configured",
    "production_raw_payload_store_available",
    "production_storage_live",
    "live_fetch_performed",
    "collectors_active",
    "source_monitoring_active",
    "live_source_coverage",
]

# Which of the settings is a secret, and therefore must never be rendered even
# as a masked or truncated value.
SECRET_SETTINGS = frozenset({"raw_payload_object_store_secret_access_key"})


class BodyStoreReadinessArtifactError(RuntimeError):
    """Raised when an artifact would carry a forbidden claim or a secret."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                c: (
                    ";".join(str(v) for v in row.get(c))
                    if isinstance(row.get(c), list)
                    else row.get(c)
                )
                for c in columns
            }
        )
    return buffer.getvalue()


def _env_var_for(setting: str) -> str:
    return setting.upper()


def build_settings_rows(*, contract: dict[str, Any]) -> list[dict[str, Any]]:
    present = set(contract.get("settings_present") or [])
    placeholders = set(contract.get("placeholder_settings") or [])
    rows: list[dict[str, Any]] = []
    for name in (*REQUIRED_SETTINGS, *OPTIONAL_SETTINGS):
        rows.append(
            {
                "setting": name,
                "env_var": _env_var_for(name),
                "required": name in REQUIRED_SETTINGS,
                # Presence only. Never the value, and never a masked value -
                # a masked value still tells you the length.
                "value_present": name in present or name in placeholders,
                "is_secret": name in SECRET_SETTINGS,
            }
        )
    return rows


def build_readiness_bundle() -> dict[str, Any]:
    contract = build_body_store_contract()
    readiness = build_production_readiness()
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    client_config = build_client_config()

    # A real call through the real store, proving refusal by default without
    # any client, any credential or any network.
    sample_body = '{"synthetic":"gate97 artifact sample"}'
    refused = store_body(
        body=sample_body,
        response_body_hash=body_hash(sample_body),
        bucket="",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": contract,
        "readiness": readiness,
        "matrix": matrix,
        "client_config": client_config,
        "refused_sample": refused,
        "settings_rows": build_settings_rows(contract=contract),
    }


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []
    fails.extend(body_store_invariant_failures(bundle["contract"]))
    fails.extend(production_readiness_invariant_failures(bundle["readiness"]))
    fails.extend(policy_invariant_failures(bundle["matrix"]))
    fails.extend(s3_invariant_failures(bundle["client_config"]))
    fails.extend(s3_invariant_failures(bundle["refused_sample"]))

    # The sample must actually have been refused; an artifact documenting a
    # default-refuse store with a successful write would be documenting nothing.
    if bundle["refused_sample"]["body_store_status"] != "refused":
        fails.append("sample_write_was_not_refused")

    # No settings row may carry anything but presence.
    for row in bundle["settings_rows"]:
        for key in row:
            if key not in {
                "setting",
                "env_var",
                "required",
                "value_present",
                "is_secret",
            }:
                fails.append(f"settings_row_has_an_unexpected_field:{key}")

    lowered = summary_text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            fails.append(f"banned_phrase_in_summary:{phrase}")
    for declaration in REQUIRED_DECLARATIONS:
        if declaration not in lowered:
            fails.append(f"required_declaration_missing:{declaration}")

    return fails


def render_readiness_summary(bundle: dict[str, Any]) -> str:
    contract = bundle["contract"]
    readiness = bundle["readiness"]
    lines: list[str] = []
    add = lines.append

    add("# Raw payload body store readiness")
    add("")
    add(
        "An S3-compatible write seam exists and is fully exercised by tests "
        "through an injected client. **No object store was contacted and none "
        "is configured.**"
    )
    add("")
    add("```text")
    for declaration in REQUIRED_DECLARATIONS:
        add(declaration)
    add("```")
    add("")

    add("## Two facts, kept apart")
    add("")
    add(
        "| Fact | State |\n| --- | --- |\n"
        f"| body store implementation exists | "
        f"{'yes' if contract['body_store_implementation_available'] else 'no'} |\n"
        f"| an environment configures it | "
        f"{'yes' if contract['body_store_configured'] else '**no**'} |"
    )
    add("")
    add(
        "Gate 96 folded these together by requiring an installed SDK. With an "
        "injected-client seam the client arrives at call time, so that test "
        "could never have passed however correctly an operator configured "
        "their environment."
    )
    add("")

    add("## Production components")
    add("")
    add("| Component | Available |")
    add("| --- | --- |")
    for name in REQUIRED_COMPONENTS:
        add(f"| `{name}` | {'yes' if readiness[name] else '**no**'} |")
    add("")
    add(
        f"{len(readiness['components_present'])} of {len(REQUIRED_COMPONENTS)} "
        "present. `production_raw_payload_store_available` is derived from all "
        "of them and reads "
        f"`{readiness['production_raw_payload_store_available']}`."
    )
    add("")

    add("## No dependency was added")
    add("")
    add(
        f"The store writes through any object exposing `put_object` and keys "
        f"objects at `{KEY_NAMESPACE}/<hash[:2]>/<hash[2:4]>/<hash>.bin`. No "
        "SDK is imported, `uv.lock` is untouched, and every refusal path is "
        "exercised without a network, a credential or a vendor."
    )
    add("")

    add("## Settings")
    add("")
    add("| Env var | Required | Secret | Value present |")
    add("| --- | --- | --- | --- |")
    for row in bundle["settings_rows"]:
        add(
            f"| `{row['env_var']}` | {'yes' if row['required'] else 'no'} "
            f"| {'yes' if row['is_secret'] else 'no'} "
            f"| {'yes' if row['value_present'] else 'no'} |"
        )
    add("")
    add(
        "Presence only. No value is rendered here or anywhere downstream - not "
        "even masked, since a masked value still leaks its length. The secret "
        "key is a pydantic `SecretStr`, so an accidental repr prints "
        "`**********`."
    )
    add("")
    add(
        f"A value that looks like a placeholder is not configuration: "
        f"{len(PLACEHOLDER_CREDENTIAL_VALUES)} known placeholder values are "
        "refused, including AWS's own documentation key."
    )
    add("")

    return "\n".join(lines) + "\n"


def write_readiness_artifacts(
    *, repo_root: Any = None, artifact_dir: str = ARTIFACT_DIR
) -> dict[str, Any]:
    bundle = build_readiness_bundle()
    summary_text = render_readiness_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise BodyStoreReadinessArtifactError(
            "refusing to write body store readiness artifacts: "
            + ", ".join(sorted(set(failures)))
        )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    contract = bundle["contract"]
    readiness = bundle["readiness"]
    declarations = {
        "body_store_implementation_available": bool(
            contract["body_store_implementation_available"]
        ),
        "body_store_configured": bool(contract["body_store_configured"]),
        "production_raw_payload_store_available": bool(
            readiness["production_raw_payload_store_available"]
        ),
        "production_storage_live": bool(readiness["production_storage_live"]),
        "live_fetch_performed": False,
        "collectors_active": False,
        "source_monitoring_active": False,
        "live_source_coverage": False,
    }

    (out_dir / SETTINGS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "required_settings": list(REQUIRED_SETTINGS),
                "optional_settings": list(OPTIONAL_SETTINGS),
                "secret_settings": sorted(SECRET_SETTINGS),
                "settings": bundle["settings_rows"],
                "settings_missing": list(contract.get("settings_missing") or []),
                "placeholder_settings": list(
                    contract.get("placeholder_settings") or []
                ),
                "credential_values_rendered": False,
                "note": (
                    "Names and presence only. No value appears in this file, "
                    "masked or otherwise."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / S3_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "key_namespace": KEY_NAMESPACE,
                "example_object_key": object_key_for("0" * 64),
                "modes": sorted(contract["modes"]),
                "production_capable_modes": sorted(PRODUCTION_CAPABLE_MODES),
                "non_production_modes": dict(sorted(NON_PRODUCTION_MODES.items())),
                "required_guarantees": list(REQUIRED_GUARANTEES),
                "injected_client_seam": True,
                "object_store_sdk_required": False,
                "object_store_contacted": False,
                "default_write_refused": True,
                "sample_refusal_reasons": list(
                    bundle["refused_sample"]["blocked_reasons"]
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = [{**row, **declarations} for row in bundle["settings_rows"]]
    (out_dir / MATRIX_CSV_NAME).write_text(
        _rows_to_csv(rows, SETTINGS_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": [
                SETTINGS_JSON_NAME,
                S3_JSON_NAME,
                MATRIX_CSV_NAME,
                SUMMARY_NAME,
            ],
            "settings_documented": len(bundle["settings_rows"]),
            **declarations,
            "credential_values_rendered": False,
            "claim_failures": [],
        }
    )
