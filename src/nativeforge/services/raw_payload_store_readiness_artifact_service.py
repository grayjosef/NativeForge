"""Raw payload store readiness artifacts (Gate 95G).

Writes the readiness position to ``artifacts/raw_payload_store_readiness/``.

## A different directory from the store itself

The payload store writes to ``artifacts/raw_payload_store/``, which Gate 95 adds
to ``.gitignore``. These readiness artifacts write to
``artifacts/raw_payload_store_readiness/``, which is committed.

That separation is deliberate and load-bearing. ``artifacts/`` is not ignored in
this repo - a dozen artifact directories are committed on purpose - so a store
sharing a directory with committed artifacts would be one ``git add`` away from
putting response bodies into history. Two directories, one ignored, one not.

## Refusal

``write_readiness_artifacts`` raises before touching the filesystem if an
invariant fails or the summary carries a banned phrase. Same rule as the Gate 90
and Gate 93 artifact families: an artifact that has drifted into claiming
production storage should leave nothing behind to be quoted later.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.local_raw_payload_store_service import (
    STORAGE_MODE,
    STORE_ROOT,
)
from nativeforge.services.phase1_collector_activation_policy_service import (
    build_phase1_activation_matrix,
    default_phase1_preflights,
    policy_invariant_failures,
)
from nativeforge.services.raw_payload_evidence_model_service import (
    EVIDENCE_CRITICAL_FIELDS,
    PARSER_STATUSES,
    PROMOTION_STATUSES,
    REDACTION_STATUSES,
    REQUIRED_FIELDS,
    SECRET_SCAN_STATUSES,
    build_payload_evidence,
)
from nativeforge.services.raw_payload_promotion_gate_service import (
    REQUIREMENT_KEYS,
    evaluate_payload_promotion,
    promotion_invariant_failures,
)
from nativeforge.services.raw_payload_secret_scan_service import (
    FINDING_KINDS,
    REDACTION_PLACEHOLDER,
    SECRET_KEY_PATTERNS,
)

SCHEMA_VERSION = "nf_raw_payload_store_readiness_artifact_v1"

ARTIFACT_DIR = "artifacts/raw_payload_store_readiness"

CONTRACT_JSON_NAME = "raw_payload_store_contract.json"
MATRIX_CSV_NAME = "raw_payload_promotion_matrix.csv"
PATTERNS_JSON_NAME = "secret_scan_patterns.json"
SUMMARY_NAME = "raw_payload_store_readiness_summary.md"

# The six facts every artifact in this family states.
REQUIRED_DECLARATIONS: tuple[str, ...] = (
    "local_raw_payload_store_available: true",
    "production_raw_payload_store_available: false",
    "live_fetch_performed: false",
    "collectors_active: false",
    "source_monitoring_active: false",
    "live_source_coverage: false",
)

BANNED_PHRASES: tuple[str, ...] = (
    "production storage is live",
    "production store available",
    "collectors active",
    "monitoring is active",
    "live coverage",
    "65% improvement",
    "improvement over",
    "payloads fetched",
)

MATRIX_CSV_COLUMNS = [
    "scenario",
    "secret_scan_status",
    "redaction_status",
    "terms_status",
    "parser_status",
    "created_from_fixture",
    "activation_preflight_present",
    "can_promote",
    "promotion_status",
    "human_review_required",
    "blocked_reasons",
    "local_raw_payload_store_available",
    "production_raw_payload_store_available",
    "live_fetch_performed",
    "collectors_active",
    "source_monitoring_active",
    "live_source_coverage",
]

# A deterministic hash for the matrix rows. Not a real payload - the scenarios
# describe promotion outcomes, and no body is needed to state them.
_SCENARIO_HASH = "0" * 64
_SCENARIO_REF = f"bodies/00/{_SCENARIO_HASH}.bin"


class RawPayloadReadinessArtifactError(RuntimeError):
    """Raised when a readiness artifact would carry a forbidden claim."""


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


# Scenarios the promotion matrix documents. Each is a real call through the
# gate, not a hand-written table - so the artifact cannot drift from the code.
_SCENARIOS: tuple[tuple[str, dict[str, Any], bool], ...] = (
    ("clean fixture payload", {}, False),
    ("secret scan pending", {"secret_scan_status": "pending"}, False),
    ("secret findings", {"secret_scan_status": "findings_blocked"}, False),
    ("redaction pending", {"redaction_status": "pending"}, False),
    ("redaction failed", {"redaction_status": "failed"}, False),
    ("terms review required", {"terms_status": "TERMS_REVIEW_REQUIRED"}, False),
    ("human review only", {"terms_status": "HUMAN_REVIEW_ONLY"}, False),
    ("terms unknown", {"terms_status": "UNKNOWN"}, False),
    ("parse failed", {"parser_status": "parse_failed"}, False),
    ("parser unavailable", {"parser_status": "parser_unavailable"}, False),
    ("live payload, no preflight", {}, True),
)


def build_promotion_matrix() -> list[dict[str, Any]]:
    """Run each scenario through the real gate and record what came back."""
    rows: list[dict[str, Any]] = []
    for name, patch, as_live in _SCENARIOS:
        base = dict(
            source_id="example_source",
            retrieved_at="2026-08-27T00:00:00Z",
            response_body_hash=_SCENARIO_HASH,
            raw_payload_ref=_SCENARIO_REF,
            request_fingerprint="scenario",
            secret_scan_status="clean",
            redaction_status="not_required",
            terms_status="NO_REVIEW_REQUIRED",
            parser_status="not_started",
            created_from_fixture=not as_live,
            created_from_live_fetch=as_live,
        )
        base.update(patch)
        payload = build_payload_evidence(**base)
        decision = evaluate_payload_promotion(payload=payload)
        rows.append(
            {
                "scenario": name,
                "secret_scan_status": payload["secret_scan_status"],
                "redaction_status": payload["redaction_status"],
                "terms_status": payload["terms_status"],
                "parser_status": payload["parser_status"],
                "created_from_fixture": payload["created_from_fixture"],
                "activation_preflight_present": decision[
                    "activation_preflight_present"
                ],
                "can_promote": decision["can_promote"],
                "promotion_status": decision["promotion_status"],
                "human_review_required": decision["human_review_required"],
                "blocked_reasons": decision["blocked_reasons"],
                # Kept for invariant checking; dropped from the CSV by the
                # column list, which names its columns explicitly.
                "decision": decision,
            }
        )
    return rows


def build_readiness_bundle() -> dict[str, Any]:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    promotion_rows = build_promotion_matrix()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase1_matrix": matrix,
        "promotion_rows": promotion_rows,
    }


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []
    fails.extend(policy_invariant_failures(bundle["phase1_matrix"]))

    # Every promotion row must be a decision the gate would actually make, and
    # must satisfy the same invariants a live decision does. Importing the
    # invariant checker and not calling it was the gap ruff surfaced.
    for row in bundle["promotion_rows"]:
        if row["can_promote"] and row["blocked_reasons"]:
            fails.append(f"matrix_row_promotes_with_blockers:{row['scenario']}")
        for failure in promotion_invariant_failures(row["decision"]):
            fails.append(f"matrix_row_invariant:{row['scenario']}:{failure}")

    lowered = summary_text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            fails.append(f"banned_phrase_in_summary:{phrase}")
    for declaration in REQUIRED_DECLARATIONS:
        if declaration not in lowered:
            fails.append(f"required_declaration_missing:{declaration}")

    return fails


def render_readiness_summary(bundle: dict[str, Any]) -> str:
    rows = bundle["promotion_rows"]
    lines: list[str] = []
    add = lines.append

    add("# Raw payload store readiness")
    add("")
    add(
        "A local, deterministic store for raw source responses, and the gates "
        "a payload passes before anything parsed from it may be called "
        "collected. **Nothing here fetches.**"
    )
    add("")
    add("```text")
    for declaration in REQUIRED_DECLARATIONS:
        add(declaration)
    add("```")
    add("")

    add("## Why the store exists")
    add("")
    add(
        "Gates 87 to 89 measured the corpus and found **185 records, 18 with "
        "independent transport evidence**. The other 167 were parsed and "
        "persisted while the bytes were discarded, so their origin can only be "
        "believed. Keeping the response, hashing it, and refusing to promote a "
        "parse without it is the whole of the fix."
    )
    add("")

    add("## Promotion matrix")
    add("")
    add("| Scenario | Promotes | Status | Human review |")
    add("| --- | --- | --- | --- |")
    for row in rows:
        add(
            f"| {row['scenario']} | {'yes' if row['can_promote'] else 'no'} "
            f"| `{row['promotion_status']}` "
            f"| {'yes' if row['human_review_required'] else 'no'} |"
        )
    add("")
    promoting = sum(1 for r in rows if r["can_promote"])
    add(
        f"{promoting} of {len(rows)} scenarios promote. Every row is produced by "
        "calling the real promotion gate, so this table cannot drift from the "
        "code that enforces it."
    )
    add("")

    add("## What the local store is not")
    add("")
    add(
        f"It writes to `{STORE_ROOT}` at storage mode `{STORAGE_MODE}`, refuses "
        "to write unless explicitly enabled, refuses customer data unless "
        "separately allowed, and never calls `now()` - the caller supplies "
        "`retrieved_at`, because a timestamp the store invents describes the "
        "store rather than the fetch."
    )
    add("")
    add(
        "The store root is gitignored. These readiness artifacts live in a "
        "different directory precisely so that one is committable and the "
        "other is not."
    )
    add("")

    add("## Secret scanning")
    add("")
    add(
        f"{len(FINDING_KINDS)} finding kinds. Gate 89 found a committed JWT "
        "inside a recorded API response; a store that keeps bodies without "
        "scanning them is a machine for repeating that. Findings report kind, "
        "location and an 8-hex fingerprint - never the value."
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
        raise RawPayloadReadinessArtifactError(
            "refusing to write raw payload store readiness artifacts: "
            + ", ".join(sorted(set(failures)))
        )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = {
        "local_raw_payload_store_available": True,
        "production_raw_payload_store_available": False,
        "live_fetch_performed": False,
        "collectors_active": False,
        "source_monitoring_active": False,
        "live_source_coverage": False,
    }

    (out_dir / CONTRACT_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "storage_root": STORE_ROOT,
                "storage_mode": STORAGE_MODE,
                "store_root_is_gitignored": True,
                "required_fields": list(REQUIRED_FIELDS),
                "evidence_critical_fields": list(EVIDENCE_CRITICAL_FIELDS),
                "promotion_requirements": list(REQUIREMENT_KEYS),
                "vocabularies": {
                    "secret_scan_status": sorted(SECRET_SCAN_STATUSES),
                    "redaction_status": sorted(REDACTION_STATUSES),
                    "parser_status": sorted(PARSER_STATUSES),
                    "promotion_status": sorted(PROMOTION_STATUSES),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    matrix_rows = [{**row, **declarations} for row in bundle["promotion_rows"]]
    (out_dir / MATRIX_CSV_NAME).write_text(
        _rows_to_csv(matrix_rows, MATRIX_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / PATTERNS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "finding_kinds": sorted(FINDING_KINDS),
                "secret_key_names": sorted(kind for kind, _ in SECRET_KEY_PATTERNS),
                "redaction_placeholder": REDACTION_PLACEHOLDER,
                "secret_values_included": False,
                "note": (
                    "Pattern names and finding kinds only. The regular "
                    "expressions live in the service; publishing them here "
                    "would not help a reader and listing any matched value "
                    "would defeat the point of the scanner."
                ),
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
            "files": [
                CONTRACT_JSON_NAME,
                MATRIX_CSV_NAME,
                PATTERNS_JSON_NAME,
                SUMMARY_NAME,
            ],
            "promotion_scenarios": len(bundle["promotion_rows"]),
            **declarations,
            "claim_failures": [],
        }
    )
