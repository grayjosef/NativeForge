"""Grant lane separation (Gate 91B).

Splits a customer's grant records into **pursuit** lanes and **awarded** lanes.

## Why this is not just another status field

A pursuit is a possibility. An award is an obligation - reporting, financial,
performance, compliance and closeout duties that begin on award and run for
years, with federal deadlines attached.

Moving between them is not a status update, it is a change in what the customer
owes. Gate 91A confirmed the current model cannot express that:
``GrantPipelineStage.awarded`` is a plain enum member assignable by anything,
and it is the only place the word "awarded" appears in the codebase.

So this module declares a separate lane vocabulary and derives the
pursuit/awarded split from it, rather than reading a stage field and hoping.

## Deny by default on `unknown`

``unknown`` is neither a pursuit lane nor an awarded lane. It is explicitly in
neither set, and both ``is_pursuit`` and ``is_awarded`` are ``False`` for it.

That matters in both directions. Defaulting unknown to *pursuit* would hide a
real award and its deadlines; defaulting it to *awarded* would invent
obligations nobody agreed to. The honest answer is that the lane is unresolved
and a person needs to look, which is what ``human_review_required`` says.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_grant_lane_separation_v1"

GRANT_LANES = frozenset(
    {
        "pursuit",
        "application_in_progress",
        "submitted",
        "award_pending",
        "awarded_active",
        "awarded_closeout",
        "awarded_closed",
        "not_pursued",
        "archived",
        "unknown",
    }
)

# The three lanes that mean the customer holds an award. Membership here is what
# turns on active obligation tracking.
AWARDED_LANES = frozenset({"awarded_active", "awarded_closeout", "awarded_closed"})

# The four lanes that mean the customer is still deciding or applying.
PURSUIT_LANES = frozenset(
    {"pursuit", "application_in_progress", "submitted", "award_pending"}
)

# Neither active pursuit nor active award. Kept visible rather than dropped: a
# record that disappears looks like one that never existed.
INACTIVE_LANES = frozenset({"not_pursued", "archived"})

# Derived, not listed. A lane added later belongs to no category until somebody
# deliberately places it, and lands in `unknown` handling meanwhile.
UNCATEGORISED_LANES = GRANT_LANES - AWARDED_LANES - PURSUIT_LANES - INACTIVE_LANES

# Only an awarded lane may carry active reporting obligations.
REPORTING_TRACKING_LANES = AWARDED_LANES

# Only a pursuit lane still has an application to track.
APPLICATION_TRACKING_LANES = PURSUIT_LANES

# Lanes a record may not be moved *out of* into an award without human review.
# Marking something archived or explicitly not-pursued as awarded is either a
# correction of a mistake or a mistake in itself, and a person should say which.
REVIEW_REQUIRED_SOURCE_LANES = INACTIVE_LANES

LANE_CONFIDENCES = frozenset({"declared", "derived", "unresolved"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def classify_grant_lane(
    *,
    grant_record_id: str,
    lane: str | None = None,
    source_opportunity_id: str | None = None,
    customer_org_id: str | None = None,
    lane_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Classify one customer grant record into a lane.

    ``lane`` is the customer's or the workflow's declared lane. An unrecognised
    or absent value resolves to ``unknown`` - never to a guess.
    """
    evidence = list(lane_evidence or [])
    blocked: list[str] = []
    declared = (lane or "").strip()

    if declared in GRANT_LANES:
        resolved = declared
        confidence = "declared"
        evidence.append(f"lane_declared:{declared}")
    elif declared:
        resolved = "unknown"
        confidence = "unresolved"
        blocked.append(f"unrecognised_lane:{declared}")
    else:
        resolved = "unknown"
        confidence = "unresolved"
        blocked.append("no_lane_declared")

    is_awarded = resolved in AWARDED_LANES
    is_pursuit = resolved in PURSUIT_LANES

    if not customer_org_id:
        # A grant record without a customer is not a customer's grant.
        blocked.append("no_customer_org_id")

    human_review = resolved == "unknown" or not customer_org_id

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_record_id": grant_record_id,
            "source_opportunity_id": source_opportunity_id,
            "customer_org_id": customer_org_id,
            "lane": resolved,
            "lane_confidence": confidence,
            "lane_evidence": evidence,
            "is_pursuit": is_pursuit,
            "is_awarded": is_awarded,
            # Active obligations, only from an awarded lane.
            "requires_reporting_tracking": resolved in REPORTING_TRACKING_LANES,
            # An application to finish, only from a pursuit lane.
            "requires_application_tracking": resolved in APPLICATION_TRACKING_LANES,
            "blocked_reasons": blocked,
            "human_review_required": human_review,
            # Said out loud: a stage value is not a lane, and neither is an
            # awarded-grant record.
            "pipeline_stage_is_not_a_lane": True,
            "fabricated": False,
        }
    )


def separate_grant_lanes(*, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Split a set of customer grant records into the two portfolios."""
    classified = [
        classify_grant_lane(
            grant_record_id=str(r.get("grant_record_id") or ""),
            lane=r.get("lane"),
            source_opportunity_id=r.get("source_opportunity_id"),
            customer_org_id=r.get("customer_org_id"),
            lane_evidence=r.get("lane_evidence"),
        )
        for r in records
    ]

    pursuit = [c for c in classified if c["is_pursuit"]]
    awarded = [c for c in classified if c["is_awarded"]]
    inactive = [c for c in classified if c["lane"] in INACTIVE_LANES]
    unresolved = [c for c in classified if c["lane"] == "unknown"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total_records": len(classified),
            "pursuit_records": pursuit,
            "awarded_records": awarded,
            "inactive_records": inactive,
            "unresolved_records": unresolved,
            "pursuit_count": len(pursuit),
            "awarded_count": len(awarded),
            "inactive_count": len(inactive),
            "unresolved_count": len(unresolved),
            "records_removed": 0,
            "records_hidden": 0,
            "fabricated": False,
        }
    )


def lane_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Checks one classification or one separation result."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    single = "lane" in result
    entries = [result] if single else (
        (result.get("pursuit_records") or [])
        + (result.get("awarded_records") or [])
        + (result.get("inactive_records") or [])
        + (result.get("unresolved_records") or [])
    )

    for entry in entries:
        rid = entry.get("grant_record_id")
        lane = entry.get("lane")

        if lane not in GRANT_LANES:
            fails.append(f"lane_out_of_vocabulary:{lane}")
        if entry.get("lane_confidence") not in LANE_CONFIDENCES:
            fails.append(f"lane_confidence_out_of_vocabulary:{rid}")

        # The core separation: never both, and unknown is never either.
        if entry.get("is_pursuit") and entry.get("is_awarded"):
            fails.append(f"record_is_both_pursuit_and_awarded:{rid}")
        if lane == "unknown" and (entry.get("is_pursuit") or entry.get("is_awarded")):
            fails.append(f"unknown_lane_defaulted:{rid}")
        if lane in INACTIVE_LANES and (
            entry.get("is_pursuit") or entry.get("is_awarded")
        ):
            fails.append(f"inactive_lane_treated_as_active:{rid}")

        # Active reporting obligations require an awarded lane, full stop.
        if entry.get("requires_reporting_tracking") and lane not in AWARDED_LANES:
            fails.append(f"reporting_tracking_without_awarded_lane:{rid}")
        if entry.get("requires_application_tracking") and lane not in PURSUIT_LANES:
            fails.append(f"application_tracking_without_pursuit_lane:{rid}")

        if lane == "unknown" and not entry.get("human_review_required"):
            fails.append(f"unknown_lane_without_human_review:{rid}")

    if not single:
        total = int(result.get("total_records") or 0)
        counted = (
            int(result.get("pursuit_count") or 0)
            + int(result.get("awarded_count") or 0)
            + int(result.get("inactive_count") or 0)
            + int(result.get("unresolved_count") or 0)
        )
        if counted != total:
            fails.append("lane_counts_do_not_cover_every_record")
        for field in ("records_removed", "records_hidden"):
            if result.get(field):
                fails.append(f"separation_altered_the_records:{field}")

    return fails
