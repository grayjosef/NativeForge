"""Critical-path coverage map for Gate 06 / Block 17."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_critical_path_coverage_map_v1"

# Classification: strong | adequate | partial | weak | untested | unknown
CRITICAL_PATHS: tuple[dict[str, Any], ...] = (
    {
        "path_id": "sc_customer_demo_route",
        "label": "SC customer demo route",
        "classification": "strong",
        "evidence": [
            "ScCustomerDemoPage.test.tsx",
            "sc_customer_demo.smoke.spec.ts",
            "sc_monday_demo_bridge_service",
        ],
    },
    {
        "path_id": "opportunity_engine",
        "label": "Opportunity engine",
        "classification": "adequate",
        "evidence": ["campaign block01 smokes", "bridge invariants"],
    },
    {
        "path_id": "eligibility_evidence",
        "label": "Eligibility evidence",
        "classification": "adequate",
        "evidence": ["campaign block02", "demo panel assertions"],
    },
    {
        "path_id": "org_memory",
        "label": "Organization evidence memory",
        "classification": "adequate",
        "evidence": ["organization_evidence_memory_*", "campaign08"],
    },
    {
        "path_id": "pursuit_workspace",
        "label": "Pursuit workspace",
        "classification": "adequate",
        "evidence": ["pursuit_workspace_assembler", "campaign03"],
    },
    {
        "path_id": "evidence_binder",
        "label": "Evidence binder",
        "classification": "partial",
        "evidence": ["pursuit binder fields; fewer dedicated isolation tests"],
    },
    {
        "path_id": "checklist",
        "label": "Application checklist",
        "classification": "adequate",
        "evidence": ["application_plan_workspace"],
    },
    {
        "path_id": "intake_approvals",
        "label": "Intake / approvals",
        "classification": "adequate",
        "evidence": ["intake_approval_workspace"],
    },
    {
        "path_id": "narrative_budget",
        "label": "Narrative / budget scaffold",
        "classification": "adequate",
        "evidence": ["narrative_budget_scaffold; budget fabrication guards"],
    },
    {
        "path_id": "readiness_queue",
        "label": "Readiness / operator queue",
        "classification": "adequate",
        "evidence": ["package_readiness_queue"],
    },
    {
        "path_id": "nofo_extraction_pilot",
        "label": "NOFO extraction pilot",
        "classification": "adequate",
        "evidence": ["nofo_extraction_pilot_*; no full PDF claim"],
    },
    {
        "path_id": "source_freshness_pilot",
        "label": "Source freshness pilot",
        "classification": "adequate",
        "evidence": ["source_freshness_pilot_*; external live not claimed"],
    },
    {
        "path_id": "draft_workspace",
        "label": "Draft workspace",
        "classification": "adequate",
        "evidence": ["draft_workspace_*; AI drafting disabled"],
    },
    {
        "path_id": "controlled_drafting",
        "label": "Controlled drafting v0",
        "classification": "strong",
        "evidence": ["evidence_cited_drafting; $ fabrication fail"],
    },
    {
        "path_id": "ai_governance",
        "label": "AI governance / QA gates",
        "classification": "strong",
        "evidence": ["proposal_qa_gate; personalization checker"],
    },
    {
        "path_id": "feedback_report_hooks",
        "label": "Feedback / report hooks",
        "classification": "adequate",
        "evidence": ["feedback_loop_assembler; report contract"],
    },
    {
        "path_id": "slack_alert_plumbing",
        "label": "Slack alert plumbing",
        "classification": "adequate",
        "evidence": ["feedback_slack_alert_service; dry-run default"],
    },
    {
        "path_id": "collaboration_dark_flags",
        "label": "Collaboration dark flags",
        "classification": "adequate",
        "evidence": ["collaboration_dark_flag_service"],
    },
    {
        "path_id": "package_export_preview",
        "label": "Package export preview",
        "classification": "adequate",
        "evidence": ["package_export_preview_*; export_allowed=false"],
    },
    {
        "path_id": "forms_attachments_map",
        "label": "Forms / attachments mapping",
        "classification": "adequate",
        "evidence": ["forms_attachments_*; completion/persistence false"],
    },
)


def build_critical_path_coverage_map() -> dict[str, Any]:
    paths = [dict(p) for p in CRITICAL_PATHS]
    by_class: dict[str, int] = {}
    for p in paths:
        c = str(p["classification"])
        by_class[c] = by_class.get(c, 0) + 1
    weakest = [
        p
        for p in paths
        if p["classification"] in {"weak", "untested", "partial", "unknown"}
    ]
    strongest = [p for p in paths if p["classification"] in {"strong", "adequate"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_block": 17,
        "path_count": len(paths),
        "paths": paths,
        "classification_counts": by_class,
        "strongest_areas": [p["path_id"] for p in strongest if p["classification"] == "strong"],
        "weakest_areas": [p["path_id"] for p in weakest],
        "recommended_block18_focus": [
            "prompt injection / adversarial fixtures",
            "cross-profile data isolation",
            "Slack message injection escaping",
            "QA / claim / export bypass resistance",
            "HTML/script rendering safety",
        ],
        "full_suite_run": False,
        "full_suite_passed": False,
        "pen_test_ready_claimed": False,
        "notes": [
            "Map is expert/heuristic based on Gate 01–05 shipped tests + smokes.",
            "Not a coverage.py percentage report.",
            "Evidence binder remains partial — isolation tests prioritized in Block 18.",
        ],
    }


def critical_path_coverage_map_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("pen_test_ready_claimed") is True:
        fails.append("pen_test_ready_claimed")
    if (report.get("path_count") or 0) < 10:
        fails.append("too_few_paths")
    return fails


def write_critical_path_coverage_report(
    report: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = report if report is not None else build_critical_path_coverage_map()
    out = path or Path("docs/operations/150_CRITICAL_PATH_COVERAGE_MAP.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Critical-Path Coverage Map (Gate 06 / Block 17)",
        "",
        f"Schema: `{doc.get('schema_version')}`",
        "",
        f"Paths mapped: **{doc.get('path_count')}**",
        "",
        f"Classification counts: `{json.dumps(doc.get('classification_counts') or {})}`",
        "",
        "## Paths",
        "",
    ]
    for p in doc.get("paths") or []:
        lines.append(
            f"- **{p['path_id']}** ({p['classification']}): {p['label']} — "
            f"{', '.join(p.get('evidence') or [])}"
        )
    lines.extend(
        [
            "",
            "## Strongest",
            "",
            *(f"- {x}" for x in (doc.get("strongest_areas") or [])),
            "",
            "## Weakest / partial",
            "",
            *(f"- {x}" for x in (doc.get("weakest_areas") or []) or ["(none marked weak)"]),
            "",
            "## Recommended Block 18 focus",
            "",
            *(f"- {x}" for x in (doc.get("recommended_block18_focus") or [])),
            "",
            "## Honesty",
            "",
            f"- full_suite_run: `{doc.get('full_suite_run')}`",
            f"- pen_test_ready_claimed: `{doc.get('pen_test_ready_claimed')}`",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
