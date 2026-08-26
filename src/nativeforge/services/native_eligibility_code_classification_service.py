"""Native eligibility code classification (Gate 92F).

## The recall set is five codes, not two

Grants.gov "Eligible Applicants" is a 2-character coded value. Three codes are
direct tribal positives:

* ``07`` Native American tribal governments (Federally recognized)
* ``11`` Native American tribal organizations (other than Federally recognized
  tribal governments)
* ``08`` Public housing authorities/Indian housing authorities

But two more must be in the **recall** set:

* ``99`` Unrestricted (open to any type of entity) - silently tribe-eligible
* ``25`` Others (see the free-text "Additional Information on Eligibility")

``25`` hides tribal eligibility inside a 4,000-character free-text field. A
system that filters on ``07|11`` looks clean and silently misses a large share
of tribally-eligible money. That is the exact failure NativeForge exists to
prevent, so it is encoded as an invariant here rather than left to a query.

## Graded, never boolean

The output is a ``confidence`` band, not a yes/no:

``direct``           the code names tribal applicants (07, 11, 08 / ET230x0)
``requires_reading`` eligible-in-principle; the answer is in text we have not
                     read (99, 25, ET12010)
``negative``         no tribal-eligible code present
``unknown``          no code present at all - **not** the same as negative

``requires_reading`` never collapses into either neighbour. Treating it as a
positive fabricates eligibility; treating it as a negative hides money.

## The SAM crosswalk is a mapping, not an equivalence

``ET23010``/``ET23020``/``ET23030`` map onto ``07``/``11``/``08``, and the
research pass tagged that mapping as its own inference rather than as
documentation. It is recorded here with ``mapping_is_inferred: True`` so a
later reviewer can see it was never claimed as documented.

``ET12010`` ("Specific Restrictions Determined at NOFO Level") means the
Assistance Listing **under-determines** eligibility - the NOFO text is
authoritative.

## What this does not do

It does not read the free-text field. It marks it as requiring a read, records
whether text is even present, and stops. No NLP, no keyword guessing, no
inference from a title. Classification is over codes that exist in a record.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_native_eligibility_code_classification_v1"

# Grants.gov "Eligible Applicants" codes that name tribal applicants directly.
DIRECT_TRIBAL_CODES: dict[str, str] = {
    "07": "Native American tribal governments (Federally recognized)",
    "11": (
        "Native American tribal organizations (other than Federally recognized "
        "tribal governments)"
    ),
    "08": "Public housing authorities/Indian housing authorities",
}

# Codes that are eligible-in-principle and push the real answer into text.
REQUIRES_READING_CODES: dict[str, str] = {
    "99": "Unrestricted (i.e., open to any type of entity below)",
    "25": 'Others (see text field entitled "Additional Information on Eligibility")',
}

# The recall set. Deny-by-default: the allowed set is derived, never subtracted.
NATIVE_RECALL_CODES = frozenset(DIRECT_TRIBAL_CODES) | frozenset(
    REQUIRES_READING_CODES
)

# SAM.gov Assistance Listings applicant/beneficiary type codes.
SAM_DIRECT_TRIBAL_CODES: dict[str, str] = {
    "ET23010": (
        "Federally Recognized Indian/Native American/Alaska Native Tribal "
        "Government"
    ),
    "ET23020": (
        "Indian/Native American/Alaska Native Tribal Government (Other than "
        "Federally Recognized)"
    ),
    "ET23030": "Tribally Designated Housing Authority",
    "ET26040": "Tribal",
}

SAM_REQUIRES_READING_CODES: dict[str, str] = {
    "ET12010": "Specific Restrictions Determined at NOFO Level",
    "ET11010": "Unrestricted by Entity Type",
    "ET11020": "Unrestricted by Individual Type",
}

SAM_RECALL_CODES = frozenset(SAM_DIRECT_TRIBAL_CODES) | frozenset(
    SAM_REQUIRES_READING_CODES
)

# Inferred, and labelled as such wherever it is used.
SAM_TO_GRANTS_GOV_CROSSWALK: dict[str, str] = {
    "ET23010": "07",
    "ET23020": "11",
    "ET23030": "08",
}

CONFIDENCE_BANDS = frozenset({"direct", "requires_reading", "negative", "unknown"})

# The controlled applicant-class vocabulary. Twelve members including UNKNOWN.
ELIGIBILITY_CLASSES = frozenset(
    {
        "federally-recognized-tribe",
        "state-recognized-tribe",
        "tribal-government",
        "tribal-organization",
        "native-nonprofit",
        "native-owned-business",
        "native-serving-nonprofit",
        "tribal-college-or-BIE-school",
        "native-individual",
        "consortium-with-tribal-partner",
        "state-or-local-govt-serving-natives",
        "UNKNOWN",
    }
)

# Classes a code implies. Only where the code's own label says so.
CODE_TO_CLASSES: dict[str, tuple[str, ...]] = {
    "07": ("federally-recognized-tribe", "tribal-government"),
    "11": ("tribal-organization",),
    "08": ("tribal-organization",),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _clean_codes(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = raw.replace("|", ",").split(",")
    else:
        parts = list(raw)
    return [str(p).strip().upper() for p in parts if str(p).strip()]


def classify_native_eligibility(
    *,
    eligible_applicant_codes: Any = None,
    sam_applicant_type_codes: Any = None,
    additional_eligibility_text: Any = None,
    opportunity_key: Any = None,
) -> dict[str, Any]:
    """Grade one opportunity's tribal eligibility from its codes alone."""
    gg = _clean_codes(eligible_applicant_codes)
    sam = _clean_codes(sam_applicant_type_codes)

    gg_direct = [c for c in gg if c in DIRECT_TRIBAL_CODES]
    gg_reading = [c for c in gg if c in REQUIRES_READING_CODES]
    sam_direct = [c for c in sam if c in SAM_DIRECT_TRIBAL_CODES]
    sam_reading = [c for c in sam if c in SAM_REQUIRES_READING_CODES]

    text = additional_eligibility_text
    has_text = bool(text is not None and str(text).strip())

    if gg_direct or sam_direct:
        confidence = "direct"
    elif gg_reading or sam_reading:
        confidence = "requires_reading"
    elif gg or sam:
        confidence = "negative"
    else:
        # No codes at all. Absence of a code is not a negative finding.
        confidence = "unknown"

    classes = sorted(
        {cls for c in gg_direct for cls in CODE_TO_CLASSES.get(c, ())}
    ) or ["UNKNOWN"]

    # The crosswalk is applied only to report what SAM codes *would* map to.
    # It never manufactures a Grants.gov code onto the record.
    crosswalked = sorted(
        {
            SAM_TO_GRANTS_GOV_CROSSWALK[c]
            for c in sam_direct
            if c in SAM_TO_GRANTS_GOV_CROSSWALK
        }
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_key": opportunity_key,
            "confidence": confidence,
            "in_recall_set": bool(gg_direct or gg_reading or sam_direct or sam_reading),
            "grants_gov_codes_present": gg,
            "grants_gov_direct_codes": sorted(gg_direct),
            "grants_gov_requires_reading_codes": sorted(gg_reading),
            "sam_codes_present": sam,
            "sam_direct_codes": sorted(sam_direct),
            "sam_requires_reading_codes": sorted(sam_reading),
            "sam_crosswalked_to_grants_gov": crosswalked,
            "crosswalk_is_inferred": True,
            # The free-text lane.
            "free_text_screening_required": bool(gg_reading or sam_reading),
            "free_text_present": has_text,
            "free_text_screened": False,
            "free_text_read_by_this_service": False,
            "nofo_text_is_authoritative": bool(sam_reading),
            # Classes, and the hard separations.
            "implied_eligibility_classes": classes,
            "is_boolean_filter": False,
            "customer_eligibility_determined": False,
            "fabricated": False,
        }
    )


def summarise_classification(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_band = {band: 0 for band in sorted(CONFIDENCE_BANDS)}
    for r in results:
        band = r.get("confidence")
        if band in by_band:
            by_band[band] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "classified_count": len(results),
            "by_confidence": by_band,
            "recall_set_count": sum(1 for r in results if r.get("in_recall_set")),
            "free_text_screening_backlog": sum(
                1 for r in results if r.get("free_text_screening_required")
            ),
            "free_text_screened_count": 0,
            "customers_matched": 0,
            "fabricated": False,
        }
    )


def classification_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    band = result.get("confidence")
    if band not in CONFIDENCE_BANDS:
        fails.append("confidence_out_of_vocabulary")

    # The whole point of the gate: grading, not filtering.
    if result.get("is_boolean_filter") is not False:
        fails.append("classification_collapsed_to_boolean")
    if result.get("customer_eligibility_determined") is not False:
        fails.append("opportunity_classification_claimed_customer_eligibility")

    # 99 and 25 must never be silently dropped or silently promoted.
    gg = result.get("grants_gov_codes_present") or []
    reading = set(result.get("grants_gov_requires_reading_codes") or [])
    for code in REQUIRES_READING_CODES:
        if code in gg and code not in reading:
            fails.append(f"recall_code_dropped:{code}")
    if reading and band == "negative":
        fails.append("requires_reading_collapsed_to_negative")
    direct = result.get("grants_gov_direct_codes") or []
    sam_direct = result.get("sam_direct_codes") or []
    if reading and not direct and not sam_direct and band == "direct":
        fails.append("requires_reading_promoted_to_direct")

    # An empty code list is unknown, never negative.
    if not gg and not (result.get("sam_codes_present") or []) and band != "unknown":
        fails.append("absent_codes_treated_as_a_finding")

    # This service must not claim to have read anything.
    if result.get("free_text_screened") is not False:
        fails.append("free_text_claimed_screened")
    if result.get("free_text_read_by_this_service") is not False:
        fails.append("free_text_claimed_read")
    if result.get("free_text_screening_required") and band != "requires_reading":
        if not direct and not sam_direct:
            fails.append("screening_required_without_requires_reading_band")

    # ET12010 means the listing under-determines; the NOFO decides.
    if "ET12010" in (result.get("sam_codes_present") or []):
        if result.get("nofo_text_is_authoritative") is not True:
            fails.append("et12010_did_not_defer_to_nofo")

    if result.get("crosswalk_is_inferred") is not True:
        fails.append("sam_crosswalk_claimed_as_documented")

    for cls in result.get("implied_eligibility_classes") or []:
        if cls not in ELIGIBILITY_CLASSES:
            fails.append(f"eligibility_class_out_of_vocabulary:{cls}")

    return fails
