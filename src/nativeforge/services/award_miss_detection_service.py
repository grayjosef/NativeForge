"""Gate 176E/I: evidence that NativeForge missed funding, and an honest
scorecard of how much it knows it does not know.

This is the uncomfortable half of the product. Everything else in the campaign
answers "what did we find". This answers:

```text
what does the world know about funding that we did not?
```

An award exists for a program we never observed as open. That is not a fact
about the funder - it is a fact about US. It is evidence AGAINST our coverage,
and the only honest thing to do with it is write it down where somebody has to
look at it.

Three refusals define this module:

**Never invent the solicitation.** The missing opportunity is missing. Writing
a placeholder canonical opportunity so the graph looks complete would turn a
coverage failure into a data-quality failure, and a Tribe would eventually see
a funding opportunity that never existed.

**Never mark coverage healthy to make the number look better.** A miss with no
resolution stays unresolved. `resolved_award_miss_count` counts resolutions,
not dismissals.

**Never auto-onboard the publisher.** The award names a source we do not
collect from; that is a candidate for review, and the Gate 162-171
authorization boundary says a human decides.

**The denominator problem (176I).** It is tempting to report "coverage: 94%".
We cannot. The denominator - how much Native-relevant funding exists - is
unknown and this system has no way to learn it. So the scorecard reports
counts and REFUSES to divide by an unknown, and says why.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.early_funding_signal_service import (
    AWARD_WITHOUT_SOLICITATION,
    DERIVED_FACT,
    MISS_EVIDENCE_TYPES,
    OBSERVED,
    OBSERVED_FACT,
    OPEN_STATES,
    RESOLVED,
    build_signal,
)

SCHEMA_VERSION = "nf_award_miss_detection_v1"

# --------------------------------------------------------------------
# how a miss was resolved - or was not
# --------------------------------------------------------------------

#: The solicitation was found after all, in a source we already collect.
FOUND_IN_EXISTING_SOURCE = "FOUND_IN_EXISTING_SOURCE"
#: The publisher was reviewed and onboarded by a human.
PUBLISHER_ONBOARDED = "PUBLISHER_ONBOARDED"
#: The award turned out not to come from a competitive solicitation at all.
NOT_A_SOLICITATION = "NOT_A_SOLICITATION"
#: Out of scope - not Native-relevant, not in our remit.
OUT_OF_SCOPE = "OUT_OF_SCOPE"
#: Still open.
UNRESOLVED = "UNRESOLVED"

RESOLUTIONS: tuple[str, ...] = (
    FOUND_IN_EXISTING_SOURCE,
    PUBLISHER_ONBOARDED,
    NOT_A_SOLICITATION,
    OUT_OF_SCOPE,
    UNRESOLVED,
)

RESOLUTION_MEANINGS: dict[str, str] = {
    FOUND_IN_EXISTING_SOURCE: (
        "the solicitation existed in a source we already collect and we had "
        "simply not linked it - a parsing or identity gap, not a coverage gap"
    ),
    PUBLISHER_ONBOARDED: (
        "a human reviewed the publisher and authorized collection - a real "
        "coverage gap, now closed"
    ),
    NOT_A_SOLICITATION: (
        "the money did not come from a competitive announcement - an earmark, "
        "a formula award, a continuation"
    ),
    OUT_OF_SCOPE: "reviewed and judged outside what NativeForge covers",
    UNRESOLVED: "nobody has answered the question yet",
}

#: Resolutions that count as ANSWERED. `UNRESOLVED` is excluded, obviously,
#: but so is nothing else - a dismissal is a decision and counts.
ANSWERED: frozenset[str] = frozenset(
    {FOUND_IN_EXISTING_SOURCE, PUBLISHER_ONBOARDED, NOT_A_SOLICITATION, OUT_OF_SCOPE}
)

#: Resolutions that indicate a REAL coverage failure rather than a linking
#: failure. Reported separately because they mean different work.
REAL_COVERAGE_FAILURE: frozenset[str] = frozenset({PUBLISHER_ONBOARDED})

MISS_FIELDS: tuple[str, ...] = (
    "miss_id",
    "award_ref",
    "award_number",
    "funder_name",
    "program_key",
    "program_name",
    "awarded_at",
    "signal_id",
    "publisher_key",
    "resolution",
    "resolved_by",
    "resolved_at",
    "searched_source_ids",
    "observed_solicitation_count",
    "evidence_ref",
    "award_is_demo_fixture",
    "counts_toward_real_metrics",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_miss_id(*, award_ref: Any, program_key: Any) -> str:
    parts = [str(award_ref or ""), str(program_key or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def detect_award_miss(
    *,
    award_ref: Any,
    observed_solicitation_count: int,
    searched_source_ids: list[str] | None = None,
    award_is_demo_fixture: bool = False,
    award_number: Any = None,
    funder_name: Any = None,
    program_key: Any = None,
    program_name: Any = None,
    awarded_at: Any = None,
    publisher_key: Any = None,
    evidence_ref: Any = None,
    supporting_text: Any = None,
    source_id: Any = None,
    raw_payload_sha256: Any = None,
    observed_at: Any = None,
) -> dict[str, Any] | None:
    """An award with no observed solicitation is evidence against our coverage.

    Returns None when a solicitation WAS observed - there is nothing to report
    and reporting it anyway would inflate the miss count.

    `observed_solicitation_count` is supplied by the caller that searched the
    graph, and `searched_source_ids` records WHERE it looked. A miss claimed
    without saying where we looked is not evidence, it is a shrug.
    """
    if int(observed_solicitation_count) > 0:
        return None

    signal = build_signal(
        signal_type=AWARD_WITHOUT_SOLICITATION,
        source_id=source_id,
        detail_key=str(award_ref),
        program_key=program_key,
        program_name=program_name,
        funder_name=funder_name,
        raw_payload_sha256=raw_payload_sha256,
        # The evidence for "this award had no solicitation" is the award
        # record itself. The caller may name it; if not, the award ref IS the
        # reference. Without this the trace fails its own evidence invariant
        # while the row beside it happily records the evidence_ref.
        document_ref=str(evidence_ref) if evidence_ref else f"award:{award_ref}",
        supporting_text=(
            supporting_text
            or f"award {award_number or award_ref} with no observed solicitation"
        ),
        confidence_class=OBSERVED_FACT if raw_payload_sha256 else DERIVED_FACT,
        signal_state=OBSERVED,
        observed_at=observed_at,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "miss_id": build_miss_id(award_ref=award_ref, program_key=program_key),
            "award_ref": str(award_ref),
            "award_number": str(award_number) if award_number else None,
            "funder_name": str(funder_name) if funder_name else None,
            "program_key": str(program_key) if program_key else None,
            "program_name": str(program_name) if program_name else None,
            "awarded_at": awarded_at,
            "signal_id": signal["signal_id"],
            "signal": signal,
            "publisher_key": str(publisher_key) if publisher_key else None,
            "resolution": UNRESOLVED,
            "resolved_by": None,
            "resolved_at": None,
            # WHERE we looked. Without this the miss is unfalsifiable.
            "searched_source_ids": sorted(searched_source_ids or []),
            "observed_solicitation_count": int(observed_solicitation_count),
            "evidence_ref": str(evidence_ref) if evidence_ref else None,
            # Provenance of the AWARD, not of the miss. Every award row in
            # this repository is a demo fixture, so without this the detector
            # would report 2,757 fabricated coverage failures.
            "award_is_demo_fixture": bool(award_is_demo_fixture),
            "counts_toward_real_metrics": not bool(award_is_demo_fixture),
            # The three refusals, stated on the row.
            "opportunity_invented": False,
            "coverage_marked_healthy": False,
            "source_auto_onboarded": False,
            "review_required": True,
        }
    )


def resolve_award_miss(
    *, miss: dict[str, Any], resolution: str, resolved_by: Any, resolved_at: Any = None
) -> dict[str, Any]:
    """Close a miss. A resolution needs a human and a reason in the vocabulary."""
    if str(resolution) not in RESOLUTIONS:
        return _json_safe(
            {"accepted": False, "why": f"unknown resolution {resolution}", "miss": miss}
        )
    if str(resolution) != UNRESOLVED and not resolved_by:
        return _json_safe(
            {
                "accepted": False,
                "why": "a resolution requires a human",
                "miss": miss,
            }
        )

    resolved = dict(miss)
    resolved["resolution"] = str(resolution)
    resolved["resolved_by"] = str(resolved_by) if resolved_by else None
    resolved["resolved_at"] = resolved_at
    signal = dict(resolved.get("signal") or {})
    if signal:
        signal["signal_state"] = RESOLVED
        resolved["signal"] = signal
    return _json_safe({"accepted": True, "miss": resolved})


def miss_invariant_failures(miss: dict[str, Any]) -> list[str]:
    """Refuse a miss record that invented, excused, or onboarded anything."""
    failures: list[str] = []

    for field in MISS_FIELDS:
        if field not in miss:
            failures.append(f"miss_missing_field:{field}")

    resolution = str(miss.get("resolution") or "")
    if resolution not in RESOLUTIONS:
        failures.append(f"resolution_outside_the_vocabulary:{resolution or 'missing'}")

    if not miss.get("award_ref"):
        failures.append("miss_names_no_award")

    # A miss claimed without saying where we looked is a shrug.
    if not miss.get("searched_source_ids"):
        failures.append("miss_does_not_say_where_it_looked")

    # The load-bearing refusals.
    if miss.get("opportunity_invented"):
        failures.append("miss_invented_a_solicitation")
    if miss.get("coverage_marked_healthy"):
        failures.append("miss_marked_coverage_healthy")
    if miss.get("source_auto_onboarded"):
        failures.append("miss_auto_onboarded_a_source")

    # A miss only exists when nothing was observed.
    if int(miss.get("observed_solicitation_count") or 0) > 0:
        failures.append("miss_recorded_despite_an_observed_solicitation")

    # A demo fixture may exercise the detector; it may never move a real
    # metric. The two flags must agree.
    if miss.get("award_is_demo_fixture") and miss.get("counts_toward_real_metrics"):
        failures.append("demo_fixture_award_counted_toward_real_metrics")

    # A resolution needs a decider.
    if resolution in ANSWERED and not miss.get("resolved_by"):
        failures.append(f"resolution_{resolution}_names_no_decider")
    if resolution == UNRESOLVED and miss.get("resolved_by"):
        failures.append("unresolved_miss_names_a_decider")

    return sorted(set(failures))


def build_coverage_scorecard(
    *,
    misses: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    solicitations_observed: int,
    computed_at: Any = None,
) -> dict[str, Any]:
    """176I: how good is our coverage? Counts, never a fabricated percentage."""
    # REAL misses only. A demo fixture exercises the detector and is counted
    # separately, because a coverage number inflated by test data is worse
    # than no coverage number at all.
    real_misses = [m for m in misses if m.get("counts_toward_real_metrics")]
    demo_misses = [m for m in misses if not m.get("counts_toward_real_metrics")]

    by_resolution: dict[str, int] = dict.fromkeys(RESOLUTIONS, 0)
    for miss in real_misses:
        key = str(miss.get("resolution") or UNRESOLVED)
        if key in by_resolution:
            by_resolution[key] += 1

    by_signal_type: dict[str, int] = {}
    open_signals = 0
    for signal in signals:
        kind = str(signal.get("signal_type"))
        by_signal_type[kind] = by_signal_type.get(kind, 0) + 1
        if str(signal.get("signal_state")) in OPEN_STATES:
            open_signals += 1

    resolved = sum(by_resolution[key] for key in ANSWERED)
    unresolved = by_resolution[UNRESOLVED]
    real_failures = sum(by_resolution[key] for key in REAL_COVERAGE_FAILURE)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "computed_at": computed_at,
            "solicitations_observed": int(solicitations_observed),
            "award_without_solicitation": len(real_misses),
            "demo_fixture_miss_count": len(demo_misses),
            "demo_fixture_awards_excluded_from_real_metrics": True,
            "resolved_award_miss_count": resolved,
            "unresolved_award_miss_count": unresolved,
            "real_coverage_failure_count": real_failures,
            "misses_by_resolution": by_resolution,
            "amendment_without_original": by_signal_type.get(
                "AMENDMENT_WITHOUT_ORIGINAL", 0
            ),
            "expected_recurring_absent": by_signal_type.get(
                "EXPECTED_RECURRING_PROGRAM_ABSENT", 0
            ),
            "unmonitored_source_reference": by_signal_type.get(
                "SOURCE_REFERENCES_UNMONITORED_PUBLISHER", 0
            ),
            "deadline_without_opportunity": by_signal_type.get(
                "DEADLINE_WITHOUT_OPPORTUNITY", 0
            ),
            "signals_by_type": dict(sorted(by_signal_type.items())),
            "open_signal_count": open_signals,
            "miss_evidence_signal_count": sum(
                count
                for kind, count in by_signal_type.items()
                if kind in MISS_EVIDENCE_TYPES
            ),
            # 176I. The refusal that makes this scorecard worth reading.
            "coverage_percentage": None,
            "denominator_known": False,
            "why_no_coverage_percentage": (
                "the denominator - how much Native-relevant funding exists - is "
                "unknown, and this system has no way to learn it. A percentage "
                "here would be a number we made up, and it would be believed."
            ),
        }
    )


def scorecard_invariant_failures(scorecard: dict[str, Any]) -> list[str]:
    """Refuse a scorecard that divides by an unknown."""
    failures: list[str] = []

    if scorecard.get("coverage_percentage") is not None:
        failures.append("scorecard_reports_a_coverage_percentage")
    if scorecard.get("denominator_known"):
        failures.append("scorecard_claims_the_denominator_is_known")
    if not scorecard.get("why_no_coverage_percentage"):
        failures.append("scorecard_does_not_say_why_it_has_no_percentage")

    total = int(scorecard.get("award_without_solicitation") or 0)
    resolved = int(scorecard.get("resolved_award_miss_count") or 0)
    unresolved = int(scorecard.get("unresolved_award_miss_count") or 0)
    if resolved + unresolved != total:
        failures.append(
            f"miss_counts_do_not_reconcile:{resolved}+{unresolved}!={total}"
        )

    return sorted(set(failures))


def describe_miss_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "resolutions": list(RESOLUTIONS),
            "every_resolution_has_a_meaning": set(RESOLUTION_MEANINGS)
            == set(RESOLUTIONS),
            "answered_resolutions": sorted(ANSWERED),
            "real_coverage_failure_resolutions": sorted(REAL_COVERAGE_FAILURE),
            # The refusals.
            "never_invents_a_solicitation": True,
            "never_marks_coverage_healthy": True,
            "never_auto_onboards_a_source": True,
            "a_miss_must_say_where_it_looked": True,
            "no_miss_without_zero_observed_solicitations": True,
            "coverage_percentage_is_never_reported": True,
            "unknown_denominator_preserved": True,
            "demo_fixture_awards_excluded_from_real_metrics": True,
        }
    )
