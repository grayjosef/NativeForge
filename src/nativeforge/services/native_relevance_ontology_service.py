"""Gate 173B/D/E: what "Native-relevant" means, in a vocabulary that can be
versioned and argued with.

The product principle this exists to enforce:

```text
Native relevance is NOT the presence of the words Native, Indian or Tribal.
```

A highly Native-relevant opportunity may never use Native-specific language in
its title. Relevance can arise from who may apply, who benefits, where the
money goes, what statute authorises it, which agency runs it, what the program
has historically funded, or simply from a general-government eligibility list
that includes Tribes without saying so prominently.

So the ontology is deliberately NOT a single score. A score is useful for
ranking a list; it is useless for defending an answer, and it cannot be
reviewed. What is durable here is:

```text
classification + evidence + reason + uncertainty
```

A score may be derived from those for ordering. It never replaces them.

Three vocabularies live in this module because they are read together and
would drift apart if they were separated:

*   **relevance classes** - how Native-relevant an opportunity is
*   **entity classes** - what KIND of Native organisation is involved, because
    a tribal government, a tribal college and a Native-serving nonprofit are
    not interchangeable and an eligibility list that names one does not name
    the others
*   **sectors** - what the money is FOR, data-driven, because a rigid enum
    means a code change every time a funder invents a program area

Gate 173 classifies RELEVANCE. Gate 174 decides ELIGIBILITY. The two are
separate on purpose: an opportunity can be unmistakably Native-relevant and
still be one a given Tribe cannot apply for.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_native_relevance_ontology_v1"

#: Bumped when a class is added, removed or redefined. Stored alongside every
#: assessment so a classification made under an older vocabulary is never
#: silently compared against a newer one.
ONTOLOGY_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# 173B: relevance classes
# --------------------------------------------------------------------

NATIVE_SPECIFIC = "NATIVE_SPECIFIC"
NATIVE_PRIORITY = "NATIVE_PRIORITY"
NATIVE_ELIGIBLE = "NATIVE_ELIGIBLE"
BROADLY_ELIGIBLE_NATIVE_RELEVANT = "BROADLY_ELIGIBLE_NATIVE_RELEVANT"
NATIVE_BENEFICIARY_RELEVANT = "NATIVE_BENEFICIARY_RELEVANT"
INDIRECTLY_RELEVANT = "INDIRECTLY_RELEVANT"
UNCERTAIN = "UNCERTAIN"
NOT_RELEVANT = "NOT_RELEVANT"

RELEVANCE_CLASSES: tuple[str, ...] = (
    NATIVE_SPECIFIC,
    NATIVE_PRIORITY,
    NATIVE_ELIGIBLE,
    BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    NATIVE_BENEFICIARY_RELEVANT,
    INDIRECTLY_RELEVANT,
    UNCERTAIN,
    NOT_RELEVANT,
)

#: One meaning per class, written once. The distinctions are the product.
CLASS_MEANINGS: dict[str, str] = {
    NATIVE_SPECIFIC: (
        "only Native entities may apply - the opportunity exists for them"
    ),
    NATIVE_PRIORITY: (
        "open more widely, but Native applicants are preferred, set aside for, "
        "or scored higher by the program's own terms"
    ),
    NATIVE_ELIGIBLE: (
        "Native entities are named in the eligibility list alongside others"
    ),
    BROADLY_ELIGIBLE_NATIVE_RELEVANT: (
        "eligibility is general government or general nonprofit and therefore "
        "includes Tribes without naming them"
    ),
    NATIVE_BENEFICIARY_RELEVANT: (
        "the applicant need not be Native, but Native people or lands are the "
        "beneficiaries the money is meant to reach"
    ),
    INDIRECTLY_RELEVANT: (
        "a real but weak connection - sector, geography or agency mission - "
        "with no evidence that Native entities or beneficiaries are in scope"
    ),
    UNCERTAIN: (
        "the evidence on file does not settle the question; this is a request "
        "for a human, not a soft NOT_RELEVANT"
    ),
    NOT_RELEVANT: (
        "evidence positively indicates this is not Native-relevant, including "
        "explicit exclusion of Native entities"
    ),
}

#: Classes that mean "a Native entity may itself apply". Beneficiary relevance
#: is deliberately NOT in this set: who benefits and who may apply are
#: different questions, and collapsing them is the mistake that makes a
#: pipeline recommend opportunities nobody can submit.
APPLICANT_RELEVANT: frozenset[str] = frozenset(
    {
        NATIVE_SPECIFIC,
        NATIVE_PRIORITY,
        NATIVE_ELIGIBLE,
        BROADLY_ELIGIBLE_NATIVE_RELEVANT,
    }
)

#: Classes that must never be filtered out of an operator's view. UNCERTAIN is
#: here on purpose - hiding it is how a high-recall stage quietly becomes a
#: low-recall one.
MUST_REMAIN_VISIBLE: frozenset[str] = frozenset(
    APPLICANT_RELEVANT | {NATIVE_BENEFICIARY_RELEVANT, UNCERTAIN}
)

#: Classes that are NOT a finding and must not be reported as one.
NOT_A_FINDING: frozenset[str] = frozenset({UNCERTAIN})

#: Ordering for ranking ONLY. It is not the truth and nothing may be derived
#: from it except display order. UNCERTAIN deliberately outranks
#: INDIRECTLY_RELEVANT: an unanswered question deserves attention before a
#: weak answer does.
_RANK: dict[str, int] = {
    NATIVE_SPECIFIC: 80,
    NATIVE_PRIORITY: 70,
    NATIVE_ELIGIBLE: 60,
    BROADLY_ELIGIBLE_NATIVE_RELEVANT: 50,
    NATIVE_BENEFICIARY_RELEVANT: 40,
    UNCERTAIN: 30,
    INDIRECTLY_RELEVANT: 20,
    NOT_RELEVANT: 0,
}

# --------------------------------------------------------------------
# 173D: entity classes
# --------------------------------------------------------------------

#: (key, is_native, description). `is_native` answers "is this entity itself a
#: Native entity", which is a different question from whether it is eligible
#: for anything - that belongs to Gate 174.
_ENTITY_CLASSES: tuple[tuple[str, bool, str], ...] = (
    (
        "tribal_government",
        True,
        "a federally or state recognised Tribe acting as a government",
    ),
    ("tribal_consortium", True, "two or more Tribes acting jointly under an agreement"),
    ("tribal_enterprise", True, "a business arm chartered by a Tribe"),
    (
        "tribal_authority",
        True,
        "a chartered authority such as a utility or transit authority",
    ),
    ("tribal_housing_entity", True, "a TDHE or equivalent housing authority"),
    ("tribal_college_or_university", True, "a TCU"),
    (
        "native_health_organization",
        True,
        "an IHS-funded or tribally operated health organisation",
    ),
    ("native_nonprofit", True, "a nonprofit controlled by Native people or a Tribe"),
    (
        "native_serving_nonprofit",
        False,
        "a nonprofit serving Native people without Native control",
    ),
    ("alaska_native_village", True, "an ANV, where the program's scope recognises it"),
    (
        "alaska_native_corporation",
        True,
        "an ANC, where the program's scope recognises it",
    ),
    (
        "native_hawaiian_organization",
        True,
        "an NHO, where the program's scope recognises it",
    ),
    ("local_government", False, "a county, city, town or equivalent"),
    ("state_government", False, "a state or state agency"),
    ("nonprofit", False, "a nonprofit with no Native-specific character"),
    ("university", False, "an institution of higher education"),
    ("utility", False, "a utility or cooperative"),
    (
        "special_purpose_entity",
        False,
        "a district, authority or other special-purpose body",
    ),
    ("for_profit", False, "a commercial entity"),
    ("individual", False, "a natural person"),
    (
        "other_entity",
        False,
        "an entity class the source names that this vocabulary does not",
    ),
)

ENTITY_CLASSES: tuple[str, ...] = tuple(key for key, _, _ in _ENTITY_CLASSES)

ENTITY_CLASS_MEANINGS: dict[str, str] = {
    key: description for key, _, description in _ENTITY_CLASSES
}

#: Entity classes that are themselves Native entities. `native_serving_nonprofit`
#: is deliberately excluded: serving Native people is not being a Native entity,
#: and an eligibility list naming "Indian tribes" does not name it.
NATIVE_ENTITY_CLASSES: frozenset[str] = frozenset(
    key for key, is_native, _ in _ENTITY_CLASSES if is_native
)

#: Classes whose eligibility is commonly assumed to transfer to Tribes and
#: does not. Naming them is the point: an opportunity open to "units of local
#: government" does not thereby name a Tribe, though many programs do treat
#: Tribes as such - which is a fact that must come from EVIDENCE, per source.
DOES_NOT_IMPLY_TRIBAL: frozenset[str] = frozenset(
    {"local_government", "state_government", "nonprofit", "university"}
)

# --------------------------------------------------------------------
# 173E: sectors
# --------------------------------------------------------------------

#: Seeded, not fixed. `register_sector` extends it at runtime, because a rigid
#: enum means a code change every time a funder invents a program area - and
#: the alternative to extending is silently mapping a new sector onto "other",
#: which loses the fact that it was new.
_SEED_SECTORS: tuple[str, ...] = (
    "housing",
    "infrastructure",
    "transportation",
    "broadband",
    "energy",
    "water",
    "public_safety",
    "justice",
    "health",
    "behavioral_health",
    "education",
    "language_and_culture",
    "economic_development",
    "workforce",
    "tourism",
    "food_and_agriculture",
    "environment",
    "climate_and_resilience",
    "emergency_management",
    "technology",
    "community_facilities",
    "child_and_family_services",
    "elder_services",
    "land_and_natural_resources",
    "other_sector",
)

_SECTORS: dict[str, str] = {key: "seed" for key in _SEED_SECTORS}


def sectors() -> tuple[str, ...]:
    """Every known sector, seeded plus registered."""
    return tuple(sorted(_SECTORS))


def register_sector(name: str, *, origin: str = "runtime") -> str:
    """Add a sector the data revealed. Idempotent; returns the stored key.

    A sector arriving from a source is a FACT about that source, so it is
    recorded rather than folded into `other_sector`.
    """
    key = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not key:
        return "other_sector"
    _SECTORS.setdefault(key, origin)
    return key


def sector_is_seeded(name: str) -> bool:
    return _SECTORS.get(str(name)) == "seed"


def reset_registered_sectors() -> None:
    """Drop runtime registrations. Exists so a test can prove extensibility
    without leaking a sector into the next test."""
    for key in [key for key, origin in _SECTORS.items() if origin != "seed"]:
        del _SECTORS[key]


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def is_relevance_class(value: Any) -> bool:
    return str(value) in RELEVANCE_CLASSES


def is_entity_class(value: Any) -> bool:
    return str(value) in ENTITY_CLASSES


def is_native_entity_class(value: Any) -> bool:
    return str(value) in NATIVE_ENTITY_CLASSES


def ranking_score(relevance_class: Any) -> int:
    """For ORDERING a list. Never for deciding anything.

    Kept deliberately coarse and deliberately separate from the class so that
    nothing can quietly start thresholding on it.
    """
    return _RANK.get(str(relevance_class), 0)


def class_requires_review(relevance_class: Any) -> bool:
    return str(relevance_class) in NOT_A_FINDING


def describe_ontology() -> dict[str, Any]:
    """Structural facts a verifier can assert without re-deriving them."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "ontology_version": ONTOLOGY_VERSION,
            "relevance_classes": list(RELEVANCE_CLASSES),
            "entity_classes": list(ENTITY_CLASSES),
            "native_entity_classes": sorted(NATIVE_ENTITY_CLASSES),
            "seed_sector_count": len(_SEED_SECTORS),
            "sector_count": len(_SECTORS),
            "classes_are_distinct": len(set(RELEVANCE_CLASSES))
            == len(RELEVANCE_CLASSES),
            "every_class_has_a_meaning": set(CLASS_MEANINGS) == set(RELEVANCE_CLASSES),
            "every_meaning_is_distinct": len(set(CLASS_MEANINGS.values()))
            == len(RELEVANCE_CLASSES),
            "every_entity_class_has_a_meaning": set(ENTITY_CLASS_MEANINGS)
            == set(ENTITY_CLASSES),
            # The three facts that carry the product principle.
            "relevance_is_not_a_single_score": True,
            "beneficiary_relevance_is_not_applicant_relevance": (
                NATIVE_BENEFICIARY_RELEVANT not in APPLICANT_RELEVANT
            ),
            "uncertain_is_not_not_relevant": (
                UNCERTAIN in MUST_REMAIN_VISIBLE and UNCERTAIN != NOT_RELEVANT
            ),
            "native_serving_is_not_a_native_entity": (
                "native_serving_nonprofit" not in NATIVE_ENTITY_CLASSES
            ),
            "general_government_does_not_imply_tribal": sorted(DOES_NOT_IMPLY_TRIBAL),
            "sectors_are_extensible": True,
        }
    )
