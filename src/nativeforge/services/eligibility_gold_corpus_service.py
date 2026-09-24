"""Gate 174I: the eligibility cases NativeForge has to get right.

Same discipline as Gate 173's relevance corpus: every row supplies RAW
requirements and a RAW profile, and the runner pushes them through the real
`match_eligibility`. No row states the answer the engine then agrees with.

The cases are chosen around the four ways an eligibility layer hurts someone:

```text
saying yes when a disqualifier applies    -> three weeks wasted, then rejected
saying no when the block is obtainable    -> a fundable cycle abandoned
saying yes on an unanswered question      -> a claim nobody can defend
transferring eligibility between classes  -> a Tribe told to apply as a TCU
```

The last one is the most specific to this product and the least likely to be
caught by a generic test suite, so four rows exercise it directly.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_match_engine_service import (
    match_eligibility,
    match_invariant_failures,
)
from nativeforge.services.eligibility_requirement_model_service import (
    APPLICANT_TYPE,
    CONDITIONALLY_ELIGIBLE,
    DEADLINE,
    ELIGIBLE,
    EXCLUSION,
    GEOGRAPHIC,
    INELIGIBLE,
    LIKELY_ELIGIBLE,
    MATCHING_FUNDS,
    PARTNERSHIP,
    PURSUABLE,
    RECOGNITION_OR_DESIGNATION,
    REGISTRATION,
    UNKNOWN,
    build_requirement,
    requirement_invariant_failures,
)
from nativeforge.services.organization_capability_profile_service import (
    build_profile,
    profile_invariant_failures,
)

SCHEMA_VERSION = "nf_eligibility_gold_corpus_v1"


def _req(
    canonical_id: str,
    kind: str,
    value: Any,
    text: str,
    *,
    polarity: str = "INCLUSION",
    classes: list[str] | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    return build_requirement(
        canonical_id=canonical_id,
        requirement_kind=kind,
        normalized_value=value,
        original_text=text,
        polarity=polarity,
        applies_to_entity_classes=classes,
        raw_payload_sha256="gold.eligibility.payload",
        source_id="gold.source",
        evidence_ids=[f"ev.{canonical_id}.{kind.lower()}"],
        section_ref=section,
    )


def _row(
    key: str,
    why: str,
    *,
    expected: set[str],
    set_reason: str = "",
    requirements: list[dict[str, Any]],
    facts: dict[str, Any],
) -> dict[str, Any]:
    if len(expected) > 1 and not set_reason:
        raise ValueError(f"{key}: a set of expected results must say why it is a set")
    return {
        "key": key,
        "why": why,
        "expected_results": sorted(expected),
        "set_reason": set_reason,
        "requirements": requirements,
        "facts": facts,
    }


def corpus() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # ---- 1. Tribes explicitly eligible, applicant is a Tribe --------
    key = "tribes_explicitly_eligible"
    rows.append(
        _row(
            key,
            "the notice names Indian tribes and the applicant is one",
            expected={ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Federally recognized Indian tribes are eligible",
                    classes=["tribal_government"],
                )
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 2. Tribes explicitly EXCLUDED -------------------------------
    key = "tribes_explicitly_excluded"
    rows.append(
        _row(
            key,
            "an exclusion names tribal governments",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["local_government"],
                    "Units of local government are eligible",
                    classes=["local_government"],
                ),
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Tribal governments are not eligible under this notice",
                    polarity=EXCLUSION,
                    classes=["tribal_government"],
                ),
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 3. local governments eligible, Tribal status ambiguous ------
    key = "local_government_eligible_tribe_not_named"
    rows.append(
        _row(
            key,
            "'units of local government' does not name a Tribe",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["local_government"],
                    "Units of general local government",
                    classes=["local_government"],
                )
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 4. Native nonprofit eligible, tribal government not ---------
    key = "native_nonprofit_eligible_tribe_not"
    rows.append(
        _row(
            key,
            "the notice names Native nonprofits only",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["native_nonprofit"],
                    "Native-led nonprofit organizations",
                    classes=["native_nonprofit"],
                )
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 5. tribal government eligible, enterprise not ---------------
    key = "tribe_eligible_enterprise_not"
    rows.append(
        _row(
            key,
            "a tribal enterprise is not a tribal government",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                )
            ],
            facts={"entity_class": "tribal_enterprise"},
        )
    )

    # ---- 6. consortium required, applicant has no partner ------------
    key = "consortium_required_no_partner"
    rows.append(
        _row(
            key,
            "a partnership is required and the profile says there is none",
            expected={CONDITIONALLY_ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(
                    key,
                    PARTNERSHIP,
                    ["institution_of_higher_education"],
                    "Applicants must partner with an institution of higher education",
                ),
            ],
            facts={
                "entity_class": "tribal_government",
                "partnership_capability": ["community_health_center"],
            },
        )
    )

    # ---- 7. matching funds required, applicant cannot -----------------
    key = "matching_funds_required_cannot_meet"
    rows.append(
        _row(
            key,
            "a cost share is required and the profile says no",
            expected={CONDITIONALLY_ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(
                    key,
                    MATCHING_FUNDS,
                    True,
                    "A 20% non-federal match is required",
                    section="Section III.B",
                ),
            ],
            facts={
                "entity_class": "tribal_government",
                "matching_funds_capability": False,
            },
        )
    )

    # ---- 8. match capability UNANSWERED ------------------------------
    key = "matching_funds_unknown"
    rows.append(
        _row(
            key,
            "nobody has asked whether this Tribe can match",
            expected={LIKELY_ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(key, MATCHING_FUNDS, True, "A 20% match is required"),
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 9. geographic restriction, applicant outside ----------------
    key = "geographic_restriction_outside"
    rows.append(
        _row(
            key,
            "the program is scoped to a region the applicant is not in",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(
                    key,
                    GEOGRAPHIC,
                    ["alaska"],
                    "Projects must be located in Alaska",
                ),
            ],
            facts={
                "entity_class": "tribal_government",
                "geographies_served": ["oklahoma"],
            },
        )
    )

    # ---- 10. recognition requirement, self-declared ------------------
    key = "recognition_required_self_declared"
    rows.append(
        _row(
            key,
            "federal recognition is required and the Tribe told us it has it",
            expected={ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(
                    key,
                    RECOGNITION_OR_DESIGNATION,
                    True,
                    "Applicant must be a federally recognized tribe",
                ),
            ],
            facts={
                "entity_class": "tribal_government",
                "federal_recognition": True,
            },
        )
    )

    # ---- 11. registration missing ------------------------------------
    key = "registration_missing"
    rows.append(
        _row(
            key,
            "SAM registration is required and the profile says no",
            expected={CONDITIONALLY_ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(key, REGISTRATION, True, "Active SAM.gov registration required"),
            ],
            facts={
                "entity_class": "tribal_government",
                "sam_registration": False,
            },
        )
    )

    # ---- 12. missing evidence entirely -------------------------------
    key = "no_requirements_normalized"
    rows.append(
        _row(
            key,
            "nothing has been parsed for this opportunity yet",
            expected={UNKNOWN},
            requirements=[],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 13. applicant entity class unstated -------------------------
    key = "applicant_entity_class_unstated"
    rows.append(
        _row(
            key,
            "the profile has never been asked what kind of entity it is",
            expected={UNKNOWN},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                )
            ],
            facts={},
        )
    )

    # ---- 14. deadline is not an eligibility question -----------------
    key = "deadline_is_not_eligibility"
    rows.append(
        _row(
            key,
            "a deadline belongs to the pursuit layer, not here",
            expected={ELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(key, DEADLINE, "2026-11-01", "Applications due November 1, 2026"),
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    # ---- 15. exclusion outranks many satisfied requirements ----------
    key = "exclusion_outranks_positives"
    rows.append(
        _row(
            key,
            "five satisfied requirements do not outvote one exclusion",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Indian tribes",
                    classes=["tribal_government"],
                ),
                _req(key, MATCHING_FUNDS, True, "20% match"),
                _req(key, REGISTRATION, True, "SAM registration"),
                _req(key, GEOGRAPHIC, ["oklahoma"], "Projects in Oklahoma"),
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_government"],
                    "Prior-year grantees under this program are not eligible",
                    polarity=EXCLUSION,
                    classes=["tribal_government"],
                ),
            ],
            facts={
                "entity_class": "tribal_government",
                "matching_funds_capability": True,
                "sam_registration": True,
                "geographies_served": ["oklahoma"],
            },
        )
    )

    # ---- 16. tribal consortium named, Tribe applying -----------------
    key = "consortium_named_tribe_applying"
    rows.append(
        _row(
            key,
            "a notice for tribal consortia does not name a single Tribe",
            expected={INELIGIBLE},
            requirements=[
                _req(
                    key,
                    APPLICANT_TYPE,
                    ["tribal_consortium"],
                    "Tribal consortia are eligible",
                    classes=["tribal_consortium"],
                )
            ],
            facts={"entity_class": "tribal_government"},
        )
    )

    return rows


def run_corpus() -> dict[str, Any]:
    """Every row through the real engine. Expectations consulted afterwards."""
    results: list[dict[str, Any]] = []

    for row in corpus():
        key = row["key"]
        profile = build_profile(organization_id=f"org.{key}", facts=row["facts"])
        match = match_eligibility(
            canonical_id=key,
            requirements=row["requirements"],
            profile=profile,
            tenant_id=f"tenant.{key}",
        )
        actual = str(match["eligibility_result"])
        expected = set(row["expected_results"])

        results.append(
            {
                "key": key,
                "why": row["why"],
                "expected_results": row["expected_results"],
                "actual_result": actual,
                "correct": actual in expected,
                "reason": match["reason"],
                "satisfied": len(match["satisfied_requirements"]),
                "unsatisfied": len(match["unsatisfied_requirements"]),
                "unknown": len(match["unknown_requirements"]),
                "review": len(match["review_required_items"]),
                "conditions": match["conditions_to_obtain"],
                "applied_exclusions": len(match["applied_exclusions"]),
                "match_failures": match_invariant_failures(match),
                "requirement_failures": sorted(
                    {
                        f
                        for requirement in row["requirements"]
                        for f in requirement_invariant_failures(requirement)
                    }
                ),
                "profile_failures": profile_invariant_failures(profile),
                "truth_is_pursuable": bool(expected & PURSUABLE),
                "engine_says_pursuable": actual in PURSUABLE,
            }
        )

    total = len(results)
    pursuable_truth = [r for r in results if r["truth_is_pursuable"]]
    blocked_truth = [r for r in results if not r["truth_is_pursuable"]]

    def ratio(numerator: int, denominator: int) -> float | None:
        return None if denominator == 0 else round(numerator / denominator, 4)

    # A false POSITIVE here means telling somebody to apply when they cannot.
    false_positives = [r for r in blocked_truth if r["engine_says_pursuable"]]
    # A false NEGATIVE means abandoning a cycle that was winnable.
    false_negatives = [r for r in pursuable_truth if not r["engine_says_pursuable"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_size": total,
        "pursuable_truth_count": len(pursuable_truth),
        "blocked_truth_count": len(blocked_truth),
        "eligibility_false_positive_count": len(false_positives),
        "eligibility_false_negative_count": len(false_negatives),
        "eligibility_false_positives": sorted(r["key"] for r in false_positives),
        "eligibility_false_negatives": sorted(r["key"] for r in false_negatives),
        "unknown_count": sum(1 for r in results if r["actual_result"] == UNKNOWN),
        "review_required_count": sum(1 for r in results if r["review"]),
        "conditional_count": sum(
            1 for r in results if r["actual_result"] == CONDITIONALLY_ELIGIBLE
        ),
        "result_accuracy": ratio(sum(1 for r in results if r["correct"]), total),
        "rows_with_wrong_result": sorted(r["key"] for r in results if not r["correct"]),
        "invariant_failures": sorted(
            {
                f"{r['key']}:{failure}"
                for r in results
                for failure in (
                    r["match_failures"]
                    + r["requirement_failures"]
                    + r["profile_failures"]
                )
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
                "no_row_states_its_own_answer": all(
                    "eligibility_result" not in row["facts"] for row in rows
                ),
                "every_multi_result_row_says_why": all(
                    row["set_reason"]
                    for row in rows
                    if len(row["expected_results"]) > 1
                ),
                "entity_class_transfer_rows": sorted(
                    row["key"]
                    for row in rows
                    if "tribe" in row["key"] or "consortium" in row["key"]
                ),
            },
            default=str,
        )
    )
