"""What a customer may be told about a change (Gate 170K), and whether the
change graph is sound (Gate 170O).

## An allowlist, not a redaction pass

The customer-facing payload is built by naming the fields that may appear.
Gate 164 established why: a denylist is a list of things somebody remembered,
and the first field added after it was written is exposed by default. Nothing
reaches a customer unless it is in `CUSTOMER_FIELDS`.

Excluded on purpose, and each for a reason:

```text
change_event_id, version ids      internal keys with no customer meaning
raw_payload_sha256                evidence pointer, not evidence
observation_id                    internal
materiality_rule                  the rule NAME is engineering vocabulary
source_id                         the source's PUBLISHER is shown instead
```

The rule name is deliberately withheld while the human-readable explanation
is shown. `deadline_shortened_reduces_time_to_apply` is how an engineer argues
with a classification; "the application deadline moved earlier" is what a
Tribe needs to read.

## A provisional identity is never presented as settled

If the opportunity carries an unresolved conflict on the field that changed,
the payload says so. Gate 169 established that a provisional merge must never
appear as truth; the same applies to a contested value - showing one source's
deadline as *the* deadline while another source disagrees is a worse failure
than showing nothing.

## No sending

This builds a payload. It does not deliver anything, and nothing here knows
what a recipient is.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_opportunity_change_read_model_v1"

EVENTS = "nf_opportunity_change_events"
CONFLICTS = "nf_opportunity_field_conflicts"
CANONICAL = "nf_canonical_opportunities"

#: The only keys that may appear in a customer-facing change payload.
CUSTOMER_FIELDS: tuple[str, ...] = (
    "opportunity_title",
    "opportunity_number",
    "funder",
    "what_changed",
    "prior_value",
    "new_value",
    "importance",
    "detected_at",
    "effective_date",
    "reported_by_sources",
    "corroborating_source_count",
    "has_unresolved_conflict",
    "conflict_note",
    "explanation",
)

#: Markers that must never appear in a serialized customer payload. Checked as
#: negative proof over the output, the way Gate 164 checked provenance.
FORBIDDEN_MARKERS: tuple[str, ...] = (
    "raw_payload_sha256",
    "change_event_id",
    "observation_id",
    "new_version_id",
    "prior_version_id",
    "materiality_rule",
    "/home/",
    ".venv",
    "nativeforge.local.db",
    "warrant",
    "authorized_source_id",
)

#: Human-readable text per change type. Engineering vocabulary stays out.
EXPLANATIONS: dict[str, str] = {
    "DEADLINE_SHORTENED": "The application deadline moved earlier.",
    "DEADLINE_EXTENDED": "The application deadline was extended.",
    "DEADLINE_CHANGED": "The application deadline changed.",
    "OPEN_DATE_CHANGED": "The date applications open changed.",
    "STATUS_CHANGED": "The opportunity status changed.",
    "FORECAST_TO_POSTED": "A forecasted opportunity is now open for applications.",
    "POSTED_TO_CLOSED": "The opportunity has closed.",
    "REOPENED": "A closed opportunity is accepting applications again.",
    "CANCELLED": "The opportunity was cancelled.",
    "TITLE_CHANGED": "The opportunity title was edited.",
    "ELIGIBILITY_CHANGED": "Who may apply changed.",
    "FUNDING_MIN_CHANGED": "The minimum award amount changed.",
    "FUNDING_MAX_CHANGED": "The maximum award amount changed.",
    "AGENCY_CHANGED": "The funding agency changed.",
    "OPPORTUNITY_NUMBER_CHANGED": "The opportunity number changed.",
    "DOCUMENT_ADDED": "A document was added.",
    "DOCUMENT_REMOVED": "A document is no longer available.",
    "DOCUMENT_REPLACED": "A document was replaced.",
    "SOURCE_URL_CHANGED": "The opportunity page moved.",
    "ASSISTANCE_LISTINGS_CHANGED": "The assistance listing numbers changed.",
    "AMENDMENT_PUBLISHED": "The agency published an amendment.",
    "CONFLICT_INTRODUCED": "Sources began reporting different values.",
    "CONFLICT_RESOLVED": "Sources now agree.",
    "FIRST_OBSERVED": "This opportunity was seen for the first time.",
    "UNKNOWN_CHANGE": "Something changed that we cannot describe yet.",
}

#: Customer-facing importance. The internal class names leak engineering
#: judgement; these are what a reader can act on.
IMPORTANCE: dict[str, str] = {
    "CRITICAL": "act_now",
    "MATERIAL": "review_soon",
    "INFORMATIONAL": "for_information",
    "NON_MATERIAL": "no_action",
    "UNKNOWN": "unclassified",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_customer_change_feed(
    *,
    connection: Any = None,
    canonical_id: Any = None,
    minimum_importance: Any = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Customer-safe change payloads. Reads only; sends nothing."""
    if connection is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "changes": [],
            "measured": False,
            "reason": "no_connection",
        }

    events = sa.text(
        f"SELECT e.*, c.title AS opp_title, c.normalized_opportunity_number AS num, "
        f"c.funder_agency_name AS funder_name, c.funder_agency_code AS funder_code "
        f"FROM {EVENTS} e JOIN {CANONICAL} c ON c.canonical_id = e.canonical_id "
        + ("WHERE e.canonical_id = :c " if canonical_id else "")
        + "ORDER BY e.detected_at DESC, e.change_event_id LIMIT :n"
    )
    params: dict[str, Any] = {"n": int(limit)}
    if canonical_id:
        params["c"] = str(canonical_id)

    rows = connection.execute(events, params).mappings().all()

    conflicts = {
        (str(row["canonical_id"]), str(row["field_name"])): dict(row)
        for row in connection.execute(
            sa.text(
                f"SELECT canonical_id, field_name, conflict_state, "
                f"competing_source_count FROM {CONFLICTS} "
                "WHERE conflict_state = 'OPEN_CONFLICT'"
            )
        ).mappings()
    }

    allowed = set(IMPORTANCE.values())
    wanted = str(minimum_importance or "").strip() or None
    if wanted and wanted not in allowed:
        wanted = None

    changes: list[dict[str, Any]] = []
    for row in rows:
        importance = IMPORTANCE.get(str(row["materiality"]), "unclassified")
        if wanted and importance != wanted:
            continue

        try:
            corroborators = json.loads(row["corroborated_by_json"] or "[]")
        except Exception:  # noqa: BLE001
            corroborators = []

        conflict = conflicts.get(
            (str(row["canonical_id"]), str(row["field_name"]))
        )

        payload = {
            "opportunity_title": row["opp_title"],
            "opportunity_number": row["num"],
            "funder": row["funder_name"] or row["funder_code"],
            "what_changed": row["change_type"],
            "prior_value": row["prior_value"],
            "new_value": row["new_value"],
            "importance": importance,
            "detected_at": row["detected_at"],
            "effective_date": row["effective_date"],
            # The PUBLISHER count, not the internal source ids.
            "reported_by_sources": 1 + len(corroborators),
            "corroborating_source_count": row["corroborating_source_count"],
            "has_unresolved_conflict": conflict is not None,
            "conflict_note": (
                "Sources currently report different values for this field."
                if conflict is not None
                else None
            ),
            "explanation": EXPLANATIONS.get(
                str(row["change_type"]), EXPLANATIONS["UNKNOWN_CHANGE"]
            ),
        }
        # The allowlist is applied HERE, so a future key added above cannot
        # reach a customer without being named.
        changes.append({k: payload.get(k) for k in CUSTOMER_FIELDS})

    serialized = json.dumps(changes, default=str)
    leaked = sorted({m for m in FORBIDDEN_MARKERS if m in serialized})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "measured": True,
            "changes": changes,
            "change_count": len(changes),
            "allowlisted_fields": list(CUSTOMER_FIELDS),
            "forbidden_markers_checked": list(FORBIDDEN_MARKERS),
            "forbidden_markers_found": leaked,
            "customer_safe": not leaked,
            "notifications_sent": 0,
            "delivery_is_not_built_in_this_gate": True,
        }
    )


def read_model_invariant_failures(feed: dict[str, Any]) -> list[str]:
    """Refuse a payload that leaked, or that claims safety it did not check."""
    fails: list[str] = []

    if feed.get("forbidden_markers_found"):
        fails.append(f"forbidden_marker_in_output:{feed['forbidden_markers_found']}")
    if feed.get("customer_safe") and feed.get("forbidden_markers_found"):
        fails.append("claimed_safe_while_naming_a_leak")
    if feed.get("notifications_sent"):
        fails.append("this_gate_sent_a_notification")

    for change in feed.get("changes") or []:
        extra = sorted(set(change) - set(CUSTOMER_FIELDS))
        if extra:
            fails.append(f"key_outside_the_allowlist:{extra}")
        if change.get("importance") not in set(IMPORTANCE.values()):
            fails.append(f"importance_outside_the_vocabulary:{change.get('importance')}")

    return sorted(set(fails))


# ------------------------------------------------------------- health

HEALTH_CONDITIONS: tuple[str, ...] = (
    "version_chain_valid",
    "diff_deterministic",
    "change_events_idempotent",
    "materiality_rules_named",
    "deadline_shapes_preserved",
    "amendment_not_recurrence",
    "conflicts_preserved",
    "conflict_resolution_supported",
    "multi_source_corroboration_supported",
    "unchanged_observation_noop",
    "replay_deterministic",
    "network_requests_zero",
)


def build_change_health(
    *,
    connection: Any = None,
    diff_deterministic: bool | None = None,
    events_idempotent: bool | None = None,
    amendment_not_recurrence: bool | None = None,
    corroboration_supported: bool | None = None,
    unchanged_noop: bool | None = None,
    replay_deterministic: bool | None = None,
    network_requests: int | None = None,
) -> dict[str, Any]:
    """Judge the change graph. A gap is NAMED; it never passes as healthy.

    Six conditions are PASSED IN and say so. None is readable from a row -
    they are properties of the detector measured by phase scripts - and
    deriving them from whatever happens to be stored would be the
    unfalsifiable-check pattern this campaign keeps removing.
    """
    conditions = dict.fromkeys(HEALTH_CONDITIONS, False)
    gaps: list[str] = []
    notes: dict[str, Any] = {}

    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "change_intelligence_ready": False,
                "conditions": conditions,
                "named_gaps": ["no_connection_so_nothing_was_measured"],
            }
        )

    def scalar(sql: str) -> int:
        try:
            return int(connection.execute(sa.text(sql)).scalar() or 0)
        except Exception:  # noqa: BLE001
            return -1

    # ---- the version chain every event points into --------------------
    orphan_version = scalar(
        f"SELECT count(*) FROM {EVENTS} e WHERE e.new_version_id NOT IN "
        "(SELECT version_id FROM nf_opportunity_versions)"
    )
    orphan_prior = scalar(
        f"SELECT count(*) FROM {EVENTS} e WHERE e.prior_version_id IS NOT NULL "
        "AND e.prior_version_id NOT IN "
        "(SELECT version_id FROM nf_opportunity_versions)"
    )
    same_version = scalar(
        f"SELECT count(*) FROM {EVENTS} WHERE prior_version_id = new_version_id"
    )
    conditions["version_chain_valid"] = (
        orphan_version == 0 and orphan_prior == 0 and same_version == 0
    )
    notes["events_pointing_at_a_missing_version"] = orphan_version + orphan_prior
    if orphan_version or orphan_prior:
        gaps.append(
            f"event_points_at_a_missing_version:{orphan_version + orphan_prior}"
        )
    if same_version:
        gaps.append(f"event_between_one_version_and_itself:{same_version}")

    # ---- every materiality carries its rule ---------------------------
    unruled = scalar(
        f"SELECT count(*) FROM {EVENTS} WHERE materiality <> 'UNKNOWN' "
        "AND (materiality_rule IS NULL OR materiality_rule = '')"
    )
    conditions["materiality_rules_named"] = unruled == 0
    notes["classifications_without_a_rule"] = unruled
    if unruled:
        gaps.append(f"materiality_without_a_named_rule:{unruled}")

    # ---- evidence on every event --------------------------------------
    no_evidence = scalar(
        f"SELECT count(*) FROM {EVENTS} WHERE length(raw_payload_sha256) <> 64"
    )
    if no_evidence:
        gaps.append(f"change_event_naming_no_evidence:{no_evidence}")
    notes["events_without_evidence"] = no_evidence

    # ---- deadline shapes survived -------------------------------------
    bad_shape = scalar(
        f"SELECT count(*) FROM {EVENTS} WHERE deadline_shape IS NOT NULL "
        "AND deadline_shape NOT IN ('single','dual','per_region','phased',"
        "'revised','multi_year','unknown')"
    )
    collapsed = scalar(
        f"SELECT count(*) FROM {EVENTS} WHERE field_name = 'close_date' "
        "AND deadline_shape IS NULL"
    )
    conditions["deadline_shapes_preserved"] = bad_shape == 0 and collapsed == 0
    notes["deadline_events_without_a_shape"] = collapsed
    if bad_shape:
        gaps.append(f"deadline_shape_outside_the_vocabulary:{bad_shape}")
    if collapsed:
        gaps.append(f"deadline_change_with_no_recorded_shape:{collapsed}")

    # ---- conflicts kept their facts and their start ------------------
    conflict_without_sides = scalar(
        f"SELECT count(*) FROM {CONFLICTS} WHERE conflict_state <> 'NO_CONFLICT' "
        "AND competing_source_count < 2"
    )
    conflict_without_start = scalar(
        f"SELECT count(*) FROM {CONFLICTS} WHERE first_detected_at IS NULL"
    )
    unsigned_resolution = scalar(
        f"SELECT count(*) FROM {CONFLICTS} WHERE conflict_state = "
        "'RESOLVED_CONFLICT' AND (resolved_by IS NULL OR "
        "resolution_evidence_json IS NULL)"
    )
    conditions["conflicts_preserved"] = (
        conflict_without_sides == 0 and conflict_without_start == 0
    )
    conditions["conflict_resolution_supported"] = unsigned_resolution == 0
    notes["open_conflicts"] = scalar(
        f"SELECT count(*) FROM {CONFLICTS} WHERE conflict_state = 'OPEN_CONFLICT'"
    )
    notes["resolved_conflicts"] = scalar(
        f"SELECT count(*) FROM {CONFLICTS} WHERE conflict_state = "
        "'RESOLVED_CONFLICT'"
    )
    if conflict_without_sides:
        gaps.append(f"conflict_with_fewer_than_two_sides:{conflict_without_sides}")
    if conflict_without_start:
        gaps.append(f"conflict_without_a_first_detected_time:{conflict_without_start}")
    if unsigned_resolution:
        gaps.append(f"resolution_without_a_signature:{unsigned_resolution}")

    notes["change_events_total"] = scalar(f"SELECT count(*) FROM {EVENTS}")
    notes["versions_without_events"] = scalar(
        "SELECT count(*) FROM nf_opportunity_versions WHERE version_id NOT IN "
        f"(SELECT new_version_id FROM {EVENTS})"
    )
    if notes["versions_without_events"] > 0:
        # Named, not failed: the backfill is idempotent and a version whose
        # diff produced nothing legitimately has no events.
        gaps.append(f"versions_without_events:{notes['versions_without_events']}")

    # ---- measured by the detector, not readable from a row ------------
    supplied = {
        "diff_deterministic": diff_deterministic,
        "change_events_idempotent": events_idempotent,
        "amendment_not_recurrence": amendment_not_recurrence,
        "multi_source_corroboration_supported": corroboration_supported,
        "unchanged_observation_noop": unchanged_noop,
        "replay_deterministic": replay_deterministic,
    }
    for name, value in supplied.items():
        conditions[name] = bool(value)
        if value is None:
            gaps.append(f"{name}_was_not_measured")
        elif value is False:
            gaps.append(f"{name}_failed")

    conditions["network_requests_zero"] = network_requests == 0
    if network_requests is None:
        gaps.append("network_requests_were_not_measured")
    elif network_requests:
        gaps.append(f"network_requests_were_made:{network_requests}")

    notes["conditions_supplied_by_phase_measurement"] = sorted(supplied)

    ready = all(conditions.values()) and not gaps

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "change_intelligence_ready": bool(ready),
            "conditions": conditions,
            "named_gaps": sorted(set(gaps)),
            "notes": notes,
        }
    )


def change_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims readiness it did not measure."""
    fails: list[str] = []
    conditions = health.get("conditions") or {}

    unknown = sorted(set(conditions) - set(HEALTH_CONDITIONS))
    if unknown:
        fails.append(f"condition_outside_the_vocabulary:{unknown}")
    missing = sorted(set(HEALTH_CONDITIONS) - set(conditions))
    if missing:
        fails.append(f"condition_not_measured:{missing}")

    if health.get("change_intelligence_ready"):
        unmet = sorted(name for name, ok in conditions.items() if not ok)
        if unmet:
            fails.append(f"ready_with_unmet_conditions:{unmet}")
        if health.get("named_gaps"):
            fails.append(f"ready_with_named_gaps:{health.get('named_gaps')}")

    return sorted(set(fails))
