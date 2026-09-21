"""Normalizing the strings identity rests on (Gate 169C).

Identity must not turn on whether a publisher wrote "U.S. Dept. of Justice" or
"United States Department of Justice". It must also not turn on whether they
wrote FY26 or FY27, and the difference between those two statements is the
whole difficulty of this module.

## Normalization strength is part of the answer

Every function here returns a normalized value AND says how much that value
can be trusted to establish identity:

```text
AUTHORITATIVE   a published identifier, normalized only in form
                (opportunity number: case, whitespace, punctuation)
CORROBORATING   a code from a declared namespace
                (agency code - meaningful, but namespaces do not align)
WEAK            a human-written name or title
                (agency name, program name, title band)
```

`WEAK` values may generate CANDIDATES. They may never settle a merge. The
identity service is explicit about why: agency identity spans three
non-matching namespaces - Grants.gov `agencyCode`, Federal Register slugs, SAM
FPDS codes - and it **refuses to match agencies by name string**. Nothing here
overrides that; this module makes the weakness explicit rather than papering
over it with a similarity score.

## What normalization must never erase

```text
the fiscal year            FY26 and FY27 are different opportunities
the opportunity number     a different number is a different solicitation
the doc type               a forecast is not the posting it becomes
```

Those are carried OUT of normalization as separate fields precisely so a
title-similarity comparison cannot reach across them. Gate 169F's hard
negatives are all built on this: annual recurrences have near-identical
language, and a normalizer that smoothed the year away would merge a Tribe's
FY27 opportunity into last year's closed one.

## The original is never replaced

Normalized values are for KEYS and COMPARISON. The source's own strings stay
in field provenance exactly as published, because a normalized agency name is
not evidence of anything a publisher said.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

SCHEMA_VERSION = "nf_opportunity_entity_normalization_v1"

AUTHORITATIVE = "AUTHORITATIVE"
CORROBORATING = "CORROBORATING"
WEAK = "WEAK"

NORMALIZATION_STRENGTHS: tuple[str, ...] = (AUTHORITATIVE, CORROBORATING, WEAK)

#: Tokens that carry no identity signal in a funder or program name. Kept
#: deliberately short: every word removed is a distinction that can no longer
#: be made, so this list holds only legal-form and honorific noise.
_STOP_TOKENS: frozenset[str] = frozenset(
    {
        "the",
        "of",
        "for",
        "and",
        "office",
        "bureau",
        "department",
        "dept",
        "administration",
        "agency",
        "division",
        "program",
        "programs",
        "us",
        "usa",
        "united",
        "states",
        "u",
        "s",
        "inc",
        "llc",
        "foundation",
        "trust",
    }
)

#: Evidence-backed abbreviation expansions. NOT a general acronym guesser: each
#: entry is a form that appears in published federal source material. An
#: expansion nobody can point at is a fabricated identity claim.
_ALIASES: dict[str, str] = {
    "doj": "justice",
    "usdoj": "justice",
    "hhs": "health human services",
    "hud": "housing urban development",
    "usda": "agriculture",
    "doi": "interior",
    "bia": "indian affairs",
    "bja": "justice assistance",
    "ojp": "justice programs",
    "epa": "environmental protection",
    "doe": "energy",
    "dot": "transportation",
    "nsf": "science",
    "ihs": "indian health",
}

#: Query parameters that identify a visitor or a campaign, not a document.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "referrer",
        "session",
        "sessionid",
        "sid",
    }
)

_FISCAL_YEAR = re.compile(
    r"\b(?:fy|fiscal\s+year)\s*[-–]?\s*((?:19|20)?\d{2})\b", re.IGNORECASE
)
_BARE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _fold(text: Any) -> str:
    """Unicode-fold to comparable ASCII-ish lowercase.

    NFKD then drop combining marks, so "Peña" and "Pena" compare equal - two
    spellings of one funder, not two funders. Compatibility folding also
    collapses full-width and ligature forms that copy-paste introduces.
    """
    raw = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return stripped.casefold().strip()


def normalize_opportunity_number(raw: Any) -> dict[str, Any]:
    """A published identifier, normalized in FORM only.

    Case, whitespace and punctuation are removed because publishers vary them;
    digits and letters are untouched because they are the identifier. This
    deliberately matches `opportunity_identity_versioning_service`, which owns
    the L1 rule - the two must not drift.
    """
    folded = _fold(raw)
    value = _NON_ALNUM.sub("", folded).upper()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "opportunity_number",
            "original": str(raw) if raw is not None else None,
            "normalized": value or None,
            "strength": AUTHORITATIVE,
            "why": "a published identifier; only its form was normalized",
        }
    )


def normalize_funder(
    *, agency_code: Any = None, agency_name: Any = None
) -> dict[str, Any]:
    """A funder, as strongly as the evidence allows.

    A CODE is corroborating: it comes from a declared namespace, but the
    namespaces do not align across sources, so a code match supports identity
    without settling it. A NAME alone is weak, whatever it looks like.
    """
    code = _NON_ALNUM.sub("-", _fold(agency_code)).strip("-").upper() or None

    tokens = [t for t in _NON_ALNUM.split(_fold(agency_name)) if t]
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_ALIASES.get(token, token).split())
    meaningful = sorted({t for t in expanded if t and t not in _STOP_TOKENS})
    name_key = " ".join(meaningful) or None

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "funder",
            "original_code": str(agency_code) if agency_code is not None else None,
            "original_name": str(agency_name) if agency_name is not None else None,
            "normalized_code": code,
            "normalized_name_key": name_key,
            # The strongest thing available, named rather than implied.
            "strength": CORROBORATING if code else (WEAK if name_key else WEAK),
            "why": (
                "an agency code from a declared namespace; namespaces do not "
                "align across sources, so it corroborates but does not settle"
                if code
                else "only a human-written name was available"
            ),
            "name_alone_can_settle_identity": False,
            "crosswalk_required": True,
        }
    )


def normalize_program(raw: Any) -> dict[str, Any]:
    """A program or program-family name. Always weak."""
    tokens = [t for t in _NON_ALNUM.split(_fold(raw)) if t]
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_ALIASES.get(token, token).split())
    meaningful = sorted({t for t in expanded if t and t not in _STOP_TOKENS})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "program",
            "original": str(raw) if raw is not None else None,
            "normalized": " ".join(meaningful) or None,
            "strength": WEAK,
            "why": "a human-written program name",
        }
    )


def extract_period(*values: Any) -> dict[str, Any]:
    """The fiscal year, pulled OUT of the text so comparison cannot lose it.

    An explicit FY marker wins over a bare year: a title saying "FY26" in a
    document dated 2025 is about FY26. Two-digit years are expanded on the
    2000s, which is correct for this corpus and stated rather than assumed.
    """
    for value in values:
        text = str(value or "")
        match = _FISCAL_YEAR.search(text)
        if match:
            digits = match.group(1)
            year = int(digits) if len(digits) == 4 else 2000 + int(digits)
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "field": "period",
                    "fiscal_year": year,
                    "basis": "explicit_fiscal_year_marker",
                    "strength": CORROBORATING,
                }
            )

    for value in values:
        match = _BARE_YEAR.search(str(value or ""))
        if match:
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "field": "period",
                    "fiscal_year": int(match.group(1)),
                    "basis": "bare_four_digit_year",
                    "strength": WEAK,
                }
            )

    # Absent, not guessed. A missing year must not default to this one.
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "period",
            "fiscal_year": None,
            "basis": "no_year_found",
            "strength": WEAK,
        }
    )


def normalize_title(raw: Any) -> dict[str, Any]:
    """A title, normalized for comparison, with the year REMOVED.

    The year is stripped from the comparison key on purpose: it is carried
    separately by `extract_period`, so a recurrence comparison can see that
    two titles are the same text about different years. Leaving the year in
    would make FY26 and FY27 look different by one token - close enough for a
    similarity threshold to merge them, which is exactly the failure Gate 169F
    guards against.
    """
    text = _fold(raw)
    without_year = _FISCAL_YEAR.sub(" ", text)
    without_year = _BARE_YEAR.sub(" ", without_year)
    tokens = [t for t in _NON_ALNUM.split(without_year) if t]
    meaningful = [t for t in tokens if t not in _STOP_TOKENS]
    key = " ".join(meaningful)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "title",
            "original": str(raw) if raw is not None else None,
            "normalized": key or None,
            "token_count": len(meaningful),
            "year_removed_and_carried_separately": True,
            "strength": WEAK,
            "why": "free text a publisher may edit at will",
        }
    )


def title_band(raw: Any, *, tokens: int = 6) -> str | None:
    """A blocking band for a title: a digest of its first N sorted tokens.

    A BAND, not a similarity score. Its only job is to put plausibly-related
    titles in the same bucket so candidate generation stays bounded; whether
    they are actually related is decided afterwards, with the year and the
    number in hand. Sorted so word order does not split a band.
    """
    normalized = normalize_title(raw)["normalized"]
    if not normalized:
        return None
    parts = sorted(normalized.split())[:tokens]
    if not parts:
        return None
    return hashlib.sha256(" ".join(parts).encode("utf-8")).hexdigest()[:24]


def normalize_source_url(raw: Any) -> dict[str, Any]:
    """Strip visitor and campaign noise; keep everything that selects a document."""
    text = str(raw or "").strip()
    if not text:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "field": "source_url",
                "original": None,
                "normalized": None,
                "removed_parameters": [],
                "strength": WEAK,
            }
        )

    base, _, query = text.partition("?")
    kept: list[str] = []
    removed: list[str] = []
    for pair in query.split("&"):
        if not pair:
            continue
        name = pair.split("=", 1)[0].casefold()
        if name in _TRACKING_PARAMS:
            removed.append(name)
        else:
            kept.append(pair)

    normalized = base.rstrip("/")
    if kept:
        normalized = f"{normalized}?{'&'.join(sorted(kept))}"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field": "source_url",
            "original": text,
            "normalized": normalized,
            "removed_parameters": sorted(removed),
            "strength": WEAK,
            "why": "a URL locates a document; it does not identify one",
        }
    )


def normalization_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a normalization that claims more strength than it has."""
    fails: list[str] = []

    strength = result.get("strength")
    if strength not in NORMALIZATION_STRENGTHS:
        fails.append(f"strength_outside_the_vocabulary:{strength}")

    field = result.get("field")

    # A name-derived value may never call itself authoritative.
    if field in ("title", "program") and strength != WEAK:
        fails.append(f"{field}_claimed_more_than_weak:{strength}")

    if field == "funder":
        if result.get("name_alone_can_settle_identity"):
            fails.append("funder_name_claimed_to_settle_identity")
        if not result.get("normalized_code") and strength == CORROBORATING:
            fails.append("funder_without_a_code_claimed_corroborating")

    if field == "opportunity_number" and result.get("normalized"):
        if strength != AUTHORITATIVE:
            fails.append("published_number_not_marked_authoritative")

    # The year must be carried out of the title, never left in it.
    if field == "title" and not result.get("year_removed_and_carried_separately"):
        fails.append("title_normalization_kept_the_year")

    return sorted(set(fails))
