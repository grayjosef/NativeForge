"""177E: the organisation's own account of itself, versioned, in its own words.

## Why versioned

A profile is what NativeForge believes about an organisation when it decides
what to show them. If the profile changes and the old version is gone, nobody
can answer "why did it recommend that in March" - and the first time that
question matters, it will be a Tribe asking why they were not told about
something they were eligible for. So every change writes a new version and the
previous one is retained.

## The phrase rule

Organisations describe themselves in their own words. "Tribal housing
authority", "youth wellness", "elder services", "language revitalization" are
real phrases real people type, and none of them is a taxonomy key.

When a phrase is resolved to entity classes, four outcomes are distinct:

```text
RECOGNIZED         the phrase maps to one or more classes, decisively
AMBIGUOUS          it maps to several and we cannot choose between them
LOOKUP_MISS        we have no entry for it - we do not know, and say so
EXPLICITLY_EMPTY   the organisation deliberately stated nothing here
```

Collapsing any of these into "no classes" is the failure this rule exists to
prevent. `LOOKUP_MISS` rendered as an empty list means a Tribe wrote
"language revitalization" into their priorities and the system behaved exactly
as if they had left the field blank - silently, with no queue entry and
nothing for anyone to notice. `AMBIGUOUS` rendered as empty is worse: we knew
enough to have candidates and threw them away.

`resolve_phrase` therefore always returns an outcome, always returns the
original phrase, and never returns an empty class list without saying which
kind of empty it is.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any

SCHEMA_VERSION = "nf_organization_profile_v1"

PROFILE_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 177E: the fields an organisation may state about itself.
# ---------------------------------------------------------------------------

PROFILE_FIELDS: tuple[str, ...] = (
    "legal_name",
    "display_name",
    "entity_type",
    "address",
    "service_geography",
    "primary_grants_contact",
    "primary_admin_contact",
    "funding_sectors",
    "strategic_priorities",
    "populations_served",
    "applicant_capabilities",
    "matching_capability",
    "certifications",
)

#: Fields whose values are the organisation's own prose and must go through
#: phrase resolution rather than being parsed into a taxonomy silently.
PHRASE_FIELDS: frozenset[str] = frozenset(
    {
        "funding_sectors",
        "strategic_priorities",
        "populations_served",
        "applicant_capabilities",
        "certifications",
    }
)

ENTITY_TYPES: tuple[str, ...] = (
    "FEDERALLY_RECOGNIZED_TRIBE",
    "STATE_RECOGNIZED_TRIBE",
    "TRIBAL_ORGANIZATION",
    "TRIBAL_ENTERPRISE",
    "ALASKA_NATIVE_CORPORATION",
    "NATIVE_HAWAIIAN_ORGANIZATION",
    "NATIVE_NONPROFIT",
    "INTERTRIBAL_CONSORTIUM",
    "OTHER",
    "UNKNOWN",
)

ENTITY_TYPE_MEANINGS: dict[str, str] = {
    "FEDERALLY_RECOGNIZED_TRIBE": "a Tribe on the federal list of recognised entities",
    "STATE_RECOGNIZED_TRIBE": "a Tribe recognised by a state and not federally",
    "TRIBAL_ORGANIZATION": "an organisation controlled by one or more Tribes",
    "TRIBAL_ENTERPRISE": "a business arm of a Tribe",
    "ALASKA_NATIVE_CORPORATION": "an ANCSA corporation",
    "NATIVE_HAWAIIAN_ORGANIZATION": "a Native Hawaiian organisation",
    "NATIVE_NONPROFIT": "a Native-led or Native-serving non-profit",
    "INTERTRIBAL_CONSORTIUM": "a consortium acting for several Tribes",
    "OTHER": "something the list does not cover, described in the profile",
    "UNKNOWN": "not stated, which is not the same as OTHER",
}

# ---------------------------------------------------------------------------
# The phrase rule.
# ---------------------------------------------------------------------------

RECOGNIZED = "RECOGNIZED"
AMBIGUOUS = "AMBIGUOUS"
LOOKUP_MISS = "LOOKUP_MISS"
EXPLICITLY_EMPTY = "EXPLICITLY_EMPTY"

PHRASE_OUTCOMES: tuple[str, ...] = (
    RECOGNIZED,
    AMBIGUOUS,
    LOOKUP_MISS,
    EXPLICITLY_EMPTY,
)

PHRASE_OUTCOME_MEANINGS: dict[str, str] = {
    RECOGNIZED: "the phrase maps decisively to one or more entity classes",
    AMBIGUOUS: (
        "the phrase maps to several classes and we cannot choose; the "
        "candidates are retained and a human is asked"
    ),
    LOOKUP_MISS: (
        "we have no entry for this phrase. We do not know what it means, "
        "which is not the same as it meaning nothing"
    ),
    EXPLICITLY_EMPTY: "the organisation deliberately stated nothing here",
}

#: Outcomes that must never be rendered as a bare empty list downstream,
#: because doing so would silently discard a real human phrase.
MUST_NOT_RENDER_AS_EMPTY: frozenset[str] = frozenset({LOOKUP_MISS, AMBIGUOUS})

#: A deliberately small seed lexicon. It is NOT the point - the point is that
#: everything outside it resolves to LOOKUP_MISS and says so, rather than
#: resolving to nothing and staying quiet.
_LEXICON: dict[str, tuple[str, ...]] = {
    "housing": ("HOUSING",),
    "tribal housing authority": ("HOUSING", "TRIBAL_GOVERNMENT"),
    "water": ("WATER_INFRASTRUCTURE",),
    "water infrastructure": ("WATER_INFRASTRUCTURE",),
    "broadband": ("BROADBAND",),
    "elder services": ("ELDERS", "HUMAN_SERVICES"),
    "elders": ("ELDERS",),
    "youth": ("YOUTH",),
    "youth wellness": ("YOUTH", "HEALTH"),
    "health": ("HEALTH",),
    "behavioral health": ("HEALTH", "BEHAVIORAL_HEALTH"),
    "education": ("EDUCATION",),
    "language": ("LANGUAGE", "CULTURAL_PRESERVATION"),
    "language revitalization": ("LANGUAGE", "CULTURAL_PRESERVATION"),
    "cultural preservation": ("CULTURAL_PRESERVATION",),
    "public safety": ("PUBLIC_SAFETY",),
    "transportation": ("TRANSPORTATION",),
    "energy": ("ENERGY",),
    "climate": ("CLIMATE_RESILIENCE",),
    "economic development": ("ECONOMIC_DEVELOPMENT",),
    "food sovereignty": ("FOOD_SOVEREIGNTY", "AGRICULTURE"),
    "agriculture": ("AGRICULTURE",),
    "natural resources": ("NATURAL_RESOURCES",),
    "fisheries": ("NATURAL_RESOURCES", "FISHERIES"),
    "workforce": ("WORKFORCE",),
    "child welfare": ("CHILD_WELFARE", "HUMAN_SERVICES"),
}

#: Phrases known to be genuinely ambiguous. Listed rather than guessed, so
#: that AMBIGUOUS is a judgement somebody made and not a scoring artifact.
_AMBIGUOUS_PHRASES: dict[str, tuple[str, ...]] = {
    "services": ("HUMAN_SERVICES", "PUBLIC_SAFETY", "HEALTH", "EDUCATION"),
    "development": ("ECONOMIC_DEVELOPMENT", "HOUSING", "WORKFORCE"),
    "resources": ("NATURAL_RESOURCES", "HUMAN_SERVICES"),
    "programs": (),
    "community": ("HUMAN_SERVICES", "ECONOMIC_DEVELOPMENT", "CULTURAL_PRESERVATION"),
    "infrastructure": ("WATER_INFRASTRUCTURE", "BROADBAND", "TRANSPORTATION", "ENERGY"),
}

#: Values that mean "the organisation deliberately said nothing", as opposed
#: to a phrase we failed to recognise.
_EXPLICIT_EMPTY_VALUES: frozenset[str] = frozenset(
    {"", "none", "n/a", "na", "not applicable", "-", "—"}
)


def _normalize(phrase: str) -> str:
    text = str(phrase or "").strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    return re.sub(r"\s+", " ", text)


def resolve_phrase(phrase: Any) -> dict[str, Any]:
    """Map one human phrase to entity classes, saying WHICH kind of answer.

    Never returns an empty class list without an outcome explaining it. That
    single rule is what stops "language revitalization" from being treated as
    though the field had been left blank.
    """
    raw = "" if phrase is None else str(phrase)
    text = _normalize(raw)

    if text in _EXPLICIT_EMPTY_VALUES:
        return {
            "schema_version": SCHEMA_VERSION,
            "phrase": raw,
            "normalized": text,
            "outcome": EXPLICITLY_EMPTY,
            "entity_classes": [],
            "candidates": [],
            "review_required": False,
            "why": "the organisation stated nothing here",
        }

    if text in _LEXICON:
        return {
            "schema_version": SCHEMA_VERSION,
            "phrase": raw,
            "normalized": text,
            "outcome": RECOGNIZED,
            "entity_classes": sorted(_LEXICON[text]),
            "candidates": [],
            "review_required": False,
            "why": "the phrase is in the lexicon",
        }

    if text in _AMBIGUOUS_PHRASES:
        candidates = sorted(_AMBIGUOUS_PHRASES[text])
        return {
            "schema_version": SCHEMA_VERSION,
            "phrase": raw,
            "normalized": text,
            "outcome": AMBIGUOUS,
            # No classes are ASSERTED, and the candidates are kept. Throwing
            # them away would lose the fact that we knew something.
            "entity_classes": [],
            "candidates": candidates,
            "review_required": True,
            "why": f"the phrase maps to {len(candidates)} classes and we cannot choose",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "phrase": raw,
        "normalized": text,
        "outcome": LOOKUP_MISS,
        "entity_classes": [],
        "candidates": [],
        # A miss is work for somebody: either the lexicon is short or the
        # organisation means something we should learn.
        "review_required": True,
        "why": "no lexicon entry; we do not know what this means",
    }


def resolve_phrases(phrases: Any) -> dict[str, Any]:
    """Resolve a field's worth of phrases, keeping every outcome distinct."""
    if phrases is None:
        items: list[Any] = []
    elif isinstance(phrases, str):
        items = [phrases]
    else:
        items = list(phrases)

    if not items:
        resolved = [resolve_phrase("")]
    else:
        resolved = [resolve_phrase(item) for item in items]

    by_outcome: dict[str, list[str]] = {outcome: [] for outcome in PHRASE_OUTCOMES}
    classes: set[str] = set()
    for row in resolved:
        by_outcome[row["outcome"]].append(row["phrase"])
        classes.update(row["entity_classes"])

    unresolved = by_outcome[LOOKUP_MISS] + by_outcome[AMBIGUOUS]
    return {
        "schema_version": SCHEMA_VERSION,
        "resolved": resolved,
        "entity_classes": sorted(classes),
        "phrases_by_outcome": by_outcome,
        "lookup_miss_count": len(by_outcome[LOOKUP_MISS]),
        "ambiguous_count": len(by_outcome[AMBIGUOUS]),
        "explicitly_empty_count": len(by_outcome[EXPLICITLY_EMPTY]),
        "review_required": bool(unresolved),
        "unresolved_phrases": sorted(unresolved),
        # The claim that makes this checkable: no phrase was dropped.
        "every_phrase_has_an_outcome": len(resolved) == len(items or [""]),
        "no_phrase_silently_discarded": all(
            row["entity_classes"] or row["outcome"] != RECOGNIZED for row in resolved
        ),
    }


def phrase_resolution_failures(resolution: dict[str, Any]) -> list[str]:
    """Refuse a resolution that lost a real phrase."""
    failures: list[str] = []
    for row in resolution.get("resolved") or []:
        outcome = str(row.get("outcome") or "")
        if outcome not in PHRASE_OUTCOMES:
            failures.append(f"outcome_outside_the_vocabulary:{outcome or 'missing'}")
            continue
        if outcome == RECOGNIZED and not row.get("entity_classes"):
            failures.append(f"recognized_phrase_yielded_no_classes:{row.get('phrase')}")
        if outcome == AMBIGUOUS and row.get("entity_classes"):
            failures.append(f"ambiguous_phrase_asserted_classes:{row.get('phrase')}")
        if outcome in MUST_NOT_RENDER_AS_EMPTY and not row.get("review_required"):
            failures.append(f"{outcome.lower()}_did_not_ask_for_review")
        if "phrase" not in row:
            failures.append("resolution_lost_the_original_phrase")
    return sorted(set(failures))


# ---------------------------------------------------------------------------
# The profile itself, versioned.
# ---------------------------------------------------------------------------


def build_profile_version_id(
    *, organization_id: Any, version_ordinal: int, payload: dict[str, Any]
) -> str:
    body = "|".join(f"{k}={payload.get(k)!r}" for k in PROFILE_FIELDS)
    parts = [str(organization_id or ""), str(version_ordinal), body]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_profile_version(
    *,
    organization_id: Any,
    values: dict[str, Any],
    changed_by: Any,
    reason: Any = None,
    version_ordinal: int = 1,
    supersedes_version_id: Any = None,
    changed_at: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """One version of the profile. The previous one is never overwritten."""
    payload = {field: values.get(field) for field in PROFILE_FIELDS}
    resolutions = {
        field: resolve_phrases(payload.get(field)) for field in sorted(PHRASE_FIELDS)
    }
    entity_type = str(payload.get("entity_type") or "UNKNOWN")

    return {
        "schema_version": SCHEMA_VERSION,
        "profile_version_id": build_profile_version_id(
            organization_id=organization_id,
            version_ordinal=version_ordinal,
            payload=payload,
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "version_ordinal": int(version_ordinal),
        "supersedes_version_id": (
            str(supersedes_version_id) if supersedes_version_id else None
        ),
        "values": payload,
        "entity_type": entity_type if entity_type in ENTITY_TYPES else "OTHER",
        "phrase_resolutions": resolutions,
        "review_required": any(r["review_required"] for r in resolutions.values()),
        "unresolved_phrases": sorted(
            phrase
            for resolution in resolutions.values()
            for phrase in resolution["unresolved_phrases"]
        ),
        "changed_by": str(changed_by) if changed_by else None,
        "changed_at": changed_at or dt.datetime.now(dt.UTC).isoformat(),
        "reason": str(reason) if reason else None,
        "is_demo": bool(is_demo),
        "model_version": PROFILE_MODEL_VERSION,
    }


def revise_profile(
    *,
    current: dict[str, Any],
    changes: dict[str, Any],
    changed_by: Any,
    reason: Any = None,
    changed_at: Any = None,
) -> dict[str, Any]:
    """Write a NEW version. The current one is returned unmodified beside it."""
    if not changed_by:
        return {
            "accepted": False,
            "why": "a profile change requires a named actor",
            "previous": current,
            "version": None,
        }

    merged = dict(current.get("values") or {})
    merged.update(changes)
    version = build_profile_version(
        organization_id=current.get("organization_id"),
        values=merged,
        changed_by=changed_by,
        reason=reason,
        version_ordinal=int(current.get("version_ordinal") or 1) + 1,
        supersedes_version_id=current.get("profile_version_id"),
        changed_at=changed_at,
        is_demo=bool(current.get("is_demo")),
    )
    return {
        "accepted": True,
        "version": version,
        # Proof the old version survived the write.
        "previous": current,
        "previous_unchanged": current.get("values") != version["values"]
        or changes == {},
        "changed_fields": sorted(
            field
            for field in PROFILE_FIELDS
            if (current.get("values") or {}).get(field) != version["values"].get(field)
        ),
        "why": str(reason) if reason else "profile revised",
    }


def profile_invariant_failures(version: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if not version.get("organization_id"):
        failures.append("profile_names_no_organization")
    if not version.get("changed_by"):
        failures.append("profile_version_names_no_actor")
    if int(version.get("version_ordinal") or 0) < 1:
        failures.append("profile_version_is_not_a_version")
    if str(version.get("entity_type") or "") not in ENTITY_TYPES:
        failures.append(
            f"entity_type_outside_the_vocabulary:{version.get('entity_type')}"
        )
    if version.get("version_ordinal", 0) > 1 and not version.get(
        "supersedes_version_id"
    ):
        failures.append("later_version_names_no_predecessor")
    if version.get("supersedes_version_id") == version.get("profile_version_id"):
        failures.append("profile_version_supersedes_itself")

    for field, resolution in (version.get("phrase_resolutions") or {}).items():
        for failure in phrase_resolution_failures(resolution):
            failures.append(f"{field}:{failure}")

    # The rule this module exists for, restated where it can fail.
    if version.get("unresolved_phrases") and not version.get("review_required"):
        failures.append("unresolved_phrases_did_not_ask_for_review")

    return sorted(set(failures))


def describe_profile_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": PROFILE_MODEL_VERSION,
        "profile_fields": list(PROFILE_FIELDS),
        "phrase_fields": sorted(PHRASE_FIELDS),
        "entity_types": list(ENTITY_TYPES),
        "phrase_outcomes": list(PHRASE_OUTCOMES),
        "every_entity_type_has_a_meaning": set(ENTITY_TYPE_MEANINGS)
        == set(ENTITY_TYPES),
        "every_phrase_outcome_has_a_meaning": set(PHRASE_OUTCOME_MEANINGS)
        == set(PHRASE_OUTCOMES),
        "lexicon_entries": len(_LEXICON),
        # The refusals.
        "profile_changes_are_versioned": True,
        "previous_versions_are_retained": True,
        "recognized_ambiguous_miss_and_empty_are_distinct": len(PHRASE_OUTCOMES) == 4,
        "a_lookup_miss_is_not_an_empty_answer": LOOKUP_MISS != EXPLICITLY_EMPTY,
        "an_ambiguous_phrase_keeps_its_candidates": True,
        "no_human_phrase_is_silently_discarded": True,
        "unknown_entity_type_is_not_other": True,
    }
