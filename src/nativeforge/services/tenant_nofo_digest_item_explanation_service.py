"""Tenant NOFO digest item explanation (Gate 104D).

Why one opportunity appears in one tenant's digest, in language a grants officer
can act on and a lawyer can defend.

## Matches and exclusions are explained separately

`why_this_matches` and `why_this_may_not_match` are different fields, populated
from different sources on the row, and a row can have both. Merging them into one
"relevance" paragraph is how a partial match with three disqualifying conditions
reads as a recommendation.

An excluded item that offers no reason fails an invariant. A refusal a tenant
cannot interrogate is worse than no refusal.

## Nothing overstates eligibility

The headline is derived from the item status, and the statuses a match can carry
are capped by what the underlying row actually established:

```text
eligibility_match_status  matched -> "matches your profile"
                          partial_match -> "may match - some conditions unmet"
                          needs_human_review -> "needs review before you act"
                          excluded / downgraded -> stated as such
                          unknown -> "eligibility not established"
```

`eligibility_determined` is False on every explanation. This service describes
what a match assessment said; it does not make one.

## Unverified deadlines say unverified

`deadline_note` is derived from Gate 87's provenance status, not from the date.
A `suspected_placeholder` or `unknown_deadline` produces a note that says so
rather than a countdown, and an invariant fails any explanation presenting an
unverified deadline as a deadline.

## Unsupported reporting burden stays unsupported

`reporting_burden_note` distinguishes "we previewed it" from "the document type
is not supported" from "nobody looked". Doc 570's rule: unsupported or unclear
requirements are `UNKNOWN`, `NEEDS_HUMAN_REVIEW` or `UNSUPPORTED_DOCUMENT_TYPE`,
never a confident-sounding summary.

## The allowability cap is carried, not re-derived

`allowability_note` renders the label the review service produced. When that
label is `requires_human_review` because the assessed cost was NativeForge
itself, the note says so — the cap survives into the customer-facing surface
rather than being smoothed away at the presentation layer, which is exactly where
a cap like that usually dies.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.deadline_provenance_service import (
    FRESHNESS_BLOCKING_STATUSES,
    VERIFIED_STATUSES,
)
from nativeforge.services.software_capacity_allowability_review_service import (
    ALLOWABILITY_LABELS,
    SELF_ASSESSMENT_CAP,
)
from nativeforge.services.tenant_nofo_digest_change_detection_service import (
    CHANGE_TYPES,
)
from nativeforge.services.tenant_nofo_digest_snapshot_service import (
    ELIGIBILITY_MATCH_STATUSES,
    REPORTING_BURDEN_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_item_explanation_v1"

DIGEST_ITEM_STATUSES = frozenset(
    {
        "new_match",
        "first_seen",
        "high_fit_unreviewed",
        "changed",
        "approaching_deadline",
        "newly_excluded",
        "downgraded",
        "needs_human_review",
        "suppressed",
        "unchanged",
        "unknown",
    }
)

# Statuses that put the item in the tenant's "look at this" view.
VISIBLE_ITEM_STATUSES = frozenset(
    {
        "new_match",
        "first_seen",
        "high_fit_unreviewed",
        "changed",
        "approaching_deadline",
        "newly_excluded",
        "downgraded",
        "needs_human_review",
    }
)

HEADLINES: dict[str, str] = {
    "matched": "Matches your tenant profile",
    "partial_match": "May match - some conditions are not established",
    "excluded": "Excluded for your tenant",
    "downgraded": "Downgraded for your tenant",
    "needs_human_review": "Needs human review before you act",
    "unknown": "Eligibility not established",
}

DEADLINE_NOTES: dict[str, str] = {
    "verified_deadline": "Deadline verified against the source record.",
    "unverified_deadline": (
        "Deadline shown as recorded, but not verified - confirm with the source "
        "before relying on it."
    ),
    "suspected_placeholder": (
        "This date appears in a large cluster with no fetch evidence behind it "
        "and is likely a placeholder, not a real deadline."
    ),
    "missing_deadline": "No deadline was recorded for this opportunity.",
    "unknown_deadline": "Nobody has established where this date came from.",
}

REPORTING_BURDEN_NOTES: dict[str, str] = {
    "preview_available": "A reporting burden preview is available for this item.",
    "partial": "A partial reporting burden preview is available; some "
    "requirements could not be read.",
    "unsupported_document_type": (
        "The attached document type is not supported, so reporting requirements "
        "could not be read. UNSUPPORTED_DOCUMENT_TYPE."
    ),
    "not_assessed": "Reporting burden has not been assessed for this item.",
    "unknown": "Reporting burden is UNKNOWN for this item.",
}

EVIDENCE_STATUSES = frozenset(
    {"evidence_stored", "evidence_missing", "not_applicable", "unknown"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _item_status(
    *, change_types: set[str], match_status: str, suppression_status: str
) -> str:
    """The one status this item carries, from the strongest signal present."""
    if suppression_status not in {"not_suppressed", "unknown"}:
        return "suppressed"
    if "human_review_required" in change_types or match_status == "needs_human_review":
        return "needs_human_review"
    if "newly_excluded" in change_types or match_status == "excluded":
        return "newly_excluded"
    if "downgraded" in change_types or match_status == "downgraded":
        return "downgraded"
    if "new_match" in change_types:
        return "new_match"
    if "first_seen" in change_types:
        return "first_seen"
    if change_types & {"deadline_changed", "deadline_changed_unverified", "amended"}:
        return "changed"
    if "approaching_deadline" in change_types:
        return "approaching_deadline"
    if match_status in {"matched", "partial_match"}:
        return "high_fit_unreviewed"
    if "unchanged" in change_types:
        return "unchanged"
    return "unknown"


def build_digest_item_explanation(
    *,
    tenant_id: Any,
    opportunity_row: dict[str, Any],
    change: dict[str, Any] | None = None,
    allowability_is_nativeforge_itself: bool = False,
) -> dict[str, Any]:
    """Why this item is here, and what is not established about it."""
    row = opportunity_row or {}
    change_types = set((change or {}).get("change_types") or [])

    match_status = _norm(
        row.get("eligibility_match_status"),
        ELIGIBILITY_MATCH_STATUSES,
        fallback="unknown",
    )
    suppression_status = str(row.get("suppression_status") or "not_suppressed")
    provenance = str(row.get("deadline_provenance_status") or "unknown_deadline")
    burden = _norm(
        row.get("reporting_burden_preview_status"),
        REPORTING_BURDEN_STATUSES,
        fallback="unknown",
    )
    allowability = _norm(
        row.get("software_capacity_allowability_label"),
        ALLOWABILITY_LABELS,
        fallback="not_indicated",
    )

    item_status = _item_status(
        change_types=change_types,
        match_status=match_status,
        suppression_status=suppression_status,
    )

    matches = list(row.get("tenant_match_reasons") or [])
    exclusions = list(row.get("tenant_exclusion_reasons") or [])
    reviews = list(row.get("human_review_reasons") or [])

    what_changed = sorted(
        change_types & CHANGE_TYPES - {"unchanged"}
    ) or ["nothing_changed_since_the_previous_snapshot"]

    allowability_note = (
        f"Software/capacity cost allowability: {allowability}."
    )
    if allowability_is_nativeforge_itself:
        allowability_note += (
            f" Capped at {SELF_ASSESSMENT_CAP} because the assessed cost is "
            "NativeForge itself - a self-assessment always goes to a person."
        )

    blocked_reasons: list[str] = []
    if provenance not in VERIFIED_STATUSES:
        blocked_reasons.append(f"deadline_not_verified:{provenance}")
    if provenance in FRESHNESS_BLOCKING_STATUSES:
        blocked_reasons.append(f"deadline_blocks_freshness:{provenance}")
    if burden not in {"preview_available", "partial"}:
        blocked_reasons.append(f"reporting_burden_not_previewable:{burden}")
    if match_status in {"unknown", "needs_human_review"}:
        blocked_reasons.append(f"eligibility_{match_status}")
    if match_status in {"excluded", "downgraded"} and not exclusions:
        blocked_reasons.append("exclusion_without_a_stated_reason")
    if not matches and match_status in {"matched", "partial_match"}:
        blocked_reasons.append("match_without_a_stated_reason")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "opportunity_id": row.get("opportunity_id"),
            "digest_item_status": item_status,
            "headline": HEADLINES.get(match_status, HEADLINES["unknown"]),
            "why_this_matches": matches,
            "why_this_may_not_match": exclusions,
            "what_changed": what_changed,
            "deadline_note": DEADLINE_NOTES.get(
                provenance, DEADLINE_NOTES["unknown_deadline"]
            ),
            "deadline_provenance_status": provenance,
            "deadline_verified": provenance in VERIFIED_STATUSES,
            "reporting_burden_note": REPORTING_BURDEN_NOTES.get(
                burden, REPORTING_BURDEN_NOTES["unknown"]
            ),
            "reporting_burden_status": burden,
            "allowability_note": allowability_note,
            "allowability_label": allowability,
            "allowability_self_assessment_capped": bool(
                allowability_is_nativeforge_itself
            ),
            "human_review_note": (
                "; ".join(reviews) if reviews else "No human review flagged."
            ),
            "human_review_reasons": reviews,
            "evidence_status": _norm(
                row.get("raw_payload_evidence_status"),
                EVIDENCE_STATUSES,
                fallback="unknown",
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # An explanation describes an assessment; it does not make one.
            "eligibility_determined": False,
            "deadline_guaranteed": False,
            "reporting_requirements_verified": False,
            "fabricated": False,
        }
    )


def explanation_invariant_failures(explanation: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if explanation.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if explanation.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "eligibility_determined",
        "deadline_guaranteed",
        "reporting_requirements_verified",
    ):
        if explanation.get(constant) is not False:
            fails.append(f"explanation_claimed:{constant}")

    if explanation.get("digest_item_status") not in DIGEST_ITEM_STATUSES:
        fails.append("digest_item_status_out_of_vocabulary")

    # Matches and exclusions stay in separate fields.
    if not isinstance(explanation.get("why_this_matches"), list):
        fails.append("why_this_matches_not_a_list")
    if not isinstance(explanation.get("why_this_may_not_match"), list):
        fails.append("why_this_may_not_match_not_a_list")

    status = explanation.get("digest_item_status")
    if status in {"newly_excluded", "downgraded"}:
        if not explanation.get("why_this_may_not_match"):
            fails.append("exclusion_without_an_explanation")

    # An unverified deadline may never be presented as verified.
    if explanation.get("deadline_verified") != (
        explanation.get("deadline_provenance_status") in VERIFIED_STATUSES
    ):
        fails.append("deadline_verified_disagrees_with_provenance")
    if not explanation.get("deadline_verified"):
        note = str(explanation.get("deadline_note") or "").lower()
        if "verified against the source" in note:
            fails.append("unverified_deadline_presented_as_verified")
        if "deadline_not_verified" not in " ".join(
            explanation.get("blocked_reasons") or []
        ):
            fails.append("unverified_deadline_not_flagged")

    # Unsupported reporting burden stays visible.
    if explanation.get("reporting_burden_status") == "unsupported_document_type":
        if "UNSUPPORTED_DOCUMENT_TYPE" not in str(
            explanation.get("reporting_burden_note")
        ):
            fails.append("unsupported_document_type_not_stated")

    # The allowability cap survives to the surface.
    if explanation.get("allowability_self_assessment_capped"):
        note = str(explanation.get("allowability_note") or "")
        if SELF_ASSESSMENT_CAP not in note:
            fails.append("self_assessment_cap_dropped_from_the_explanation")

    if explanation.get("allowability_label") not in ALLOWABILITY_LABELS:
        fails.append("allowability_label_out_of_vocabulary")

    # A human-review item must carry its reasons.
    if status == "needs_human_review" and not explanation.get(
        "human_review_reasons"
    ):
        fails.append("human_review_item_without_reasons")

    return fails
