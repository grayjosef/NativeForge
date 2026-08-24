"""Notice amendment / version detection (Gate 81D).

Reads a notice and decides what *kind* of notice it is - original, amended,
corrected, cancelled, superseded - and emits the evidence
:mod:`opportunity_freshness_service` needs to decide whether the opportunity is
still current.

These are two different axes and this module is careful not to merge them:

  * **Notice status** answers "what happened to this document".
  * **Freshness** answers "is this grant still open".

They overlap at ``amended`` and ``superseded`` and diverge everywhere else. A
cancelled notice is not "expired" - nothing expired, the funder pulled it - but
freshness has no word for that, so the projection is recorded as lossy rather
than pretending the distinction never existed. This is the same
canonical-plus-projection shape Gate 79B used for funding lanes.

Rules enforced rather than documented:

  * ``amended`` / ``extended`` require an evidence quote. No evidence means
    ``unknown``, never ``amended`` - a notice we merely suspect was amended is
    a notice we have not read.
  * ``cancelled`` / ``withdrawn`` never disappear. They stay visible, marked,
    and non-current. A grant that vanishes looks like a grant we never found.
  * ``superseded`` requires same-lineage plus evidence, delegated to
    :func:`opportunity_freshness_service.evaluate_supersession` rather than
    re-decided here.

Nothing here fetches.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.opportunity_freshness_service import (
    CURRENT_STATES,
    EXTENSION_EVIDENCE_KINDS,
    FRESHNESS_STATES,
    SUPERSESSION_EVIDENCE_KINDS,
    evaluate_supersession,
)

SCHEMA_VERSION = "nf_nofo_amendment_detector_v1"
DETECTOR_VERSION = "gate81_v1"

NOTICE_STATUSES = frozenset(
    {
        "original",
        "amended",
        "corrected",
        "supplemented",
        "extended",
        "cancelled",
        "withdrawn",
        "superseded",
        "unknown",
    }
)

# A notice that still describes a live opportunity. Derived by difference so a
# status added later is non-current until someone deliberately includes it.
CURRENT_NOTICE_STATUSES = frozenset(
    {"original", "amended", "corrected", "supplemented", "extended"}
)
NON_CURRENT_NOTICE_STATUSES = NOTICE_STATUSES - CURRENT_NOTICE_STATUSES

# Every status keeps the notice visible. Visibility and currency are different
# properties, and a cancelled notice is often the most useful thing we can show.
VISIBLE_NOTICE_STATUSES = NOTICE_STATUSES

# Statuses that may not be asserted without a cited quote.
EVIDENCE_REQUIRED_STATUSES = frozenset(
    {"amended", "corrected", "supplemented", "extended", "cancelled", "withdrawn"}
)

# Projection onto opportunity_freshness_service.FRESHNESS_STATES. ``None`` means
# "no opinion" - the freshness service decides from dates, which is correct for
# an original notice.
FRESHNESS_PROJECTION: dict[str, str | None] = {
    "original": None,
    "amended": "amended",
    "corrected": "amended",
    "supplemented": "amended",
    "extended": "amended",
    # Lossy: freshness has no "cancelled". Both land on a non-current state.
    "cancelled": "expired",
    "withdrawn": "expired",
    "superseded": "superseded",
    "unknown": "unknown",
}

# Statuses whose projection loses information worth flagging.
LOSSY_PROJECTIONS = frozenset({"cancelled", "withdrawn", "corrected", "supplemented"})

# Cue phrases per status. Ordered by consequence in _STATUS_PRECEDENCE below.
STATUS_CUES: dict[str, tuple[str, ...]] = {
    "cancelled": (
        "this notice is cancelled",
        "this notice is canceled",
        "notice of cancellation",
        "the funding opportunity is cancelled",
        "the funding opportunity is canceled",
        "cancelled",
        "canceled",
    ),
    "withdrawn": (
        "this notice is withdrawn",
        "notice of withdrawal",
        "has been withdrawn",
        "is hereby rescinded",
        "withdrawn",
        "rescinded",
    ),
    "superseded": (
        "is superseded by",
        "supersedes",
        "superseded",
        "has been replaced by",
        "replaced by notice",
    ),
    "extended": (
        "deadline has been extended",
        "deadline is extended",
        "application deadline extended",
        "closing date has been extended",
        "new closing date",
        "new application deadline",
        "extended to",
        "deadline extension",
    ),
    "corrected": (
        "notice of correction",
        "this notice corrects",
        "corrected notice",
        "correction to",
        "corrigendum",
    ),
    "supplemented": (
        "supplemental notice",
        "notice of supplement",
        "addendum",
        "supplements the",
    ),
    "amended": (
        "this notice is amended",
        "amended notice",
        "notice of amendment",
        "amendment no",
        "amendment number",
        "has been amended",
        "modification to",
        "amended",
        "amendment",
    ),
}

# Most consequential first. A cancelled notice that was also amended is
# cancelled; reporting it as amended would put a dead programme back in front of
# a customer.
_STATUS_PRECEDENCE: tuple[str, ...] = (
    "cancelled",
    "withdrawn",
    "superseded",
    "extended",
    "corrected",
    "supplemented",
    "amended",
)

_VERSION_PATTERNS: tuple[str, ...] = (
    r"amendment\s+(?:no\.?|number|#)\s*([0-9]+)",
    r"version\s+([0-9]+(?:\.[0-9]+)?)",
    r"revision\s+([0-9]+)",
    r"\bv([0-9]+(?:\.[0-9]+)?)\b",
)

_MAX_QUOTE_CHARS = 300


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _clip(text: str, limit: int = _MAX_QUOTE_CHARS) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def find_status_cues(raw_text: str | None) -> list[dict[str, Any]]:
    """Locate every status cue with its span. Detection is not conclusion."""
    text = str(raw_text or "")
    if not text.strip():
        return []
    low = text.lower()
    found: list[dict[str, Any]] = []
    for status, cues in STATUS_CUES.items():
        for cue in cues:
            for m in re.finditer(re.escape(cue), low):
                found.append(
                    {
                        "status": status,
                        "cue": cue,
                        "start": m.start(),
                        "end": m.end(),
                        "quote": _clip(text[max(0, m.start() - 100) : m.end() + 100]),
                    }
                )
    found.sort(key=lambda d: (d["start"], d["status"]))
    return found


def detect_version_label(raw_text: str | None) -> dict[str, Any] | None:
    text = str(raw_text or "")
    if not text.strip():
        return None
    low = text.lower()
    for pattern in _VERSION_PATTERNS:
        m = re.search(pattern, low)
        if m:
            return {
                "label": m.group(1),
                "raw": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "quote": _clip(text[max(0, m.start() - 80) : m.end() + 80]),
            }
    return None


def _dedupe_cues(cues: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    """Keep the longest cue per position - "cancelled" inside "this notice is
    cancelled" is the same finding stated twice."""
    same = [c for c in cues if c["status"] == status]
    kept: list[dict[str, Any]] = []
    for c in sorted(same, key=lambda d: (d["start"], -(d["end"] - d["start"]))):
        if any(k["start"] <= c["start"] and c["end"] <= k["end"] for k in kept):
            continue
        kept.append(c)
    return kept


def detect_notice_status(
    *,
    notice_id: str,
    raw_text: str | None = None,
    extraction: dict[str, Any] | None = None,
    notice_url: str | None = None,
    declared_version: str | int | None = None,
    amendment_date: str | None = None,
) -> dict[str, Any]:
    """Decide one notice's status from its own text.

    ``extraction`` is the Gate 81B result. When supplied, its amendment sections
    are preferred as the citation site, because a cue inside an amendment
    section is far stronger evidence than the same word in a summary paragraph.
    """
    reasons: list[str] = []
    text = str(raw_text or "")

    if not text.strip():
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "detector_version": DETECTOR_VERSION,
                "notice_id": notice_id,
                "notice_status": "unknown",
                "status_evidence": [],
                "all_cues": [],
                "version_label": (
                    str(declared_version) if declared_version is not None else None
                ),
                "version_evidence": None,
                "amendment_date": amendment_date,
                "is_current_notice": False,
                "visible": True,
                "projected_freshness_state": "unknown",
                "projection_lossy": False,
                "extension_evidence": [],
                "supersession_evidence": [],
                "supersedes": None,
                "human_review_required": True,
                "reasons": ["no_raw_text"],
                "amendment_asserted_without_evidence": False,
                "cancelled_notice_hidden": False,
                "live_fetch_performed": False,
            }
        )

    cues = find_status_cues(text)

    amendment_spans = [
        (int(s.get("start", 0)), int(s.get("end", 0)))
        for s in (extraction or {}).get("amendment_sections") or []
    ]

    status = "original"
    evidence: list[dict[str, Any]] = []
    for candidate in _STATUS_PRECEDENCE:
        hits = _dedupe_cues(cues, candidate)
        if not hits:
            continue
        in_section = [
            h for h in hits if any(s <= h["start"] < e for s, e in amendment_spans)
        ]
        chosen = in_section or hits
        status = candidate
        evidence = chosen
        if in_section:
            reasons.append(f"cue_found_in_amendment_section:{candidate}")
        else:
            reasons.append(f"cue_found_in_body:{candidate}")
        break

    # No cue at all is not "original" unless the text was actually read; it is,
    # but say so explicitly rather than letting the default speak.
    if status == "original":
        reasons.append("no_amendment_cue_found")

    # Evidence gate. A status that needs a quote and has none falls back to
    # unknown - not to the status we suspected.
    if status in EVIDENCE_REQUIRED_STATUSES and not evidence:
        reasons.append(f"status_requires_evidence_quote:{status}")
        status = "unknown"

    version = detect_version_label(text)
    version_label = (
        str(declared_version)
        if declared_version is not None
        else (version["label"] if version else None)
    )

    projected = FRESHNESS_PROJECTION.get(status, "unknown")
    lossy = status in LOSSY_PROJECTIONS
    if lossy:
        reasons.append(f"lossy_freshness_projection:{status}->{projected}")

    # Evidence handed to the freshness service, in the kinds it already accepts.
    extension_evidence: list[dict[str, Any]] = []
    if status == "extended" and evidence:
        extension_evidence = [
            {
                "kind": "amendment_notice_url" if notice_url else (
                    "operator_verified_extension"
                ),
                "reference": notice_url,
                "quote": evidence[0]["quote"],
                "start": evidence[0]["start"],
                "end": evidence[0]["end"],
            }
        ]

    supersession_evidence: list[dict[str, Any]] = []
    if status == "superseded" and evidence:
        supersession_evidence = [
            {
                "kind": "funder_stated_supersession",
                "reference": notice_url,
                "quote": evidence[0]["quote"],
                "start": evidence[0]["start"],
                "end": evidence[0]["end"],
            }
        ]

    is_current = status in CURRENT_NOTICE_STATUSES
    human_review = status == "unknown" or (status in NON_CURRENT_NOTICE_STATUSES)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "detector_version": DETECTOR_VERSION,
            "notice_id": notice_id,
            "notice_status": status,
            "status_evidence": evidence,
            "all_cues": cues,
            "version_label": version_label,
            "version_evidence": version,
            "amendment_date": amendment_date,
            "is_current_notice": is_current,
            # Always true. Enforced by an invariant, not by convention.
            "visible": True,
            "projected_freshness_state": projected,
            "projection_lossy": lossy,
            "extension_evidence": extension_evidence,
            "supersession_evidence": supersession_evidence,
            "supersedes": None,
            "human_review_required": human_review,
            "reasons": reasons,
            "amendment_asserted_without_evidence": False,
            "cancelled_notice_hidden": False,
            "live_fetch_performed": False,
        }
    )


def evaluate_notice_supersession(
    *,
    older: dict[str, Any],
    newer: dict[str, Any],
    detection: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Decide supersession by delegating to the Gate 76D authority.

    This module contributes the *evidence* it read out of the notice; it does
    not re-answer the lineage question, which
    :func:`opportunity_freshness_service.evaluate_supersession` already answers
    correctly and conservatively.
    """
    combined = list(evidence or [])
    if detection:
        combined.extend(detection.get("supersession_evidence") or [])

    result = evaluate_supersession(older=older, newer=newer, evidence=combined)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "delegated_to": "opportunity_freshness_service.evaluate_supersession",
            "supersession": result,
            "evidence_supplied": combined,
            # The older notice is never removed, whatever the verdict.
            "older_remains_visible": True,
            "older_status_if_superseded": "superseded",
        }
    )


def amendment_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = result.get("notice_status")
    if status not in NOTICE_STATUSES:
        fails.append(f"notice_status_out_of_vocabulary:{status}")

    # A status that requires evidence must carry a quote with a span.
    if status in EVIDENCE_REQUIRED_STATUSES:
        ev = result.get("status_evidence") or []
        if not ev:
            fails.append(f"status_asserted_without_evidence:{status}")
        for e in ev:
            s, en = e.get("start"), e.get("end")
            if not isinstance(s, int) or not isinstance(en, int) or en <= s:
                fails.append(f"status_evidence_without_a_valid_span:{status}")
            if not str(e.get("quote") or "").strip():
                fails.append(f"status_evidence_without_a_quote:{status}")

    # Nothing ever disappears.
    if result.get("visible") is not True:
        fails.append("notice_hidden_instead_of_marked")
    if status in {"cancelled", "withdrawn"} and result.get("is_current_notice"):
        fails.append(f"non_current_status_reported_as_current:{status}")

    # The projection must stay inside the freshness vocabulary, and must never
    # put a dead notice into a current freshness state.
    projected = result.get("projected_freshness_state")
    if projected is not None and projected not in FRESHNESS_STATES:
        fails.append(f"projection_outside_freshness_vocabulary:{projected}")
    if status in NON_CURRENT_NOTICE_STATUSES and projected in CURRENT_STATES:
        fails.append(f"non_current_notice_projected_onto_a_current_state:{status}")

    # Lossy projections must say so.
    if status in LOSSY_PROJECTIONS and not result.get("projection_lossy"):
        fails.append(f"lossy_projection_not_marked:{status}")

    # Evidence handed onward must use kinds the freshness service accepts.
    for e in result.get("extension_evidence") or []:
        if e.get("kind") not in EXTENSION_EVIDENCE_KINDS:
            fails.append(f"extension_evidence_kind_unknown:{e.get('kind')}")
    for e in result.get("supersession_evidence") or []:
        if e.get("kind") not in SUPERSESSION_EVIDENCE_KINDS:
            fails.append(f"supersession_evidence_kind_unknown:{e.get('kind')}")

    # Extension evidence only makes sense for an extended notice.
    if result.get("extension_evidence") and status != "extended":
        fails.append(f"extension_evidence_on_a_non_extended_notice:{status}")

    for forbidden in (
        "amendment_asserted_without_evidence",
        "cancelled_notice_hidden",
        "live_fetch_performed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
