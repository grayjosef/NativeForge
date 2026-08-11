"""CLI/static visibility layer for NM/WA operator surfacing demo artifacts.

Offline-only. No auth changes. No production routes. Renderable HTML + text.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)

SCHEMA_VERSION = "nf_nm_wa_operator_surfacing_demo_render_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_visibility_payload(
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sprint 021: serializable demo visibility payload for CLI/HTML."""
    a = artifact if artifact is not None else build_demo_artifact()
    combined = a["combined_review_queue"]
    rows = combined["rows"]
    sample = rows[:5]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "NM/WA Operator Surfacing Demo (offline)",
            "offline_only": True,
            "demo_dev_only": True,
            "final_eligibility_claim_allowed": False,
            "nm_profile_count": a["fixtures"]["nm_profile_count"],
            "wa_profile_count": a["fixtures"]["wa_profile_count"],
            "combined_profile_count": combined["combined_profile_count"],
            "combined_review_needed_count": combined["combined_review_needed_count"],
            "combined_missing_data_count": combined["combined_missing_data_count"],
            "missing_data_summary": a["missing_data_summary"],
            "provenance_evidence_summary": a["provenance_evidence_summary"],
            "operator_next_check_summary": a["operator_next_check_summary"],
            "confidence_distribution": combined["combined_confidence_distribution"],
            "sample_rows": sample,
            "content_digest": a["content_digest"],
        }
    )


def render_demo_text_report(payload: dict[str, Any] | None = None) -> str:
    """Sprint 022: plain-text operator demo report."""
    p = payload if payload is not None else build_demo_visibility_payload()
    lines = [
        p["title"],
        f"schema={p['schema_version']}",
        f"offline_only={p['offline_only']} demo_dev_only={p['demo_dev_only']}",
        f"NM={p['nm_profile_count']} WA={p['wa_profile_count']} "
        f"combined={p['combined_profile_count']}",
        f"review_needed={p['combined_review_needed_count']} "
        f"missing_data_rows={p['combined_missing_data_count']}",
        f"final_eligibility_claim_allowed={p['final_eligibility_claim_allowed']}",
        f"next_checks_present={p['operator_next_check_summary']['rows_with_next_checks']}",
        f"content_digest={p['content_digest']}",
        "",
        "Sample rows (first 5):",
    ]
    for r in p["sample_rows"]:
        lines.append(
            f"- {r.get('state_cohort')}:{r.get('profile_id')} "
            f"readiness={r.get('match_readiness_label')} "
            f"human_review={r.get('human_review_required')} "
            f"missing={len(r.get('missing_data') or [])} "
            f"next_checks={len(r.get('operator_next_check') or [])}"
        )
    return "\n".join(lines) + "\n"


def render_demo_html_report(payload: dict[str, Any] | None = None) -> str:
    """Sprint 023: minimal static HTML demo report (no auth, no production route)."""
    p = payload if payload is not None else build_demo_visibility_payload()
    rows_html = []
    for r in p["sample_rows"]:
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('state_cohort')))}</td>"
            f"<td>{html.escape(str(r.get('profile_id')))}</td>"
            f"<td>{html.escape(str(r.get('match_readiness_label')))}</td>"
            f"<td>{html.escape(str(r.get('human_review_required')))}</td>"
            f"<td>{html.escape(str(r.get('missing_data')))}</td>"
            f"<td>{html.escape(str(r.get('operator_next_check')))}</td>"
            "</tr>"
        )
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(p["title"])}</title>
<style>
body {{ font-family: Georgia, serif; margin: 2rem; background: #f7f3ea; color: #1c1a17; }}
h1 {{ font-size: 1.6rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #b7a98a; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #e8dfc8; }}
.meta {{ margin: 0.4rem 0; }}
.flag {{ color: #6b3b1f; font-weight: 600; }}
</style>
</head>
<body>
<h1>{html.escape(p["title"])}</h1>
<p class="meta flag">demo_dev_only / offline_synthetic — not a production surface</p>
<p class="meta">NM={p["nm_profile_count"]} WA={p["wa_profile_count"]} combined={p["combined_profile_count"]}</p>
<p class="meta">review_needed={p["combined_review_needed_count"]} missing_data_rows={p["combined_missing_data_count"]}</p>
<p class="meta">final_eligibility_claim_allowed={p["final_eligibility_claim_allowed"]}</p>
<p class="meta">content_digest={html.escape(p["content_digest"])}</p>
<table>
<thead><tr>
<th>State</th><th>Profile</th><th>Readiness</th><th>Human review</th><th>Missing data</th><th>Next checks</th>
</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</body>
</html>
"""
    return body


def write_demo_html_report(
    path: Path | str,
    *,
    artifact: dict[str, Any] | None = None,
) -> str:
    """Sprint 024: write static HTML demo report to local path."""
    payload = build_demo_visibility_payload(artifact)
    html_doc = render_demo_html_report(payload)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return html_doc
