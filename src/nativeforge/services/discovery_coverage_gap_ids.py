"""Stable identifiers and ordering keys for coverage gap intelligence."""

from __future__ import annotations

import hashlib

from nativeforge.domain.enums import CoverageGapSeverity


def gap_id(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:22]


def recommendation_id(gap_id: str) -> str:
    return hashlib.sha256(f"rec|{gap_id}".encode()).hexdigest()[:22]


def severity_rank(sev: str) -> int:
    order = {
        CoverageGapSeverity.critical.value: 0,
        CoverageGapSeverity.high.value: 1,
        CoverageGapSeverity.medium.value: 2,
        CoverageGapSeverity.low.value: 3,
    }
    return order.get(sev, 9)
