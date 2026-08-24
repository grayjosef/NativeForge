"""Opportunity freshness, amendment and supersession (Gate 76D).

The survey found sixteen freshness-adjacent services and all of them answer a
different question: *source* freshness, "when did we last look at this page".
This module answers **opportunity** freshness — "is this grant still open, was it
amended, has a newer version replaced it".

They are not the same question and conflating them is expensive. A source checked
an hour ago can serve a grant that closed last month, and showing a customer that
grant as current is the failure that costs them a deadline. That is the single
worst thing this product could do to a tribal grant office.

Rules that are enforced rather than documented:

  * A close date in the past is **expired**, unless there is evidence of an
    extension or amendment. Not "probably still fine".
  * A missing close date is **unknown**, never fresh. Absence of a deadline is
    absence of information.
  * A missing check timestamp is **unknown**. We cannot vouch for what we have
    not looked at.
  * A newer version supersedes an older one **only with evidence**. Same title
    and funder is a coincidence generator, not a supersession proof.
  * Stale and expired opportunities stay **visible** as stale and expired. A
    grant that vanishes looks like a grant we never found.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_opportunity_freshness_v1"

FRESHNESS_STATES = frozenset(
    {"fresh", "stale", "expired", "amended", "superseded", "unknown"}
)

# Only these count toward current discovery quality. Derived, so a state added
# later is excluded until someone deliberately includes it.
CURRENT_STATES = frozenset({"fresh", "amended"})
NON_CURRENT_STATES = FRESHNESS_STATES - CURRENT_STATES

# Every state keeps the opportunity visible. Visibility and currency are
# different properties, and collapsing them loses the audit trail of what we
# once found.
VISIBLE_STATES = FRESHNESS_STATES

# What counts as evidence that a closed date moved. A caller asserting
# "extended" without one of these does not move the state.
EXTENSION_EVIDENCE_KINDS = frozenset(
    {
        "amendment_notice_url",
        "federal_register_notice_url",
        "funder_announcement_url",
        "operator_verified_extension",
    }
)

# What counts as evidence that a newer version replaces an older one.
SUPERSESSION_EVIDENCE_KINDS = frozenset(
    {
        "same_opportunity_number",
        "amendment_notice_url",
        "funder_stated_supersession",
        "operator_verified_supersession",
    }
)

# Staleness thresholds in days since last check, for an opportunity that is
# otherwise open.
AGING_AFTER_DAYS = 14
STALE_AFTER_DAYS = 30


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _evidence_kinds(evidence: list[dict[str, Any]] | None) -> set[str]:
    """Collect the declared kinds from an evidence list.

    An evidence entry needs both a recognised ``kind`` and a non-empty
    ``reference``. A kind with nothing behind it is an assertion wearing the
    word evidence.
    """
    kinds: set[str] = set()
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        reference = item.get("reference")
        if kind and reference and str(reference).strip():
            kinds.add(kind)
    return kinds


def _days_between(earlier: str | None, later: str | None) -> int | None:
    """Whole days between two ISO-8601 date strings, or None if uncomputable.

    Deliberately string-based and lexicographic-safe: callers across this
    codebase pass ``YYYY-MM-DD`` or full ISO timestamps, and parsing with
    ``datetime`` here would need a timezone policy this module has no business
    setting. Only the date part is used.
    """
    if not earlier or not later:
        return None
    try:
        from datetime import date

        a = date.fromisoformat(str(earlier)[:10])
        b = date.fromisoformat(str(later)[:10])
    except (ValueError, TypeError):
        return None
    return (b - a).days


def evaluate_opportunity_freshness(
    *,
    opportunity_id: str,
    close_date: str | None = None,
    posted_date: str | None = None,
    amendment_date: str | None = None,
    version: str | int | None = None,
    last_checked_at: str | None = None,
    now: str | None = None,
    extension_evidence: list[dict[str, Any]] | None = None,
    superseded_by: str | None = None,
    supersession_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve one opportunity's freshness state.

    ``now`` is caller-supplied so the result is deterministic under test rather
    than dependent on the wall clock — the mistake caught in Gate 60.
    """
    reasons: list[str] = []
    state = "unknown"

    ext_kinds = _evidence_kinds(extension_evidence) & EXTENSION_EVIDENCE_KINDS
    sup_kinds = _evidence_kinds(supersession_evidence) & SUPERSESSION_EVIDENCE_KINDS

    # ── supersession first: it overrides everything else ─────────────────
    if superseded_by:
        if sup_kinds:
            state = "superseded"
            reasons.append("superseded_with_evidence")
        else:
            # Claimed supersession with no evidence must not silently hide the
            # older opportunity — that would remove a real grant from view on
            # somebody's say-so.
            reasons.append("supersession_claimed_without_evidence")

    if state == "unknown":
        if not last_checked_at:
            # We cannot vouch for what we have not looked at.
            reasons.append("never_checked")
        elif not close_date:
            reasons.append("no_close_date")
        else:
            days_to_close = _days_between(now, close_date) if now else None
            if days_to_close is None:
                reasons.append("close_date_or_now_unparseable")
            elif days_to_close < 0:
                # Past its close date.
                if ext_kinds:
                    state = "amended"
                    reasons.append("closed_but_extension_evidence_present")
                else:
                    state = "expired"
                    reasons.append(f"close_date_passed_{abs(days_to_close)}_days_ago")
            else:
                # Still open. How long since we looked?
                age = _days_between(last_checked_at, now) if now else None
                if age is None:
                    reasons.append("last_checked_or_now_unparseable")
                elif age > STALE_AFTER_DAYS:
                    state = "stale"
                    reasons.append(f"not_checked_for_{age}_days")
                elif amendment_date and str(amendment_date) > str(posted_date or ""):
                    state = "amended"
                    reasons.append("amendment_date_newer_than_posted_date")
                elif age > AGING_AFTER_DAYS:
                    state = "fresh"
                    reasons.append(f"aging_but_open_checked_{age}_days_ago")
                else:
                    state = "fresh"

    counts_as_current = state in CURRENT_STATES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "freshness_state": state,
            "reasons": reasons,
            "close_date": close_date,
            "posted_date": posted_date,
            "amendment_date": amendment_date,
            "version": str(version) if version is not None else None,
            "last_checked_at": last_checked_at,
            "observed_at": now,
            "superseded_by": superseded_by if state == "superseded" else None,
            "supersession_evidence_kinds": sorted(sup_kinds),
            "extension_evidence_kinds": sorted(ext_kinds),
            # Visibility and currency are different properties.
            "visible": state in VISIBLE_STATES,
            "counts_as_current": counts_as_current,
            "counts_toward_quality": counts_as_current,
            "human_review_required": state == "unknown"
            or "supersession_claimed_without_evidence" in reasons,
        }
    )


def evaluate_supersession(
    *,
    older: dict[str, Any],
    newer: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Decide whether ``newer`` supersedes ``older``.

    Same source, title and funder is **not** sufficient. Agencies re-post
    similar programs annually, and treating a new fiscal year's NOFO as
    superseding last year's would erase a grant record that is still the correct
    reference for an in-flight application.
    """
    reasons: list[str] = []
    kinds = _evidence_kinds(evidence) & SUPERSESSION_EVIDENCE_KINDS

    same_source = older.get("source_id") and older.get("source_id") == newer.get(
        "source_id"
    )
    same_funder = older.get("agency_or_funder") and older.get(
        "agency_or_funder"
    ) == newer.get("agency_or_funder")
    same_title = older.get("title") and older.get("title") == newer.get("title")

    if not (same_source and same_funder and same_title):
        reasons.append("not_the_same_opportunity_lineage")
    if not kinds:
        reasons.append("no_supersession_evidence")

    newer_amendment = str(newer.get("amendment_date") or "")
    older_amendment = str(older.get("amendment_date") or older.get("posted_date") or "")
    if newer_amendment and older_amendment and newer_amendment <= older_amendment:
        reasons.append("newer_version_is_not_actually_newer")

    supersedes = not reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "older_opportunity_id": older.get("opportunity_id"),
            "newer_opportunity_id": newer.get("opportunity_id"),
            "supersedes": supersedes,
            "blocked_reasons": reasons,
            "evidence_kinds": sorted(kinds),
            "same_lineage": bool(same_source and same_funder and same_title),
            # The older record stays visible either way; supersession changes
            # what is current, not what existed.
            "older_remains_visible": True,
            "human_review_required": not supersedes and bool(kinds),
        }
    )


def freshness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("freshness_state") not in FRESHNESS_STATES:
        fails.append("freshness_state_invalid")

    state = result.get("freshness_state")

    if result.get("counts_as_current") and state not in CURRENT_STATES:
        fails.append(f"non_current_state_counted_as_current:{state}")
    if state in NON_CURRENT_STATES and result.get("counts_toward_quality"):
        fails.append(f"non_current_state_counted_toward_quality:{state}")

    # Freshness requires having looked, and having a deadline.
    if state == "fresh":
        if not result.get("last_checked_at"):
            fails.append("fresh_without_a_check_timestamp")
        if not result.get("close_date"):
            fails.append("fresh_without_a_close_date")

    if state == "superseded" and not result.get("supersession_evidence_kinds"):
        fails.append("superseded_without_evidence")

    # Nothing disappears.
    if not result.get("visible"):
        fails.append("opportunity_hidden_instead_of_marked")
    return fails


def supersession_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("supersedes"):
        if result.get("blocked_reasons"):
            fails.append("supersedes_with_blocked_reasons")
        if not result.get("evidence_kinds"):
            fails.append("supersedes_without_evidence")
        if not result.get("same_lineage"):
            fails.append("supersedes_across_different_lineage")
    if result.get("older_remains_visible") is not True:
        fails.append("older_opportunity_hidden")
    return fails
