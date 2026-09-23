"""Gate 173G/H: the relevance classification, and what it is not allowed to do.

```text
RAW SIGNAL -> CANDIDATE -> EVIDENCE -> CLASSIFICATION -> CONFIDENCE -> REVIEW
```

Three rules make this defensible rather than merely confident.

**A classification cannot exist without evidence.** Not "should not" - the
invariant checker refuses it. An explanation with no evidence behind it is the
one output an intelligence product must never ship, because it is
indistinguishable from a correct one until someone acts on it.

**A class in the applicant band needs applicant-bearing evidence.** Knowing
that Native people benefit does not establish that a Tribe may apply. These
are separate facts and the ontology keeps them separate; this is where that
separation is enforced.

**UNCERTAIN is a real answer.** It is not a soft NOT_RELEVANT and it is not a
low score. It means the evidence on file does not settle the question, and it
routes to a human rather than to a filter.

**173H - global, not tenant.** What this module computes is GLOBAL Native
relevance: is this opportunity Native-relevant to anyone? Whether it matches a
particular Tribe's priorities, geography, sectors or exclusions is a different
question with a different answer, and it is deliberately not computed here.
Folding tenants in at this layer would mean classifying every opportunity once
per tenant - an O(opportunities x tenants) sweep that recomputes identical
global facts, which is the shape Gate 172 spent a whole phase proving the
fleet must not have.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_candidate_service import (
    CANDIDATE,
    NOT_CANDIDATE,
    candidate_invariant_failures,
)
from nativeforge.services.native_relevance_evidence_service import (
    APPLICANT_BEARING,
    APPLICANT_ELIGIBILITY,
    BENEFICIARY_POPULATION,
    BLOCKS_DEFINITE,
    DEFINITE_ENOUGH,
    ENTITY_CLASS_AMBIGUOUS,
    is_definite_enough,
    summarise_evidence,
)
from nativeforge.services.native_relevance_ontology_service import (
    APPLICANT_RELEVANT,
    BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    INDIRECTLY_RELEVANT,
    NATIVE_BENEFICIARY_RELEVANT,
    NATIVE_ELIGIBLE,
    NATIVE_PRIORITY,
    NATIVE_SPECIFIC,
    NOT_RELEVANT,
    ONTOLOGY_VERSION,
    RELEVANCE_CLASSES,
    UNCERTAIN,
    ranking_score,
)

SCHEMA_VERSION = "nf_native_relevance_classification_v2"

#: Why a human is being asked. Each is a condition, not a score threshold.
REVIEW_REASONS: tuple[str, ...] = (
    "evidence_is_ambiguous",
    "only_suggestive_evidence",
    "no_applicant_bearing_evidence_for_an_applicant_class",
    "sources_disagree",
    "candidate_state_unknown",
    "entity_class_not_established",
    "evidence_may_describe_a_prior_cycle",
    "classification_is_uncertain",
)

#: The fields a stored assessment carries.
ASSESSMENT_FIELDS: tuple[str, ...] = (
    "canonical_id",
    "ontology_version",
    "relevance_class",
    "candidate_state",
    "confidence",
    "review_required",
    "review_reasons",
    "reasons",
    "evidence_ids",
    "evidence_types",
    "entity_classes",
    "sectors",
    "ranking_score",
    "computed_at",
)

HIGH = "HIGH"
MODERATE = "MODERATE"
LOW = "LOW"
NONE = "NONE"

CONFIDENCE_LEVELS: tuple[str, ...] = (HIGH, MODERATE, LOW, NONE)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _supports(items: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    return [item for item in items if target in (item.get("supports_classes") or [])]


def classify_relevance(
    *,
    canonical_id: Any,
    candidate: dict[str, Any],
    evidence_items: list[dict[str, Any]] | None = None,
    entity_classes: list[str] | None = None,
    sectors: list[str] | None = None,
    explicit_native_exclusion: bool = False,
    computed_at: Any = None,
) -> dict[str, Any]:
    """One global relevance classification, derived from the evidence on file."""
    items = list(evidence_items or [])
    summary = summarise_evidence(items)
    reasons: list[str] = []
    review: list[str] = []

    candidate_state = str(candidate.get("candidate_state") or "UNKNOWN")

    definite = [item for item in items if is_definite_enough(item)]
    applicant_definite = [
        item for item in definite if str(item.get("evidence_type")) in APPLICANT_BEARING
    ]
    beneficiary_definite = [
        item
        for item in definite
        if str(item.get("evidence_type")) == BENEFICIARY_POPULATION
    ]

    # Evidence that would be definite but for entity-class ambiguity. This is
    # the shape general-government eligibility ALWAYS has - "units of local
    # government" is sure of itself and unsure whether a Tribe is one - and it
    # is exactly what BROADLY_ELIGIBLE_NATIVE_RELEVANT exists to express. It
    # can carry that class and nothing stronger.
    entity_ambiguous_applicant = [
        item
        for item in items
        if str(item.get("evidence_type")) in APPLICANT_BEARING
        and str(item.get("confidence_class")) in DEFINITE_ENOUGH
        and str(item.get("ambiguity_class")) == ENTITY_CLASS_AMBIGUOUS
    ]
    general_signals = set(candidate.get("signal_names") or []) & {
        "unrestricted_or_read_the_text_eligibility",
        "general_government_eligibility",
        "broad_entity_eligibility",
    }

    # ---- the classes the evidence itself claims to support ------------
    claimed = {
        name: _supports(definite, name)
        for name in RELEVANCE_CLASSES
        if _supports(definite, name)
    }

    # ---- ordered, and each branch names the evidence that carried it --
    if explicit_native_exclusion:
        relevance = NOT_RELEVANT
        reasons.append("source_explicitly_excludes_native_entities")

    elif not items:
        # The load-bearing refusal. No evidence, no classification.
        relevance = UNCERTAIN
        reasons.append("no_evidence_on_file")
        review.append("classification_is_uncertain")

    elif candidate_state == NOT_CANDIDATE:
        relevance = NOT_RELEVANT
        reasons.append("candidate_stage_found_no_signal_against_stated_eligibility")

    elif entity_ambiguous_applicant and general_signals and not definite:
        # General eligibility, stated plainly, ambiguous only about whether a
        # Tribe counts as one of the named classes. That IS this class.
        relevance = BROADLY_ELIGIBLE_NATIVE_RELEVANT
        reasons.append("general_eligibility_with_an_unresolved_entity_class")
        review.append("entity_class_not_established")

    elif not definite:
        # Everything we have is inferred or unknown-confidence. That is a
        # hypothesis, and a hypothesis is a question for a human.
        relevance = UNCERTAIN
        reasons.append("no_evidence_reaches_a_definite_confidence_class")
        review.append("classification_is_uncertain")

    elif claimed:
        # Strongest claimed class wins, but only if the evidence carrying it
        # is allowed to carry it.
        relevance = max(claimed, key=ranking_score)
        reasons.append(f"evidence_supports_{relevance.lower()}")
        if relevance in APPLICANT_RELEVANT and not applicant_definite:
            # Somebody asserted an applicant class from beneficiary or sector
            # evidence. Refuse the promotion rather than the evidence.
            relevance = (
                NATIVE_BENEFICIARY_RELEVANT
                if any(
                    str(item.get("evidence_type")) == BENEFICIARY_POPULATION
                    for item in definite
                )
                else UNCERTAIN
            )
            reasons.append("applicant_class_not_supported_by_applicant_evidence")
            review.append("no_applicant_bearing_evidence_for_an_applicant_class")

    elif applicant_definite:
        # Applicant-bearing evidence with no explicit class claim. The
        # candidate signals say which band it lands in.
        signals = set(candidate.get("signal_names") or [])
        if "native_applicant_eligibility_code" in signals:
            relevance = NATIVE_ELIGIBLE
            reasons.append("applicant_codes_name_native_entities")
        elif signals & {
            "unrestricted_or_read_the_text_eligibility",
            "general_government_eligibility",
            "broad_entity_eligibility",
        }:
            relevance = BROADLY_ELIGIBLE_NATIVE_RELEVANT
            reasons.append("eligibility_is_general_and_does_not_exclude_tribes")
        elif beneficiary_definite:
            # The applicant is not Native and the beneficiaries are. Reading
            # the applicant evidence first must not make the beneficiary
            # evidence invisible - that is the whole distinction.
            relevance = NATIVE_BENEFICIARY_RELEVANT
            reasons.append("native_beneficiaries_with_a_non_native_applicant_class")
        else:
            relevance = UNCERTAIN
            reasons.append("applicant_evidence_present_but_inconclusive")
            review.append("classification_is_uncertain")

    elif beneficiary_definite:
        relevance = NATIVE_BENEFICIARY_RELEVANT
        reasons.append("native_beneficiaries_without_native_applicant_evidence")

    elif summary["only_suggestive"]:
        # Sector, agency, source context. Real, weak, and never a finding on
        # its own.
        relevance = INDIRECTLY_RELEVANT
        reasons.append("only_suggestive_evidence")
        review.append("only_suggestive_evidence")

    else:
        relevance = UNCERTAIN
        reasons.append("evidence_does_not_settle_the_question")
        review.append("classification_is_uncertain")

    # ---- review conditions, independent of the class ------------------
    ambiguities = set(summary["ambiguities"])
    if ambiguities & BLOCKS_DEFINITE:
        review.append("evidence_is_ambiguous")
    if "TEMPORAL_AMBIGUOUS" in ambiguities:
        review.append("evidence_may_describe_a_prior_cycle")
    if "CONFLICTING_SOURCES" in ambiguities:
        review.append("sources_disagree")
    if candidate_state not in (CANDIDATE, NOT_CANDIDATE):
        review.append("candidate_state_unknown")
    if relevance in APPLICANT_RELEVANT and not entity_classes:
        review.append("entity_class_not_established")
    if relevance == UNCERTAIN:
        review.append("classification_is_uncertain")

    # ---- confidence is a REPORT of the evidence, not a threshold ------
    if relevance == UNCERTAIN or not definite:
        confidence = NONE if not items else LOW
    elif ambiguities & BLOCKS_DEFINITE:
        confidence = LOW
    elif applicant_definite and len(summary["sources"]) > 1:
        confidence = HIGH
    elif applicant_definite or len(definite) > 1:
        confidence = MODERATE
    else:
        confidence = LOW

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_id": str(canonical_id) if canonical_id else None,
            "ontology_version": ONTOLOGY_VERSION,
            "relevance_class": relevance,
            "candidate_state": candidate_state,
            "confidence": confidence,
            "review_required": bool(review),
            "review_reasons": sorted(set(review)),
            "reasons": sorted(set(reasons)),
            "evidence_ids": sorted(
                {
                    str(item.get("evidence_id"))
                    for item in items
                    if item.get("evidence_id")
                }
            ),
            "evidence_types": summary["types_present"],
            "entity_classes": sorted(entity_classes or []),
            "sectors": sorted(sectors or []),
            "ranking_score": ranking_score(relevance),
            "computed_at": computed_at,
            # 173H. Stated on every row so nothing downstream can mistake a
            # global classification for a tenant match.
            "scope": "GLOBAL",
            "tenant_id": None,
        }
    )


def classification_invariant_failures(
    *,
    assessment: dict[str, Any],
    evidence_items: list[dict[str, Any]] | None = None,
    candidate: dict[str, Any] | None = None,
) -> list[str]:
    """Refuse an assessment that claims more than its evidence supports."""
    failures: list[str] = []
    items = list(evidence_items or [])

    for field in ASSESSMENT_FIELDS:
        if field not in assessment:
            failures.append(f"assessment_missing_field:{field}")

    relevance = str(assessment.get("relevance_class") or "")
    if relevance not in RELEVANCE_CLASSES:
        failures.append(f"class_outside_the_ontology:{relevance or 'missing'}")

    if str(assessment.get("confidence")) not in CONFIDENCE_LEVELS:
        failures.append(
            f"confidence_outside_the_vocabulary:{assessment.get('confidence')}"
        )

    for reason in assessment.get("review_reasons") or []:
        if str(reason) not in REVIEW_REASONS:
            failures.append(f"review_reason_outside_the_vocabulary:{reason}")

    if not assessment.get("ontology_version"):
        failures.append("assessment_does_not_record_its_ontology_version")

    if not assessment.get("canonical_id"):
        failures.append("assessment_not_bound_to_a_canonical_opportunity")

    # ---- the three rules ------------------------------------------------
    # 1. no classification without evidence
    decisive = relevance not in {UNCERTAIN}
    if decisive and not items:
        failures.append(f"classification_{relevance}_without_any_evidence")

    if assessment.get("evidence_ids") and not items:
        failures.append("assessment_cites_evidence_that_was_not_supplied")

    # 2. an applicant class needs applicant-bearing evidence
    if relevance in APPLICANT_RELEVANT:
        applicant = [
            item
            for item in items
            if str(item.get("evidence_type")) in APPLICANT_BEARING
            and is_definite_enough(item)
        ]
        if relevance == BROADLY_ELIGIBLE_NATIVE_RELEVANT:
            # This class IS the entity-class ambiguity, so applicant evidence
            # blocked only by that ambiguity still carries it. Nothing
            # stronger may be reached this way.
            applicant = applicant + [
                item
                for item in items
                if str(item.get("evidence_type")) in APPLICANT_BEARING
                and str(item.get("confidence_class")) in DEFINITE_ENOUGH
                and str(item.get("ambiguity_class")) == ENTITY_CLASS_AMBIGUOUS
            ]
        if not applicant:
            failures.append(
                f"applicant_class_{relevance}_without_applicant_bearing_evidence"
            )

    # 3. UNCERTAIN must ask for a human
    if relevance == UNCERTAIN and not assessment.get("review_required"):
        failures.append("uncertain_classification_does_not_ask_for_review")

    # A candidate the stage rejected cannot come out relevant.
    if candidate is not None:
        failures.extend(candidate_invariant_failures(candidate))
        if (
            str(candidate.get("candidate_state")) == NOT_CANDIDATE
            and relevance in APPLICANT_RELEVANT
        ):
            failures.append("not_candidate_promoted_to_an_applicant_relevant_class")

    # 173H: a global assessment may not carry a tenant.
    if assessment.get("scope") != "GLOBAL":
        failures.append(f"assessment_scope_is_not_global:{assessment.get('scope')}")
    if assessment.get("tenant_id"):
        failures.append("global_assessment_carries_a_tenant_id")

    return sorted(set(failures))


def describe_classifier() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "ontology_version": ONTOLOGY_VERSION,
            "confidence_levels": list(CONFIDENCE_LEVELS),
            "review_reasons": list(REVIEW_REASONS),
            "assessment_fields": list(ASSESSMENT_FIELDS),
            "classification_requires_evidence": True,
            "applicant_class_requires_applicant_evidence": sorted(APPLICANT_BEARING),
            "uncertain_always_requests_review": True,
            "scope_is_global_not_tenant": True,
            "inference_alone_cannot_decide": "INFERRED" not in DEFINITE_ENOUGH,
            "beneficiary_cannot_promote_to_applicant": (
                NATIVE_BENEFICIARY_RELEVANT not in APPLICANT_RELEVANT
            ),
            "applicant_bearing_evidence_types": sorted(APPLICANT_BEARING),
            "strongest_applicant_class": NATIVE_SPECIFIC,
            "priority_class_present": NATIVE_PRIORITY in RELEVANCE_CLASSES,
            "beneficiary_evidence_type": BENEFICIARY_POPULATION,
            "applicant_evidence_type": APPLICANT_ELIGIBILITY,
        }
    )
