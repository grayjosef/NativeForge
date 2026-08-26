"""Software-allowability source classifier (Gate 90E).

Ranks registry sources by how plausibly an award from them could pay for
capability-development software like NativeForge.

## This is a sales/discovery prioritisation aid. It is not legal advice.

Nothing here establishes that any customer may buy anything. 2 CFR 200 permits
costs that are necessary, reasonable and allocable - it does not make a product
allowable because it is useful, and the dossier is explicit that allowability
belongs at the **opportunity + budget-category** level with program-family
defaults no stronger than "sometimes allowable".

So the strongest thing this classifier can say about a *source* is that it is
worth looking at. Every result carries
``requires_live_nofo_and_approved_budget: True``.

## Reads only the registry row

``software_cost_allowability``, ``program_examples``, ``source_type`` and
``notes`` - all committed CSV values. No inference from agency reputation, no
lookup, no fetch.

## `clearly_allowable` is reachable and currently empty

The bucket exists because the vocabulary should be complete, and nothing in the
current seed reaches it: the strongest value in 55 rows is "Likely allowable",
on three rows. An empty top bucket is the honest outcome of a dossier that
deliberately refused to assert one, not a gap in the classifier.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_software_allowability_source_v1"

ALLOWABILITY_CLASSES = frozenset(
    {
        "clearly_allowable",
        "likely_allowable",
        "sometimes_allowable",
        "unclear",
        "unlikely_allowable",
        "unknown",
    }
)

# Classes strong enough to put a source on a watchlist. Deliberately excludes
# `sometimes_allowable`: 44 of 55 rows are "sometimes", so a watchlist that
# included them would be the registry with extra steps.
WATCHLIST_CLASSES = frozenset({"clearly_allowable", "likely_allowable"})

# Classes that must never be read as "the customer can buy software".
NON_AFFIRMATIVE_CLASSES = frozenset(
    {"sometimes_allowable", "unclear", "unlikely_allowable", "unknown"}
)

# Source types that describe historical award data rather than a funding route.
AWARD_DATABASE_TYPES = frozenset({"award_database"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalise(text: Any) -> str:
    return str(text or "").strip().lower()


def classify_software_allowability(*, source: dict[str, Any]) -> dict[str, Any]:
    """Classify one registry row. Reads the row and nothing else."""
    raw = str(source.get("software_cost_allowability") or "").strip()
    lowered = _normalise(raw)
    source_type = _normalise(source.get("source_type"))
    program_examples = str(source.get("program_examples") or "")
    notes = str(source.get("notes") or "")

    explanation: list[str] = []
    blocked: list[str] = []

    if not raw:
        classification = "unknown"
        explanation.append("registry row carries no allowability value")
    elif raw == "UNKNOWN":
        # Preserved, never coerced.
        classification = "unknown"
        explanation.append("registry row records UNKNOWN")
    elif lowered.startswith("not applicable"):
        classification = "unlikely_allowable"
        explanation.append(f"registry row reads {raw!r}")
        if source_type in AWARD_DATABASE_TYPES:
            explanation.append(
                "source is an award database, not a funding route - it reports "
                "past awards and cannot itself pay for anything"
            )
    elif lowered.startswith("clearly"):
        classification = "clearly_allowable"
        explanation.append(f"registry row reads {raw!r}")
    elif lowered.startswith("likely"):
        classification = "likely_allowable"
        explanation.append(f"registry row reads {raw!r}")
    elif lowered.startswith("sometimes"):
        classification = "sometimes_allowable"
        explanation.append(f"registry row reads {raw!r}")
    elif lowered.startswith("unclear") or lowered.startswith("varies"):
        # "Varies" and "Unclear" are both refusals to commit, and are kept as
        # `unclear` rather than promoted to `sometimes`.
        classification = "unclear"
        explanation.append(f"registry row reads {raw!r}, which does not commit")
    else:
        classification = "unknown"
        explanation.append(f"unrecognised allowability value {raw!r}")

    if program_examples:
        explanation.append(f"program examples: {program_examples[:120]}")
    if notes:
        explanation.append(f"registry notes: {notes[:120]}")

    if classification in NON_AFFIRMATIVE_CLASSES:
        blocked.append(f"not_an_affirmative_allowability_finding:{classification}")
    blocked.append("requires_live_nofo_and_approved_budget")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source.get("source_id"),
            "source_name": source.get("source_name"),
            "priority_tier": source.get("priority_tier"),
            "raw_allowability_value": raw,
            "allowability_class": classification,
            "on_watchlist": classification in WATCHLIST_CLASSES,
            "explanation": explanation,
            "blocked_reasons": blocked,
            # Constants. No source-level classification can establish these.
            "customer_may_purchase_software": False,
            "requires_live_nofo_and_approved_budget": True,
            "is_legal_advice": False,
            "fabricated": False,
        }
    )


def build_software_allowability_watchlist(
    *, sources: list[dict[str, Any]]
) -> dict[str, Any]:
    results = [classify_software_allowability(source=s) for s in sources]

    by_class = {c: 0 for c in sorted(ALLOWABILITY_CLASSES)}
    for r in results:
        by_class[r["allowability_class"]] += 1

    watchlist = [r for r in results if r["on_watchlist"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total_sources": len(results),
            "by_allowability_class": by_class,
            "watchlist_count": len(watchlist),
            "watchlist": watchlist,
            "classifications": results,
            "customer_may_purchase_software": False,
            "is_legal_advice": False,
            "fabricated": False,
        }
    )


def allowability_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if result.get("is_legal_advice") is not False:
        fails.append("classifier_claimed_to_be_legal_advice")
    if result.get("customer_may_purchase_software") is not False:
        fails.append("classifier_claimed_a_purchase_is_permitted")

    single = "allowability_class" in result
    entries = [result] if single else (result.get("classifications") or [])

    for entry in entries:
        sid = entry.get("source_id")
        cls = entry.get("allowability_class")
        if cls not in ALLOWABILITY_CLASSES:
            fails.append(f"allowability_class_out_of_vocabulary:{cls}")
        if entry.get("requires_live_nofo_and_approved_budget") is not True:
            fails.append(f"missing_nofo_precondition:{sid}")
        if entry.get("customer_may_purchase_software") is not False:
            fails.append(f"purchase_permitted_claimed:{sid}")
        if not entry.get("explanation"):
            fails.append(f"classification_without_explanation:{sid}")
        # A watchlist entry must come from an affirmative class.
        if entry.get("on_watchlist") and cls not in WATCHLIST_CLASSES:
            fails.append(f"watchlisted_from_non_affirmative_class:{sid}")
        # "Sometimes" must never be silently promoted.
        if cls == "sometimes_allowable" and entry.get("on_watchlist"):
            fails.append(f"sometimes_promoted_to_watchlist:{sid}")

    return fails
