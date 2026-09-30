"""Gate 173 calibration report — gold corpus + error taxonomy (methodology 2026.09.1)."""

from __future__ import annotations

from typing import Any

from nativeforge.services.native_relevance_gold_corpus_service import (
    RELEVANT_TRUTH,
    corpus,
    run_corpus,
)
from nativeforge.services.native_relevance_ontology_service import (
    APPLICANT_RELEVANT,
    ONTOLOGY_VERSION,
)

SCHEMA_VERSION = "nf_gate173_calibration_v1"


def _categorize_row(row: dict[str, Any]) -> str:
    if row.get("hard_negative"):
        return "negative_control"
    expected = set(row.get("expected_classes") or [])
    if expected & set(APPLICANT_RELEVANT):
        return "positive_control"
    if expected & RELEVANT_TRUTH:
        return "positive_control_beneficiary"
    if expected == {"UNCERTAIN"} or (
        expected & RELEVANT_TRUTH and expected - RELEVANT_TRUTH
    ):
        return "hard_case"
    return "negative_control"


def _error_taxonomy_for_row(result: dict[str, Any]) -> str | None:
    if result.get("class_correct"):
        return None
    if result.get("actual_class") == "UNCERTAIN" and result.get("truth_is_relevant"):
        return "classifier_rule_too_restrictive_or_missing_evidence"
    if result.get("actual_candidate") == "NOT_CANDIDATE" and result.get(
        "truth_is_relevant"
    ):
        return "candidate_false_negative"
    if result.get("model_says_relevant") and not result.get("truth_is_relevant"):
        return "classifier_false_positive"
    return "other"


def build_gate173_calibration_report() -> dict[str, Any]:
    """Run unchanged methodology 2026.09.1 against the gold calibration corpus."""
    metrics = run_corpus()
    rows = corpus()
    by_key = {row["key"]: row for row in rows}
    categorized: dict[str, list[str]] = {
        "positive_control": [],
        "positive_control_beneficiary": [],
        "negative_control": [],
        "hard_case": [],
    }
    for row in rows:
        categorized[_categorize_row(row)].append(row["key"])

    errors: dict[str, str] = {}
    for result in metrics.get("results") or []:
        cause = _error_taxonomy_for_row(result)
        if cause:
            errors[result["key"]] = cause

    positives = [
        r
        for r in metrics.get("results") or []
        if r.get("truth_is_relevant") and not r.get("truth_is_ambiguous")
    ]
    negatives = [
        r for r in metrics.get("results") or [] if not r.get("truth_is_relevant")
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "relevance_methodology_version": ONTOLOGY_VERSION,
        "classifier_changed": False,
        "calibration_corpus": {
            "source": "native_relevance_gold_corpus_service.corpus",
            "size": len(rows),
            "positive_controls": categorized["positive_control"],
            "positive_controls_beneficiary": categorized[
                "positive_control_beneficiary"
            ],
            "negative_controls": categorized["negative_control"],
            "hard_cases": categorized["hard_case"],
            "every_row_has_why": all(row.get("why") for row in rows),
        },
        "metrics": {
            "positive_controls_total": len(positives),
            "positive_controls_correct": sum(
                1 for r in positives if r.get("model_says_relevant")
            ),
            "negative_controls_total": len(negatives),
            "negative_controls_correct": sum(
                1 for r in negatives if not r.get("model_says_relevant")
            ),
            "false_negatives": metrics.get("false_negatives") or [],
            "false_positives": metrics.get("false_positives") or [],
            "precision": metrics.get("classification_precision"),
            "recall": metrics.get("classification_recall"),
            "candidate_recall": metrics.get("candidate_recall"),
        },
        "error_taxonomy": errors,
        "calibration_result": (
            "CLASSIFIER_RECALL_GAP"
            if metrics.get("false_negatives")
            else "CORRECT_ON_GOLD_CORPUS"
        ),
        "row_provenance": {
            key: {
                "why": by_key[key]["why"],
                "expected_classes": by_key[key]["expected_classes"],
                "set_reason": by_key[key].get("set_reason") or "",
            }
            for key in by_key
        },
    }
