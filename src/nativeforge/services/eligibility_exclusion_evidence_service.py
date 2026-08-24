"""Eligibility exclusion evidence (Gate 79C).

Lets the product say *"this programme's cited eligibility text appears to exclude
this applicant class"* — a claim it previously could not make.

Gate 78R is the case. `advance.sc.gov/grants-state-tribes` is South Carolina's
own resource *for state tribes*, and the programmes on it are federal. NACTEP's
eligibility, quoted on that page, reads:

    "Federally recognized Indian tribes, tribal organizations, Alaska Native
    entities, and eligible BIE-funded schools"

South Carolina has one federally recognized tribe and ten state-recognized ones.
That sentence is not silence about state-recognized tribes — it is an enumerated,
exclusive list they are not on. Until now the product could only answer
``unknown``, which is less than the evidence supports and less than a grant
office needs. Telling a tribal organization "we don't know" when the notice
plainly excludes them wastes the scarcest thing they have, which is staff time.

**The distinction that keeps this honest.** ``excluded_by_evidence`` is
programme-specific and evidence-bound: *this* notice's cited text excludes *this*
applicant class. It is not ``not_eligible``, which would be a universal claim
about an organization. ``federal_native_eligibility_service`` hardcodes
``not_eligible_asserted: False`` with an invariant forbidding anything else, and
Gate 79 leaves that exactly as it is. This module never asserts that an
organization is ineligible for anything in general.

Four inferences refused, each of which would produce a confident wrong answer:

  * **Silence is not exclusion.** A notice that simply does not mention
    state-recognized tribes yields ``unknown``, not exclusion. Only an
    *exclusive* list excludes.
  * **A narrow grant is not a broad one.** "BIE-funded schools" does not make
    tribal governments eligible, and does not exclude them either — it says
    nothing about them unless the list is exclusive.
  * **A restriction is not an exclusion.** "On Federal Trust land" narrows how a
    class may use an award; it does not remove the class.
  * **Exclusion is per class.** Excluding state-recognized tribes says nothing
    about Native nonprofits.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_eligibility_exclusion_evidence_v1"

APPLICANT_CLASSES = frozenset(
    {
        "federally_recognized_tribe",
        "state_recognized_tribe",
        "native_nonprofit",
        "native_business",
        "tribal_organization",
        "bie_funded_school",
        "native_individual",
        "unknown",
    }
)

RESULT_STATES = frozenset(
    {
        "eligible",
        "possibly_eligible",
        "excluded_by_evidence",
        "not_supported_by_evidence",
        "unknown",
        "human_review_required",
    }
)

# Bridge onto federal_native_eligibility_service.RECOGNITION_TIERS, which names
# the federal tier differently and has only three members. Classes with no tier
# there map to None rather than borrowing one.
FEDERAL_TIER_MAP: dict[str, str | None] = {
    "federally_recognized_tribe": "federally_recognized_tribal_government",
    "state_recognized_tribe": "state_recognized_tribe",
    "native_nonprofit": "native_nonprofit",
    "native_business": None,
    "tribal_organization": None,
    "bie_funded_school": None,
    "native_individual": None,
    "unknown": None,
}

# Phrases that make an eligibility list *exclusive*. Without one of these, a
# list is illustrative and its omissions prove nothing.
EXCLUSIVITY_MARKERS = (
    "only",
    "limited to",
    "restricted to",
    "must be",
    "eligible applicants are",
    "eligibility is limited",
    "solely",
    "exclusively",
)

# What each class looks like in eligibility prose. Deliberately conservative:
# a phrase must clearly name the class.
CLASS_PHRASES: dict[str, tuple[str, ...]] = {
    "federally_recognized_tribe": (
        "federally recognized indian tribe",
        "federally recognized tribal government",
        "federally recognized tribe",
        "federally-recognized tribe",
        "federally recognized american indian",
    ),
    "state_recognized_tribe": (
        "state recognized tribe",
        "state-recognized tribe",
        "state recognized indian",
    ),
    "native_nonprofit": (
        "native nonprofit",
        "native american nonprofit",
        "native-serving nonprofit",
        "nonprofit native",
    ),
    "native_business": (
        "native owned business",
        "native-owned business",
        "indian-owned business",
        "native american business",
    ),
    "tribal_organization": ("tribal organization", "tribal organisations"),
    "bie_funded_school": (
        "bie-funded school",
        "bie funded school",
        "bureau of indian education",
    ),
    "native_individual": (
        "native american student",
        "american indian and alaska native student",
        "native individual",
        "american indian and alaska native undergraduate",
    ),
}

# Restrictions that narrow how an award may be used without removing a class.
RESTRICTION_PHRASES: dict[str, tuple[str, ...]] = {
    "federal_trust_land": ("federal trust land", "trust land", "on trust land"),
    "reservation_only": ("on the reservation", "reservation boundaries"),
    "service_area_only": ("within the service area", "designated service area"),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalise(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def federal_tier_for(applicant_class: str) -> str | None:
    """Project an applicant class onto the Gate 77 recognition tier set."""
    return FEDERAL_TIER_MAP.get(applicant_class)


def analyse_eligibility_text(text: str | None) -> dict[str, Any]:
    """Find which classes an eligibility statement names, and whether the list
    it presents is exclusive."""
    normalised = _normalise(text)
    named = sorted(
        cls
        for cls, phrases in CLASS_PHRASES.items()
        if any(p in normalised for p in phrases)
    )
    markers = sorted(m for m in EXCLUSIVITY_MARKERS if m in normalised)
    restrictions = sorted(
        name
        for name, phrases in RESTRICTION_PHRASES.items()
        if any(p in normalised for p in phrases)
    )
    return {
        "text_present": bool(normalised),
        "named_classes": named,
        "exclusivity_markers": markers,
        "is_exclusive_list": bool(markers and named),
        "restrictions": restrictions,
    }


def evaluate_applicant_class(
    *,
    opportunity_id: str,
    applicant_class: str,
    eligibility_text: str | None = None,
    evidence_reference: str | None = None,
    additional_expanding_evidence: list[dict[str, Any]] | None = None,
    additional_named_classes: list[str] | None = None,
    negated_classes: list[str] | None = None,
) -> dict[str, Any]:
    """Decide one applicant class's standing against one programme's cited text.

    ``evidence_reference`` is required for any exclusion. An exclusion without a
    citation is an accusation, and it would discourage a real applicant on our
    say-so.

    Gate 81: ``additional_named_classes`` carries classes found by a richer
    vocabulary than ``CLASS_PHRASES`` knows - typically the non-Native classes
    the Gate 81 parser adds. A notice reading "only units of local government
    may apply" names nobody this module recognises, so without them the list
    would not register as exclusive and a tribe would come back
    ``not_supported_by_evidence`` when the text plainly excludes it.

    They can only ever make a list **exclusive**. They are never treated as
    naming *this* class, so they cannot manufacture eligibility.
    """
    reasons: list[str] = []
    cls = applicant_class if applicant_class in APPLICANT_CLASSES else "unknown"
    if applicant_class not in APPLICANT_CLASSES:
        reasons.append(f"unrecognised_applicant_class:{applicant_class}")

    analysis = analyse_eligibility_text(eligibility_text)
    extra_named = sorted(
        {
            str(c)
            for c in (additional_named_classes or [])
            if str(c) and str(c) != cls
        }
    )
    if extra_named and analysis["exclusivity_markers"]:
        # Markers were present but nothing this module knows was named. The
        # richer vocabulary supplies the missing half of "exclusive list".
        analysis = dict(analysis)
        analysis["is_exclusive_list"] = True

    has_citation = bool(str(evidence_reference or "").strip())

    # Evidence that widens eligibility beyond the primary text. Needs its own
    # reference; a bare assertion does not reopen a closed list.
    expanding = [
        item
        for item in (additional_expanding_evidence or [])
        if isinstance(item, dict)
        and str(item.get("reference") or "").strip()
        and cls in (item.get("expands_classes") or [])
    ]

    # Gate 81: the class is named, but named as *excluded* - "federally
    # recognized tribes are not eligible under this program". Without this the
    # naming alone reads as eligibility, which is the worst direction to be
    # wrong in: it would tell a tribe to spend weeks on a programme that has
    # already ruled them out in writing.
    negated = cls != "unknown" and cls in {
        str(c) for c in (negated_classes or [])
    }

    state = "unknown"

    if cls == "unknown":
        reasons.append("applicant_class_unknown")
    elif not analysis["text_present"]:
        reasons.append("no_eligibility_text")
    elif negated:
        if has_citation:
            state = "excluded_by_evidence"
            reasons.append("applicant_class_named_as_excluded_in_eligibility_text")
        else:
            state = "human_review_required"
            reasons.append("negation_indicated_but_no_citation_supplied")
    elif cls in analysis["named_classes"]:
        state = "eligible"
        reasons.append("applicant_class_named_in_eligibility_text")
    elif analysis["is_exclusive_list"]:
        if expanding:
            # A later notice or funder confirmation reopened the list.
            state = "possibly_eligible"
            reasons.append("exclusive_list_widened_by_additional_evidence")
        elif not has_citation:
            # The evidence is there but nobody cited it. Refuse to conclude.
            state = "human_review_required"
            reasons.append("exclusion_indicated_but_no_citation_supplied")
        else:
            state = "excluded_by_evidence"
            reasons.append(
                "exclusive_eligibility_list_does_not_include_this_class:"
                + ",".join(analysis["exclusivity_markers"][:3])
            )
    else:
        # Text exists, names other classes, but is not exclusive. Silence is not
        # exclusion.
        state = "not_supported_by_evidence"
        reasons.append("eligibility_text_does_not_address_this_class")

    if state not in RESULT_STATES:
        state = "unknown"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "applicant_class": cls,
            "federal_recognition_tier": federal_tier_for(cls),
            "result_state": state,
            "excluded": state == "excluded_by_evidence",
            "reasons": reasons,
            "evidence_reference": evidence_reference if has_citation else None,
            "has_citation": has_citation,
            "named_classes": analysis["named_classes"],
            # Kept separate from named_classes: these come from a vocabulary
            # this module does not own, and merging them would make it look as
            # though CLASS_PHRASES had grown.
            "additional_named_classes": extra_named,
            "negated": negated,
            "exclusivity_markers": analysis["exclusivity_markers"],
            "is_exclusive_list": analysis["is_exclusive_list"],
            "restrictions": analysis["restrictions"],
            "expanding_evidence_count": len(expanding),
            "human_review_required": state
            in {"human_review_required", "unknown", "not_supported_by_evidence"},
            # This module never asserts universal ineligibility. Gate 77's
            # forbidden claim stands untouched.
            "not_eligible_asserted": False,
            "eligibility_proven": state == "eligible" and has_citation,
        }
    )


def evaluate_all_applicant_classes(
    *,
    opportunity_id: str,
    eligibility_text: str | None = None,
    evidence_reference: str | None = None,
    additional_expanding_evidence: list[dict[str, Any]] | None = None,
    additional_named_classes: list[str] | None = None,
    negated_classes: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate every applicant class against one programme.

    Returns a per-class verdict rather than a single answer, because a notice
    that excludes state-recognized tribes may still be open to Native
    nonprofits, and collapsing that into one state would lose the useful half.
    """
    per_class = {
        cls: evaluate_applicant_class(
            opportunity_id=opportunity_id,
            applicant_class=cls,
            eligibility_text=eligibility_text,
            evidence_reference=evidence_reference,
            additional_expanding_evidence=additional_expanding_evidence,
            additional_named_classes=additional_named_classes,
            negated_classes=negated_classes,
        )
        for cls in sorted(APPLICANT_CLASSES - {"unknown"})
    }

    excluded = sorted(c for c, r in per_class.items() if r["excluded"])
    eligible = sorted(
        c for c, r in per_class.items() if r["result_state"] == "eligible"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "per_class": per_class,
            "eligible_classes": eligible,
            "excluded_classes": excluded,
            "any_exclusion": bool(excluded),
            "evidence_reference": evidence_reference,
            "restrictions": analyse_eligibility_text(eligibility_text)["restrictions"],
            "not_eligible_asserted": False,
            "coverage_claimed": False,
        }
    )


def exclusion_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("applicant_class") not in APPLICANT_CLASSES:
        fails.append("applicant_class_invalid")
    if result.get("result_state") not in RESULT_STATES:
        fails.append("result_state_invalid")

    state = result.get("result_state")

    # An exclusion must be cited, and must rest on either an exclusive list or
    # an explicit negation of this class.
    if state == "excluded_by_evidence":
        negated = bool(result.get("negated"))
        if not result.get("has_citation"):
            fails.append("exclusion_without_citation")
        if not result.get("is_exclusive_list") and not negated:
            fails.append("exclusion_without_an_exclusive_eligibility_list")
        # Being named is only evidence of eligibility when the naming is not a
        # negation. "Tribes are not eligible" names the class and excludes it.
        if (
            not negated
            and result.get("applicant_class") in (result.get("named_classes") or [])
        ):
            fails.append("excluded_a_class_the_text_names_as_eligible")
    if result.get("excluded") and state != "excluded_by_evidence":
        fails.append("excluded_flag_without_exclusion_state")

    # Eligible requires the text to name the class.
    if state == "eligible" and result.get("applicant_class") not in (
        result.get("named_classes") or []
    ):
        fails.append("eligible_without_being_named")

    if result.get("eligibility_proven") and state != "eligible":
        fails.append("eligibility_proven_without_eligible_state")

    # The Gate 77 boundary, restated and enforced here too.
    if result.get("not_eligible_asserted") is not False:
        fails.append("forbidden_claim:not_eligible_asserted")
    return fails


def all_classes_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    per_class = result.get("per_class") or {}
    if set(per_class) != APPLICANT_CLASSES - {"unknown"}:
        fails.append("per_class_set_incomplete")

    for cls, verdict in per_class.items():
        for failure in exclusion_invariant_failures(verdict):
            fails.append(f"{cls}:{failure}")

    # A class cannot be both eligible and excluded.
    overlap = set(result.get("eligible_classes") or []) & set(
        result.get("excluded_classes") or []
    )
    if overlap:
        fails.append(f"class_both_eligible_and_excluded:{sorted(overlap)}")

    if result.get("not_eligible_asserted") is not False:
        fails.append("forbidden_claim:not_eligible_asserted")
    if result.get("coverage_claimed") is not False:
        fails.append("forbidden_claim:coverage_claimed")
    return fails
