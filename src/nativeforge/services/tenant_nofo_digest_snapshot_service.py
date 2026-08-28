"""Tenant NOFO digest snapshot (Gate 104B).

A recorded set of opportunity rows as they appeared to one tenant at one moment.
Snapshots are the substrate change detection compares; building one fetches
nothing.

## Four kinds, and only one of them requires collection

```text
demo_fixture      invented for a demo, labelled as such
recorded_fixture  captured from a real observation and stored
live_observation  taken from a live collection just now
unknown           nobody said which
```

`live_observation` is the only kind that asserts collection happened, and it is
**refused unless `source_collection_status` proves it**. Passing the kind is not
enough: a caller claiming a live observation while collection status says
`not_active` gets `unknown` and a stated reason.

That refusal is the whole reason the kind field exists. Doc 570 flagged that
change detection needs a time series and no live collection exists to produce
one, so every snapshot in this repository today is a fixture — and the contract
has to make a fixture that *claims* to be live impossible rather than merely
discouraged.

## A snapshot never claims coverage

```text
source_monitoring_live  false
live_source_coverage    false
collectors_active       0
```

Held by invariants on every snapshot regardless of kind. A recorded fixture of a
real observation is still not monitoring, and a hundred rows of real
opportunities are still not coverage.

## Unknowns stay visible

An opportunity row carries `deadline_provenance_status` from Gate 87's
vocabulary and `reporting_burden_preview_status` from its own. Neither is ever
defaulted to something reassuring:

```text
deadline with no provenance  -> unknown_deadline
reporting burden unsupported -> unsupported_document_type / unknown
eligibility not established  -> unknown / needs_human_review
```

A row that cannot say where its deadline came from says so, and Gate 104C is
built to carry that through to the digest rather than resolve it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.deadline_provenance_service import (
    FRESHNESS_BLOCKING_STATUSES,
    PROVENANCE_STATUSES,
    VERIFIED_STATUSES,
)
from nativeforge.services.opportunity_deadline_and_amendment_model_service import (
    AMENDMENT_CATEGORIES,
)
from nativeforge.services.software_capacity_allowability_review_service import (
    ALLOWABILITY_LABELS,
)

SCHEMA_VERSION = "nf_tenant_nofo_digest_snapshot_v1"

SNAPSHOT_KINDS = frozenset(
    {"demo_fixture", "recorded_fixture", "live_observation", "unknown"}
)

# The only kind that asserts collection happened.
LIVE_SNAPSHOT_KINDS = frozenset({"live_observation"})

# Kinds that are safe without any collection at all.
FIXTURE_SNAPSHOT_KINDS = frozenset({"demo_fixture", "recorded_fixture"})

# Gate 93's collector vocabulary. Only the last proves a live observation.
SOURCE_COLLECTION_STATUSES = frozenset(
    {"not_active", "human_review_only", "terms_review_required", "collected", "unknown"}
)
COLLECTION_PROVEN_STATUSES = frozenset({"collected"})

# Amendment status on a row. Bridged from Gate 92's categories plus the two
# states a row can be in before any amendment is classified.
AMENDMENT_STATUSES = frozenset(AMENDMENT_CATEGORIES) | {
    "no_amendment",
    "unknown",
}

ELIGIBILITY_MATCH_STATUSES = frozenset(
    {
        "matched",
        "partial_match",
        "excluded",
        "downgraded",
        "needs_human_review",
        "unknown",
    }
)
# Statuses that put an item in front of a tenant as a candidate.
MATCHING_STATUSES = frozenset({"matched", "partial_match"})

ELIGIBILITY_CONFIDENCE_LEVELS = frozenset(
    {"high", "medium", "low", "unknown", "not_assessed"}
)

REPORTING_BURDEN_STATUSES = frozenset(
    {
        "preview_available",
        "partial",
        "unsupported_document_type",
        "not_assessed",
        "unknown",
    }
)
# Statuses where a burden preview may actually be shown as a preview.
BURDEN_SHOWABLE_STATUSES = frozenset({"preview_available", "partial"})

PURSUIT_STATUSES = frozenset(
    {"not_pursued", "pursuing", "submitted", "awarded", "not_selected", "unknown"}
)
# A pursuit record exists in these states, which is what suppression needs.
PURSUIT_ACTIVE_STATUSES = frozenset(
    {"pursuing", "submitted", "awarded", "not_selected"}
)

SUPPRESSION_STATUSES = frozenset(
    {
        "not_suppressed",
        "suppressed_from_new_digest",
        "suppressed_from_daily_alert",
        "suppressed_from_weekly_digest",
        "human_review_required",
        "unknown",
    }
)

RAW_PAYLOAD_EVIDENCE_STATUSES = frozenset(
    {"evidence_stored", "evidence_missing", "not_applicable", "unknown"}
)

OPPORTUNITY_ROW_FIELDS: tuple[str, ...] = (
    "opportunity_id",
    "opportunity_number",
    "source_id",
    "source_name",
    "title",
    "agency",
    "source_kind",
    "state_scope",
    "federal_scope",
    "deadline",
    "deadline_provenance_status",
    "amendment_status",
    "eligibility_match_status",
    "eligibility_confidence",
    "tenant_match_reasons",
    "tenant_exclusion_reasons",
    "human_review_reasons",
    "reporting_burden_preview_status",
    "software_capacity_allowability_label",
    "pursuit_status",
    "suppression_status",
    "raw_payload_evidence_status",
)

SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id",
    "tenant_id",
    "snapshot_label",
    "snapshot_kind",
    "observed_at",
    "source_collection_status",
    "source_monitoring_live",
    "live_source_coverage",
    "opportunity_rows",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _strings(values: Any) -> list[str]:
    return sorted({str(v).strip() for v in (values or []) if str(v).strip()})


def build_snapshot_id(
    *, tenant_id: Any, snapshot_label: Any, observed_at: Any
) -> str:
    """Deterministic from what the snapshot is, not when it was built."""
    return hashlib.sha256(
        "|".join(
            str(p if p is not None else "")
            for p in (tenant_id, snapshot_label, observed_at)
        ).encode("utf-8")
    ).hexdigest()


def build_opportunity_row(
    *,
    opportunity_id: Any,
    opportunity_number: Any = None,
    source_id: Any = None,
    source_name: Any = None,
    title: Any = None,
    agency: Any = None,
    source_kind: Any = None,
    state_scope: Any = None,
    federal_scope: bool = False,
    deadline: Any = None,
    deadline_provenance_status: Any = None,
    amendment_status: Any = None,
    eligibility_match_status: Any = None,
    eligibility_confidence: Any = None,
    tenant_match_reasons: list[Any] | None = None,
    tenant_exclusion_reasons: list[Any] | None = None,
    human_review_reasons: list[Any] | None = None,
    reporting_burden_preview_status: Any = None,
    software_capacity_allowability_label: Any = None,
    pursuit_status: Any = None,
    suppression_status: Any = None,
    raw_payload_evidence_status: Any = None,
) -> dict[str, Any]:
    """One opportunity as it appeared to one tenant. Unknowns stay unknown."""
    provenance = _norm(
        deadline_provenance_status, PROVENANCE_STATUSES, fallback="unknown_deadline"
    )
    # A date with no provenance is not a verified date. Recording the date and
    # the fact that nobody can vouch for it is more useful than dropping either.
    if deadline and provenance == "unknown_deadline":
        provenance = "unverified_deadline"

    return _json_safe(
        {
            "opportunity_id": opportunity_id,
            "opportunity_number": opportunity_number,
            "source_id": source_id,
            "source_name": source_name,
            "title": title,
            "agency": agency,
            "source_kind": source_kind,
            "state_scope": (
                str(state_scope).strip().upper() if state_scope else None
            ),
            "federal_scope": bool(federal_scope),
            "deadline": deadline,
            "deadline_provenance_status": provenance,
            "deadline_verified": provenance in VERIFIED_STATUSES,
            "deadline_blocks_freshness": provenance in FRESHNESS_BLOCKING_STATUSES,
            "amendment_status": _norm(
                amendment_status, AMENDMENT_STATUSES, fallback="unknown"
            ),
            "eligibility_match_status": _norm(
                eligibility_match_status,
                ELIGIBILITY_MATCH_STATUSES,
                fallback="unknown",
            ),
            "eligibility_confidence": _norm(
                eligibility_confidence,
                ELIGIBILITY_CONFIDENCE_LEVELS,
                fallback="unknown",
            ),
            "tenant_match_reasons": _strings(tenant_match_reasons),
            "tenant_exclusion_reasons": _strings(tenant_exclusion_reasons),
            "human_review_reasons": _strings(human_review_reasons),
            "reporting_burden_preview_status": _norm(
                reporting_burden_preview_status,
                REPORTING_BURDEN_STATUSES,
                fallback="unknown",
            ),
            "software_capacity_allowability_label": _norm(
                software_capacity_allowability_label,
                ALLOWABILITY_LABELS,
                fallback="not_indicated",
            ),
            "pursuit_status": _norm(
                pursuit_status, PURSUIT_STATUSES, fallback="not_pursued"
            ),
            "suppression_status": _norm(
                suppression_status, SUPPRESSION_STATUSES, fallback="not_suppressed"
            ),
            "raw_payload_evidence_status": _norm(
                raw_payload_evidence_status,
                RAW_PAYLOAD_EVIDENCE_STATUSES,
                fallback="unknown",
            ),
        }
    )


def build_digest_snapshot(
    *,
    tenant_id: Any,
    snapshot_label: Any,
    snapshot_kind: Any = None,
    observed_at: Any = None,
    source_collection_status: Any = None,
    opportunity_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One tenant snapshot. Nothing is collected, monitored, or claimed."""
    requested_kind = _norm(snapshot_kind, SNAPSHOT_KINDS, fallback="unknown")
    collection = _norm(
        source_collection_status, SOURCE_COLLECTION_STATUSES, fallback="not_active"
    )

    blocked_reasons: list[str] = []

    # A live observation must be backed by collection that actually happened.
    kind = requested_kind
    if requested_kind in LIVE_SNAPSHOT_KINDS and collection not in (
        COLLECTION_PROVEN_STATUSES
    ):
        blocked_reasons.append(
            f"live_observation_without_proven_collection:{collection}"
        )
        kind = "unknown"

    if kind == "unknown":
        blocked_reasons.append("snapshot_kind_unknown")
    if collection not in COLLECTION_PROVEN_STATUSES:
        blocked_reasons.append(f"source_collection_status:{collection}")

    rows = list(opportunity_rows or [])
    # Stable order so digests and artifacts regenerate byte-identically.
    rows.sort(key=lambda r: str(r.get("opportunity_id")))

    unverified = sum(1 for r in rows if not r.get("deadline_verified"))
    unknown_burden = sum(
        1
        for r in rows
        if r.get("reporting_burden_preview_status") not in BURDEN_SHOWABLE_STATUSES
    )
    if unverified:
        blocked_reasons.append(f"unverified_deadlines:{unverified}")
    if unknown_burden:
        blocked_reasons.append(f"unknown_reporting_burden:{unknown_burden}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": build_snapshot_id(
                tenant_id=tenant_id,
                snapshot_label=snapshot_label,
                observed_at=observed_at,
            ),
            "tenant_id": tenant_id,
            "snapshot_label": snapshot_label,
            "snapshot_kind": kind,
            "requested_snapshot_kind": requested_kind,
            "observed_at": observed_at,
            "source_collection_status": collection,
            "row_count": len(rows),
            "unverified_deadline_count": unverified,
            "unknown_reporting_burden_count": unknown_burden,
            "opportunity_rows": rows,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # A snapshot is a record, never a capability.
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def snapshot_invariant_failures(snapshot: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if snapshot.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "live_source_coverage",
        "fetch_performed",
    ):
        if snapshot.get(constant) is not False:
            fails.append(f"snapshot_claimed:{constant}")
    if snapshot.get("collectors_active") != 0:
        fails.append("snapshot_claimed_active_collectors")

    for field in SNAPSHOT_FIELDS:
        if field not in snapshot:
            fails.append(f"snapshot_missing_field:{field}")

    kind = snapshot.get("snapshot_kind")
    if kind not in SNAPSHOT_KINDS:
        fails.append("snapshot_kind_out_of_vocabulary")

    # The load-bearing rule: a live observation needs proven collection.
    if kind in LIVE_SNAPSHOT_KINDS:
        if snapshot.get("source_collection_status") not in (
            COLLECTION_PROVEN_STATUSES
        ):
            fails.append("live_observation_without_proven_collection")

    rows = snapshot.get("opportunity_rows")
    if not isinstance(rows, list):
        fails.append("opportunity_rows_not_a_list")
        return fails

    for row in rows:
        for field in OPPORTUNITY_ROW_FIELDS:
            if field not in row:
                fails.append(f"row_missing_field:{field}:{row.get('opportunity_id')}")
        if row.get("deadline_provenance_status") not in PROVENANCE_STATUSES:
            fails.append(f"provenance_out_of_vocabulary:{row.get('opportunity_id')}")
        if row.get("eligibility_match_status") not in ELIGIBILITY_MATCH_STATUSES:
            fails.append(f"match_status_out_of_vocabulary:{row.get('opportunity_id')}")
        if row.get("suppression_status") not in SUPPRESSION_STATUSES:
            fails.append(
                f"suppression_status_out_of_vocabulary:{row.get('opportunity_id')}"
            )
        if row.get("amendment_status") not in AMENDMENT_STATUSES:
            fails.append(
                f"amendment_status_out_of_vocabulary:{row.get('opportunity_id')}"
            )
        # `deadline_verified` is derived, never asserted beside the status.
        if row.get("deadline_verified") != (
            row.get("deadline_provenance_status") in VERIFIED_STATUSES
        ):
            fails.append(
                f"deadline_verified_disagrees_with_provenance:"
                f"{row.get('opportunity_id')}"
            )
        # An excluded row that offers no reason is an unexplained refusal.
        if row.get("eligibility_match_status") in {"excluded", "downgraded"}:
            if not row.get("tenant_exclusion_reasons"):
                fails.append(f"exclusion_without_a_reason:{row.get('opportunity_id')}")
        if row.get("eligibility_match_status") == "needs_human_review":
            if not row.get("human_review_reasons"):
                fails.append(
                    f"human_review_without_a_reason:{row.get('opportunity_id')}"
                )

    # Counts derived from the rows.
    if snapshot.get("row_count") != len(rows):
        fails.append("row_count_disagrees_with_the_rows")
    if snapshot.get("unverified_deadline_count") != sum(
        1 for r in rows if not r.get("deadline_verified")
    ):
        fails.append("unverified_count_disagrees_with_the_rows")

    # Identity reproducible from the snapshot's own fields.
    expected = build_snapshot_id(
        tenant_id=snapshot.get("tenant_id"),
        snapshot_label=snapshot.get("snapshot_label"),
        observed_at=snapshot.get("observed_at"),
    )
    if snapshot.get("snapshot_id") != expected:
        fails.append("snapshot_id_not_derivable_from_its_fields")

    return fails
