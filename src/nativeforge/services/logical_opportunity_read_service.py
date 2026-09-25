"""What the product shows when two source rows are one real opportunity.

The resolver in `opportunity_identity_repository` answers "which logical
opportunity does this L1 id belong to?". This module is what the read and
write paths actually call, so that none of them has to learn the answer twice.

    resolutions = resolve_logical_canonical_ids(connection=..., canonical_ids=ids)
    feed        = build_feed(..., logical_resolutions=resolutions)
    decision    = build_decision(..., logical_canonical_id=logical_key(id, resolutions))

Resolution is passed IN, already batched. Nothing here touches a database,
which is what keeps a customer feed of N opportunities from issuing N
relationship queries - the caller resolves once and every consumer reuses it.

## Customer state binds to the logical opportunity, evidence does not

A pursuit, a watch, a dismissal belong to the grant the customer is chasing.
Provenance, versions and raw payloads stay attached to the representation they
actually came from: the forecast said what it said, and rewriting that to
point at the posting would destroy the record of what was known beforehand.

## Conflicts are named, never won

If someone dismissed the forecast and pursued the posting, this reports a
CONFLICT and keeps both. Picking the later timestamp would be inventing an
intention the customer never expressed.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_logical_opportunity_read_v1"

#: A decision that means the customer did something deliberate. NEW is the
#: absence of a decision, so it never conflicts with anything.
_DELIBERATE_STATES: frozenset[str] = frozenset({"WATCHED", "DISMISSED", "PURSUING"})

CONFLICT = "CONFLICT"
AGREED = "AGREED"
SINGLE = "SINGLE"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def logical_key(canonical_id: Any, resolutions: Any = None) -> str:
    """The id customer state should bind to. Falls back to the id itself.

    A missing resolution is not an error: an opportunity with no relationship
    IS its own logical opportunity, and that is the overwhelmingly common
    case.
    """
    key = str(canonical_id or "")
    table = (resolutions or {}).get("resolutions") or {}
    entry = table.get(key) or {}
    return str(entry.get("logical_canonical_id") or key)


def collapse_rows(
    rows: list[dict[str, Any]],
    *,
    resolutions: Any = None,
    id_field: str = "canonical_id",
) -> dict[str, Any]:
    """Collapse representation rows to one row per logical opportunity.

    The surviving row is the one whose own id IS the logical id - the primary.
    If the primary is not in the batch (a feed page that contains the forecast
    but not the posting), the first representation survives and is marked, so
    the caller can tell "this is the opportunity" from "this is all of it we
    were given".
    """
    by_logical: dict[str, dict[str, Any]] = {}
    superseded: dict[str, str] = {}
    order: list[str] = []

    for row in rows:
        raw = str(row.get(id_field) or "")
        logical = logical_key(raw, resolutions)
        if logical != raw:
            superseded[raw] = logical
        existing = by_logical.get(logical)
        if existing is None:
            by_logical[logical] = dict(row)
            order.append(logical)
            continue
        # Two rows for one opportunity. Keep the primary.
        if raw == logical:
            merged = dict(row)
            merged["_replaced"] = existing
            by_logical[logical] = merged

    collapsed: list[dict[str, Any]] = []
    for logical in order:
        row = dict(by_logical[logical])
        row.pop("_replaced", None)
        history = sorted(r for r, lg in superseded.items() if lg == logical)
        row["logical_opportunity_id"] = logical
        row["historical_representations"] = history
        row["has_pre_publication_history"] = bool(history)
        row["is_primary_representation"] = str(row.get(id_field) or "") == logical
        collapsed.append(row)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "representation_count": len(rows),
            "logical_opportunity_count": len(collapsed),
            "collapsed_count": len(rows) - len(collapsed),
            "rows": collapsed,
            "superseded_by": dict(sorted(superseded.items())),
        }
    )


def logical_opportunity_count(
    canonical_ids: list[Any], *, resolutions: Any = None
) -> int:
    """How many real opportunities these representations amount to.

    Distinct from a representation count, which is a legitimate number with a
    different meaning - `representation_count` in `collapse_rows` reports it.
    """
    return len({logical_key(c, resolutions) for c in canonical_ids if str(c or "")})


def reconcile_customer_state(
    decisions: list[dict[str, Any]], *, resolutions: Any = None
) -> dict[str, Any]:
    """One customer's decisions across representations of one opportunity.

    Returns a state per logical opportunity, and refuses to pick a winner when
    two representations disagree.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        logical = logical_key(decision.get("canonical_id"), resolutions)
        grouped.setdefault(logical, []).append(decision)

    results: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    for logical, rows in sorted(grouped.items()):
        states = {
            str(r.get("decision_state") or "")
            for r in rows
            if str(r.get("decision_state") or "") in _DELIBERATE_STATES
        }
        if len(states) > 1:
            conflicts.append(logical)
            results[logical] = {
                "logical_canonical_id": logical,
                "status": CONFLICT,
                "decision_state": None,
                "competing_states": sorted(states),
                # Both histories survive. Neither is discarded because it was
                # older, which would be inventing an intention.
                "decisions": sorted(rows, key=lambda r: str(r.get("canonical_id"))),
                "requires_human": True,
            }
            continue
        state = next(iter(states)) if states else "NEW"
        results[logical] = {
            "logical_canonical_id": logical,
            "status": AGREED if len(rows) > 1 else SINGLE,
            "decision_state": state,
            "competing_states": [],
            "decisions": sorted(rows, key=lambda r: str(r.get("canonical_id"))),
            "requires_human": False,
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": results,
            "logical_opportunity_count": len(results),
            "conflicts": sorted(conflicts),
            "conflict_count": len(conflicts),
        }
    )


def duplicate_pursuit_failures(
    pursuits: list[dict[str, Any]], *, resolutions: Any = None
) -> list[str]:
    """Two pursuits for one real grant is split-brain, not two projects."""
    seen: dict[str, list[str]] = {}
    for pursuit in pursuits:
        logical = logical_key(pursuit.get("canonical_id"), resolutions)
        seen.setdefault(logical, []).append(str(pursuit.get("pursuit_id") or ""))
    return sorted(
        f"duplicate_pursuits_for_one_opportunity:{logical}:{sorted(ids)}"
        for logical, ids in seen.items()
        if len(ids) > 1
    )


# --------------------------------------------------------------------
# Intelligence layers: relevance, eligibility, documents, change history
#
# All four have the same shape - rows attached to a representation that must
# read as one opportunity - so they share one grouping rule rather than four
# slightly different ones that drift apart.
# --------------------------------------------------------------------

#: States that a later, better-evidenced assessment REFINES rather than
#: contradicts. A forecast that said "we cannot tell yet" is not in conflict
#: with a posting that says "eligible"; it was superseded by evidence.
REFINABLE_STATES: frozenset[str] = frozenset(
    {
        "UNKNOWN",
        "NOT_ASSESSED",
        "ELIGIBILITY_NOT_ASSESSED",
        "RELEVANCE_UNCERTAIN",
        "CONDITIONAL",
        "",
    }
)

REFINED = "REFINED"


def aggregate_assessments(
    assessments: list[dict[str, Any]],
    *,
    resolutions: Any = None,
    state_field: str = "state",
    refinable_states: frozenset[str] | None = None,
) -> dict[str, Any]:
    """One logical state per opportunity, for relevance OR eligibility.

    Generic on purpose: Native relevance and tenant eligibility are different
    questions with different answers, and keeping them separate matters - but
    "two representations of one grant must not hold two unrelated states" is
    the same rule for both, and writing it twice would let the two copies
    disagree.

    A refinable earlier state (UNKNOWN, CONDITIONAL, not-yet-assessed) is
    superseded by a definite later one, with the earlier kept as history. Two
    DEFINITE states that disagree are a CONFLICT: the forecast said eligible,
    the posted NOFO says disqualifying, and picking the newer one silently
    would hide that something changed which the customer needs to know about.
    """
    refinable = REFINABLE_STATES if refinable_states is None else refinable_states
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in assessments:
        logical = logical_key(row.get("canonical_id"), resolutions)
        grouped.setdefault(logical, []).append(row)

    results: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    for logical, rows in sorted(grouped.items()):
        definite = [r for r in rows if str(r.get(state_field) or "") not in refinable]
        states = {str(r.get(state_field) or "") for r in definite}

        if len(states) > 1:
            conflicts.append(logical)
            results[logical] = {
                "logical_canonical_id": logical,
                "status": CONFLICT,
                state_field: None,
                "competing_states": sorted(states),
                "requires_human": True,
                "contributing": _by_representation(rows),
            }
            continue

        if definite and len(rows) > len(definite):
            status = REFINED
        elif len(rows) > 1:
            status = AGREED
        else:
            status = SINGLE

        results[logical] = {
            "logical_canonical_id": logical,
            "status": status,
            state_field: next(iter(states)) if states else None,
            "competing_states": [],
            "requires_human": False,
            # Every representation that contributed, so a refinement can be
            # read back rather than merely trusted.
            "contributing": _by_representation(rows),
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": results,
            "logical_opportunity_count": len(results),
            "assessment_count": len(assessments),
            "conflicts": sorted(conflicts),
            "conflict_count": len(conflicts),
        }
    )


def _by_representation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        ({"canonical_id": str(r.get("canonical_id") or ""), **r} for r in rows),
        key=lambda r: (str(r.get("observed_at") or ""), str(r.get("canonical_id"))),
    )


def aggregate_documents(
    documents: list[dict[str, Any]], *, resolutions: Any = None
) -> dict[str, Any]:
    """One evidence history per opportunity, provenance untouched.

    The forecast's early notice and the posted NOFO belong to the same grant.
    Neither document is rewritten to claim it came from the other: each keeps
    its own canonical_id, hash and retrieval metadata, because a document's
    provenance is the reason it can be cited at all.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for doc in documents:
        logical = logical_key(doc.get("canonical_id"), resolutions)
        grouped.setdefault(logical, []).append(dict(doc))

    histories: dict[str, dict[str, Any]] = {}
    for logical, docs in sorted(grouped.items()):
        ordered = sorted(
            docs,
            key=lambda d: (str(d.get("observed_at") or ""), str(d.get("document_id"))),
        )
        representations = sorted({str(d.get("canonical_id") or "") for d in ordered})
        histories[logical] = {
            "logical_canonical_id": logical,
            "documents": ordered,
            "document_count": len(ordered),
            "contributing_representations": representations,
            "spans_multiple_representations": len(representations) > 1,
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": histories,
            "logical_opportunity_count": len(histories),
            "document_count": len(documents),
        }
    )


def merge_change_timeline(
    events: list[dict[str, Any]], *, resolutions: Any = None
) -> dict[str, Any]:
    """One chronological history per opportunity.

    After confirmed continuity a customer should see forecast -> posted ->
    amendment as a single story, not two disconnected ones. Replay is
    idempotent: the same event observed twice contributes once, keyed on what
    the event IS rather than on when it was read.
    """
    grouped: dict[str, dict[tuple[str, ...], dict[str, Any]]] = {}
    for event in events:
        logical = logical_key(event.get("canonical_id"), resolutions)
        fingerprint = (
            str(event.get("canonical_id") or ""),
            str(event.get("change_type") or ""),
            str(event.get("field_name") or ""),
            str(event.get("observed_at") or ""),
        )
        grouped.setdefault(logical, {})[fingerprint] = dict(event)

    timelines: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for logical, unique in sorted(grouped.items()):
        ordered = sorted(
            unique.values(),
            key=lambda e: (
                str(e.get("observed_at") or ""),
                str(e.get("change_type") or ""),
            ),
        )
        transitions = [
            e for e in ordered if str(e.get("change_type")) == "FORECAST_TO_POSTED"
        ]
        if len(transitions) > 1:
            failures.append(
                f"forecast_to_posted_emitted_{len(transitions)}_times:{logical}"
            )
        timelines[logical] = {
            "logical_canonical_id": logical,
            "events": ordered,
            "event_count": len(ordered),
            "forecast_to_posted_count": len(transitions),
            "contributing_representations": sorted(
                {str(e.get("canonical_id") or "") for e in ordered}
            ),
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": timelines,
            "logical_opportunity_count": len(timelines),
            "event_count": len(events),
            "invariant_failures": sorted(set(failures)),
        }
    )


# ---- coverage: dedupe WITHOUT destroying lifecycle evidence ----------

STAGE_PRE_PUBLICATION = "PRE_PUBLICATION"
STAGE_PUBLISHED = "PUBLISHED"

LIFECYCLE_COMPLETE = "FORECAST_AND_POSTING_OBSERVED"
LIFECYCLE_POSTING_ONLY = "POSTING_OBSERVED_FORECAST_NOT_OBSERVED"
LIFECYCLE_FORECAST_ONLY = "FORECAST_OBSERVED_POSTING_NOT_OBSERVED"
LIFECYCLE_UNKNOWN = "LIFECYCLE_UNKNOWN"


def lifecycle_coverage(
    representations: list[dict[str, Any]],
    *,
    resolutions: Any = None,
    pre_publication_doc_types: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Count opportunities once, and still say which stages were seen.

    This is the one place where collapsing is dangerous. A forecast and its
    posting are ONE opportunity - but seeing only the posting means the early
    signal was missed, and that is a real coverage fact about this system's
    reach. If dedupe erased it, the product would report perfect coverage of a
    lifecycle it only ever caught the end of.

    So the logical count and the lifecycle evidence are two separate outputs,
    and neither is derived from the other.

    What it refuses: a forecast with no posting is NOT a missed posting. The
    posting may simply not have happened yet. That stays
    FORECAST_OBSERVED_POSTING_NOT_OBSERVED - an observation, not an accusation
    - and Gate 176 owns whether an expected posting is overdue.
    """
    pre_types = (
        frozenset({"forecast"})
        if pre_publication_doc_types is None
        else pre_publication_doc_types
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in representations:
        logical = logical_key(row.get("canonical_id"), resolutions)
        grouped.setdefault(logical, []).append(row)

    coverage: dict[str, dict[str, Any]] = {}
    for logical, rows in sorted(grouped.items()):
        stages = set()
        for row in rows:
            doc_type = str(row.get("doc_type") or "").strip().lower()
            if not doc_type:
                continue
            stages.add(
                STAGE_PRE_PUBLICATION if doc_type in pre_types else STAGE_PUBLISHED
            )
        if STAGE_PRE_PUBLICATION in stages and STAGE_PUBLISHED in stages:
            lifecycle = LIFECYCLE_COMPLETE
        elif STAGE_PUBLISHED in stages:
            lifecycle = LIFECYCLE_POSTING_ONLY
        elif STAGE_PRE_PUBLICATION in stages:
            lifecycle = LIFECYCLE_FORECAST_ONLY
        else:
            lifecycle = LIFECYCLE_UNKNOWN

        coverage[logical] = {
            "logical_canonical_id": logical,
            "lifecycle": lifecycle,
            "stages_observed": sorted(stages),
            "representation_count": len(rows),
            # Named as an observation about OUR reach, not a claim about the
            # publisher's behaviour.
            "early_signal_was_observed": STAGE_PRE_PUBLICATION in stages,
            "early_signal_coverage_gap": lifecycle == LIFECYCLE_POSTING_ONLY,
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": coverage,
            # Two numbers, two meanings, neither derived from the other.
            "logical_opportunity_count": len(coverage),
            "representation_count": len(representations),
            "early_signal_coverage_gaps": sorted(
                k for k, v in coverage.items() if v["early_signal_coverage_gap"]
            ),
            "complete_lifecycles": sorted(
                k for k, v in coverage.items() if v["lifecycle"] == LIFECYCLE_COMPLETE
            ),
            "lifecycle_evidence_survived_dedupe": True,
        }
    )


def customer_visible_invariant_failures(
    *,
    rows: list[dict[str, Any]],
    resolutions: Any = None,
    id_field: str = "canonical_id",
) -> list[str]:
    """The close condition, as something that can actually fail."""
    failures: list[str] = []
    collapsed = collapse_rows(rows, resolutions=resolutions, id_field=id_field)
    visible = {str(r.get(id_field) or "") for r in collapsed["rows"]}
    superseded = collapsed["superseded_by"]

    for representation, logical in superseded.items():
        if representation in visible:
            failures.append(f"superseded_representation_is_visible:{representation}")
        if logical not in visible and any(
            str(r.get(id_field) or "") == logical for r in rows
        ):
            failures.append(f"primary_is_not_visible:{logical}")
    return sorted(set(failures))
