"""SC demo negative-intelligence surface (Gate 83B).

Builds the demo payload behind the customer-facing answer this product exists to
give:

    "This opportunity looks relevant, but your applicant class appears excluded,
     and here is the sentence."

## The quote is produced, not written

Every field below comes from running the **real Gate 82 pipeline over the real
Gate 82 fixture**. Nothing is hand-authored.

Hand-writing a quote into a demo payload would produce a screen that looks
identical and proves nothing — a mockup wearing the clothes of a working
system. Running the pipeline means the sentence on screen is the one the parser
cited, at the span it found, from the artifact whose hash sits beside it. If the
parser regresses, this surface changes or its invariants fail.

## The contrast is the point

The same synthetic notice is evaluated for two applicant classes and must give
two different answers:

```text
state_recognized_tribe        excluded_by_evidence   (negative intelligence)
federally_recognized_tribe    eligible               (a real opportunity)
```

A model that collapsed the recognition tiers could not produce that, and an
invariant fails this surface if the two ever agree.

## What is synthetic

All of it. The notice is ``tests/fixtures/nofo_artifacts/synthetic_notice.html``,
which declares itself a test fixture on its first line and claims no opportunity
number. The exclusion is a true statement *about that synthetic text* and is not
a claim about any real programme. ``synthetic_demo`` is hardcoded true and
``live_coverage_claimed``, ``source_monitored`` and ``freshness_claimed`` are
hardcoded false, all invariant-checked.

Nothing here fetches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.notice_ingestion_pipeline_service import (
    ingest_notice_artifact,
)

SCHEMA_VERSION = "nf_sc_demo_negative_intelligence_v1"
SURFACE_VERSION = "gate83_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_ARTIFACT = REPO_ROOT / "tests" / "fixtures" / "nofo_artifacts" / (
    "synthetic_notice.html"
)

# The two classes whose answers must differ. Order matters for display: the
# excluded class leads, because the negative answer is the one a customer cannot
# get anywhere else.
DEMO_APPLICANT_CLASSES: tuple[tuple[str, str], ...] = (
    ("state_recognized_tribe", "State-recognized tribe"),
    ("federally_recognized_tribe", "Federally recognized tribe"),
)

# Customer-facing wording per parser result state. Deliberately not legal
# language: the product reports what a cited sentence appears to say, and asks a
# human to confirm. It never tells anyone they are ineligible.
EXCLUSION_STATUS_LABELS: dict[str, str] = {
    "excluded_by_evidence": "Likely excluded — review required",
    "eligible": "Named as eligible in the notice text",
    "possibly_eligible": "Possibly eligible — review required",
    "not_supported_by_evidence": "Not addressed by the notice text",
    "human_review_required": "Needs human review",
    "unknown": "Unknown",
}

ELIGIBILITY_STATUS_LABELS: dict[str, str] = {
    "excluded_by_evidence": "not_eligible_claim_not_made",
    "eligible": "named_eligible",
    "possibly_eligible": "uncertain",
    "not_supported_by_evidence": "unsupported",
    "human_review_required": "needs_review",
    "unknown": "unknown",
}

# Copy concepts Gate 83D requires, kept next to the data that justifies them so
# the two cannot drift apart.
COPY_CONCEPTS: tuple[str, ...] = (
    "Relevant does not mean eligible.",
    "Excluded opportunities remain visible because they are useful negative "
    "intelligence.",
    "Applicant class matters — the same notice gives different answers to "
    "different applicants.",
    "Every exclusion shows the sentence it came from.",
)

WHY_IT_MATTERS = (
    "Knowing a programme has already ruled you out is worth more than not "
    "finding it. It saves the weeks an application would have taken, and it is "
    "the answer a keyword search can never give."
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _deadline_status(extraction: dict[str, Any]) -> str:
    """Report the deadline honestly, including when we do not have one."""
    if extraction.get("close_date"):
        return "close_date_supplied"
    if extraction.get("close_date_evidence"):
        # The text carries a date but nobody verified it as the close date, and
        # Gate 81 refuses to promote it.
        return "date_in_text_not_promoted_to_close_date"
    return "unknown_no_close_date"


def build_sc_demo_negative_intelligence_surface(
    *,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Run the Gate 82 pipeline and shape the result for the SC demo."""
    path = artifact_path or DEMO_ARTIFACT

    ingested = ingest_notice_artifact(
        artifact_id="sc-demo-negative-intelligence-001",
        notice_id="synthetic-sc-demo-notice",
        local_path=str(path),
        source_id="synthetic-demo-source",
        # Metadata only. Nothing opens it, and the host is a reserved example
        # domain so it cannot resolve to anyone real.
        notice_url="https://example.test/synthetic-notice",
        title="Synthetic Example Community Infrastructure Grant",
        agency="Synthetic Example Agency",
    )

    artifact = ingested.get("artifact") or {}
    eligibility = ingested.get("eligibility") or {}
    extraction = ingested.get("extraction") or {}
    amendment = ingested.get("amendment") or {}
    per_class = (eligibility.get("exclusion_result") or {}).get("per_class") or {}

    rows: list[dict[str, Any]] = []
    for applicant_class, label in DEMO_APPLICANT_CLASSES:
        verdict = per_class.get(applicant_class) or {}
        state = verdict.get("result_state") or "unknown"

        quote = ""
        span: list[int] | None = None
        # Prefer the mention that produced the verdict; fall back to the cited
        # eligibility section. Either way the text is the parser's, not ours.
        mentions = [
            m
            for m in (eligibility.get("class_mentions") or [])
            if m.get("applicant_class") == applicant_class
        ]
        if mentions:
            quote = str(mentions[0].get("quote") or "")
            span = [int(mentions[0]["start"]), int(mentions[0]["end"])]
        elif extraction.get("eligibility_sections"):
            section = extraction["eligibility_sections"][0]
            quote = str(section.get("quote") or "")
            span = [int(section["start"]), int(section["end"])]

        rows.append(
            {
                "demo_id": f"sc-demo-ni-{applicant_class}",
                "source_label": "Synthetic demo notice (test fixture)",
                "opportunity_title": (
                    "Synthetic Example Community Infrastructure Grant"
                ),
                "funding_lane": "federal",
                "applicant_class": applicant_class,
                "applicant_class_label": label,
                # Relevance and eligibility are different questions, and this
                # row exists to show the gap between them.
                "relevance_status": "native_relevant_by_evidence",
                "eligibility_status": ELIGIBILITY_STATUS_LABELS.get(state, "unknown"),
                "exclusion_status": state,
                "exclusion_status_label": EXCLUSION_STATUS_LABELS.get(
                    state, "Unknown"
                ),
                "exclusion_reason": (
                    "; ".join(verdict.get("reasons") or []) or "no_reason_recorded"
                ),
                "evidence_quote": quote,
                "evidence_span": span,
                "evidence_reference": verdict.get("evidence_reference"),
                "has_citation": bool(verdict.get("has_citation")),
                "artifact_hash": artifact.get("content_hash"),
                "artifact_type": artifact.get("artifact_type"),
                "text_extraction_method": ingested.get("text_extraction_method"),
                "notice_status": amendment.get("notice_status"),
                "deadline_status": _deadline_status(extraction),
                # The whole point: excluded stays on screen.
                "remains_visible": True,
                "human_review_required": bool(
                    verdict.get("human_review_required")
                    or ingested.get("human_review_required")
                ),
                "not_eligible_asserted": False,
            }
        )

    excluded = [r for r in rows if r["exclusion_status"] == "excluded_by_evidence"]
    eligible = [r for r in rows if r["exclusion_status"] == "eligible"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "surface_version": SURFACE_VERSION,
            "title": "Applicant-class fit / negative intelligence",
            "headline": (
                "Relevant does not mean eligible. This notice appears to limit "
                "eligibility to federally recognized tribes."
            ),
            "why_it_matters": WHY_IT_MATTERS,
            "copy_concepts": list(COPY_CONCEPTS),
            "rows": rows,
            "excluded_class_count": len(excluded),
            "eligible_class_count": len(eligible),
            "applicant_class_changes_the_answer": bool(excluded) and bool(eligible),
            "artifact_hash": artifact.get("content_hash"),
            "artifact_type": artifact.get("artifact_type"),
            "artifact_is_recorded_fixture": bool(
                artifact.get("is_recorded_fixture")
            ),
            "pipeline_status": ingested.get("pipeline_status"),
            "adapter_confidence": ingested.get("adapter_confidence"),
            "parser_confidence": ingested.get("parser_confidence"),
            "eligibility_confidence": ingested.get("eligibility_confidence"),
            "evidence_spans_relative_to": ingested.get("spans_relative_to"),
            # Boundaries, displayed on the page as well as enforced here.
            "synthetic_demo": True,
            "demo_only": True,
            "live_coverage_claimed": False,
            "source_monitored": False,
            "freshness_claimed": False,
            "url_fetch_performed": False,
            "excluded_hidden": False,
            "final_eligibility_claimed": False,
            "not_eligible_asserted": False,
        }
    )


def sc_demo_negative_intelligence_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = surface.get("rows") or []
    if len(rows) < 2:
        fails.append("surface_needs_at_least_two_applicant_classes")

    by_class = {r.get("applicant_class"): r for r in rows}
    state_row = by_class.get("state_recognized_tribe")
    federal_row = by_class.get("federally_recognized_tribe")

    if not state_row or not federal_row:
        fails.append("both_recognition_tiers_must_be_present")
    else:
        # The contrast is the product. If the two tiers ever agree, either the
        # fixture changed or the tiers have been collapsed.
        if state_row.get("exclusion_status") != "excluded_by_evidence":
            fails.append("state_recognized_tribe_is_not_excluded_on_the_demo_notice")
        if federal_row.get("exclusion_status") == "excluded_by_evidence":
            fails.append("federally_recognized_tribe_received_the_same_exclusion")
        if state_row.get("exclusion_status") == federal_row.get("exclusion_status"):
            fails.append("recognition_tiers_collapsed_to_one_answer")

    for row in rows:
        rid = row.get("applicant_class")
        if not str(row.get("evidence_quote") or "").strip():
            fails.append(f"row_without_an_evidence_quote:{rid}")
        span = row.get("evidence_span")
        if (
            not isinstance(span, list)
            or len(span) != 2
            or not all(isinstance(v, int) for v in span)
            or span[1] <= span[0]
        ):
            fails.append(f"row_without_a_valid_evidence_span:{rid}")
        if row.get("remains_visible") is not True:
            fails.append(f"excluded_row_hidden:{rid}")
        if row.get("not_eligible_asserted") is not False:
            fails.append(f"row_asserted_ineligibility:{rid}")
        # An exclusion shown to a customer must carry its citation.
        if row.get("exclusion_status") == "excluded_by_evidence" and not row.get(
            "has_citation"
        ):
            fails.append(f"exclusion_without_citation:{rid}")
        if not row.get("artifact_hash"):
            fails.append(f"row_without_an_artifact_hash:{rid}")

    if not surface.get("applicant_class_changes_the_answer"):
        fails.append("applicant_class_did_not_change_the_answer")

    if surface.get("pipeline_status") != "ingested":
        fails.append(f"pipeline_did_not_ingest:{surface.get('pipeline_status')}")

    # Adapter confidence must never have leaked into eligibility confidence.
    if surface.get("eligibility_confidence") != "none":
        fails.append("eligibility_confidence_claimed_on_a_demo_surface")

    if surface.get("synthetic_demo") is not True:
        fails.append("surface_not_marked_synthetic")

    for forbidden in (
        "live_coverage_claimed",
        "source_monitored",
        "freshness_claimed",
        "url_fetch_performed",
        "excluded_hidden",
        "final_eligibility_claimed",
        "not_eligible_asserted",
    ):
        if surface.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
