"""Tenant NOFO digest artifacts (Gate 104I).

Six files under `artifacts/tenant_nofo_digest_contract/` describing the digest
contract, a worked preview over the labelled fixture pair, and the suppression
matrix.

## Nine declarations, on every file and every CSV row

```text
digest_contract_available         true
weekly_digest_preview_available   true
ready_for_demo_preview            true
ready_for_operational_digest      false
email_delivery_available          false
source_monitoring_live            false
live_source_collection_available  false
live_source_coverage              false
customer_persistence_live         false
```

Three true and six false. The three true ones all describe a *preview*: contracts
exist and a digest can be rendered from labelled fixtures. None of them says a
digest arrives anywhere.

## The preview is over fixtures, and the artifact says so

`comparison_kind` is `fixture_to_fixture` in every committed file. Doc 570's
first tension made concrete: with no live collection there is no second
observation, so the preview compares two recorded snapshots and the artifact
carries that label rather than presenting the result as a week's monitoring.

## Suppressed items appear in the matrix

The suppression matrix has a row per suppressed opportunity showing what was
withheld, from which view, and that source history and provenance were preserved.
An artifact that simply omitted suppressed items would be indistinguishable from
one where they were deleted.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.tenant_nofo_digest_builder_service import (
    CADENCES,
    DEFAULT_CADENCE,
    DELIVERY_STATUSES,
    build_tenant_digest,
    digest_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_change_detection_service import (
    CHANGE_TYPES,
    change_detection_invariant_failures,
    detect_digest_changes,
    summarise_changes,
)
from nativeforge.services.tenant_nofo_digest_demo_fixture_service import (
    DEMO_TENANT_ID,
    PERIOD_END,
    PERIOD_START,
    REFERENCE_NOW,
    build_digest_demo_fixture_set,
    demo_fixture_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_item_explanation_service import (
    DIGEST_ITEM_STATUSES,
)
from nativeforge.services.tenant_nofo_digest_readiness_service import (
    DEMO_SCOPE,
    build_digest_readiness,
    digest_readiness_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_snapshot_service import SNAPSHOT_KINDS
from nativeforge.services.tenant_pursuit_suppression_service import (
    SUPPRESSION_STATUSES,
    summarise_suppressions,
    suppression_invariant_failures,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_nofo_digest_contract"

CONTRACT_JSON_NAME = "tenant_nofo_digest_contract.json"
PREVIEW_JSON_NAME = "tenant_nofo_digest_preview.json"
ITEMS_CSV_NAME = "tenant_nofo_digest_items.csv"
CHANGE_CSV_NAME = "tenant_nofo_digest_change_matrix.csv"
SUPPRESSION_CSV_NAME = "tenant_pursuit_suppression_matrix.csv"
SUMMARY_NAME = "tenant_nofo_digest_readiness_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    CONTRACT_JSON_NAME,
    PREVIEW_JSON_NAME,
    ITEMS_CSV_NAME,
    CHANGE_CSV_NAME,
    SUPPRESSION_CSV_NAME,
    SUMMARY_NAME,
)

DECLARATION_KEYS: tuple[str, ...] = (
    "digest_contract_available",
    "weekly_digest_preview_available",
    "ready_for_demo_preview",
    "ready_for_operational_digest",
    "email_delivery_available",
    "source_monitoring_live",
    "live_source_collection_available",
    "live_source_coverage",
    "customer_persistence_live",
)

FALSE_DECLARATION_KEYS: tuple[str, ...] = (
    "ready_for_operational_digest",
    "email_delivery_available",
    "source_monitoring_live",
    "live_source_collection_available",
    "live_source_coverage",
    "customer_persistence_live",
)

ITEMS_CSV_COLUMNS: tuple[str, ...] = (
    "opportunity_id",
    "digest_item_status",
    "visible",
    "suppressed",
    "requires_human_review",
    "deadline_verified",
    "reporting_burden_status",
    "allowability_label",
    *DECLARATION_KEYS,
)

CHANGE_CSV_COLUMNS: tuple[str, ...] = (
    "opportunity_id",
    "change_types",
    "previous_status",
    "current_status",
    "deadline_provenance_status",
    "requires_human_review",
    "previous_row_preserved",
    "deleted",
    *DECLARATION_KEYS,
)

SUPPRESSION_CSV_COLUMNS: tuple[str, ...] = (
    "tenant_id",
    "opportunity_id",
    "suppression_status",
    "suppression_reason",
    "source_history_preserved",
    "provenance_preserved",
    "visible_in_pipeline",
    "opportunity_deleted",
    "suppressed_globally",
    *DECLARATION_KEYS,
)


class TenantDigestArtifactError(RuntimeError):
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


def build_digest_artifact_bundle() -> dict[str, Any]:
    """Everything the six artifacts are rendered from. Deterministic."""
    fixtures = build_digest_demo_fixture_set()
    readiness = build_digest_readiness()

    changes = detect_digest_changes(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        previous_snapshot=fixtures["previous_snapshot"],
        now=REFERENCE_NOW,
    )
    digest = build_tenant_digest(
        tenant_id=DEMO_TENANT_ID,
        current_snapshot=fixtures["current_snapshot"],
        change_detection=changes,
        previous_snapshot=fixtures["previous_snapshot"],
        suppressions=fixtures["suppressions"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    declarations = {
        "digest_contract_available": bool(readiness["digest_contract_available"]),
        "weekly_digest_preview_available": bool(
            readiness["weekly_digest_preview_available"]
        ),
        "ready_for_demo_preview": bool(readiness["ready_for_demo_preview"]),
        "ready_for_operational_digest": bool(
            readiness["ready_for_operational_digest"]
        ),
        "email_delivery_available": bool(readiness["email_delivery_available"]),
        "source_monitoring_live": bool(readiness["source_monitoring_live"]),
        "live_source_collection_available": bool(
            readiness["live_source_collection_available"]
        ),
        "live_source_coverage": bool(readiness["live_source_coverage"]),
        "customer_persistence_live": bool(readiness["customer_persistence_live"]),
    }

    item_rows = [
        {
            "opportunity_id": item["opportunity_id"],
            "digest_item_status": item["digest_item_status"],
            "visible": item["visible"],
            "suppressed": item["suppressed"],
            "requires_human_review": item["requires_human_review"],
            "deadline_verified": item["deadline_verified"],
            "reporting_burden_status": item["reporting_burden_status"],
            "allowability_label": item["allowability_label"],
            **declarations,
        }
        for item in digest["digest_items"]
    ]

    change_rows = [
        {
            "opportunity_id": change["opportunity_id"],
            "change_types": "; ".join(change["change_types"]),
            "previous_status": change.get("previous_eligibility_match_status") or "",
            "current_status": change.get("current_eligibility_match_status") or "",
            "deadline_provenance_status": change.get("deadline_provenance_status")
            or "",
            "requires_human_review": change["requires_human_review"],
            "previous_row_preserved": change["previous_row_preserved"],
            "deleted": change["deleted"],
            **declarations,
        }
        for change in changes["changes"]
    ]

    suppression_rows = [
        {
            "tenant_id": record["tenant_id"],
            "opportunity_id": record["opportunity_id"],
            "suppression_status": record["suppression_status"],
            "suppression_reason": record["suppression_reason"],
            "source_history_preserved": record["source_history_preserved"],
            "provenance_preserved": record["provenance_preserved"],
            "visible_in_pipeline": record["visible_in_pipeline"],
            "opportunity_deleted": record["opportunity_deleted"],
            "suppressed_globally": record["suppressed_globally"],
            **declarations,
        }
        for record in fixtures["suppressions"]
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures": fixtures,
            "readiness": readiness,
            "changes": changes,
            "change_summary": summarise_changes(changes),
            "digest": digest,
            "suppression_summary": summarise_suppressions(fixtures["suppressions"]),
            "item_rows": item_rows,
            "change_rows": change_rows,
            "suppression_rows": suppression_rows,
            "declarations": declarations,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    fails: list[str] = []

    fixtures = bundle.get("fixtures") or {}
    readiness = bundle.get("readiness") or {}
    changes = bundle.get("changes") or {}
    digest = bundle.get("digest") or {}
    declarations = bundle.get("declarations") or {}

    fails.extend(
        f"fixture_invariant:{f}" for f in demo_fixture_invariant_failures(fixtures)
    )
    fails.extend(
        f"readiness_invariant:{f}"
        for f in digest_readiness_invariant_failures(readiness)
    )
    fails.extend(
        f"change_invariant:{f}" for f in change_detection_invariant_failures(changes)
    )
    fails.extend(f"digest_invariant:{f}" for f in digest_invariant_failures(digest))
    for record in fixtures.get("suppressions") or []:
        fails.extend(
            f"suppression_invariant:{f}"
            for f in suppression_invariant_failures(record)
        )

    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
    for key in FALSE_DECLARATION_KEYS:
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")

    # The demo scope must be the one the readiness service declares. A scope
    # that drifted would let "ready for demo" travel without its qualifier.
    if readiness.get("demo_scope") != DEMO_SCOPE:
        fails.append(f"demo_scope_altered:{readiness.get('demo_scope')}")

    # The preview must be over fixtures, and say so.
    if changes.get("comparison_kind") != "fixture_to_fixture":
        fails.append(
            f"preview_comparison_is_not_fixture_to_fixture:"
            f"{changes.get('comparison_kind')}"
        )

    # Nothing delivered, nothing deleted.
    if digest.get("delivery_status") not in {"preview_only", "not_configured"}:
        fails.append(f"digest_delivery_beyond_preview:{digest.get('delivery_status')}")
    if digest.get("emails_sent"):
        fails.append("digest_sent_email")
    if changes.get("rows_deleted"):
        fails.append("comparison_deleted_rows")
    for record in fixtures.get("suppressions") or []:
        if record.get("opportunity_deleted") is not False:
            fails.append("suppression_deleted_an_opportunity")
        if record.get("provenance_deleted") is not False:
            fails.append("suppression_deleted_provenance")

    if fixtures.get("real_tribe_named"):
        fails.append("fixture_named_a_real_tribe")

    rendered = json.dumps(bundle, sort_keys=True).lower() + summary_text.lower()
    for marker in ("-----begin", "postgresql://", "bearer ", "api_key=", "password="):
        if marker in rendered:
            fails.append(f"artifact_carries_a_secret_marker:{marker.strip()}")

    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")

    return sorted(set(fails))


def render_summary(bundle: dict[str, Any]) -> str:
    declarations = bundle["declarations"]
    readiness = bundle["readiness"]
    digest = bundle["digest"]
    changes = bundle["changes"]

    lines: list[str] = []
    lines.append("# Tenant NOFO digest readiness")
    lines.append("")
    lines.append(
        "Generated by `tenant_nofo_digest_artifact_service`. No email was sent, "
        "no collector ran, no source was checked, and nothing was deleted."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        lines.append(f"{key:<36}{str(declarations[key]).lower()}")
    lines.append(f"{'demo_scope':<36}{readiness['demo_scope']}")
    lines.append(f"{'comparison_kind':<36}{changes['comparison_kind']}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Three lines are true and all three describe a **preview**: the "
        "contracts exist and a digest can be rendered from labelled fixture "
        "snapshots. None of them says a digest arrives anywhere."
    )
    lines.append("")
    lines.append("## The preview compares two recorded snapshots")
    lines.append("")
    lines.append(
        "`comparison_kind` is `fixture_to_fixture`. Change detection needs two "
        "observations and there is no live collection to produce a second one, "
        "so the preview compares a recorded pair and labels the result rather "
        "than presenting it as a week of monitoring."
    )
    lines.append("")
    lines.append("## Digest preview")
    lines.append("")
    lines.append("```text")
    for key in (
        "cadence",
        "delivery_status",
        "items_total",
        "items_visible",
        "items_suppressed",
        "items_human_review",
        "items_with_unverified_deadlines",
        "items_with_unknown_reporting_burden",
    ):
        lines.append(f"{key:<36}{digest[key]}")
    lines.append("```")
    lines.append("")
    lines.append(
        f"{digest['items_with_unverified_deadlines']} of "
        f"{digest['items_total']} items carry a deadline nobody can vouch for, "
        "and that count is in the header rather than buried per item. A digest "
        "where most deadlines are unverified should say so at the top."
    )
    lines.append("")
    lines.append("| Opportunity | Status | Visible | Review | Deadline verified |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in digest["digest_items"]:
        lines.append(
            f"| `{item['opportunity_id']}` | {item['digest_item_status']} "
            f"| {str(item['visible']).lower()} "
            f"| {str(item['requires_human_review']).lower()} "
            f"| {str(item['deadline_verified']).lower()} |"
        )
    lines.append("")
    lines.append("## Suppression")
    lines.append("")
    lines.append(
        f"{digest['items_suppressed']} item suppressed, **counted not deleted**. "
        "Source history and provenance are preserved, the opportunity stays "
        "visible in the tenant's pursuit pipeline, and no other tenant's digest "
        "is affected."
    )
    lines.append("")
    lines.append("## What is missing before an operational digest")
    lines.append("")
    for key in readiness["operational_components_missing"]:
        lines.append(f"- `{key}`")
    lines.append("")
    lines.append("## What must happen next")
    lines.append("")
    for index, action in enumerate(readiness["next_required_actions"], 1):
        lines.append(f"{index}. `{action['action']}` — {action['why']}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_digest_artifacts(
    *,
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all six files, or refuse and write none."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    bundle = build_digest_artifact_bundle()
    summary_text = render_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise TenantDigestArtifactError(
            "refusing to write tenant digest artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]

    (out_dir / CONTRACT_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "demo_scope": bundle["readiness"]["demo_scope"],
                "cadences": sorted(CADENCES),
                "default_cadence": DEFAULT_CADENCE,
                "delivery_statuses": sorted(DELIVERY_STATUSES),
                "change_types": sorted(CHANGE_TYPES),
                "digest_item_statuses": sorted(DIGEST_ITEM_STATUSES),
                "snapshot_kinds": sorted(SNAPSHOT_KINDS),
                "suppression_statuses": sorted(SUPPRESSION_STATUSES),
                "readiness": bundle["readiness"],
                "change_summary": bundle["change_summary"],
                "suppression_summary": bundle["suppression_summary"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / PREVIEW_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "comparison_kind": bundle["changes"]["comparison_kind"],
                "digest": bundle["digest"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / ITEMS_CSV_NAME).write_text(
        _rows_to_csv(bundle["item_rows"], ITEMS_CSV_COLUMNS), encoding="utf-8"
    )
    (out_dir / CHANGE_CSV_NAME).write_text(
        _rows_to_csv(bundle["change_rows"], CHANGE_CSV_COLUMNS), encoding="utf-8"
    )
    (out_dir / SUPPRESSION_CSV_NAME).write_text(
        _rows_to_csv(bundle["suppression_rows"], SUPPRESSION_CSV_COLUMNS),
        encoding="utf-8",
    )
    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "comparison_kind": bundle["changes"]["comparison_kind"],
            "items_total": bundle["digest"]["items_total"],
            "items_suppressed": bundle["digest"]["items_suppressed"],
            "emails_sent": 0,
            "claim_failures": [],
            "fabricated": False,
        }
    )
