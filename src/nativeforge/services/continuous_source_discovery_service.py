"""Continuous source discovery + scraping safety architecture (Gate 55).

Models the source registry and the candidate lifecycle. Nothing here performs
network I/O: this is the contract layer that decides what *may* be monitored and
how a source's freshness may be described. Live ingestion remains NOT claimed.

Two rules do most of the work:
  * a source cannot reach ``monitoring`` without human review
  * freshness is only ever reported from a recorded timestamp, never inferred
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_continuous_source_discovery_v1"

CANDIDATE_STATES = frozenset(
    {
        "discovered",
        "triaged",
        "approved_for_monitoring",
        "monitoring",
        "stale",
        "blocked_terms",
        "blocked_low_quality",
        "retired",
        "unknown",
    }
)

# Only an explicitly approved source may be monitored.
PROMOTABLE_FROM = frozenset({"triaged", "approved_for_monitoring"})
BLOCKED_STATES = frozenset({"blocked_terms", "blocked_low_quality", "retired"})

ACCESS_METHODS = frozenset({"api", "rss", "public_feed", "html_scrape", "unknown"})

# Preference order — APIs and feeds before scraping.
PREFERRED_ACCESS_METHODS = ("api", "rss", "public_feed")

TERMS_REVIEW_STATES = frozenset(
    {"not_reviewed", "permitted", "restricted", "prohibited", "unknown"}
)

DEFAULT_RATE_LIMIT_PER_MIN = 10
DEFAULT_STALE_AFTER_DAYS = 30


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_source_id(source_url: str) -> str:
    raw = f"src::{source_url}".encode()
    return f"src_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_candidate_fingerprint(*, title: str, source_url: str) -> str:
    raw = f"cand::{title.strip().lower()}::{source_url.strip().lower()}".encode()
    return f"cf_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_source_candidate(
    *,
    source_url: str,
    source_type: str,
    access_method: str = "unknown",
    terms_review_state: str = "not_reviewed",
    robots_allows: bool | None = None,
    state: str = "discovered",
    extraction_confidence: float | None = None,
    provenance: dict[str, Any] | None = None,
    source_timestamp: str | None = None,
    extraction_timestamp: str | None = None,
    reviewed_by: str | None = None,
) -> dict[str, Any]:
    """Build a source candidate record with safety metadata attached."""
    st = state if state in CANDIDATE_STATES else "unknown"
    am = access_method if access_method in ACCESS_METHODS else "unknown"
    tr = (
        terms_review_state
        if terms_review_state in TERMS_REVIEW_STATES
        else "unknown"
    )

    # Prohibited terms or a robots disallow forces the blocked state.
    if tr == "prohibited" or robots_allows is False:
        st = "blocked_terms"

    conf = extraction_confidence
    if conf is not None:
        conf = round(max(0.0, min(1.0, float(conf))), 4)

    prov = dict(provenance or {})
    provenance_complete = bool(
        prov.get("publisher") and source_url and extraction_timestamp
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": make_source_id(source_url),
            "source_url": source_url,
            "source_type": source_type,
            "access_method": am,
            "access_method_preferred": am in PREFERRED_ACCESS_METHODS,
            "terms_review_state": tr,
            "robots_allows": robots_allows,
            "state": st,
            "extraction_confidence": conf,
            "provenance": prov,
            "provenance_complete": provenance_complete,
            "source_timestamp": source_timestamp,
            "extraction_timestamp": extraction_timestamp,
            "reviewed_by": reviewed_by,
            "rate_limit_per_min": DEFAULT_RATE_LIMIT_PER_MIN,
            # Honest boundaries.
            "live_ingest_claimed": False,
            "authoritative_without_metadata": False,
            "freshness_inferred": False,
        }
    )


def evaluate_source_promotion(
    *, candidate: dict[str, Any], approver_id: str | None = None
) -> dict[str, Any]:
    """Decide whether a candidate may be promoted to ``monitoring``."""
    reasons: list[str] = []
    state = candidate.get("state")

    if state in BLOCKED_STATES:
        reasons.append(f"source_blocked:{state}")
    if state == "unknown":
        reasons.append("unknown_source_requires_review")
    if state == "discovered":
        reasons.append("candidate_not_yet_triaged")
    if state not in PROMOTABLE_FROM and state not in BLOCKED_STATES:
        if state not in {"discovered", "unknown"}:
            reasons.append(f"state_not_promotable:{state}")

    if candidate.get("terms_review_state") in {"not_reviewed", "unknown"}:
        reasons.append("terms_review_required")
    if candidate.get("terms_review_state") == "prohibited":
        reasons.append("terms_prohibit_use")
    if candidate.get("robots_allows") is False:
        reasons.append("robots_disallows")
    if not candidate.get("provenance_complete"):
        reasons.append("provenance_incomplete")
    if not approver_id:
        reasons.append("human_review_approval_required")

    allowed = not reasons
    new_state = "monitoring" if allowed else candidate.get("state")

    event_type = (
        "source_candidate_promoted" if allowed else "source_candidate_blocked"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": candidate.get("source_id"),
            "allowed": allowed,
            "resulting_state": new_state,
            "blocked_reasons": reasons,
            "approver_id": approver_id,
            "audit_event": {
                "event_type": event_type,
                "source_id": candidate.get("source_id"),
                "reasons": reasons,
                "persisted": False,
            },
            "live_ingest_claimed": False,
        }
    )


def evaluate_source_freshness(
    *,
    candidate: dict[str, Any],
    now_days_since_epoch: int | None = None,
    last_seen_days_since_epoch: int | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Report freshness only from recorded timestamps. Never infer it.

    Days are passed as integers rather than read from the clock so the result is
    deterministic and cannot silently drift in tests.
    """
    if now_days_since_epoch is None or last_seen_days_since_epoch is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "source_id": candidate.get("source_id"),
                "freshness_state": "unknown",
                "age_days": None,
                "reason": "missing_timestamp_freshness_unknown",
                "counted_as_fresh": False,
                "freshness_inferred": False,
            }
        )

    age = int(now_days_since_epoch) - int(last_seen_days_since_epoch)
    stale = age > int(stale_after_days)
    state = "stale" if stale else "fresh"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": candidate.get("source_id"),
            "freshness_state": state,
            "age_days": age,
            "stale_after_days": int(stale_after_days),
            "reason": "computed_from_recorded_timestamps",
            "counted_as_fresh": state == "fresh",
            "freshness_inferred": False,
            "audit_event": (
                {
                    "event_type": "opportunity_source_stale",
                    "source_id": candidate.get("source_id"),
                    "age_days": age,
                    "persisted": False,
                }
                if stale
                else None
            ),
        }
    )


def dedupe_candidates(*, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge candidates sharing a fingerprint; flag rather than silently drop."""
    seen: dict[str, str] = {}
    unique: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []

    for c in candidates:
        fp = make_candidate_fingerprint(
            title=str(c.get("title") or ""), source_url=str(c.get("source_url") or "")
        )
        if fp in seen:
            flagged.append(
                {
                    "fingerprint": fp,
                    "duplicate_of": seen[fp],
                    "source_url": c.get("source_url"),
                    "audit_event": {
                        "event_type": "opportunity_duplicate_flagged",
                        "fingerprint": fp,
                        "persisted": False,
                    },
                }
            )
        else:
            seen[fp] = str(c.get("source_url") or "")
            item = dict(c)
            item["fingerprint"] = fp
            unique.append(item)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "input_count": len(candidates),
            "unique_count": len(unique),
            "duplicate_count": len(flagged),
            "unique": unique,
            "duplicates_flagged": flagged,
        }
    )


def source_candidate_invariant_failures(candidate: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if candidate.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if candidate.get("state") not in CANDIDATE_STATES:
        fails.append("state_invalid")
    if candidate.get("access_method") not in ACCESS_METHODS:
        fails.append("access_method_invalid")
    if candidate.get("terms_review_state") not in TERMS_REVIEW_STATES:
        fails.append("terms_review_state_invalid")
    conf = candidate.get("extraction_confidence")
    if conf is not None and not (0.0 <= float(conf) <= 1.0):
        fails.append("extraction_confidence_out_of_range")
    # A prohibited or robots-disallowed source must never be monitoring.
    if candidate.get("state") == "monitoring":
        if candidate.get("terms_review_state") == "prohibited":
            fails.append("monitoring_while_terms_prohibited")
        if candidate.get("robots_allows") is False:
            fails.append("monitoring_while_robots_disallows")
    for forbidden in (
        "live_ingest_claimed",
        "authoritative_without_metadata",
        "freshness_inferred",
    ):
        if candidate.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
