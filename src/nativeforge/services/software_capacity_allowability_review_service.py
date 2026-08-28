"""Software / capacity cost allowability review (Gate 103F).

Assesses whether software, grant administration, compliance, reporting, data
infrastructure or capacity-development costs **may be** allowable under a given
opportunity.

## Six labels, and what they are allowed to rest on

```text
clearly_allowable      the source text names this cost type as allowable
likely_allowable       the source text names a close category
possibly_allowable     the source text is permissive but not specific
not_indicated          the source says nothing either way
likely_not_allowable   the source text excludes this cost type
requires_human_review  consequential, contested, or self-assessed
```

**No label above `not_indicated` may be reached without evidence.** Evidence is
a quote or a reference from the opportunity's own text, carried on the result.
An assessment with no evidence is `not_indicated`, never a hopeful
`possibly_allowable`, and an invariant fails any affirmative label whose evidence
list is empty.

The permitted wording is *may be allowable* / *appears potentially allowable* /
*requires human review* / *not indicated*. Never "this cost is allowable"
without supporting source text, and never "NativeForge is always grant-funded" —
`PROHIBITED_CLAIMS` records both and an invariant scans rendered claims for them.

## The self-assessment cap

**When the assessed cost is NativeForge itself, the label is capped at
`requires_human_review` regardless of how strong the evidence is.**

A tool that tells a customer buying the tool is grant-allowable has an obvious
incentive problem. A self-assessment that can only ever return "ask a human" is
defensible; one that can return "clearly allowable" is not, however good the
citation. The cap is applied after classification, the pre-cap label is retained
as `uncapped_label` so nothing is hidden, and an invariant fails any self-assessed
result that escaped it.

This is the one place in Gate 103 that removes a capability rather than adding
one, and it is deliberate.

## Bridged, not forked

`nativeforge_software_allowability_source_service` (Gate 92) already classifies
**sources** — *does this funding source ever allow software costs?* This service
answers a different question — *may this cost type be allowable under this
opportunity?* — and the two vocabularies differ:

```text
source-level (Gate 92)    review-level (here)
clearly_allowable      -> clearly_allowable
likely_allowable       -> likely_allowable
sometimes_allowable    -> possibly_allowable
unclear                -> requires_human_review
unlikely_allowable     -> likely_not_allowable
unknown                -> not_indicated
```

`SOURCE_CLASS_TO_REVIEW_LABEL` holds that mapping explicitly so the two cannot
drift, and a test asserts it covers every source class. Gate 92's service is not
modified — 55 registry rows and its own tests depend on it.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nativeforge_software_allowability_source_service import (
    ALLOWABILITY_CLASSES as SOURCE_ALLOWABILITY_CLASSES,
)

SCHEMA_VERSION = "nf_software_capacity_allowability_review_v1"

ALLOWABILITY_LABELS = frozenset(
    {
        "clearly_allowable",
        "likely_allowable",
        "possibly_allowable",
        "not_indicated",
        "likely_not_allowable",
        "requires_human_review",
    }
)

# Labels that assert something positive and therefore require evidence.
AFFIRMATIVE_LABELS = frozenset(
    {"clearly_allowable", "likely_allowable", "possibly_allowable"}
)

# Labels reachable without evidence, because they assert nothing.
NON_AFFIRMATIVE_LABELS = ALLOWABILITY_LABELS - AFFIRMATIVE_LABELS

# The cap for a self-assessment. Also the honest answer when a source is
# contested.
SELF_ASSESSMENT_CAP = "requires_human_review"

# Gate 92's source classes mapped to this service's labels. Explicit so the two
# vocabularies cannot drift apart silently.
SOURCE_CLASS_TO_REVIEW_LABEL: dict[str, str] = {
    "clearly_allowable": "clearly_allowable",
    "likely_allowable": "likely_allowable",
    "sometimes_allowable": "possibly_allowable",
    "unclear": "requires_human_review",
    "unlikely_allowable": "likely_not_allowable",
    "unknown": "not_indicated",
}

COST_TYPES = frozenset(
    {
        "software_license",
        "grant_administration",
        "compliance_infrastructure",
        "reporting_infrastructure",
        "data_document_infrastructure",
        "capacity_development",
        "program_support",
        "indirect_cost",
        "unknown",
    }
)

# Cost types that are NativeForge itself. Assessing these caps at human review.
SELF_ASSESSED_COST_TYPES = frozenset(
    {"software_license", "compliance_infrastructure", "reporting_infrastructure"}
)

# Claims this service must never render. Declared as a blocklist, which means a
# text scanner run over this file would flag the declaration itself - Gate 93
# hit exactly that, and its scanner had to learn to skip declared blocklists.
PROHIBITED_CLAIMS: tuple[str, ...] = (
    "nativeforge is always grant-funded",
    "this cost is allowable",
    "guaranteed allowable",
    "always allowable",
)

# The permitted phrasing, per the product requirement.
PERMITTED_PHRASING: dict[str, str] = {
    "clearly_allowable": "the source text names this cost type as allowable",
    "likely_allowable": "appears potentially allowable - the source names a "
    "close category",
    "possibly_allowable": "may be allowable - the source is permissive but not "
    "specific",
    "not_indicated": "not indicated - the source says nothing either way",
    "likely_not_allowable": "the source text appears to exclude this cost type",
    "requires_human_review": "requires human review",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def review_label_for_source_class(source_class: Any) -> str:
    """Bridge a Gate 92 source class to a review label.

    Two different unknowns, both landing on human review but for different
    reasons worth telling apart:

    - a class Gate 92 defines that this bridge has no mapping for means the two
      vocabularies have drifted, which is a bug here
    - a string that is not a Gate 92 class at all is somebody else's value

    `SOURCE_ALLOWABILITY_CLASSES` is imported to make the first case detectable
    rather than silently identical to the second.
    """
    text = str(source_class or "").strip()
    mapped = SOURCE_CLASS_TO_REVIEW_LABEL.get(text)
    if mapped is not None:
        return mapped
    return "requires_human_review"


def bridge_coverage_gaps() -> list[str]:
    """Gate 92 classes this bridge has no mapping for. Empty means no drift."""
    return sorted(SOURCE_ALLOWABILITY_CLASSES - set(SOURCE_CLASS_TO_REVIEW_LABEL))


def build_allowability_review(
    *,
    opportunity_id: Any,
    assessed_cost_type: Any = None,
    is_nativeforge_itself: bool = False,
    evidence_quotes: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    source_allowability_class: Any = None,
    proposed_label: Any = None,
) -> dict[str, Any]:
    """One cost-type assessment. Evidence-backed, and capped when self-assessed."""
    cost_type = _norm(assessed_cost_type, COST_TYPES, fallback="unknown")

    quotes = [str(q).strip() for q in (evidence_quotes or []) if str(q).strip()]
    refs = [str(r).strip() for r in (evidence_refs or []) if str(r).strip()]
    has_evidence = bool(quotes or refs)

    # Start from whichever signal is available. A caller-proposed label is a
    # claim; the source class is a bridged classification.
    if proposed_label is not None:
        label = _norm(
            proposed_label, ALLOWABILITY_LABELS, fallback="requires_human_review"
        )
    elif source_allowability_class is not None:
        label = review_label_for_source_class(source_allowability_class)
    else:
        label = "not_indicated"

    blocked_reasons: list[str] = []

    # No affirmative label without evidence. This is the load-bearing rule.
    if label in AFFIRMATIVE_LABELS and not has_evidence:
        blocked_reasons.append(f"affirmative_label_without_evidence:{label}")
        label = "not_indicated"

    uncapped_label = label

    # The self-assessment cap. Applied last, and never lifted.
    #
    # Driven by the explicit flag alone. A cost type of `software_license` is
    # not self-assessment on its own - a tenant may legitimately assess some
    # other vendor's software, and capping that would make the feature useless
    # for the case it is actually for.
    self_assessed = bool(is_nativeforge_itself)
    if self_assessed and label != SELF_ASSESSMENT_CAP:
        blocked_reasons.append("self_assessment_capped_at_human_review")
        label = SELF_ASSESSMENT_CAP

    # A cost type NativeForge could plausibly be, assessed without the flag set,
    # is worth flagging: the caller may have forgotten which product they are
    # assessing. It is a prompt for the caller, not an automatic cap.
    if not self_assessed and cost_type in SELF_ASSESSED_COST_TYPES:
        blocked_reasons.append(f"confirm_vendor_is_not_nativeforge:{cost_type}")

    if cost_type == "unknown":
        blocked_reasons.append("assessed_cost_type_unknown")
    if not has_evidence:
        blocked_reasons.append("no_evidence_supplied")

    human_review_required = label == SELF_ASSESSMENT_CAP or self_assessed

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "assessed_cost_type": cost_type,
            "allowability_label": label,
            "uncapped_label": uncapped_label,
            "label_wording": PERMITTED_PHRASING[label],
            "evidence_quotes_or_refs": sorted(set(quotes + refs)),
            "evidence_present": has_evidence,
            "is_nativeforge_itself": bool(is_nativeforge_itself),
            "self_assessment_capped": self_assessed and uncapped_label != label,
            "source_allowability_class": source_allowability_class,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # An assessment is not a determination, and not a purchase advice.
            "allowability_determined": False,
            "funding_guaranteed": False,
            "fabricated": False,
        }
    )


def summarise_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    by_label = {label: 0 for label in sorted(ALLOWABILITY_LABELS)}
    for review in reviews:
        label = review.get("allowability_label")
        if label in by_label:
            by_label[label] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "review_count": len(reviews),
            "by_allowability_label": by_label,
            "evidence_backed_count": sum(
                1 for r in reviews if r.get("evidence_present")
            ),
            "self_assessed_count": sum(
                1 for r in reviews if r.get("is_nativeforge_itself")
            ),
            "self_assessment_capped_count": sum(
                1 for r in reviews if r.get("self_assessment_capped")
            ),
            "allowability_determined": False,
            "funding_guaranteed": False,
            "fabricated": False,
        }
    )


def allowability_review_invariant_failures(review: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if review.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if review.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("allowability_determined", "funding_guaranteed"):
        if review.get(constant) is not False:
            fails.append(f"review_claimed:{constant}")

    label = review.get("allowability_label")
    if label not in ALLOWABILITY_LABELS:
        fails.append("allowability_label_out_of_vocabulary")
        return fails
    if review.get("assessed_cost_type") not in COST_TYPES:
        fails.append("assessed_cost_type_out_of_vocabulary")

    # No affirmative label without evidence.
    if label in AFFIRMATIVE_LABELS and not review.get("evidence_present"):
        fails.append("affirmative_label_without_evidence")
    if label in AFFIRMATIVE_LABELS and not review.get("evidence_quotes_or_refs"):
        fails.append("affirmative_label_without_a_quote_or_ref")

    # The self-assessment cap, from both directions.
    if review.get("is_nativeforge_itself"):
        if label != SELF_ASSESSMENT_CAP:
            fails.append("self_assessment_escaped_the_human_review_cap")
        if not review.get("human_review_required"):
            fails.append("self_assessment_without_human_review_required")

    # The wording must match the label.
    if review.get("label_wording") != PERMITTED_PHRASING.get(label):
        fails.append("label_wording_does_not_match_the_label")

    # No prohibited claim may appear in any rendered text on the record.
    rendered = " ".join(
        str(review.get(field) or "")
        for field in ("label_wording", "assessed_cost_type", "opportunity_id")
    ).lower()
    for claim in PROHIBITED_CLAIMS:
        if claim in rendered:
            fails.append(f"review_rendered_a_prohibited_claim:{claim}")

    # A refusal or a cap must name itself.
    if label in NON_AFFIRMATIVE_LABELS and not review.get("blocked_reasons"):
        fails.append("non_affirmative_label_without_a_reason")

    return fails
