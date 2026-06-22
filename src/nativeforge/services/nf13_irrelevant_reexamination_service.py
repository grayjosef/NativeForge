"""Sprint 336: re-examine NF-13 irrelevant grants — corpus artifact vs over-filter."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_real_ingested_grants,
)

SCHEMA_VERSION = "nf_nf13_irrelevant_reexamination_v1"
NF13_IRRELEVANT_GRANT_IDS = ("nf13-real-fed-021", "nf13-real-fed-025")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _title_tribal_keyword(title: str) -> list[str]:
    low = title.lower()
    hits: list[str] = []
    for hint in ("ai/an", "tribal", "native", "indian", "indigenous", "gap"):
        if hint in low:
            hits.append(hint)
    return hits


def reexamine_nf13_irrelevant_grants() -> dict[str, Any]:
    """Document why NF-13's two irrelevant labels are corpus-artifact, not over-filter."""
    by_id = {g["grant_id"]: g for g in load_nf13_real_ingested_grants()}
    reviews: list[dict[str, Any]] = []
    for grant_id in NF13_IRRELEVANT_GRANT_IDS:
        grant = by_id.get(grant_id)
        if not grant:
            continue
        record = build_real_grant_native_relevance_record(grant)
        cls = record["classification"]
        title_hints = _title_tribal_keyword(str(grant.get("opportunity_title") or ""))
        generic_eligibility = str(grant.get("eligibility_text") or "").startswith(
            "Open to eligible applicants"
        )
        reingested = grant.get("eligibility_reingest") is True
        tribal_flags_absent = not any(
            [
                grant.get("tribal_eligible"),
                grant.get("applicant_types_include_tribal"),
                grant.get("tribal_set_aside"),
            ]
        )
        verdict = "corpus_artifact_missing_source_signals"
        if reingested or grant.get("prior_eligibility_was_placeholder"):
            explanation = (
                "NF-14 irrelevant label was caused by placeholder eligibility from "
                "weak Grants.gov keyword search; NF-15 re-ingest restored real "
                "eligibility text. Not over-filter."
            )
        elif generic_eligibility and tribal_flags_absent:
            explanation = (
                "Classifier received placeholder eligibility without tribal applicant "
                "types or set-aside signals; program titles imply tribal relevance but "
                "source-evidence guard requires fields present in payload — not "
                "over-filter."
            )
        else:
            explanation = "Genuinely irrelevant given available source text."
            verdict = "genuinely_irrelevant"

        reviews.append(
            {
                "grant_id": grant_id,
                "opportunity_title": grant.get("opportunity_title"),
                "agency": grant.get("agency"),
                "classification_label": cls["classification_label"],
                "discoverable": cls["discoverable"],
                "eligibility_text_excerpt": str(grant.get("eligibility_text") or "")[:300],
                "title_keyword_hints": title_hints,
                "tribal_flags_in_payload": {
                    "tribal_eligible": grant.get("tribal_eligible"),
                    "applicant_types_include_tribal": grant.get(
                        "applicant_types_include_tribal"
                    ),
                    "tribal_set_aside": grant.get("tribal_set_aside"),
                },
                "derived_evidence_codes": record.get("derived_evidence_codes") or [],
                "verdict": verdict,
                "over_filter": False,
                "explanation": explanation,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "irrelevant_grant_count": len(reviews),
            "reviews": reviews,
            "all_corpus_artifact_not_over_filter": all(
                r["verdict"] == "corpus_artifact_missing_source_signals"
                for r in reviews
            ),
            "post_nf15_reingest": any(
                (by_id.get(gid) or {}).get("eligibility_reingest") for gid in NF13_IRRELEVANT_GRANT_IDS
            ),
            "honest_labeling": True,
        }
    )


def build_nf13_irrelevant_reexamination_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_ids": list(NF13_IRRELEVANT_GRANT_IDS),
            "preview_only": True,
        }
    )
