"""Discovery Baseline X metric contract (Gate 85B).

Declares *what* Baseline X measures and what it is forbidden to claim. The
measurement itself lives in :mod:`discovery_baseline_x_service`.

The contract exists so the shape of the baseline is reviewable independently of
the numbers, and so the forbidden claims are enforced by an invariant rather
than by discipline. A baseline that is allowed to drift into claiming coverage
is worse than no baseline: it becomes the number a later campaign measures its
"65% improvement" against.

## Vocabulary rule

**Every metric key is drawn from an existing frozenset.** Baseline X declares no
new applicant class, funding lane, freshness state or result state - it imports
them. Gate 79B's lesson was that a forked vocabulary is the expensive mistake,
and a measurement layer is exactly where one would be tempting to invent.

A drift test pins each imported set.

Nothing here fetches, and nothing here measures - this module is declarative.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    RESULT_STATES,
)
from nativeforge.services.nofo_amendment_detector_service import NOTICE_STATUSES
from nativeforge.services.opportunity_freshness_service import FRESHNESS_STATES
from nativeforge.services.opportunity_funding_lane_service import FUNDING_LANES

SCHEMA_VERSION = "nf_discovery_baseline_metric_contract_v1"
BASELINE_NAME = "Discovery Baseline X"
BASELINE_VERSION = "x1"

# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

# How a record came to exist. `live` is present so it can be counted and
# reported as zero, not so it can be claimed.
PROVENANCE_KINDS: tuple[str, ...] = (
    "synthetic",
    "recorded",
    "live",
    "unknown",
)

CORPUS_COMPOSITION_METRICS: tuple[str, ...] = (
    "total_records",
    "synthetic_records",
    "recorded_records",
    "live_records",
    "unknown_source_records",
)

SOURCE_COVERAGE_METRICS: tuple[str, ...] = (
    "total_sources",
    "monitorable_sources",
    "monitored_sources",
    "terms_cleared_sources",
    "robots_cleared_sources",
    "stale_sources",
    "retired_sources",
    "blocked_terms_sources",
)

OPPORTUNITY_QUALITY_METRICS: tuple[str, ...] = (
    "evidence_backed_records",
    "records_with_source_url",
    "records_with_notice_text",
    "records_with_cited_eligibility",
    "records_with_cited_exclusion",
    "records_with_deadline",
    "records_with_uncertain_deadline",
    # Gate 86. The deadline story needs five numbers, not one, because the
    # causes have different fixes: no date at all, a date in a format nobody
    # parses, a date whose format is genuinely ambiguous, and a date that
    # normalized fine but belongs to a record nobody has ever checked.
    #
    # `records_with_raw_deadline` counts what the corpus carries.
    # `records_with_normalized_deadline` counts what a parser could resolve.
    # The two are reported separately so normalization can never be mistaken
    # for the corpus having gained a deadline it did not have.
    "records_with_raw_deadline",
    "records_with_normalized_deadline",
    # Gate 86 redefines this. Through Gate 85 it counted a freshness-evaluator
    # reason (`close_date_or_now_unparseable`); it now counts a parser verdict
    # of unparseable or impossible. The old reading conflated "the evaluator
    # cannot read this" with "this is not a date", and Gate 86 can tell them
    # apart.
    "records_with_unparseable_deadline",
    "records_with_ambiguous_deadline",
    "deadline_normalization_rate",
    # Gate 87. Parsing a deadline and trusting it are different questions, and
    # answering them with one number is how 40 records carrying an identical
    # year-end sentinel came to be counted alongside 19 fetched deadlines.
    #
    # `records_with_raw_deadline` above is untouched and still counts what the
    # corpus carries. These say how much of it stands up.
    "verified_deadlines",
    "unverified_deadlines",
    "suspected_placeholder_deadlines",
    "missing_deadlines",
    "unknown_deadlines",
    "freshness_blocked_by_deadline_provenance",
    "deadline_verification_rate",
    "placeholder_suspicion_rate",
    # Stated as its own metric so the overstatement is a number somebody has to
    # read, not an inference from two other numbers.
    "raw_deadline_count_overstated_by",
    # Gate 88. The same separation, applied to the records themselves.
    # `corpus_summary.recorded_records` counts what a record's flags say about
    # how it was produced; these count what committed evidence survives to show
    # it. A boolean can never reach the verified column - by rule, and by
    # invariant.
    "recorded_verified_records",
    "recorded_asserted_records",
    "recorded_circular_records",
    "synthetic_declared_records",
    "demo_synthetic_records",
    "unknown_provenance_records",
    "missing_provenance_records",
    "verified_recorded_rate",
    "asserted_recorded_rate",
    "circular_recorded_rate",
    "provenance_confidence_level",
    # The weakest tier, named: supported by a boolean and nothing else.
    "flags_only_records",
    # Two overstatement figures answering two different questions - see the
    # comments at their assignment in discovery_baseline_x_service.
    "recorded_count_overstated_by",
    "corpus_summary_recorded_records",
    "corpus_summary_recorded_overstated_by",
    "records_never_checked",
    "records_with_resolvable_freshness",
    "records_with_amendment_evidence",
    "duplicate_candidates",
    "spam_or_low_quality_candidates",
    # Rows where a source was checked and carried no live notice. Neither
    # fabrication nor coverage; counted by name so they can be read as neither.
    "honest_empty_records",
)

# Per applicant class. Mirrors eligibility_exclusion_evidence_service.RESULT_STATES
# plus the two counts Gate 79B added.
APPLICANT_CLASS_METRICS: tuple[str, ...] = (
    "eligible_count",
    "excluded_by_evidence_count",
    "possibly_eligible_count",
    "not_supported_by_evidence_count",
    "unknown_count",
    "human_review_required_count",
    "negative_intelligence_count",
)

READINESS_METRICS: tuple[str, ...] = (
    "baseline_quality_score",
    "confidence_level",
    "production_usable",
    "customer_demo_usable",
    "controlled_pilot_usable",
    "improvement_claim_allowed",
)

CONFIDENCE_LEVELS: tuple[str, ...] = (
    "none",
    "synthetic_only",
    "recorded_pre_live",
    "live_partial",
    "live_verified",
)

# The only honest label for this baseline: the corpus is recorded and synthetic,
# nothing is monitored, and no notice has been fetched.
DEFAULT_CONFIDENCE_LEVEL = "recorded_pre_live"

# Claims this contract forbids outright. Each must be present and False on any
# baseline result.
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "improvement_claim_allowed",
    "live_coverage_claimed",
    "source_monitoring_claimed",
    "fixture_mutation_performed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def applicant_classes() -> tuple[str, ...]:
    """Canonical applicant classes, `unknown` last so reports read naturally."""
    named = sorted(APPLICANT_CLASSES - {"unknown"})
    return (*named, "unknown")


def funding_lanes() -> tuple[str, ...]:
    return tuple(sorted(FUNDING_LANES))


def freshness_states() -> tuple[str, ...]:
    return tuple(sorted(FRESHNESS_STATES))


def notice_statuses() -> tuple[str, ...]:
    return tuple(sorted(NOTICE_STATUSES))


def result_states() -> tuple[str, ...]:
    return tuple(sorted(RESULT_STATES))


def build_discovery_baseline_metric_contract() -> dict[str, Any]:
    """The declarative shape of Baseline X."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "baseline_name": BASELINE_NAME,
            "baseline_version": BASELINE_VERSION,
            "metric_groups": {
                "corpus_composition": list(CORPUS_COMPOSITION_METRICS),
                "source_coverage": list(SOURCE_COVERAGE_METRICS),
                "opportunity_quality": list(OPPORTUNITY_QUALITY_METRICS),
                "applicant_class": list(APPLICANT_CLASS_METRICS),
                "readiness": list(READINESS_METRICS),
            },
            "provenance_kinds": list(PROVENANCE_KINDS),
            "applicant_classes": list(applicant_classes()),
            "funding_lanes": list(funding_lanes()),
            "freshness_states": list(freshness_states()),
            "notice_statuses": list(notice_statuses()),
            "result_states": list(result_states()),
            "confidence_levels": list(CONFIDENCE_LEVELS),
            "default_confidence_level": DEFAULT_CONFIDENCE_LEVEL,
            "forbidden_claims": list(FORBIDDEN_CLAIMS),
            # Declared here so the contract itself carries the boundary.
            "improvement_claim_allowed": False,
            "live_coverage_claimed": False,
            "source_monitoring_claimed": False,
            "fixture_mutation_performed": False,
        }
    )


def contract_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("baseline_name") != BASELINE_NAME:
        fails.append("baseline_name_mismatch")

    # Vocabularies must be the imported ones, not local copies.
    if set(contract.get("applicant_classes") or []) != set(APPLICANT_CLASSES):
        fails.append("applicant_classes_diverged_from_canonical")
    if set(contract.get("funding_lanes") or []) != set(FUNDING_LANES):
        fails.append("funding_lanes_diverged_from_canonical")
    if set(contract.get("freshness_states") or []) != set(FRESHNESS_STATES):
        fails.append("freshness_states_diverged_from_canonical")
    if set(contract.get("result_states") or []) != set(RESULT_STATES):
        fails.append("result_states_diverged_from_canonical")

    if contract.get("default_confidence_level") not in CONFIDENCE_LEVELS:
        fails.append("default_confidence_level_out_of_vocabulary")

    for claim in FORBIDDEN_CLAIMS:
        if contract.get(claim) is not False:
            fails.append(f"forbidden_claim:{claim}")

    return fails


def baseline_result_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Checks a *measured* baseline against this contract.

    Separate from :func:`contract_invariant_failures`, which checks the
    declaration. This one is what stops a measurement drifting into a claim.
    """
    fails: list[str] = []

    if result.get("baseline_name") != BASELINE_NAME:
        fails.append("baseline_name_mismatch")

    for claim in FORBIDDEN_CLAIMS:
        if result.get(claim) is not False:
            fails.append(f"forbidden_claim:{claim}")

    corpus = result.get("corpus_summary") or {}
    # live_records may only be non-zero if something proves a live fetch, and
    # nothing in this repo can.
    if corpus.get("live_records"):
        fails.append("live_records_claimed_without_proof")

    counted = sum(
        int(corpus.get(k) or 0)
        for k in ("synthetic_records", "recorded_records", "live_records",
                  "unknown_source_records")
    )
    if counted != int(corpus.get("total_records") or 0):
        fails.append("corpus_composition_does_not_sum_to_total")

    sources = result.get("source_coverage") or {}
    if sources.get("monitored_sources"):
        fails.append("monitored_sources_claimed_without_proof")

    # Gate 86: freshness must stay bounded by what could support it.
    #
    # A record earns a freshness state only by having both a normalized deadline
    # and a timestamp saying somebody looked. Neither count may exceed the
    # other's precondition, and a normalized deadline may never outnumber the
    # raw deadlines it was derived from - that would mean a date was produced
    # for a record that has none.
    quality = result.get("opportunity_quality") or {}
    raw_deadlines = int(quality.get("records_with_raw_deadline") or 0)
    normalized_deadlines = int(quality.get("records_with_normalized_deadline") or 0)
    resolvable = int(quality.get("records_with_resolvable_freshness") or 0)

    if normalized_deadlines > raw_deadlines:
        fails.append("normalized_deadlines_exceed_raw_deadlines")
    if resolvable > normalized_deadlines:
        fails.append("resolvable_freshness_exceeds_normalized_deadlines")

    # Gate 87: verification is the narrowest claim of the three, so it must sit
    # inside both. And freshness may not outrun the deadlines that survived the
    # provenance audit.
    verified = int(quality.get("verified_deadlines") or 0)
    suspected = int(quality.get("suspected_placeholder_deadlines") or 0)
    if verified > normalized_deadlines:
        fails.append("verified_deadlines_exceed_normalized_deadlines")
    if verified + suspected > raw_deadlines:
        fails.append("deadline_provenance_counts_exceed_raw_deadlines")
    if resolvable > verified + int(quality.get("unverified_deadlines") or 0):
        fails.append("resolvable_freshness_exceeds_trusted_deadlines")

    # Gate 88: a record verified by artifact cannot outnumber the records that
    # exist, nor the records the corpus even claims were recorded.
    verified_recorded = int(quality.get("recorded_verified_records") or 0)
    total_records = int(corpus.get("total_records") or 0)
    if verified_recorded > total_records:
        fails.append("verified_recorded_records_exceed_total_records")
    if verified_recorded > int(corpus.get("recorded_records") or 0) + int(
        corpus.get("synthetic_records") or 0
    ):
        fails.append("verified_recorded_records_exceed_claimed_recorded")
    if quality.get("provenance_confidence_level") == "artifact_backed" and (
        verified_recorded < total_records * 0.9
    ):
        fails.append("provenance_confidence_overstated")

    if result.get("confidence_level") not in CONFIDENCE_LEVELS:
        fails.append("confidence_level_out_of_vocabulary")

    readiness = result.get("readiness_summary") or {}
    for gate in ("production_usable", "controlled_pilot_usable"):
        if readiness.get(gate) is not False:
            fails.append(f"readiness_overclaimed:{gate}")

    score = readiness.get("baseline_quality_score")
    if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
        fails.append("baseline_quality_score_out_of_range")

    # Applicant classes must be reported separately - collapsing the two
    # recognition tiers is the failure this product cannot afford.
    classes = result.get("applicant_class_summary") or {}
    for required in ("federally_recognized_tribe", "state_recognized_tribe"):
        if required not in classes:
            fails.append(f"applicant_class_missing:{required}")

    # Every reported class and lane must be canonical.
    for cls in classes:
        if cls not in APPLICANT_CLASSES:
            fails.append(f"non_canonical_applicant_class:{cls}")
    for lane in result.get("funding_lane_summary") or {}:
        if lane not in FUNDING_LANES:
            fails.append(f"non_canonical_funding_lane:{lane}")
    for state in result.get("freshness_summary") or {}:
        if state not in FRESHNESS_STATES:
            fails.append(f"non_canonical_freshness_state:{state}")

    return fails
