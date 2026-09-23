"""Gate 173K/L: the adversarial corpus that lets this system be proven wrong.

A classifier with no corpus is an opinion. This module holds the twenty-seven
cases NativeForge has to get right, including the seven it is most likely to
get wrong, and the runner that pushes each one through the REAL candidate
stage and the REAL classifier.

That last part is the whole design. Gate 172 spent a phase discovering that a
seventeen-row matrix had gone green without exercising a single branch,
because the fixture passed a fixed happy-path value alongside the condition it
claimed to be testing. So a row here supplies only RAW STRUCTURED INPUTS - the
applicant codes, the terms, the geography, the payload hashes - and the runner
calls `detect_candidate` and `classify_relevance` on them exactly as the
pipeline would. Nothing in a row states an answer the model then agrees with.

The corpus is deliberately unbalanced towards the cases that break keyword
matchers:

*   **no Native word anywhere**, and every Tribe in the country is eligible
*   **the word appears once**, in a background paragraph about a prior cycle
*   **the word is a place name** - Indian River County, Native Prairie
*   **eligibility is added by amendment** after the notice was first read
*   **eligibility is removed by amendment** after we already said yes

`expected_classes` is a SET where the evidence genuinely admits more than one
defensible answer, and a single value where it does not. Widening a set to
make a run go green is the move this file exists to prevent, so each set says
why it is a set.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_candidate_service import (
    CANDIDATE,
    NOT_CANDIDATE,
    candidate_invariant_failures,
    detect_candidate,
)
from nativeforge.services.native_relevance_candidate_service import (
    UNKNOWN as CANDIDATE_UNKNOWN,
)
from nativeforge.services.native_relevance_classifier_service import (
    classification_invariant_failures,
    classify_relevance,
)
from nativeforge.services.native_relevance_evidence_service import (
    AGENCY_CONTEXT,
    APPLICANT_ELIGIBILITY,
    BENEFICIARY_POPULATION,
    CONTEXT_AMBIGUOUS,
    DERIVED,
    DOCUMENT_REFERENCE,
    ENTITY_CLASS_AMBIGUOUS,
    GEOGRAPHIC_RELEVANCE,
    INFERRED,
    NO_AMBIGUITY,
    OBSERVED,
    PROGRAM_HISTORY,
    PROGRAM_PURPOSE,
    SECTOR_ALIGNMENT,
    SOURCE_CONTEXT,
    STATUTORY_LANGUAGE,
    TEMPORAL_AMBIGUOUS,
    build_evidence,
)
from nativeforge.services.native_relevance_ontology_service import (
    APPLICANT_RELEVANT,
    BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    INDIRECTLY_RELEVANT,
    NATIVE_BENEFICIARY_RELEVANT,
    NATIVE_ELIGIBLE,
    NATIVE_SPECIFIC,
    NOT_RELEVANT,
    UNCERTAIN,
)

SCHEMA_VERSION = "nf_native_relevance_gold_corpus_v1"

#: Rows whose truth is "a Native entity could pursue this". Used to compute
#: recall, so it is defined once here rather than re-derived per metric.
RELEVANT_TRUTH: frozenset[str] = frozenset(
    APPLICANT_RELEVANT | {NATIVE_BENEFICIARY_RELEVANT}
)


def _ev(
    canonical_id: str,
    kind: str,
    value: Any,
    *,
    confidence: str = OBSERVED,
    ambiguity: str = NO_AMBIGUITY,
    supports: list[str] | None = None,
    source_id: str = "gold.source",
    payload: str = "gold.payload.sha256",
    field_name: str | None = None,
    section_ref: str | None = None,
    page_ref: int | None = None,
) -> dict[str, Any]:
    return build_evidence(
        canonical_id=canonical_id,
        evidence_type=kind,
        source_id=source_id,
        raw_payload_sha256=payload,
        evidence_value=value,
        confidence_class=confidence,
        ambiguity_class=ambiguity,
        supports_classes=supports,
        field_name=field_name,
        section_ref=section_ref,
        page_ref=page_ref,
    )


def _row(
    key: str,
    why: str,
    *,
    expected_candidate: str,
    expected_classes: set[str],
    set_reason: str = "",
    inputs: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    entity_classes: list[str] | None = None,
    sectors: list[str] | None = None,
    hard_negative: bool = False,
) -> dict[str, Any]:
    if len(expected_classes) > 1 and not set_reason:
        raise ValueError(f"{key}: a set of expected classes must say why it is a set")
    return {
        "key": key,
        "why": why,
        "expected_candidate": expected_candidate,
        "expected_classes": sorted(expected_classes),
        "set_reason": set_reason,
        "inputs": dict(inputs or {}),
        "evidence": list(evidence or []),
        "entity_classes": list(entity_classes or []),
        "sectors": list(sectors or []),
        "hard_negative": hard_negative,
    }


def corpus() -> list[dict[str, Any]]:
    """Twenty-seven cases. Raw inputs only - no row states an answer."""
    rows: list[dict[str, Any]] = []

    # ---- 1. explicit Tribe-only ------------------------------------
    key = "tribe_only_set_aside"
    rows.append(
        _row(
            key,
            "only federally recognised Tribes may apply",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_SPECIFIC},
            inputs={"eligible_applicant_codes": ["07"]},
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Native American tribal governments (Federally recognized)"],
                    supports=[NATIVE_SPECIFIC],
                    field_name="eligible_applicants",
                )
            ],
            entity_classes=["tribal_government"],
        )
    )

    # ---- 2. Tribes among several eligible classes -------------------
    key = "tribes_among_many"
    rows.append(
        _row(
            key,
            "Tribes named alongside states, counties and nonprofits",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={
                "eligible_applicant_codes": ["07", "01", "02"],
                "eligible_applicant_terms": ["State governments", "County governments"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Indian tribes", "States", "Counties"],
                    field_name="eligible_applicants",
                )
            ],
            entity_classes=["tribal_government", "state_government"],
        )
    )

    # ---- 3. no Native keyword, Tribal governments eligible ----------
    # The case the product principle exists for.
    key = "no_keyword_but_unrestricted"
    rows.append(
        _row(
            key,
            "coded 99 unrestricted; no Native word appears anywhere",
            expected_candidate=CANDIDATE,
            expected_classes={BROADLY_ELIGIBLE_NATIVE_RELEVANT},
            inputs={"eligible_applicant_codes": ["99"]},
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Unrestricted - open to any type of entity"],
                    field_name="eligible_applicants",
                )
            ],
        )
    )

    # ---- 4. Native beneficiaries, non-Native applicant --------------
    key = "native_beneficiaries_state_applicant"
    rows.append(
        _row(
            key,
            "a state health agency applies; the served population is Tribal",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_BENEFICIARY_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "beneficiary_terms": ["American Indian and Alaska Native populations"],
            },
            evidence=[
                _ev(
                    key,
                    BENEFICIARY_POPULATION,
                    "American Indian and Alaska Native populations",
                    field_name="beneficiaries",
                ),
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["State governments"],
                    field_name="eligible_applicants",
                ),
            ],
            sectors=["health"],
        )
    )

    # ---- 5. HARD NEGATIVE: keyword only in background ---------------
    key = "hard_negative_background_paragraph"
    rows.append(
        _row(
            key,
            "the only Tribal mention is a prior-cycle grantee in the background",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "native_terms_in_narrative_only": ["tribal"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["State governments"],
                    field_name="eligible_applicants",
                ),
                _ev(
                    key,
                    PROGRAM_HISTORY,
                    "in FY2019 a Tribal consortium received an award",
                    confidence=DERIVED,
                    ambiguity=TEMPORAL_AMBIGUOUS,
                    section_ref="background",
                ),
            ],
            hard_negative=True,
        )
    )

    # ---- 6. HARD NEGATIVE: place name -------------------------------
    key = "hard_negative_place_name"
    rows.append(
        _row(
            key,
            "'Indian River County' is a place, not an applicant class",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["02"],
                "native_terms_in_narrative_only": ["indian river county"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["County governments"],
                    field_name="eligible_applicants",
                ),
                _ev(
                    key,
                    GEOGRAPHIC_RELEVANCE,
                    "Indian River County, Florida",
                    ambiguity=CONTEXT_AMBIGUOUS,
                ),
            ],
            hard_negative=True,
        )
    )

    # ---- 7. state program, Tribal eligibility buried ----------------
    key = "state_program_buried_tribal_eligibility"
    rows.append(
        _row(
            key,
            "eligibility to Tribes appears only in an attachment",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={
                "eligible_applicant_terms": ["State governments", "Nonprofits"],
                "document_signal_count": 1,
            },
            evidence=[
                _ev(
                    key,
                    DOCUMENT_REFERENCE,
                    "federally recognized Indian tribes located in the state",
                    supports=[NATIVE_ELIGIBLE],
                    section_ref="Attachment B, Eligibility",
                    page_ref=14,
                )
            ],
            entity_classes=["tribal_government"],
        )
    )

    # ---- 8-10. non-federal publishers --------------------------------
    for key, label, family in (
        ("foundation_opportunity", "a private foundation program", "FOUNDATION"),
        ("corporate_philanthropy", "a corporate giving program", "CORPORATE"),
        ("university_opportunity", "a university subaward", "UNIVERSITY"),
    ):
        rows.append(
            _row(
                key,
                f"{label} open to Native nonprofits",
                expected_candidate=CANDIDATE,
                expected_classes={NATIVE_ELIGIBLE},
                inputs={
                    "eligible_applicant_terms": ["Nonprofits"],
                    "source_is_native_serving": False,
                    "document_signal_count": 1,
                },
                evidence=[
                    _ev(
                        key,
                        DOCUMENT_REFERENCE,
                        "Native-led nonprofit organizations are eligible",
                        supports=[NATIVE_ELIGIBLE],
                        source_id=f"gold.{family.lower()}",
                        section_ref="Eligibility",
                    )
                ],
                entity_classes=["native_nonprofit"],
            )
        )

    # ---- 11. recurring program, title changed ------------------------
    key = "recurring_program_renamed"
    rows.append(
        _row(
            key,
            "same program, new title; relevance comes from its history",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={
                "eligible_applicant_codes": ["07"],
                "program_history_native_awards": 6,
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Native American tribal governments (Federally recognized)"],
                    field_name="eligible_applicants",
                ),
                _ev(
                    key,
                    PROGRAM_HISTORY,
                    "6 prior awards to Tribes under the predecessor title",
                    confidence=DERIVED,
                ),
            ],
        )
    )

    # ---- 12. amendment ADDS Tribes -----------------------------------
    key = "amendment_adds_tribes"
    rows.append(
        _row(
            key,
            "the original notice excluded Tribes; amendment 2 adds them",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={
                "eligible_applicant_codes": ["01", "07"],
                "document_signal_count": 1,
            },
            evidence=[
                _ev(
                    key,
                    DOCUMENT_REFERENCE,
                    "Amendment 2 adds federally recognized Indian tribes",
                    supports=[NATIVE_ELIGIBLE],
                    section_ref="Amendment 2",
                    payload="gold.payload.amendment2",
                )
            ],
            entity_classes=["tribal_government"],
        )
    )

    # ---- 13. amendment REMOVES Tribes --------------------------------
    key = "amendment_removes_tribes"
    rows.append(
        _row(
            key,
            "Tribes were eligible; amendment 3 removes them explicitly",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "explicit_native_exclusion": True,
            },
            evidence=[
                _ev(
                    key,
                    DOCUMENT_REFERENCE,
                    "Amendment 3: tribal governments are no longer eligible",
                    supports=[NOT_RELEVANT],
                    section_ref="Amendment 3",
                    payload="gold.payload.amendment3",
                )
            ],
            hard_negative=True,
        )
    )

    # ---- 14. acronym only --------------------------------------------
    key = "acronym_only_tcu"
    rows.append(
        _row(
            key,
            "'TCUs' is the only Native reference and it is an applicant class",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={
                "eligible_applicant_terms": ["TCUs", "HBCUs", "MSIs"],
                "native_terms_in_operative_text": ["TCU"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["TCUs", "HBCUs", "MSIs"],
                    supports=[NATIVE_ELIGIBLE],
                    field_name="eligible_applicants",
                )
            ],
            entity_classes=["tribal_college_or_university"],
            sectors=["education"],
        )
    )

    # ---- 15. geography-driven ----------------------------------------
    key = "geography_driven"
    rows.append(
        _row(
            key,
            "scoped to trust land and reservations; applicant class unstated",
            expected_candidate=CANDIDATE,
            expected_classes={UNCERTAIN, NATIVE_BENEFICIARY_RELEVANT},
            set_reason=(
                "geography establishes that the money lands on Native land but "
                "says nothing about who may apply; both a beneficiary reading "
                "and a request for review are defensible"
            ),
            inputs={"geography_terms": ["trust land", "reservation"]},
            evidence=[
                _ev(
                    key,
                    GEOGRAPHIC_RELEVANCE,
                    ["trust land", "reservation boundaries"],
                    field_name="geographic_scope",
                )
            ],
        )
    )

    # ---- 16. sector-driven only --------------------------------------
    key = "sector_driven_only"
    rows.append(
        _row(
            key,
            "tribal-heavy sector, nothing else",
            expected_candidate=CANDIDATE,
            expected_classes={INDIRECTLY_RELEVANT},
            inputs={
                "sector_keys": ["water"],
                "native_relevant_sectors": ["water", "housing"],
            },
            evidence=[
                _ev(key, SECTOR_ALIGNMENT, "water infrastructure", confidence=DERIVED)
            ],
            sectors=["water"],
        )
    )

    # ---- 17. broad public-government funding --------------------------
    key = "broad_public_government"
    rows.append(
        _row(
            key,
            "open to every unit of general local government",
            expected_candidate=CANDIDATE,
            expected_classes={BROADLY_ELIGIBLE_NATIVE_RELEVANT},
            inputs={
                "eligible_applicant_terms": [
                    "Units of local government",
                    "State governments",
                    "Special district governments",
                ]
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Units of local government", "State governments"],
                    ambiguity=ENTITY_CLASS_AMBIGUOUS,
                    field_name="eligible_applicants",
                )
            ],
        )
    )

    # ---- 18. strong relevance, ambiguous entity type ------------------
    key = "ambiguous_entity_type"
    rows.append(
        _row(
            key,
            "'tribal organizations' without saying which kind",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE, UNCERTAIN},
            set_reason=(
                "the Native character is unambiguous but the entity class is "
                "not, so a reviewer may reasonably be asked which one"
            ),
            inputs={"eligible_applicant_codes": ["11"]},
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Native American tribal organizations"],
                    ambiguity=ENTITY_CLASS_AMBIGUOUS,
                    supports=[NATIVE_ELIGIBLE],
                    field_name="eligible_applicants",
                )
            ],
        )
    )

    # ---- 19. clearly not relevant -------------------------------------
    key = "clearly_not_relevant"
    rows.append(
        _row(
            key,
            "a research grant for individual investigators at universities",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={"eligible_applicant_codes": ["06"]},
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Public and State controlled institutions of higher education"],
                    field_name="eligible_applicants",
                )
            ],
            hard_negative=True,
        )
    )

    # ---- 20. insufficient evidence ------------------------------------
    key = "insufficient_evidence"
    rows.append(
        _row(
            key,
            "a title and nothing else",
            expected_candidate=CANDIDATE_UNKNOWN,
            expected_classes={UNCERTAIN},
            inputs={},
            evidence=[],
        )
    )

    # ---- 21-27. the remaining hard negatives ---------------------------
    key = "hard_negative_native_as_adjective"
    rows.append(
        _row(
            key,
            "'native plant species' is botany, not a people",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "native_terms_in_narrative_only": ["native species"],
            },
            evidence=[
                _ev(
                    key,
                    PROGRAM_PURPOSE,
                    "restoration of native prairie species",
                    ambiguity=CONTEXT_AMBIGUOUS,
                ),
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["State governments"],
                    field_name="eligible_applicants",
                ),
            ],
            hard_negative=True,
        )
    )

    key = "hard_negative_prior_award_does_not_imply_current"
    rows.append(
        _row(
            key,
            "a Tribe won this in 2021; this cycle excludes them",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "explicit_native_exclusion": True,
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["State governments only"],
                    supports=[NOT_RELEVANT],
                    field_name="eligible_applicants",
                )
            ],
            hard_negative=True,
        )
    )

    key = "hard_negative_diversity_language"
    rows.append(
        _row(
            key,
            "broad diversity language with no Native applicability",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={"eligible_applicant_codes": ["06"]},
            evidence=[
                _ev(
                    key,
                    PROGRAM_PURPOSE,
                    "applicants are encouraged to promote diverse participation",
                    confidence=INFERRED,
                    ambiguity=CONTEXT_AMBIGUOUS,
                ),
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Institutions of higher education"],
                    field_name="eligible_applicants",
                ),
            ],
            hard_negative=True,
        )
    )

    key = "hard_negative_agency_mission_only"
    rows.append(
        _row(
            key,
            "the bureau serves Tribes; this particular notice does not",
            expected_candidate=CANDIDATE,
            expected_classes={INDIRECTLY_RELEVANT, UNCERTAIN},
            set_reason=(
                "agency context is a real signal and never sufficient; both a "
                "weak-relevance reading and a review request are defensible"
            ),
            inputs={"source_is_native_serving": True},
            evidence=[
                _ev(
                    key,
                    AGENCY_CONTEXT,
                    "Bureau of Indian Affairs",
                    confidence=DERIVED,
                ),
                _ev(
                    key,
                    SOURCE_CONTEXT,
                    "publisher is a Native-serving agency",
                    confidence=DERIVED,
                ),
            ],
            hard_negative=True,
        )
    )

    key = "hard_negative_archived_out_of_scope"
    rows.append(
        _row(
            key,
            "an archived notice from a closed cycle",
            expected_candidate=NOT_CANDIDATE,
            expected_classes={NOT_RELEVANT},
            inputs={
                "eligible_applicant_codes": ["01"],
                "native_terms_in_narrative_only": ["tribal"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["State governments"],
                    ambiguity=TEMPORAL_AMBIGUOUS,
                    field_name="eligible_applicants",
                )
            ],
            hard_negative=True,
        )
    )

    key = "statutory_authority_names_tribes"
    rows.append(
        _row(
            key,
            "authorised under a statute that names Indian tribes",
            expected_candidate=CANDIDATE,
            expected_classes={NATIVE_ELIGIBLE},
            inputs={"statutory_authorities": ["25 U.S.C. 5301"]},
            evidence=[
                _ev(
                    key,
                    STATUTORY_LANGUAGE,
                    "Indian Self-Determination and Education Assistance Act",
                    supports=[NATIVE_ELIGIBLE],
                    field_name="authority",
                )
            ],
            entity_classes=["tribal_government"],
        )
    )

    key = "prior_native_award_observed"
    rows.append(
        _row(
            key,
            "an award to a Tribe was observed under this exact program",
            expected_candidate=CANDIDATE,
            expected_classes={BROADLY_ELIGIBLE_NATIVE_RELEVANT},
            inputs={
                "prior_native_award_count": 3,
                "eligible_applicant_codes": ["99"],
            },
            evidence=[
                _ev(
                    key,
                    APPLICANT_ELIGIBILITY,
                    ["Unrestricted"],
                    field_name="eligible_applicants",
                )
            ],
        )
    )

    return rows


def run_corpus() -> dict[str, Any]:
    """Push every row through the real model and score it.

    Nothing here consults `expected_*` until after the model has answered.
    """
    results: list[dict[str, Any]] = []

    for row in corpus():
        key = row["key"]
        inputs = dict(row["inputs"])
        evidence = row["evidence"]

        candidate = detect_candidate(
            canonical_id=key, evidence_items=evidence, **inputs
        )
        assessment = classify_relevance(
            canonical_id=key,
            candidate=candidate,
            evidence_items=evidence,
            entity_classes=row["entity_classes"],
            sectors=row["sectors"],
            explicit_native_exclusion=bool(inputs.get("explicit_native_exclusion")),
        )

        actual_candidate = str(candidate["candidate_state"])
        actual_class = str(assessment["relevance_class"])
        expected_classes = set(row["expected_classes"])

        results.append(
            {
                "key": key,
                "why": row["why"],
                "hard_negative": row["hard_negative"],
                "expected_candidate": row["expected_candidate"],
                "actual_candidate": actual_candidate,
                "candidate_correct": actual_candidate == row["expected_candidate"],
                "expected_classes": row["expected_classes"],
                "actual_class": actual_class,
                "class_correct": actual_class in expected_classes,
                "review_required": bool(assessment["review_required"]),
                "review_reasons": assessment["review_reasons"],
                "confidence": assessment["confidence"],
                "reasons": assessment["reasons"],
                "evidence_count": len(evidence),
                "candidate_failures": candidate_invariant_failures(candidate),
                "classification_failures": classification_invariant_failures(
                    assessment=assessment,
                    evidence_items=evidence,
                    candidate=candidate,
                ),
                # Truth, for the metrics below. Expressed as "should a Native
                # entity ever see this", which is the question recall is about.
                "truth_is_relevant": bool(expected_classes & RELEVANT_TRUTH),
                # The accepted set admits both a relevant answer and a request
                # for review, so neither can be scored as a miss.
                "truth_is_ambiguous": bool(expected_classes & RELEVANT_TRUTH)
                and bool(expected_classes - RELEVANT_TRUTH),
                "model_says_relevant": actual_class in RELEVANT_TRUTH,
            }
        )

    total = len(results)
    # Recall is measured over rows that are UNAMBIGUOUSLY relevant. A row whose
    # accepted set spans a relevant class AND UNCERTAIN cannot be a miss when
    # the model answers UNCERTAIN - that answer was explicitly allowed - and
    # leaving it in the denominator scored accepted answers as failures.
    # The excluded rows are named, not silently dropped.
    positives = [
        r for r in results if r["truth_is_relevant"] and not r["truth_is_ambiguous"]
    ]
    negatives = [r for r in results if not r["truth_is_relevant"]]
    ambiguous = [r for r in results if r["truth_is_ambiguous"]]

    # Candidate-stage recall: of the rows that ARE relevant, how many did the
    # high-recall stage keep? A false negative here is unrecoverable - nothing
    # downstream ever sees the row again.
    candidate_true_positive = [
        r for r in positives if r["actual_candidate"] == CANDIDATE
    ]
    candidate_false_negative = [
        r for r in positives if r["actual_candidate"] == NOT_CANDIDATE
    ]
    candidate_false_positive = [
        r for r in negatives if r["actual_candidate"] == CANDIDATE
    ]

    classification_true_positive = [r for r in positives if r["model_says_relevant"]]
    classification_false_negative = [
        r for r in positives if not r["model_says_relevant"]
    ]
    classification_false_positive = [r for r in negatives if r["model_says_relevant"]]

    def ratio(numerator: int, denominator: int) -> float | None:
        # A metric computed against an empty denominator is not a measurement.
        return None if denominator == 0 else round(numerator / denominator, 4)

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_size": total,
        "hard_negative_count": sum(1 for r in results if r["hard_negative"]),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "ambiguous_count": len(ambiguous),
        "rows_excluded_from_recall_as_genuinely_ambiguous": sorted(
            r["key"] for r in ambiguous
        ),
        "candidate_recall": ratio(len(candidate_true_positive), len(positives)),
        "candidate_precision": ratio(
            len(candidate_true_positive),
            len(candidate_true_positive) + len(candidate_false_positive),
        ),
        "classification_recall": ratio(
            len(classification_true_positive), len(positives)
        ),
        "classification_precision": ratio(
            len(classification_true_positive),
            len(classification_true_positive) + len(classification_false_positive),
        ),
        "false_negative_count": len(classification_false_negative),
        "false_positive_count": len(classification_false_positive),
        "candidate_false_negative_count": len(candidate_false_negative),
        "candidate_false_negatives": sorted(r["key"] for r in candidate_false_negative),
        "false_negatives": sorted(r["key"] for r in classification_false_negative),
        "false_positives": sorted(r["key"] for r in classification_false_positive),
        "review_required_rate": ratio(
            sum(1 for r in results if r["review_required"]), total
        ),
        "unknown_rate": ratio(
            sum(1 for r in results if r["actual_class"] == UNCERTAIN), total
        ),
        "candidate_accuracy": ratio(
            sum(1 for r in results if r["candidate_correct"]), total
        ),
        "class_accuracy": ratio(sum(1 for r in results if r["class_correct"]), total),
        "rows_with_wrong_class": sorted(
            r["key"] for r in results if not r["class_correct"]
        ),
        "rows_with_wrong_candidate": sorted(
            r["key"] for r in results if not r["candidate_correct"]
        ),
        "invariant_failures": sorted(
            {
                f"{r['key']}:{failure}"
                for r in results
                for failure in (r["candidate_failures"] + r["classification_failures"])
            }
        ),
        "results": results,
    }


def describe_corpus() -> dict[str, Any]:
    rows = corpus()
    keys = [row["key"] for row in rows]
    return json.loads(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "corpus_size": len(rows),
                "keys_are_unique": len(set(keys)) == len(keys),
                "hard_negative_count": sum(1 for row in rows if row["hard_negative"]),
                "every_multi_class_row_says_why": all(
                    row["set_reason"]
                    for row in rows
                    if len(row["expected_classes"]) > 1
                ),
                "no_row_states_its_own_answer": all(
                    "relevance_class" not in row["inputs"] for row in rows
                ),
                "rows_with_no_evidence": sorted(
                    row["key"] for row in rows if not row["evidence"]
                ),
            },
            default=str,
        )
    )
