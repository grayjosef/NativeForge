"""Corpus provenance evidence (Gate 88B).

Gate 87 asked whether a *deadline* could be trusted. This asks the same question
of the record itself: is there committed evidence that it was ever recorded from
anywhere?

Baseline X reported ``recorded_records: 162`` on the strength of boolean flags.
This module separates the records with an artefact behind them from the records
with an assertion.

## Why a flag is not evidence

``never_synthesized: True`` is a hardcoded literal in
``source_fetch_adapter_contract_service`` - assigned unconditionally to every
payload the adapter builds. It cannot distinguish one record from another.

``real_fetch: true`` is better: ``real_fetch_honest_labeling_guard_service``
enforces that it implies ``fetch_mode == "live"``, ``search_live`` and
``detail_live``. That is a genuine fail-closed guard and it catches a fixture
mislabelled as a live fetch. But every input it inspects is a boolean on the
same payload, so it proves internal consistency, not that a request happened.

Hence the rule this module is built on: **no combination of flags on a record
can make that record verified.**

## What counts as independent

An artefact is independent when it carries information the corpus row could not
have supplied. A row cannot be the source of data it does not contain, so
33 transport fields absent from the row establish the direction of derivation.

The converse is a fixture that names the row as its ``source_of_values``. That
is ``recorded_circular``: it confirms the repository is internally consistent
and nothing more. The caller reports which case applies; this module does not
open files.

## Statuses

``recorded_verified``     an independent artefact backs the record
``recorded_circular``     an artefact exists but is derived from the record
``recorded_asserted``     flags and possibly metadata, no artefact
``synthetic_declared``    the record says it was synthesised
``demo_synthetic``        the record is demo scaffolding
``unknown_provenance``    not enough to place it
``missing_provenance``    nothing at all

``live`` is deliberately absent. Nothing in this repository can produce a live
record, and a status that cannot be reached is better than one that can be
reached by mistake - so ``record_counts_as_live`` is a constant ``False``.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_corpus_provenance_evidence_v1"

PROVENANCE_STATUSES = frozenset(
    {
        "recorded_verified",
        "recorded_circular",
        "recorded_asserted",
        "synthetic_declared",
        "demo_synthetic",
        "unknown_provenance",
        "missing_provenance",
    }
)

# Ordered weakest to strongest. The status says what is proven; this says how
# close the rest comes, so that a record with a check timestamp and an upstream
# identifier is not filed alongside one carrying four booleans.
EVIDENCE_LEVELS: tuple[str, ...] = (
    "none",
    "flags_only",
    "metadata",
    "checked_metadata",
    "upstream_identified",
    "circular_artifact",
    "independent_artifact",
)

# Only this status may count toward a verified recorded total.
VERIFIED_STATUSES = frozenset({"recorded_verified"})

# Statuses that still describe a record derived from somewhere real, whatever
# the strength of the evidence. Used for the broad `counts_as_recorded` view
# that Gate 85's composition figure represents.
RECORDED_STATUSES = frozenset(
    {"recorded_verified", "recorded_circular", "recorded_asserted"}
)

SYNTHETIC_STATUSES = frozenset({"synthetic_declared", "demo_synthetic"})

# Flags that assert a fetch. Recorded so the assertion is visible, never
# treated as proof.
FETCH_ASSERTION_FLAGS: tuple[str, ...] = (
    "real_fetch",
    "search_live",
    "detail_live",
)

# Set unconditionally by source_fetch_adapter_contract_service, so it is
# deliberately NOT in the list above - it carries no information.
NON_EVIDENTIAL_FLAGS: tuple[str, ...] = ("never_synthesized",)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def classify_corpus_provenance(
    *,
    record_id: str,
    source_file: str | None = None,
    fetch_assertion_flags: dict[str, Any] | None = None,
    checked_at: Any = None,
    provenance_block: Any = None,
    upstream_id: Any = None,
    source_url: Any = None,
    independent_artifact: Any = None,
    circular_artifact: Any = None,
    declared_synthetic: bool = False,
    declared_demo: bool = False,
) -> dict[str, Any]:
    """Classify one record's provenance from evidence the caller supplies.

    Performs no I/O. ``independent_artifact`` and ``circular_artifact`` are
    identifiers the caller has already resolved - typically a path plus the
    reason it qualifies - because deciding whether an artefact is independent
    means reading it, and reading belongs to the caller.
    """
    flags = dict(fetch_assertion_flags or {})
    evidence_reasons: list[str] = []
    warning_reasons: list[str] = []
    blocked_reasons: list[str] = []

    asserted = [f for f in FETCH_ASSERTION_FLAGS if flags.get(f) is True]
    for flag in asserted:
        warning_reasons.append(f"asserts_{flag}")
    for flag in NON_EVIDENTIAL_FLAGS:
        if flags.get(flag) is True:
            # Named explicitly so nobody later mistakes it for support.
            warning_reasons.append(f"{flag}_is_set_unconditionally_by_the_adapter")

    has_checked = bool(checked_at)
    has_provenance = bool(provenance_block)
    has_upstream = bool(upstream_id)
    has_url = bool(source_url)

    if has_checked:
        evidence_reasons.append("checked_at_present")
    if has_provenance:
        evidence_reasons.append("provenance_block_present")
    if has_upstream:
        evidence_reasons.append("upstream_identifier_present")
    if has_url:
        evidence_reasons.append("source_url_present")

    # -- declared synthesis wins: a record saying what it is beats inference --
    if declared_demo:
        return _result(
            record_id=record_id,
            source_file=source_file,
            provenance_status="demo_synthetic",
            evidence_level="metadata" if (has_provenance or has_url) else "none",
            evidence_reasons=[*evidence_reasons, "record_declares_demo_scaffolding"],
            warning_reasons=warning_reasons,
        )
    if declared_synthetic:
        return _result(
            record_id=record_id,
            source_file=source_file,
            provenance_status="synthetic_declared",
            evidence_level="metadata" if (has_provenance or has_url) else "none",
            evidence_reasons=[*evidence_reasons, "record_declares_synthesis"],
            warning_reasons=warning_reasons,
        )

    # -- artefacts ---------------------------------------------------------
    if independent_artifact:
        evidence_reasons.append(f"independent_artifact:{independent_artifact}")
        return _result(
            record_id=record_id,
            source_file=source_file,
            provenance_status="recorded_verified",
            evidence_level="independent_artifact",
            evidence_reasons=evidence_reasons,
            warning_reasons=warning_reasons,
        )

    if circular_artifact:
        warning_reasons.append(f"artifact_derived_from_this_record:{circular_artifact}")
        blocked_reasons.append("artifact_cannot_corroborate_its_own_source")
        return _result(
            record_id=record_id,
            source_file=source_file,
            provenance_status="recorded_circular",
            evidence_level="circular_artifact",
            evidence_reasons=evidence_reasons,
            warning_reasons=warning_reasons,
            blocked_reasons=blocked_reasons,
        )

    # -- no artefact: the best available is an assertion -------------------
    if has_checked and has_upstream:
        level = "upstream_identified"
    elif has_checked and (has_provenance or has_url):
        level = "checked_metadata"
    elif has_provenance or has_url or has_upstream:
        level = "metadata"
    elif asserted:
        level = "flags_only"
    else:
        level = "none"

    if level == "none":
        return _result(
            record_id=record_id,
            source_file=source_file,
            provenance_status="missing_provenance",
            evidence_level="none",
            warning_reasons=warning_reasons,
            blocked_reasons=["no_provenance_evidence_of_any_kind"],
        )

    blocked_reasons.append("no_independent_artifact")
    if level == "flags_only":
        # The Gate 88A finding in one line: a claim with nothing behind it.
        warning_reasons.append("fetch_asserted_without_any_fetch_artefact")

    return _result(
        record_id=record_id,
        source_file=source_file,
        provenance_status="recorded_asserted",
        evidence_level=level,
        evidence_reasons=evidence_reasons,
        warning_reasons=warning_reasons,
        blocked_reasons=blocked_reasons,
    )


def _result(
    *,
    record_id: str,
    source_file: str | None,
    provenance_status: str,
    evidence_level: str,
    evidence_reasons: list[str] | None = None,
    warning_reasons: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_id": record_id,
            "source_file": source_file,
            "provenance_status": provenance_status,
            "evidence_level": evidence_level,
            "evidence_reasons": list(evidence_reasons or []),
            "warning_reasons": list(warning_reasons or []),
            "blocked_reasons": list(blocked_reasons or []),
            "record_counts_as_recorded": provenance_status in RECORDED_STATUSES,
            "record_counts_as_verified_recorded": provenance_status
            in VERIFIED_STATUSES,
            "record_counts_as_synthetic": provenance_status in SYNTHETIC_STATUSES,
            # Constant. Nothing in this repository can produce a live record,
            # and this gate creates no runtime proof of one.
            "record_counts_as_live": False,
            "fabricated": False,
        }
    )


def summarise_corpus_provenance(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(PROVENANCE_STATUSES)}
    by_evidence = {level: 0 for level in EVIDENCE_LEVELS}
    for r in results:
        status = r.get("provenance_status")
        if status in by_status:
            by_status[status] += 1
        level = r.get("evidence_level")
        if level in by_evidence:
            by_evidence[level] += 1

    total = len(results)
    verified = by_status["recorded_verified"]
    asserted = by_status["recorded_asserted"]
    circular = by_status["recorded_circular"]
    recorded = verified + asserted + circular

    def _rate(n: int) -> float:
        return round(n / total, 4) if total else 0.0

    # The weakest tier, named: records whose only support is a boolean.
    flags_only = by_evidence["flags_only"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total": total,
            "recorded_verified_records": verified,
            "recorded_asserted_records": asserted,
            "recorded_circular_records": circular,
            "synthetic_declared_records": by_status["synthetic_declared"],
            "demo_synthetic_records": by_status["demo_synthetic"],
            "unknown_provenance_records": by_status["unknown_provenance"],
            "missing_provenance_records": by_status["missing_provenance"],
            "records_counted_as_recorded": recorded,
            "flags_only_records": flags_only,
            "by_provenance_status": by_status,
            "by_evidence_level": by_evidence,
            "verified_recorded_rate": _rate(verified),
            "asserted_recorded_rate": _rate(asserted),
            "circular_recorded_rate": _rate(circular),
            # How far the broad recorded count exceeds what an artefact backs.
            "recorded_count_overstated_by": recorded - verified,
            "live_records": 0,
            "records_removed": 0,
            "records_hidden": 0,
            "fabricated": False,
        }
    )


def provenance_confidence_level(summary: dict[str, Any]) -> str:
    """One word for how much of the corpus stands on an artefact."""
    total = int(summary.get("total") or 0)
    verified = int(summary.get("recorded_verified_records") or 0)
    if not total:
        return "none"
    share = verified / total
    if share >= 0.9:
        return "artifact_backed"
    if share >= 0.5:
        return "mixed_artifact_and_assertion"
    if verified:
        return "predominantly_asserted"
    return "assertion_only"


def corpus_provenance_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    # Never reachable, and checked anyway.
    if result.get("record_counts_as_live") is not False:
        fails.append("live_record_claimed")

    status = result.get("provenance_status")
    if status not in PROVENANCE_STATUSES:
        fails.append(f"provenance_status_out_of_vocabulary:{status}")
    if result.get("evidence_level") not in EVIDENCE_LEVELS:
        fails.append("evidence_level_out_of_vocabulary")

    # Verification is the strongest claim and needs the strongest evidence.
    if status == "recorded_verified":
        if result.get("evidence_level") != "independent_artifact":
            fails.append("verified_without_an_independent_artifact")
        if not any(
            str(e).startswith("independent_artifact:")
            for e in (result.get("evidence_reasons") or [])
        ):
            fails.append("verified_without_naming_the_artifact")
    elif result.get("record_counts_as_verified_recorded"):
        fails.append("counts_as_verified_without_verified_status")

    # A circular artefact must never be allowed to read as corroboration.
    if status == "recorded_circular":
        if result.get("record_counts_as_verified_recorded"):
            fails.append("circular_artifact_counted_as_verified")
        if not result.get("blocked_reasons"):
            fails.append("circular_status_without_a_stated_reason")

    # The core rule: flags alone can never verify.
    if result.get("evidence_level") == "flags_only" and status not in {
        "recorded_asserted",
        "unknown_provenance",
        "missing_provenance",
    }:
        fails.append(f"flags_only_evidence_reached_status:{status}")

    if status == "missing_provenance" and result.get("record_counts_as_recorded"):
        fails.append("missing_provenance_counted_as_recorded")

    # A verdict never costs a record its identity.
    if not result.get("record_id"):
        fails.append("classification_without_a_record_id")

    return fails
