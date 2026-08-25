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
    # Split out because the reasons are different problems with different
    # fixes: a missing date, a date nobody has ever checked, and a date that is
    # present but in a format the freshness evaluator cannot read.
    "records_with_unparseable_deadline",
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
