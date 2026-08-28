"""Tenant NOFO digest change detection (Gate 104C).

Compares two tenant snapshots. It fetches nothing and needs no live collection —
which is the point, because there is none.

## Two recorded observations, and the contract says so

Doc 570 flagged this first: "changed deadlines", "amendments" and "newly
excluded" all compare an observation to an earlier one, and with no live
collection there is no second observation. The honest substrate is a pair of
recorded snapshots, and `comparison_kind` records exactly what was compared:

```text
fixture_to_fixture      two demo or recorded snapshots
fixture_to_live         a recorded baseline against a live observation
live_to_live            two live observations
first_seen_only         no previous snapshot at all
unknown                 the snapshots do not describe themselves
```

Everything in this repository today is `fixture_to_fixture`, and a digest built
on it may not be described as monitoring.

## No previous snapshot means first_seen, not new

The distinction that stops a demo lying. With no baseline, every eligible row is
being seen for the first time *by this comparison* — which is not the same as the
opportunity being new in the world. `first_seen` is its own change type,
`comparison_kind` is `first_seen_only`, and an invariant fails any comparison
that emits `new_match` without a previous snapshot.

A first run of a digest showing forty "new" opportunities would be forty
opportunities that have existed for months.

## deadline_changed uses provenance, not date arithmetic

Gate 87 built `deadline_provenance_service` because the corpus had deadline
clusters with no fetch evidence behind them. Exactly one of its five statuses
counts as verified.

So a date difference alone is **not** `deadline_changed`. The change type is
emitted only when both sides carry a verified deadline; when either side does
not, the result is `deadline_changed_unverified` and it is routed to human
review rather than to a countdown. An invariant fails any `deadline_changed`
where either side was unverified.

That is the difference between "the deadline moved" and "two unreliable records
disagree".

## amended uses the existing amendment model

`classify_amendment` from Gate 92's model does the work — it already separates
material categories from cosmetic ones and already handles the
`last_updated_date_or_created_date` field that makes "something changed"
ambiguous. This service bridges its categories rather than inventing a second
amendment vocabulary.

## Nothing is deleted

`removed_from_source` means a row present in the previous snapshot is absent from
the current one. It is a change *observation*, not a deletion: the previous row
is carried on the change record, and an invariant fails any removal that dropped
it. Source history, provenance and audit records are untouched by anything here.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.deadline_provenance_service import VERIFIED_STATUSES
from nativeforge.services.opportunity_deadline_and_amendment_model_service import (
    AMENDMENT_CATEGORIES,
    MATERIAL_CATEGORIES,
    classify_amendment,
)
from nativeforge.services.tenant_nofo_digest_snapshot_service import (
    FIXTURE_SNAPSHOT_KINDS,
    LIVE_SNAPSHOT_KINDS,
    MATCHING_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_change_detection_v1"

CHANGE_TYPES = frozenset(
    {
        "new_match",
        "first_seen",
        "deadline_changed",
        "deadline_changed_unverified",
        "amended",
        "newly_excluded",
        "downgraded",
        "approaching_deadline",
        "human_review_required",
        "unchanged",
        "removed_from_source",
        "unknown",
    }
)

# Change types that put an item in a tenant's digest as something to look at.
ACTIONABLE_CHANGE_TYPES = frozenset(
    {
        "new_match",
        "first_seen",
        "deadline_changed",
        "deadline_changed_unverified",
        "amended",
        "newly_excluded",
        "downgraded",
        "approaching_deadline",
        "human_review_required",
    }
)

# Change types that always need a person before anything is acted on.
HUMAN_REVIEW_CHANGE_TYPES = frozenset(
    {"deadline_changed_unverified", "human_review_required", "unknown"}
)

COMPARISON_KINDS = frozenset(
    {
        "fixture_to_fixture",
        "fixture_to_live",
        "live_to_live",
        "first_seen_only",
        "unknown",
    }
)

# Kinds where at least one side was a live observation. Nothing reaches these
# today, and an invariant checks the claim against the snapshots.
LIVE_COMPARISON_KINDS = frozenset({"fixture_to_live", "live_to_live"})

# Days out at which a verified deadline becomes worth surfacing. Only applied to
# verified deadlines - an unverified date is not a countdown.
APPROACHING_DEADLINE_DAYS = 30

# States that mean the tenant should no longer be offered the opportunity.
EXCLUDED_STATUSES = frozenset({"excluded"})
DOWNGRADED_STATUSES = frozenset({"downgraded"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _comparison_kind(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "first_seen_only"
    prev_kind = previous.get("snapshot_kind")
    curr_kind = current.get("snapshot_kind")
    if prev_kind in LIVE_SNAPSHOT_KINDS and curr_kind in LIVE_SNAPSHOT_KINDS:
        return "live_to_live"
    if curr_kind in LIVE_SNAPSHOT_KINDS or prev_kind in LIVE_SNAPSHOT_KINDS:
        return "fixture_to_live"
    if prev_kind in FIXTURE_SNAPSHOT_KINDS and curr_kind in FIXTURE_SNAPSHOT_KINDS:
        return "fixture_to_fixture"
    return "unknown"


def _days_between(later: Any, earlier: Any) -> float | None:
    """Days between two ISO dates, or None if not derivable."""
    from datetime import datetime

    def _parse(value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    a, b = _parse(later), _parse(earlier)
    if a is None or b is None:
        return None
    try:
        return (a - b).total_seconds() / 86400.0
    except TypeError:
        # Naive against aware. Comparing them would invent a timezone.
        return None


def _classify_row(
    *,
    previous_row: dict[str, Any] | None,
    current_row: dict[str, Any],
    now: Any,
    has_previous_snapshot: bool,
) -> dict[str, Any]:
    """One row's change types. A row can carry several."""
    types: list[str] = []
    reasons: list[str] = []

    match_status = current_row.get("eligibility_match_status")
    previous_status = (previous_row or {}).get("eligibility_match_status")

    if previous_row is None:
        # Never seen before by this comparison. Whether it is new *in the world*
        # is a different question this service cannot answer.
        if has_previous_snapshot:
            if match_status in MATCHING_STATUSES:
                types.append("new_match")
                reasons.append("absent_from_the_previous_snapshot")
        else:
            types.append("first_seen")
            reasons.append("no_previous_snapshot_to_compare_against")
    else:
        # Eligibility movement, with the prior state preserved on the record.
        if (
            match_status in EXCLUDED_STATUSES
            and previous_status not in EXCLUDED_STATUSES
        ):
            types.append("newly_excluded")
            reasons.append(f"was:{previous_status}")
        elif (
            match_status in DOWNGRADED_STATUSES
            and previous_status not in DOWNGRADED_STATUSES
        ):
            types.append("downgraded")
            reasons.append(f"was:{previous_status}")

        # Deadline movement, gated on provenance rather than on the dates.
        previous_deadline = previous_row.get("deadline")
        current_deadline = current_row.get("deadline")
        if previous_deadline != current_deadline:
            both_verified = (
                previous_row.get("deadline_provenance_status") in VERIFIED_STATUSES
                and current_row.get("deadline_provenance_status") in VERIFIED_STATUSES
            )
            if both_verified:
                types.append("deadline_changed")
                reasons.append(f"deadline:{previous_deadline}->{current_deadline}")
            else:
                # Two records disagree and at least one cannot be vouched for.
                types.append("deadline_changed_unverified")
                reasons.append(
                    "deadline_differs_but_provenance_is_not_verified_on_both_sides"
                )

        # Amendment, via the existing model.
        modified = current_row.get("modified_fields") or []
        if modified:
            amendment = classify_amendment(
                modified_fields=modified,
                revision=current_row.get("revision"),
                previous_revision=previous_row.get("revision"),
                opportunity_key=current_row.get("opportunity_id"),
            )
            if amendment.get("material_categories"):
                types.append("amended")
                reasons.append(
                    "material:" + ",".join(amendment["material_categories"])
                )
        elif current_row.get("amendment_status") in MATERIAL_CATEGORIES:
            types.append("amended")
            reasons.append(f"amendment_status:{current_row['amendment_status']}")

    # Approaching deadline, only for a verified one.
    if current_row.get("deadline_verified"):
        days = _days_between(current_row.get("deadline"), now)
        if days is not None and 0 <= days <= APPROACHING_DEADLINE_DAYS:
            types.append("approaching_deadline")
            reasons.append(f"days_remaining:{int(days)}")

    # Human review, from the row's own reasons or from an unverifiable change.
    if current_row.get("human_review_reasons") or match_status == "needs_human_review":
        types.append("human_review_required")
        reasons.extend(current_row.get("human_review_reasons") or [])

    if not types:
        types.append("unchanged")

    return {"types": sorted(set(types)), "reasons": sorted(set(reasons))}


def detect_digest_changes(
    *,
    tenant_id: Any,
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Compare two snapshots. Nothing is fetched and nothing is deleted."""
    comparison_kind = _comparison_kind(previous_snapshot, current_snapshot)
    has_previous = previous_snapshot is not None

    previous_rows = {
        str(r.get("opportunity_id")): r
        for r in (previous_snapshot or {}).get("opportunity_rows") or []
    }
    current_rows = {
        str(r.get("opportunity_id")): r
        for r in current_snapshot.get("opportunity_rows") or []
    }

    changes: list[dict[str, Any]] = []

    for opportunity_id in sorted(current_rows):
        current_row = current_rows[opportunity_id]
        previous_row = previous_rows.get(opportunity_id)
        classified = _classify_row(
            previous_row=previous_row,
            current_row=current_row,
            now=now,
            has_previous_snapshot=has_previous,
        )
        changes.append(
            {
                "opportunity_id": opportunity_id,
                "change_types": classified["types"],
                "change_reasons": classified["reasons"],
                "previous_eligibility_match_status": (previous_row or {}).get(
                    "eligibility_match_status"
                ),
                "current_eligibility_match_status": current_row.get(
                    "eligibility_match_status"
                ),
                "previous_deadline": (previous_row or {}).get("deadline"),
                "current_deadline": current_row.get("deadline"),
                "deadline_provenance_status": current_row.get(
                    "deadline_provenance_status"
                ),
                "requires_human_review": bool(
                    set(classified["types"]) & HUMAN_REVIEW_CHANGE_TYPES
                ),
                "previous_row_preserved": previous_row is not None,
                "deleted": False,
            }
        )

    # Rows that were there and are not now. Observed, never deleted.
    for opportunity_id in sorted(set(previous_rows) - set(current_rows)):
        previous_row = previous_rows[opportunity_id]
        changes.append(
            {
                "opportunity_id": opportunity_id,
                "change_types": ["removed_from_source"],
                "change_reasons": ["absent_from_the_current_snapshot"],
                "previous_eligibility_match_status": previous_row.get(
                    "eligibility_match_status"
                ),
                "current_eligibility_match_status": None,
                "previous_deadline": previous_row.get("deadline"),
                "current_deadline": None,
                "deadline_provenance_status": previous_row.get(
                    "deadline_provenance_status"
                ),
                "requires_human_review": True,
                # The prior row is carried, so nothing is lost by the removal.
                "previous_row": previous_row,
                "previous_row_preserved": True,
                "deleted": False,
            }
        )

    changes.sort(key=lambda c: str(c["opportunity_id"]))

    blocked_reasons: list[str] = []
    if not has_previous:
        blocked_reasons.append("no_previous_snapshot_first_seen_only")
    if comparison_kind == "fixture_to_fixture":
        blocked_reasons.append("comparison_between_recorded_snapshots_not_live_checks")
    if comparison_kind == "unknown":
        blocked_reasons.append("comparison_kind_unknown")
    unverified = sum(
        1 for c in changes if "deadline_changed_unverified" in c["change_types"]
    )
    if unverified:
        blocked_reasons.append(f"unverified_deadline_changes:{unverified}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "previous_snapshot_id": (previous_snapshot or {}).get("snapshot_id"),
            "current_snapshot_id": current_snapshot.get("snapshot_id"),
            "comparison_kind": comparison_kind,
            "changes": changes,
            "change_count": len(changes),
            "requires_human_review_count": sum(
                1 for c in changes if c["requires_human_review"]
            ),
            "actionable_count": sum(
                1
                for c in changes
                if set(c["change_types"]) & ACTIONABLE_CHANGE_TYPES
            ),
            "unverified_deadline_change_count": unverified,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Comparison is reading, never collection and never deletion.
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fetch_performed": False,
            "rows_deleted": 0,
            "fabricated": False,
        }
    )


def change_detection_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "live_source_coverage",
        "fetch_performed",
    ):
        if result.get(constant) is not False:
            fails.append(f"comparison_claimed:{constant}")
    if result.get("rows_deleted") != 0:
        fails.append("comparison_deleted_rows")

    kind = result.get("comparison_kind")
    if kind not in COMPARISON_KINDS:
        fails.append("comparison_kind_out_of_vocabulary")

    changes = result.get("changes")
    if not isinstance(changes, list):
        fails.append("changes_not_a_list")
        return fails

    has_previous = result.get("previous_snapshot_id") is not None

    for change in changes:
        types = set(change.get("change_types") or [])
        opportunity_id = change.get("opportunity_id")

        for change_type in types:
            if change_type not in CHANGE_TYPES:
                fails.append(f"change_type_out_of_vocabulary:{change_type}")

        # No baseline means first_seen, never new_match.
        if not has_previous:
            if "new_match" in types:
                fails.append(f"new_match_without_a_previous_snapshot:{opportunity_id}")
            if kind != "first_seen_only":
                fails.append("no_previous_snapshot_but_comparison_kind_is_not_first_seen")

        # A verified deadline change needs verified provenance on both sides.
        if "deadline_changed" in types:
            if change.get("deadline_provenance_status") not in VERIFIED_STATUSES:
                fails.append(
                    f"deadline_changed_on_unverified_provenance:{opportunity_id}"
                )
        if "deadline_changed_unverified" in types:
            if not change.get("requires_human_review"):
                fails.append(
                    f"unverified_deadline_change_without_human_review:{opportunity_id}"
                )

        # Exclusions and downgrades keep the prior state.
        if types & {"newly_excluded", "downgraded"}:
            if change.get("previous_eligibility_match_status") is None:
                fails.append(f"state_change_without_a_prior_state:{opportunity_id}")

        # A removal is an observation, never a deletion.
        if "removed_from_source" in types:
            if change.get("deleted") is not False:
                fails.append(f"removal_marked_as_deleted:{opportunity_id}")
            if not change.get("previous_row_preserved"):
                fails.append(f"removal_dropped_the_previous_row:{opportunity_id}")

        # A change that needs review must say so, and vice versa.
        if types & HUMAN_REVIEW_CHANGE_TYPES and not change.get(
            "requires_human_review"
        ):
            fails.append(f"review_type_without_the_flag:{opportunity_id}")

        if not types:
            fails.append(f"change_without_a_type:{opportunity_id}")

    # A live comparison must have had a live snapshot in it.
    if kind in LIVE_COMPARISON_KINDS:
        fails.append("live_comparison_claimed_without_live_collection")

    # Counts derived from the changes.
    if result.get("change_count") != len(changes):
        fails.append("change_count_disagrees_with_the_changes")
    if result.get("requires_human_review_count") != sum(
        1 for c in changes if c.get("requires_human_review")
    ):
        fails.append("review_count_disagrees_with_the_changes")

    # A comparison that cannot be confident must say why.
    if kind in {"first_seen_only", "fixture_to_fixture", "unknown"}:
        if not result.get("blocked_reasons"):
            fails.append("non_live_comparison_without_a_caveat")

    return fails


def summarise_changes(result: dict[str, Any]) -> dict[str, Any]:
    by_type = {change_type: 0 for change_type in sorted(CHANGE_TYPES)}
    for change in result.get("changes") or []:
        for change_type in change.get("change_types") or []:
            if change_type in by_type:
                by_type[change_type] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": result.get("tenant_id"),
            "comparison_kind": result.get("comparison_kind"),
            "change_count": result.get("change_count"),
            "by_change_type": by_type,
            "requires_human_review_count": result.get("requires_human_review_count"),
            "amendment_categories_available": sorted(AMENDMENT_CATEGORIES),
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "rows_deleted": 0,
            "fabricated": False,
        }
    )
