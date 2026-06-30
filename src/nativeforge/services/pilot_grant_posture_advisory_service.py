"""Advisory grant_posture ranking hints — never hard-filter matches."""

from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "nf_pilot_grant_posture_advisory_v1"

VALID_POSTURES: frozenset[str] = frozenset(
    {"compact_heavy", "mixed", "discretionary_active", "UNKNOWN"}
)

_COMPACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b638\b|self[- ]governance|self[- ]determination|compact", re.I),
    re.compile(r"\bPL[- ]?93[- ]?638\b", re.I),
    re.compile(r"\bIHS compact\b", re.I),
    re.compile(r"\bNAHASDA\b|\bIHBG\b", re.I),
)


def classify_grant_funding_style(grant: dict[str, Any]) -> str:
    """Conservative discretionary vs compact-pathway label for advisory notes."""
    hay = " ".join(
        str(grant.get(k) or "")
        for k in (
            "opportunity_title",
            "eligibility_text",
            "synopsis",
            "agency",
            "program_title",
            "sc_rule_category_id",
        )
    )
    if any(p.search(hay) for p in _COMPACT_PATTERNS):
        return "compact_pathway"
    if grant.get("sc_pilot_rule_reference"):
        cat = str(grant.get("sc_rule_category_id") or "")
        if cat in {"BIA_638", "IHS_COMPACT", "HUD_NAHASDA"}:
            return "compact_pathway"
    return "discretionary"


def build_grant_posture_advisory(
    *,
    grant_posture: str | None,
    grant: dict[str, Any],
) -> dict[str, Any]:
    posture = str(grant_posture or "UNKNOWN")
    if posture not in VALID_POSTURES:
        posture = "UNKNOWN"
    funding_style = classify_grant_funding_style(grant)

    hint = "neutral"
    note: str | None = None
    if posture == "compact_heavy" and funding_style == "discretionary":
        hint = "lower"
        note = (
            "grant_posture=compact_heavy — discretionary grant relevance noted lower "
            "(advisory only; not excluded from match set)"
        )
    elif posture == "discretionary_active" and funding_style == "discretionary":
        hint = "higher"
        note = (
            "grant_posture=discretionary_active — discretionary grant "
            "relevance noted higher (advisory only)"
        )
    elif posture == "mixed" and funding_style == "discretionary":
        hint = "neutral"
        note = "grant_posture=mixed — neutral discretionary relevance advisory"

    return {
        "schema_version": SCHEMA_VERSION,
        "grant_posture": posture,
        "grant_funding_style": funding_style,
        "advisory_ranking_hint": hint,
        "advisory_note": note,
        "advisory_only": True,
        "hard_filter": False,
    }
