"""Security posture inventory (Gate 06 / Block 18). No secrets printed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_security_posture_inventory_v1"

# status: implemented | partial | missing | not_applicable | unknown
POSTURE_ITEMS: tuple[dict[str, str], ...] = (
    {
        "item_id": "demo_route_isolation",
        "label": "Demo/real data-mode isolation on SC route",
        "status": "implemented",
        "notes": "Bridge flags live_ingestion/source_activation false",
    },
    {
        "item_id": "api_authz_surface",
        "label": "API endpoint authz inventory",
        "status": "partial",
        "notes": "Existing app routes not expanded this gate; demo is static JSON",
    },
    {
        "item_id": "customer_org_isolation",
        "label": "Customer/org profile isolation",
        "status": "partial",
        "notes": "Attribution checks + Block 18 isolation tests; no multi-tenant DB gate",
    },
    {
        "item_id": "generated_text_rendering",
        "label": "Generated text rendering safety",
        "status": "partial",
        "notes": "React text nodes default-escape; no dangerouslySetInnerHTML on demo",
    },
    {
        "item_id": "feedback_input_handling",
        "label": "Feedback report input validation/bounds",
        "status": "implemented",
        "notes": "Enums + sanitization + size bounds in Gate 06 hardening",
    },
    {
        "item_id": "slack_alert_formatting",
        "label": "Slack message injection resistance",
        "status": "implemented",
        "notes": "Escape backticks/control chars; never fake sent",
    },
    {
        "item_id": "collaboration_dark_flags",
        "label": "Collaboration dark-flag defaults",
        "status": "implemented",
        "notes": "All live claims forced false",
    },
    {
        "item_id": "package_export_overclaim",
        "label": "Package export overclaim resistance",
        "status": "implemented",
        "notes": "export_allowed/final_export forced false under blockers",
    },
    {
        "item_id": "forms_upload_overclaim",
        "label": "Forms/upload persistence overclaim resistance",
        "status": "implemented",
        "notes": "completion/persistence/upload forced false",
    },
    {
        "item_id": "secret_handling",
        "label": "Secret handling / no env dump",
        "status": "implemented",
        "notes": "Inventory/security reports never print env values",
    },
    {
        "item_id": "logging_redaction",
        "label": "Logging redaction",
        "status": "partial",
        "notes": "No new broad logger; avoid webhook URL logging",
    },
    {
        "item_id": "cors_security_headers",
        "label": "CORS / security headers",
        "status": "unknown",
        "notes": "Not re-audited this gate for production deploy headers",
    },
    {
        "item_id": "dependency_risk",
        "label": "Dependency vulnerability scan",
        "status": "missing",
        "notes": "No automated SCA run claimed this gate",
    },
    {
        "item_id": "prompt_injection_resistance",
        "label": "Prompt/adversarial injection resistance",
        "status": "partial",
        "notes": "Fixtures + governance/QA block unsupported prose; not exhaustive",
    },
    {
        "item_id": "qa_bypass_resistance",
        "label": "QA / claim flag bypass resistance",
        "status": "implemented",
        "notes": "Invariant suite + adversarial bypass tests",
    },
)


def build_security_posture_inventory() -> dict[str, Any]:
    items = [dict(x) for x in POSTURE_ITEMS]
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_block": 18,
        "item_count": len(items),
        "items": items,
        "status_counts": counts,
        "pen_test_passed_claimed": False,
        "production_secure_claimed": False,
        "all_vulnerabilities_fixed_claimed": False,
        "notes": [
            "Defensive inventory only — not a pen-test certificate.",
            "Do not claim NativeForge passed pen testing.",
            "Secrets and environment variable values are never included.",
        ],
    }


def security_posture_inventory_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "pen_test_passed_claimed",
        "production_secure_claimed",
        "all_vulnerabilities_fixed_claimed",
    ):
        if report.get(key) is True:
            fails.append(key)
    if (report.get("item_count") or 0) < 5:
        fails.append("too_few_items")
    return fails


def write_security_posture_report(
    report: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = report if report is not None else build_security_posture_inventory()
    out = path or Path("docs/operations/151_SECURITY_POSTURE_INVENTORY.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Security Posture Inventory (Gate 06 / Block 18)",
        "",
        f"Schema: `{doc.get('schema_version')}`",
        "",
        f"Items: **{doc.get('item_count')}**",
        f"Status counts: `{json.dumps(doc.get('status_counts') or {})}`",
        "",
        "## Items",
        "",
    ]
    for it in doc.get("items") or []:
        lines.append(
            f"- **{it['item_id']}** [{it['status']}]: {it['label']} — {it['notes']}"
        )
    lines.extend(
        [
            "",
            "## Honesty",
            "",
            f"- pen_test_passed_claimed: `{doc.get('pen_test_passed_claimed')}`",
            f"- production_secure_claimed: `{doc.get('production_secure_claimed')}`",
            "",
            "## Notes",
            "",
            *(f"- {n}" for n in (doc.get("notes") or [])),
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
