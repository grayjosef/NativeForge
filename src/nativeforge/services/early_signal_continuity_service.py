"""Wave 1B: collapse a pre-publication signal and its posting into ONE opportunity.

A forecast and the posting it becomes are two SOURCE representations of one
real funding opportunity. L1 keeps them apart on purpose - composite_key is
`<number>|<doc_type>`, so they key as `X|forecast` and `X|synopsis`, and that
is correct: overwriting the forecast with the posting would destroy the
transition and the answer to "what did we know before this was posted?".

What is NOT correct is showing a customer two opportunities. This module is
the layer above L1 that collapses a confirmed pair into one LOGICAL
opportunity while both representations stay preserved underneath.

    forecast representation  ──┐
                               ├─ FORECAST_OF ─> ONE logical opportunity
    posted representation   ───┘                  (posting is primary)

## Nothing here is Grants.gov

The publisher-specific part - which payload field is a document type, what a
forecast looks like on the wire - stays in the adapter. This module takes
already-normalized representations and speaks only about pre-publication
versus published. A state funding calendar, a foundation's upcoming-grants
page or an agency pipeline notice reuses it unchanged.

## What it refuses

Title similarity never confirms continuity. A shared assistance listing never
confirms continuity - one programme publishes many solicitations, and merging
on that would silently fuse unrelated grants. Only a shared published
opportunity number does, which is the threshold `decide_match` already
defines and migration 0054 already permits a machine to settle at L1, because
FORECAST_OF is not a SAME_AS merge.

Anything weaker is AMBIGUOUS and stays two opportunities until a human says
otherwise. An unresolved pair is a visible question; a wrong merge is an
invisible loss.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.cross_source_identity_service import (
    DISTINCT,
    FORECAST_OF,
    REVIEW_REQUIRED,
    decide_match,
)

SCHEMA_VERSION = "nf_early_signal_continuity_v1"

#: Document kinds that describe funding BEFORE it is formally published.
#: Deliberately a set, not a hard-coded "forecast": a state calendar may call
#: its pre-publication record something else, and this module should not need
#: editing to accept it.
PRE_PUBLICATION_DOC_TYPES: frozenset[str] = frozenset({"forecast"})

# ---- continuity outcomes ---------------------------------------------
#: Named in the campaign's vocabulary and mapped onto the identity service's
#: existing decisions rather than parallel to them.
CONFIRMED_CONTINUITY = "CONFIRMED_CONTINUITY"
AMBIGUOUS = "AMBIGUOUS"
NO_MATCH = "NO_MATCH"
UNKNOWN = "UNKNOWN"

CONTINUITY_OUTCOMES: tuple[str, ...] = (
    CONFIRMED_CONTINUITY,
    AMBIGUOUS,
    NO_MATCH,
    UNKNOWN,
)

#: Only a CONFIRMED pair may be collapsed without a human.
COLLAPSIBLE: frozenset[str] = frozenset({CONFIRMED_CONTINUITY})


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def is_pre_publication(doc_type: Any) -> bool:
    """Is this representation describing funding that is not yet published?"""
    return str(doc_type or "").strip().lower() in PRE_PUBLICATION_DOC_TYPES


def resolve_continuity(
    *, earlier: dict[str, Any], later: dict[str, Any]
) -> dict[str, Any]:
    """Are these two representations one opportunity, and which one is current?

    `earlier` and `later` are normalized identity records - the same shape
    `decide_match` consumes. The names describe observation order, not trust:
    a posting can be observed before anyone saw its forecast.
    """
    decision = decide_match(left=earlier, right=later)
    verdict = str(decision.get("decision") or "")
    reasons = list(decision.get("reasons") or [])

    pre_a = is_pre_publication(earlier.get("doc_type"))
    pre_b = is_pre_publication(later.get("doc_type"))

    outcome = UNKNOWN
    primary: dict[str, Any] | None = None
    historical: dict[str, Any] | None = None

    if verdict == FORECAST_OF:
        # decide_match reached this only on one published number carrying two
        # document kinds. That is deterministic, and it is the ONLY route to
        # a confirmed pair here.
        if pre_a != pre_b:
            outcome = CONFIRMED_CONTINUITY
            primary, historical = (later, earlier) if pre_a else (earlier, later)
        else:
            # Two document kinds, neither of which is pre-publication - the
            # pair is related but this module cannot say which supersedes.
            outcome = AMBIGUOUS
            reasons.append("neither_representation_is_pre_publication")
    elif verdict == DISTINCT:
        outcome = NO_MATCH
    elif verdict == REVIEW_REQUIRED:
        outcome = AMBIGUOUS
    else:
        # EXACT_MATCH, STRONG_MATCH, RECURRENCE_OF and friends are real
        # decisions about something else. They are not forecast continuity,
        # and calling them AMBIGUOUS would invent a doubt the identity
        # service did not express.
        outcome = NO_MATCH
        reasons.append(f"decision_is_not_forecast_continuity:{verdict}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "outcome": outcome,
            "identity_decision": verdict,
            "relationship": FORECAST_OF if outcome == CONFIRMED_CONTINUITY else None,
            "may_collapse_without_human": outcome in COLLAPSIBLE,
            "primary_canonical_id": (primary or {}).get("canonical_id"),
            "historical_canonical_id": (historical or {}).get("canonical_id"),
            "identity_layer": decision.get("identity_layer"),
            "confidence": decision.get("confidence"),
            "confidence_is_a_declared_policy_not_a_probability": True,
            "evidence": decision.get("evidence"),
            "reasons": sorted(set(reasons)),
            # Said out loud because these are the two merges that look
            # attractive and destroy data.
            "title_similarity_alone_is_never_sufficient": True,
            "program_identity_alone_is_never_sufficient": True,
        }
    )


def collapse_to_logical_opportunities(
    *,
    representations: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Turn source representations into the opportunities a customer sees.

    A confirmed FORECAST_OF pair contributes ONE logical opportunity whose
    current state is the posting and whose history includes the forecast.
    Everything else contributes itself.
    """
    rows = {str(r.get("canonical_id")): dict(r) for r in representations}
    #: historical canonical_id -> primary canonical_id
    superseded_by: dict[str, str] = {}

    for rel in relationships or []:
        if str(rel.get("relationship") or "") != FORECAST_OF:
            continue
        if rel.get("revoked_at"):
            continue
        primary = str(rel.get("primary_canonical_id") or "")
        a = str(rel.get("from_canonical_id") or "")
        b = str(rel.get("to_canonical_id") or "")
        if not primary or primary not in (a, b):
            # A FORECAST_OF that does not name which side is current cannot
            # be collapsed - collapsing it would be a guess about which
            # record the customer should act on.
            continue
        historical = b if primary == a else a
        superseded_by[historical] = primary

    logical: list[dict[str, Any]] = []
    for canonical_id, row in rows.items():
        if canonical_id in superseded_by:
            continue
        history = [h for h, p in superseded_by.items() if p == canonical_id]
        logical.append(
            {
                "logical_opportunity_id": canonical_id,
                "current_representation": canonical_id,
                "historical_representations": sorted(history),
                "has_pre_publication_history": bool(history),
                "current_doc_type": row.get("doc_type"),
                "lifecycle": row.get("lifecycle") or row.get("status"),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "representation_count": len(rows),
            "logical_opportunity_count": len(logical),
            "collapsed_count": len(superseded_by),
            "logical_opportunities": sorted(
                logical, key=lambda x: str(x["logical_opportunity_id"])
            ),
            "superseded_by": dict(sorted(superseded_by.items())),
        }
    )


def duplicate_logical_opportunity_failures(
    *,
    representations: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
) -> list[str]:
    """The invariant, as a detector that can actually fail.

    `confirmed_forecast_posting_pairs_do_not_double_count_canonical_opportunities`

    Two preserved L1 representations are fine. Two customer-visible
    opportunities for one real grant are not.
    """
    failures: list[str] = []
    collapsed = collapse_to_logical_opportunities(
        representations=representations, relationships=relationships
    )
    visible = {
        str(x["logical_opportunity_id"]) for x in collapsed["logical_opportunities"]
    }

    for rel in relationships or []:
        if str(rel.get("relationship") or "") != FORECAST_OF:
            continue
        if rel.get("revoked_at"):
            continue
        a = str(rel.get("from_canonical_id") or "")
        b = str(rel.get("to_canonical_id") or "")
        primary = str(rel.get("primary_canonical_id") or "")
        if not primary:
            failures.append(f"forecast_of_without_primary:{a}|{b}")
            continue
        if a in visible and b in visible:
            failures.append(f"confirmed_pair_is_visible_twice:{a}|{b}")
        if primary not in visible and (a in visible or b in visible):
            failures.append(f"primary_is_not_the_visible_representation:{primary}")
        historical = b if primary == a else a
        if historical in visible:
            failures.append(f"historical_representation_is_visible:{historical}")

    return sorted(set(failures))
