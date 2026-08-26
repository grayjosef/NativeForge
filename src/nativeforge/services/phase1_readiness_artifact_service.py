"""Phase 1 readiness artifacts (Gate 93G).

Writes the readiness position to ``artifacts/phase1_collector_readiness/``.

Writing is confined to this module, as with the Baseline X and registry artifact
families: the preflight, policy, attribution, store and queue services all
return values and open nothing.

## Refusal

``write_phase1_readiness_artifacts`` raises before touching the filesystem if any
input carries a forbidden claim, if any invariant fails, or if the rendered
summary contains a banned phrase. An artifact that has drifted into claiming a
collector is running should leave nothing behind to be quoted later — the same
rule Gate 90's registry artifacts use, for the same reason.

Every artifact states the same four facts, and a test reads them back out of the
written files rather than out of the objects that produced them.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.grants_gov_attribution_service import (
    ATTRIBUTION_TEXT,
    attribution_invariant_failures,
    build_attribution_contract,
)
from nativeforge.services.phase1_collector_activation_policy_service import (
    build_phase1_activation_matrix,
    default_phase1_preflights,
    phase1_preflight_invariant_failures,
    policy_invariant_failures,
)
from nativeforge.services.raw_payload_store_contract_service import (
    build_store_contract,
    store_contract_invariant_failures,
)
from nativeforge.services.source_terms_review_queue_service import (
    build_terms_review_queue,
    queue_invariant_failures,
)

SCHEMA_VERSION = "nf_phase1_readiness_artifact_v1"

ARTIFACT_DIR = "artifacts/phase1_collector_readiness"

MATRIX_JSON_NAME = "phase1_activation_matrix.json"
MATRIX_CSV_NAME = "phase1_activation_matrix.csv"
SUMMARY_NAME = "phase1_readiness_summary.md"
QUEUE_CSV_NAME = "source_terms_review_queue.csv"
ATTRIBUTION_TXT_NAME = "grants_gov_attribution_contract.txt"
STORE_JSON_NAME = "raw_payload_store_contract.json"

# The four facts every artifact must state, verbatim.
REQUIRED_DECLARATIONS: tuple[str, ...] = (
    "collectors_active: false",
    "monitors_active: false",
    "live_fetch_performed: false",
    "live_source_coverage: false",
)

# Phrases that must never reach an artifact in this family.
BANNED_PHRASES: tuple[str, ...] = (
    "collectors active",
    "collector is active",
    "monitoring active",
    "monitoring is active",
    "live coverage",
    "live source coverage: true",
    "65% improvement",
    "improvement over",
    "scraper activated",
    "now fetching",
)

# Appended to every CSV row. A row lifted out of context still says that
# nothing is running - a header comment would not survive being pasted into a
# spreadsheet, and these files exist to be read by people doing exactly that.
DECLARATION_COLUMNS = [
    "collectors_active",
    "monitors_active",
    "live_fetch_performed",
    "live_source_coverage",
]

MATRIX_CSV_COLUMNS = [
    "source_id",
    "collector_status",
    "activation_status",
    "required_preconditions",
    "satisfied_preconditions",
    "missing_preconditions",
    "preflight_present",
    "preflight_passed",
    "attribution_required",
    "scraping_prohibited",
    "prior_award_only",
    "may_fetch_live_now",
    "may_schedule_monitor",
    "may_surface_customer_data",
    *DECLARATION_COLUMNS,
]

QUEUE_CSV_COLUMNS = [
    "review_item_id",
    "source_id",
    "source_name",
    "risk_type",
    "review_status",
    "review_required_reason",
    "automation_blocked",
    "human_review_only",
    "credential_required",
    "terms_url_or_note",
    "priority",
    *DECLARATION_COLUMNS,
]


class Phase1ReadinessArtifactError(RuntimeError):
    """Raised when a readiness artifact would carry a forbidden claim."""


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


def build_readiness_bundle(
    *, seeds: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    preflights = default_phase1_preflights()
    matrix = build_phase1_activation_matrix(preflight_by_source=preflights)
    queue = build_terms_review_queue(seeds=seeds)
    store = build_store_contract()
    # The attribution contract is evaluated against the live trust manifest, so
    # it reports what a customer would actually receive.
    from nativeforge.services.trust_surface_service import build_trust_manifest

    attribution = build_attribution_contract(
        trust_manifest=build_trust_manifest(org_type="demo")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "preflights": preflights,
        "matrix": matrix,
        "queue": queue,
        "store_contract": store,
        "attribution": attribution,
    }


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []

    fails.extend(policy_invariant_failures(bundle["matrix"]))
    fails.extend(phase1_preflight_invariant_failures(bundle["preflights"]))
    fails.extend(queue_invariant_failures(bundle["queue"]))
    fails.extend(store_contract_invariant_failures(bundle["store_contract"]))
    fails.extend(attribution_invariant_failures(bundle["attribution"]))

    lowered = summary_text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            fails.append(f"banned_phrase_in_summary:{phrase}")

    for declaration in REQUIRED_DECLARATIONS:
        if declaration not in lowered:
            fails.append(f"required_declaration_missing:{declaration}")

    return fails


def render_readiness_summary(bundle: dict[str, Any]) -> str:
    matrix = bundle["matrix"]
    queue = bundle["queue"]
    attribution = bundle["attribution"]

    lines: list[str] = []
    add = lines.append

    add("# Phase 1 collector readiness")
    add("")
    add(
        "The five Phase 1 sources and what each one still needs before it may "
        "collect. **Nothing here collects.**"
    )
    add("")
    add("```text")
    for declaration in REQUIRED_DECLARATIONS:
        add(declaration)
    add("```")
    add("")

    add("## Activation matrix")
    add("")
    add("| Source | Collector | Missing preconditions |")
    add("| --- | --- | --- |")
    for source in matrix["sources"]:
        missing = ", ".join(f"`{m}`" for m in source["missing_preconditions"]) or "—"
        add(f"| `{source['source_id']}` | `{source['collector_status']}` | {missing} |")
    add("")
    add(
        f"{matrix['sources_may_fetch_live_now']} of {matrix['source_count']} "
        "sources may fetch now. "
        f"{matrix['sources_may_schedule_monitor']} may schedule a monitor. "
        f"{matrix['sources_may_surface_customer_data']} may surface customer data."
    )
    add("")

    add("## Grants.gov attribution")
    add("")
    add(
        "The Grants.gov API terms require this notice to appear prominently "
        "within the application:"
    )
    add("")
    add("> " + ATTRIBUTION_TEXT)
    add("")
    surfaces = ", ".join(f"`{s}`" for s in attribution["customer_visible_surfaces"])
    add(
        f"Status: `{attribution['attribution_status']}`. "
        f"Customer-visible surfaces: {surfaces or 'none'}. "
        "A copy in documentation or a Python constant does not count - the "
        "notice has to reach a browser."
    )
    add("")

    add("## Terms and legal review queue")
    add("")
    add("| Risk type | Items |")
    add("| --- | --- |")
    for risk, count in queue["by_risk_type"].items():
        add(f"| `{risk}` | {count} |")
    add("")
    add(
        f"**{queue['queue_length']} items, all `pending`.** "
        f"{queue['approved_count']} approved. "
        "Every item blocks automation for its source until a person resolves "
        "it. The four client-rendered terms pages are queued explicitly: no "
        "policy text was ever retrieved from them, and an unread policy nobody "
        "is tracking looks exactly like one that was read and cleared."
    )
    add("")

    add("## Raw payload store")
    add("")
    add(
        f"{len(bundle['store_contract']['required_fields'])} required fields, "
        "and the store is **not implemented**. It is a required precondition "
        "for all five sources because a collector that does not retain its "
        "evidence produces records nobody can later distinguish from "
        "invention - which is the position Gates 87 to 89 spent four gates "
        "measuring from the other end."
    )
    add("")

    return "\n".join(lines) + "\n"


def write_phase1_readiness_artifacts(
    *,
    seeds: list[dict[str, Any]] | None = None,
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    bundle = build_readiness_bundle(seeds=seeds)
    summary_text = render_readiness_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise Phase1ReadinessArtifactError(
            "refusing to write Phase 1 readiness artifacts: "
            + ", ".join(sorted(set(failures)))
        )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = {
        "collectors_active": False,
        "monitors_active": False,
        "live_fetch_performed": False,
        "live_source_coverage": False,
    }

    matrix_payload = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            **declarations,
            "matrix": bundle["matrix"],
            "preflights": bundle["preflights"],
            "attribution": bundle["attribution"],
        },
        indent=2,
        sort_keys=True,
    )
    (out_dir / MATRIX_JSON_NAME).write_text(matrix_payload + "\n", encoding="utf-8")

    # Stamp the declarations onto every CSV row rather than into a header
    # comment, so a row survives being copied out on its own.
    matrix_rows = [{**row, **declarations} for row in bundle["matrix"]["sources"]]
    queue_rows = [{**row, **declarations} for row in bundle["queue"]["items"]]

    (out_dir / MATRIX_CSV_NAME).write_text(
        _rows_to_csv(matrix_rows, MATRIX_CSV_COLUMNS), encoding="utf-8"
    )
    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")
    (out_dir / QUEUE_CSV_NAME).write_text(
        _rows_to_csv(queue_rows, QUEUE_CSV_COLUMNS), encoding="utf-8"
    )

    # The attribution artifact is the notice itself, plus the four declarations
    # so this file states them like every other one.
    attribution_text = "\n".join(
        [
            "# Grants.gov API attribution - required verbatim",
            "",
            ATTRIBUTION_TEXT,
            "",
            "# Status",
            f"attribution_status: {bundle['attribution']['attribution_status']}",
            "customer_visible_surfaces: "
            + (",".join(bundle["attribution"]["customer_visible_surfaces"]) or "none"),
            "",
            "# Declarations",
            *REQUIRED_DECLARATIONS,
            "",
        ]
    )
    (out_dir / ATTRIBUTION_TXT_NAME).write_text(attribution_text, encoding="utf-8")

    (out_dir / STORE_JSON_NAME).write_text(
        json.dumps(
            {**declarations, **bundle["store_contract"]}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    return _json_safe_result(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": [
                MATRIX_JSON_NAME,
                MATRIX_CSV_NAME,
                SUMMARY_NAME,
                QUEUE_CSV_NAME,
                ATTRIBUTION_TXT_NAME,
                STORE_JSON_NAME,
            ],
            "phase1_source_count": bundle["matrix"]["source_count"],
            "queue_length": bundle["queue"]["queue_length"],
            **declarations,
            "claim_failures": [],
        }
    )


def _json_safe_result(x: Any) -> Any:
    json.dumps(x)
    return x
