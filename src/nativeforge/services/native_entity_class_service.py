"""Native-serving does not mean Tribe-eligible.

A publisher whose entire mission is Native health still runs programmes that a
Tribe cannot apply for. Measured on one such agency's live forecast portfolio,
the four opportunities its Tribal applicant-type codes fail to index are:

    Tribal Epidemiology Centers   $7,000,000   "Tribes, Tribal Organizations,
                                                Urban Organizations"
    Urban Indian 4-in-1           $9,707,858   "IHS contracted UIOs"
    Urban Indian Educ. & Research $1,450,000   "AIAN National organization"
    National Urban Indian BH        $200,000   "must be a 501(c)(3)"

One of those four is open to Tribes. Three are not. Collapsing them all to
`tribal = true` because the agency is Native-serving would show a Tribe
$11.3M it cannot apply for, and would do it while looking like coverage.

## Entity classes are legal classes

An Urban Indian Organization is not a kind of Tribe. A Tribal Organization is
not a Tribal government. A 501(c)(3) is not either. Congress wrote these as
distinct classes and the publisher repeats them exactly, so this module
records exactly what was named and nothing more.

## Three-valued, and never optimistic

`tribe_named_as_eligible_class` is YES / NO / UNKNOWN. It is YES only when a
Tribal class is actually named, NO only when the prose names classes and none
of them is Tribal, and UNKNOWN whenever the prose cannot be read. It defaults
to UNKNOWN, because the cost of a wrong YES is a Tribe spending a fortnight on
an application it was never eligible to file.

## This is evidence, not a verdict

Gate 174 decides whether a given tenant is eligible. Nothing here may
pre-empt it, and `tenant_eligibility_decided` is False on every result.

## Nothing here is any one agency

Every class is expressed in the statutory language such programmes generally
use. A different health, housing or education publisher reuses this unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_native_entity_class_v1"

# ---- entity classes ---------------------------------------------------
TRIBE_FEDERALLY_RECOGNIZED = "TRIBE_FEDERALLY_RECOGNIZED"
TRIBE_STATE_RECOGNIZED = "TRIBE_STATE_RECOGNIZED"
#: A Tribe is named and its recognition status is NOT stated. Measured: most
#: of one agency's portfolio reads simply "Tribes/Tribal Organizations", and
#: requiring the words "federally recognized" returned UNKNOWN for nine of
#: eighteen live opportunities - a false negative pointing away from money a
#: Tribe may well be able to apply for. A Tribe IS named here; what is unknown
#: is the recognition requirement, and those are two different questions.
TRIBE_RECOGNITION_UNSPECIFIED = "TRIBE_RECOGNITION_UNSPECIFIED"
TRIBAL_ORGANIZATION = "TRIBAL_ORGANIZATION"
URBAN_INDIAN_ORGANIZATION = "URBAN_INDIAN_ORGANIZATION"
AIAN_NATIONAL_ORGANIZATION = "AIAN_NATIONAL_ORGANIZATION"
TRIBAL_EPIDEMIOLOGY_CENTER = "TRIBAL_EPIDEMIOLOGY_CENTER"
TRIBAL_COLLEGE_OR_UNIVERSITY = "TRIBAL_COLLEGE_OR_UNIVERSITY"
NONPROFIT_501C3 = "NONPROFIT_501C3"
ENTITY_CLASS_UNKNOWN = "UNKNOWN"

ENTITY_CLASSES: tuple[str, ...] = (
    TRIBE_FEDERALLY_RECOGNIZED,
    TRIBE_STATE_RECOGNIZED,
    TRIBE_RECOGNITION_UNSPECIFIED,
    TRIBAL_ORGANIZATION,
    URBAN_INDIAN_ORGANIZATION,
    AIAN_NATIONAL_ORGANIZATION,
    TRIBAL_EPIDEMIOLOGY_CENTER,
    TRIBAL_COLLEGE_OR_UNIVERSITY,
    NONPROFIT_501C3,
    ENTITY_CLASS_UNKNOWN,
)

#: The classes that ARE a Tribal government, at any recognition status. A
#: Tribal organization may be controlled by Tribes and is still a different
#: applicant than the Tribe itself, and a publisher that names one and not the
#: other means it - so TRIBAL_ORGANIZATION is deliberately NOT in here.
TRIBAL_GOVERNMENT_CLASSES: frozenset[str] = frozenset(
    {
        TRIBE_FEDERALLY_RECOGNIZED,
        TRIBE_STATE_RECOGNIZED,
        TRIBE_RECOGNITION_UNSPECIFIED,
    }
)

#: Classes that are Native-serving and are NOT a Tribal government. Naming one
#: of these is evidence a programme is Native-relevant; it is not evidence a
#: Tribe may apply.
NATIVE_SERVING_NON_TRIBAL_CLASSES: frozenset[str] = frozenset(
    {
        TRIBAL_ORGANIZATION,
        URBAN_INDIAN_ORGANIZATION,
        AIAN_NATIONAL_ORGANIZATION,
        TRIBAL_EPIDEMIOLOGY_CENTER,
        TRIBAL_COLLEGE_OR_UNIVERSITY,
    }
)

# ---- three-valued answer ---------------------------------------------
NAMED_YES = "YES"
NAMED_NO = "NO"
NAMED_UNKNOWN = "UNKNOWN"

# ---- patterns ---------------------------------------------------------
#: NO trailing \b anywhere a plural or a stem is valid. This defect has now
#: shipped twice - a closing boundary on the funding acronyms classified real
#: notices as OTHER, and \bnofo\b refused "NOFOs" on a live page. Statutory
#: prose is written in both numbers ("an Indian Tribe" / "Indian Tribes",
#: "Urban Indian Organization" / "UIOs"), so every alternative below is a
#: prefix and every plural is covered by a regression test.
_PATTERNS: tuple[tuple[str, str], ...] = (
    # Most specific first: a Tribal Epidemiology Center is a Tribal
    # organization in law, and calling it the general class loses the
    # programme's actual applicant.
    (
        TRIBAL_EPIDEMIOLOGY_CENTER,
        r"\btribal\s+epidemiolog\w*\s+cent\w*|\btec\b",
    ),
    (
        URBAN_INDIAN_ORGANIZATION,
        r"\burban\s+indian\s+organi\w*|\burban\s+organi\w*|\buio\w*|"
        r"\burban\s+indian\s+health\s+program\w*",
    ),
    (
        AIAN_NATIONAL_ORGANIZATION,
        r"\baian\s+national\s+organi\w*|"
        r"\bnational\s+(?:american\s+indian|aian)\s+organi\w*|"
        r"\bamerican\s+indian\s*/?\s*alaska\s+native\s+national\s+organi\w*",
    ),
    (
        TRIBAL_COLLEGE_OR_UNIVERSITY,
        r"\btribal\s+college\w*|\btribally\s+controlled\s+college\w*|\btcu\b",
    ),
    (
        TRIBE_STATE_RECOGNIZED,
        r"\bstate[- ]recognized\s+tribe\w*|\bstate[- ]recognized\s+indian\s+tribe\w*",
    ),
    (
        TRIBE_FEDERALLY_RECOGNIZED,
        r"\bfederally[- ]recognized\s+(?:indian\s+)?tribe\w*|"
        r"\bfederally[- ]recognized\s+tribal\s+government\w*|"
        r"\bindian\s+tribe\w*|\btribal\s+government\w*|"
        r"\balaska\s+native\s+village\w*",
    ),
    (
        TRIBAL_ORGANIZATION,
        r"\btribal\s+organi\w*|\bindian\s+organi\w*|"
        r"\btribally\s+designated\s+\w+\s+entit\w*",
    ),
    # Bare "Tribe"/"Tribes", carrying no recognition qualifier. Listed last so
    # the qualified readings win their evidence first; a record may legitimately
    # carry both, and "Tribes/Tribal Organizations" must produce a Tribe class
    # AND a Tribal-organization class rather than only the latter.
    (
        TRIBE_RECOGNITION_UNSPECIFIED,
        r"\btribes\b|\btribe\b",
    ),
    (
        NONPROFIT_501C3,
        r"\b501\s*\(?\s*c\s*\)?\s*\(?\s*3\s*\)?|\bnon-?profit\s+organi\w*",
    ),
)

_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.I)) for name, pattern in _PATTERNS
)

#: "must be", "limited to", "only" - language that makes a list exhaustive.
#: Without it a list may be illustrative, and an absent Tribe means UNKNOWN
#: rather than NO.
_EXCLUSIVE_RE = re.compile(
    r"\b(must\s+be|limited\s+to|restricted\s+to|only\s+\w+\s+(?:may|are)|"
    r"eligible\s+applicants?\s+(?:are|is)|to\s+be\s+eligible)",
    re.I,
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _normalise(prose: str) -> str:
    text = re.sub(r"&quot;", '"', prose or "")
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&sect;", " section ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_entity_classes(
    eligibility_prose: str | None,
) -> dict[str, Any]:
    """Which statutory applicant classes does this prose actually name?

    Returns every class found with the exact phrase that evidenced it, so a
    reviewer can check the reading rather than trust it. Classes are never
    inferred from each other: naming a Tribal Organization does not add a
    Tribe, and naming a Tribe does not add a Tribal Organization.
    """
    text = _normalise(eligibility_prose or "")
    found: list[str] = []
    evidence: dict[str, list[str]] = {}
    for name, pattern in _COMPILED:
        matches = [m.group(0).strip() for m in pattern.finditer(text)]
        if matches:
            found.append(name)
            evidence[name] = sorted({m.lower() for m in matches})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "entity_classes": sorted(found),
            "class_evidence": {k: evidence[k] for k in sorted(evidence)},
            "prose_present": bool(text),
            "exclusive_language": bool(_EXCLUSIVE_RE.search(text)),
            "classes_are_legal_classes_not_synonyms": True,
        }
    )


def assess_tribal_applicant_class(
    eligibility_prose: str | None,
    *,
    publisher_is_native_serving: bool = False,
) -> dict[str, Any]:
    """Is a Tribal government NAMED as an eligible applicant class?

    `publisher_is_native_serving` is accepted and deliberately does not move
    the answer. It exists so a caller cannot quietly pass agency focus in as
    though it were eligibility evidence: an agency devoted entirely to Native
    health publishes programmes restricted to Urban Indian Organizations and
    to 501(c)(3)s, and three of the four measured ones are closed to Tribes.
    """
    extracted = extract_entity_classes(eligibility_prose)
    classes = list(extracted["entity_classes"])
    tribal_gov = [c for c in classes if c in TRIBAL_GOVERNMENT_CLASSES]
    native_other = [c for c in classes if c in NATIVE_SERVING_NON_TRIBAL_CLASSES]

    federally_recognized_required = TRIBE_FEDERALLY_RECOGNIZED in classes
    state_recognized_named = TRIBE_STATE_RECOGNIZED in classes
    if federally_recognized_required:
        recognition = "FEDERAL_RECOGNITION_STATED"
    elif state_recognized_named:
        recognition = "STATE_RECOGNITION_STATED"
    elif TRIBE_RECOGNITION_UNSPECIFIED in classes:
        recognition = "NOT_STATED"
    else:
        recognition = "NO_TRIBE_CLASS_NAMED"

    reasons: list[str] = []
    if tribal_gov:
        named = NAMED_YES
        reasons.append("a_tribal_government_class_is_named")
    elif not extracted["prose_present"]:
        named = NAMED_UNKNOWN
        reasons.append("no_eligibility_prose_to_read")
    elif not classes:
        named = NAMED_UNKNOWN
        reasons.append("prose_names_no_recognisable_entity_class")
    elif extracted["exclusive_language"]:
        named = NAMED_NO
        reasons.append("prose_names_classes_exclusively_and_none_is_tribal")
    else:
        # Classes are named but the list may be illustrative. Absence of a
        # Tribe in a non-exclusive list is not proof of exclusion.
        named = NAMED_UNKNOWN
        reasons.append("classes_named_without_exclusive_language")

    if publisher_is_native_serving:
        reasons.append("publisher_native_focus_recorded_and_not_used_as_evidence")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "entity_classes": classes,
            "class_evidence": extracted["class_evidence"],
            "tribe_named_as_eligible_class": named,
            "tribal_government_classes_named": sorted(tribal_gov),
            # Separate from whether a Tribe is named. A publisher that says
            # "Tribes" has named one and has NOT stated a recognition
            # requirement, and inventing one in either direction is wrong.
            "federal_recognition": recognition,
            "federal_recognition_stated": federally_recognized_required,
            # The signal that separates "restricted to another class" from
            # "prose could not be read at all".
            "no_tribal_class_named": bool(classes and not tribal_gov),
            "native_serving_non_tribal_classes_named": sorted(native_other),
            "native_relevant_evidence_present": bool(tribal_gov or native_other),
            "exclusive_language": extracted["exclusive_language"],
            "reasons": sorted(set(reasons)),
            # The guard this module exists for.
            "publisher_native_focus_is_not_eligibility": True,
            "classes_are_legal_classes_not_synonyms": True,
            "state_recognition_never_inferred": TRIBE_STATE_RECOGNIZED not in classes,
            # Gates 173 and 174 still own the verdicts.
            "native_relevance_decided": False,
            "tenant_eligibility_decided": False,
        }
    )


def summarize_entity_classes(
    assessments: list[dict[str, Any]],
) -> dict[str, Any]:
    """How much of a Native-serving portfolio is actually open to Tribes?"""
    by_named: dict[str, int] = {NAMED_YES: 0, NAMED_NO: 0, NAMED_UNKNOWN: 0}
    by_class: dict[str, int] = {c: 0 for c in ENTITY_CLASSES}
    for entry in assessments:
        named = str(entry.get("tribe_named_as_eligible_class") or NAMED_UNKNOWN)
        by_named[named] = by_named.get(named, 0) + 1
        for cls in entry.get("entity_classes") or []:
            by_class[cls] = by_class.get(cls, 0) + 1
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "assessment_count": len(assessments),
            "by_tribe_named": dict(sorted(by_named.items())),
            "by_entity_class": dict(sorted(by_class.items())),
            # The number a Native-serving publisher makes it easy to forget.
            "not_named_for_tribes": by_named.get(NAMED_NO, 0),
            "native_serving_is_not_tribe_eligible": True,
        }
    )
