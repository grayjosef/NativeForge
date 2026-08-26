"""Deadline provenance (Gate 87B).

Gate 86 answered "can this deadline be parsed". This answers the harder
question: **can it be trusted.**

A parsed date and a trustworthy date are not the same thing, and conflating them
is how 40 records carrying an identical year-end sentinel came to be counted
alongside 19 fetched deadlines as though the two were equivalent.

## Statuses

``verified_deadline``
    Normalized, and the record carries the artefacts a real fetch leaves
    behind - a check timestamp plus an upstream identifier or URL.

``unverified_deadline``
    Normalized, but the supporting evidence is incomplete. Not a claim that the
    date is wrong; a refusal to call it right.

``suspected_placeholder``
    Normalized, and the surrounding evidence says it does not behave like a
    fetched deadline. Requires **local corroborating evidence** - never asserted
    from the value alone.

``missing_deadline``
    No raw value.

``unknown_deadline``
    A raw value that does not resolve to a date.

## The rule this module refuses to break

A suspicion is not a finding. ``suspected_placeholder`` blocks freshness and
excludes a date from the verified count, but it never says the date is false,
never deletes a record, and never rewrites a value. The record stays visible
with its raw deadline intact and the reasons attached.

Equally, the absence of a suspicion is not a verification. A date with no
evidence either way is ``unverified_deadline``, not ``verified_deadline``.

## Why cluster context is an argument

Placeholder detection cannot work one record at a time. A single date of
``2026-12-31`` says nothing; forty identical ones, in a batch where no record
carries a fetch timestamp, say a great deal - especially when a comparable batch
in the same corpus shows fifteen distinct dates across nineteen records and a
timestamp on every one.

So the caller computes the cluster picture from the corpus and passes it in.
The classifier does no I/O and no corpus loading of its own.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_deadline_provenance_v1"

PROVENANCE_STATUSES = frozenset(
    {
        "verified_deadline",
        "unverified_deadline",
        "suspected_placeholder",
        "missing_deadline",
        "unknown_deadline",
    }
)

# How much the record itself supports its own deadline.
EVIDENCE_LEVELS = frozenset(
    {
        "none",
        # A flag on the record says it was fetched, with nothing to back it.
        "self_asserted",
        # A check timestamp: somebody looked, at a known time.
        "checked",
        # A timestamp plus an upstream identifier or URL to point at.
        "corroborated",
    }
)

# Statuses that may never yield a freshness state, whatever else is present.
FRESHNESS_BLOCKING_STATUSES = frozenset(
    {"suspected_placeholder", "unknown_deadline", "missing_deadline"}
)

# Only this status counts toward `verified_deadlines`.
VERIFIED_STATUSES = frozenset({"verified_deadline"})

# A cluster this large, with no fetch evidence anywhere in it, is the pattern
# Gate 87A documented. Set well above the largest innocent repeat in the corpus
# (two records legitimately sharing a close date) so ordinary coincidence cannot
# trip it.
PLACEHOLDER_CLUSTER_MIN = 10

# Sentinel dates: conventional "far future" stand-ins. Presence here is a
# *supporting* signal only. It never triggers a suspicion on its own, because a
# real notice may genuinely close on December 31.
SENTINEL_DATE_SUFFIXES: tuple[str, ...] = ("-12-31", "-01-01", "-06-30", "-09-30")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_deadline_cluster_context(
    *, records: list[dict[str, Any]], deadline_field: str = "application_deadline"
) -> dict[str, Any]:
    """Summarise how each raw deadline value is distributed across a corpus.

    Pure counting over records the caller already holds. No I/O.

    For each distinct raw value: how many records carry it, and how many of
    those carry a check timestamp. A value shared by many records where *none*
    has been checked is the shape Gate 87A found.
    """
    sizes: dict[str, int] = {}
    checked: dict[str, int] = {}

    for record in records:
        raw = record.get(deadline_field)
        if not isinstance(raw, str) or not raw.strip():
            continue
        key = raw.strip()
        sizes[key] = sizes.get(key, 0) + 1
        if record.get("ingested_at"):
            checked[key] = checked.get(key, 0) + 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cluster_sizes": sizes,
            "cluster_checked_counts": {k: checked.get(k, 0) for k in sizes},
            "distinct_values": len(sizes),
            "largest_cluster": max(sizes.values()) if sizes else 0,
        }
    )


def classify_deadline_provenance(
    *,
    raw_deadline: Any,
    normalized_deadline: str | None,
    checked_at: Any = None,
    source_url: Any = None,
    upstream_id: Any = None,
    fetch_asserted: bool = False,
    cluster_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify one already-parsed deadline.

    ``normalized_deadline`` comes from
    :mod:`deadline_normalization_service`; this module never parses.

    ``fetch_asserted`` is the record's own claim (``real_fetch``,
    ``detail_live`` and friends). It is recorded but deliberately carries little
    weight: an assertion with none of a fetch's artefacts is what the Gate 87A
    cluster consists of.
    """
    evidence_reasons: list[str] = []
    warning_reasons: list[str] = []
    blocked_reasons: list[str] = []

    has_raw = isinstance(raw_deadline, str) and bool(raw_deadline.strip())

    if not has_raw:
        return _result(
            raw_deadline=raw_deadline,
            normalized_deadline=None,
            provenance_status="missing_deadline",
            evidence_level="none",
            blocked_reasons=["no_raw_deadline"],
        )

    if not normalized_deadline:
        return _result(
            raw_deadline=raw_deadline,
            normalized_deadline=None,
            provenance_status="unknown_deadline",
            evidence_level="none",
            warning_reasons=["raw_deadline_present_but_unresolved"],
            blocked_reasons=["deadline_did_not_normalize"],
        )

    # -- evidence on the record itself ------------------------------------
    has_checked = bool(checked_at)
    has_pointer = bool(source_url) or bool(upstream_id)

    if has_checked:
        evidence_reasons.append("checked_at_present")
    else:
        warning_reasons.append("never_checked")
    if source_url:
        evidence_reasons.append("source_url_present")
    if upstream_id:
        evidence_reasons.append("upstream_identifier_present")
    if fetch_asserted and not (has_checked or has_pointer):
        # The Gate 87A pattern in one line.
        warning_reasons.append("fetch_asserted_without_fetch_artefacts")

    if has_checked and has_pointer:
        evidence_level = "corroborated"
    elif has_checked:
        evidence_level = "checked"
    elif fetch_asserted or has_pointer:
        evidence_level = "self_asserted"
    else:
        evidence_level = "none"

    # -- cluster suspicion -------------------------------------------------
    # Requires local corroborating evidence, never the date's value alone.
    context = cluster_context or {}
    key = raw_deadline.strip()
    cluster_size = int((context.get("cluster_sizes") or {}).get(key, 0) or 0)
    cluster_checked = int(
        (context.get("cluster_checked_counts") or {}).get(key, 0) or 0
    )

    suspected = False
    if cluster_size >= PLACEHOLDER_CLUSTER_MIN and cluster_checked == 0:
        # Many records share this exact value and not one of them has ever been
        # checked. Either every one was fetched and they all coincidentally
        # close on the same day with no timestamps, or the value is a default.
        suspected = True
        warning_reasons.append(f"shared_by_{cluster_size}_records")
        warning_reasons.append("no_record_sharing_this_value_has_been_checked")
        if any(key.endswith(s) for s in SENTINEL_DATE_SUFFIXES):
            # Supporting only. Never sufficient on its own - see the guard
            # below, which requires the cluster condition first.
            warning_reasons.append("value_is_a_conventional_sentinel_date")

    if suspected:
        blocked_reasons.append("suspected_placeholder_may_not_produce_freshness")
        return _result(
            raw_deadline=raw_deadline,
            normalized_deadline=normalized_deadline,
            provenance_status="suspected_placeholder",
            evidence_level=evidence_level,
            evidence_reasons=evidence_reasons,
            warning_reasons=warning_reasons,
            blocked_reasons=blocked_reasons,
        )

    if evidence_level == "corroborated":
        status = "verified_deadline"
        evidence_reasons.append("checked_and_pointed_at_a_source")
    else:
        status = "unverified_deadline"
        if not has_checked:
            blocked_reasons.append("unverified_and_never_checked")

    return _result(
        raw_deadline=raw_deadline,
        normalized_deadline=normalized_deadline,
        provenance_status=status,
        evidence_level=evidence_level,
        evidence_reasons=evidence_reasons,
        warning_reasons=warning_reasons,
        blocked_reasons=blocked_reasons,
        freshness_allowed=has_checked,
    )


def _result(
    *,
    raw_deadline: Any,
    normalized_deadline: str | None,
    provenance_status: str,
    evidence_level: str,
    evidence_reasons: list[str] | None = None,
    warning_reasons: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
    freshness_allowed: bool = False,
) -> dict[str, Any]:
    # Blocking statuses override any freshness the caller thought was available.
    if provenance_status in FRESHNESS_BLOCKING_STATUSES:
        freshness_allowed = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "raw_deadline": raw_deadline,
            "normalized_deadline": normalized_deadline,
            "provenance_status": provenance_status,
            "evidence_level": evidence_level,
            "evidence_reasons": list(evidence_reasons or []),
            "warning_reasons": list(warning_reasons or []),
            "blocked_reasons": list(blocked_reasons or []),
            "freshness_allowed": bool(freshness_allowed),
            # A raw deadline stays counted as raw whatever the verdict. The
            # record is never hidden and the value is never rewritten.
            "deadline_counts_as_raw": isinstance(raw_deadline, str)
            and bool(raw_deadline.strip()),
            "deadline_counts_as_verified": provenance_status in VERIFIED_STATUSES,
            "fabricated": False,
        }
    )


def summarise_provenance(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(PROVENANCE_STATUSES)}
    by_evidence = {level: 0 for level in sorted(EVIDENCE_LEVELS)}
    for r in results:
        status = r.get("provenance_status")
        if status in by_status:
            by_status[status] += 1
        level = r.get("evidence_level")
        if level in by_evidence:
            by_evidence[level] += 1

    raw = sum(1 for r in results if r.get("deadline_counts_as_raw"))
    verified = sum(1 for r in results if r.get("deadline_counts_as_verified"))
    suspected = by_status["suspected_placeholder"]
    blocked = sum(
        1
        for r in results
        if r.get("deadline_counts_as_raw") and not r.get("freshness_allowed")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total": len(results),
            "raw_deadlines": raw,
            "verified_deadlines": verified,
            "suspected_placeholder_deadlines": suspected,
            "freshness_blocked_by_deadline_provenance": blocked,
            "by_provenance_status": by_status,
            "by_evidence_level": by_evidence,
            # Both rates are over records that actually have a deadline. A
            # record with none is not a verification failure.
            "deadline_verification_rate": (
                round(verified / raw, 4) if raw else 0.0
            ),
            "placeholder_suspicion_rate": (
                round(suspected / raw, 4) if raw else 0.0
            ),
            "records_removed": 0,
            "records_hidden": 0,
            "deadlines_rewritten": 0,
            "fabricated": False,
        }
    )


def provenance_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    status = result.get("provenance_status")
    if status not in PROVENANCE_STATUSES:
        fails.append(f"provenance_status_out_of_vocabulary:{status}")
    if result.get("evidence_level") not in EVIDENCE_LEVELS:
        fails.append("evidence_level_out_of_vocabulary")

    # A blocking status must actually block.
    if status in FRESHNESS_BLOCKING_STATUSES and result.get("freshness_allowed"):
        fails.append(f"freshness_allowed_under_blocking_status:{status}")

    # Verification is a claim and needs the evidence that justifies it.
    if status == "verified_deadline":
        if result.get("evidence_level") != "corroborated":
            fails.append("verified_without_corroborating_evidence")
        if not result.get("normalized_deadline"):
            fails.append("verified_without_a_normalized_date")
    elif result.get("deadline_counts_as_verified"):
        fails.append("counts_as_verified_without_verified_status")

    # A suspicion must show its working, and must never rest on the date alone.
    if status == "suspected_placeholder":
        if not result.get("warning_reasons"):
            fails.append("suspicion_without_stated_reasons")
        if not any(
            str(w).startswith("shared_by_")
            for w in (result.get("warning_reasons") or [])
        ):
            fails.append("suspicion_without_cluster_evidence")
        if not result.get("normalized_deadline"):
            fails.append("suspicion_recorded_without_the_parsed_value")

    # The raw value is never discarded, whatever the verdict.
    if result.get("deadline_counts_as_raw") and not result.get("raw_deadline"):
        fails.append("counts_as_raw_without_a_raw_value")
    if status != "missing_deadline" and not result.get("deadline_counts_as_raw"):
        fails.append("raw_deadline_dropped_by_classification")

    return fails
