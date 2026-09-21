"""Is the identity graph sound? (Gate 169S)

Ten conditions, each measurable, each with a named failure. A gap is NAMED
rather than reported as healthy - the rule Gate 164 established for evidence
health and Gate 167 for the canonical graph.

The two conditions worth reading twice:

```text
no_illegal_l4_settled_merges   a fuzzy SAME_AS nobody reviewed
recurrence_not_collapsed       an annual cycle merged into one opportunity
```

The first is what migration 0054's CHECK prevents at rest; this measures
whether the table actually holds what the constraint promises. The second has
no constraint available - "these two are different years" is not expressible
as a CHECK - so it is measured here and nowhere else.

Reads only. Composes from rows that already exist; writes no second ledger.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_identity_resolution_health_v1"

CANONICAL = "nf_canonical_opportunities"
BLOCKING = "nf_opportunity_blocking_keys"
RELATIONSHIPS = "nf_opportunity_identity_relationships"
CANDIDATES = "nf_opportunity_identity_candidates"

HEALTH_CONDITIONS: tuple[str, ...] = (
    "identity_layers_valid",
    "exact_ids_unique",
    "no_illegal_l4_settled_merges",
    "provisional_candidates_reviewable",
    "relationships_non_orphaned",
    "recurrence_not_collapsed",
    "amendments_not_split",
    "false_positive_controls_clean",
    "candidate_generation_bounded",
    "identity_replay_deterministic",
)

SETTLED_LAYERS: frozenset[str] = frozenset({"L1", "L2"})


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_identity_health(
    *,
    connection: Any = None,
    controls_clean: bool | None = None,
    candidate_generation_bounded: bool | None = None,
    replay_deterministic: bool | None = None,
) -> dict[str, Any]:
    """Judge the identity graph.

    Three conditions are PASSED IN rather than derived, and say so: whether
    the false-positive controls hold, whether candidate generation is bounded,
    and whether decisions replay. None of the three is readable from a row -
    they are properties of the resolver measured by phase scripts - and
    inventing them here from what happens to be stored would be the
    unfalsifiable-check pattern this campaign keeps removing.
    """
    conditions = dict.fromkeys(HEALTH_CONDITIONS, False)
    gaps: list[str] = []
    notes: dict[str, Any] = {}

    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "identity_resolution_ready": False,
                "conditions": conditions,
                "named_gaps": ["no_connection_so_nothing_was_measured"],
            }
        )

    def scalar(sql: str, **params: Any) -> int:
        try:
            return int(
                connection.execute(sa.text(sql), params).scalar() or 0
            )
        except Exception:  # noqa: BLE001
            return -1

    # ---- 1. layers are in the vocabulary, and provisional where required
    bad_layers = scalar(
        f"SELECT count(*) FROM {CANONICAL} WHERE identity_layer NOT IN "
        "('L1','L2','L3','L4')"
    )
    unprovisional = scalar(
        f"SELECT count(*) FROM {CANONICAL} WHERE identity_layer IN ('L3','L4') "
        "AND is_provisional = 0"
    )
    conditions["identity_layers_valid"] = bad_layers == 0 and unprovisional == 0
    notes["layers_outside_the_vocabulary"] = bad_layers
    notes["probabilistic_rows_not_marked_provisional"] = unprovisional
    if bad_layers:
        gaps.append(f"identity_layers_outside_the_vocabulary:{bad_layers}")
    if unprovisional:
        gaps.append(f"probabilistic_layer_not_provisional:{unprovisional}")

    # ---- 2. one canonical row per L1 identity -----------------------
    duplicate_identities = scalar(
        "SELECT count(*) FROM (SELECT normalized_opportunity_number, doc_type "
        f"FROM {CANONICAL} GROUP BY normalized_opportunity_number, doc_type "
        "HAVING count(*) > 1)"
    )
    conditions["exact_ids_unique"] = duplicate_identities == 0
    notes["duplicate_l1_identities"] = duplicate_identities
    if duplicate_identities:
        gaps.append(f"duplicate_l1_identities:{duplicate_identities}")

    # ---- 3. THE rule: no fuzzy SAME_AS without a human --------------
    illegal = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} WHERE relationship = 'SAME_AS' "
        "AND identity_layer NOT IN ('L1','L2') AND decided_by <> 'human_review'"
    )
    unsigned_human = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} WHERE "
        "decided_by = 'human_review' AND (reviewer IS NULL OR reviewer = '')"
    )
    conditions["no_illegal_l4_settled_merges"] = (
        illegal == 0 and unsigned_human == 0
    )
    notes["fuzzy_same_as_without_review"] = illegal
    notes["human_decisions_without_a_reviewer"] = unsigned_human
    if illegal:
        gaps.append(f"fuzzy_same_as_without_a_human_decision:{illegal}")
    if unsigned_human:
        gaps.append(f"human_decision_without_a_reviewer:{unsigned_human}")

    # ---- 4. candidates are reviewable and resolutions are signed ----
    unsigned_resolution = scalar(
        f"SELECT count(*) FROM {CANDIDATES} WHERE review_state IN "
        "('approved_merge','rejected_merge') AND (reviewed_by IS NULL "
        "OR reviewed_at IS NULL)"
    )
    pending = scalar(
        f"SELECT count(*) FROM {CANDIDATES} WHERE review_state = 'pending'"
    )
    bad_state = scalar(
        f"SELECT count(*) FROM {CANDIDATES} WHERE review_state NOT IN "
        "('pending','approved_merge','rejected_merge','marked_related','deferred')"
    )
    conditions["provisional_candidates_reviewable"] = (
        unsigned_resolution == 0 and bad_state == 0
    )
    notes["pending_candidates"] = pending
    notes["unsigned_resolutions"] = unsigned_resolution
    if unsigned_resolution:
        gaps.append(f"resolution_without_a_signature:{unsigned_resolution}")
    if bad_state:
        gaps.append(f"review_state_outside_the_vocabulary:{bad_state}")

    # ---- 5. no relationship points at a missing opportunity ---------
    orphan_from = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} r WHERE r.from_canonical_id "
        f"NOT IN (SELECT canonical_id FROM {CANONICAL})"
    )
    orphan_to = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} r WHERE r.to_canonical_id "
        f"NOT IN (SELECT canonical_id FROM {CANONICAL})"
    )
    self_edges = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} WHERE "
        "from_canonical_id = to_canonical_id"
    )
    conditions["relationships_non_orphaned"] = (
        orphan_from == 0 and orphan_to == 0 and self_edges == 0
    )
    notes["orphan_relationship_endpoints"] = orphan_from + orphan_to
    notes["self_relationships"] = self_edges
    if orphan_from or orphan_to:
        gaps.append(
            "relationship_points_at_a_missing_opportunity:"
            f"{orphan_from + orphan_to}"
        )
    if self_edges:
        gaps.append(f"opportunity_related_to_itself:{self_edges}")

    # ---- 6. annual cycles were not merged ---------------------------
    #
    # A SAME_AS between two opportunities whose numbers differ is the shape a
    # collapsed recurrence takes. There is no CHECK that can express this, so
    # it is measured here and nowhere else.
    collapsed = scalar(
        f"SELECT count(*) FROM {RELATIONSHIPS} r "
        f"JOIN {CANONICAL} a ON a.canonical_id = r.from_canonical_id "
        f"JOIN {CANONICAL} b ON b.canonical_id = r.to_canonical_id "
        "WHERE r.relationship = 'SAME_AS' AND r.revoked_at IS NULL "
        "AND a.normalized_opportunity_number <> '' "
        "AND b.normalized_opportunity_number <> '' "
        "AND a.normalized_opportunity_number <> b.normalized_opportunity_number"
    )
    conditions["recurrence_not_collapsed"] = collapsed == 0
    notes["same_as_between_different_published_numbers"] = collapsed
    if collapsed:
        gaps.append(f"two_published_numbers_merged_as_one:{collapsed}")

    # ---- 7. amendments stayed on one opportunity --------------------
    #
    # A version chain that split would show as two canonical rows sharing an
    # L1 identity, which condition 2 already counts; this names the inverse -
    # an opportunity whose current pointer does not lead anywhere.
    broken_pointer = scalar(
        f"SELECT count(*) FROM {CANONICAL} c WHERE c.current_version_id IS NOT NULL "
        "AND c.current_version_id NOT IN (SELECT version_id FROM "
        "nf_opportunity_versions)"
    )
    conditions["amendments_not_split"] = (
        broken_pointer == 0 and duplicate_identities == 0
    )
    notes["broken_current_version_pointers"] = broken_pointer
    if broken_pointer:
        gaps.append(f"current_version_pointer_leads_nowhere:{broken_pointer}")

    # ---- 8/9/10. measured by the resolver, not readable from a row ----
    conditions["false_positive_controls_clean"] = bool(controls_clean)
    conditions["candidate_generation_bounded"] = bool(candidate_generation_bounded)
    conditions["identity_replay_deterministic"] = bool(replay_deterministic)
    for name, value in (
        ("false_positive_controls_clean", controls_clean),
        ("candidate_generation_bounded", candidate_generation_bounded),
        ("identity_replay_deterministic", replay_deterministic),
    ):
        if value is None:
            gaps.append(f"{name}_was_not_measured")
        elif value is False:
            gaps.append(f"{name}_failed")
    notes["conditions_supplied_by_phase_measurement"] = [
        "false_positive_controls_clean",
        "candidate_generation_bounded",
        "identity_replay_deterministic",
    ]

    # ---- coverage ----------------------------------------------------
    keyed = scalar(
        f"SELECT count(DISTINCT canonical_id) FROM {BLOCKING}"
    )
    total = scalar(f"SELECT count(*) FROM {CANONICAL}")
    notes["opportunities_with_blocking_keys"] = keyed
    notes["opportunities_total"] = total
    notes["opportunities_without_blocking_keys"] = max(total - keyed, 0)
    if total > 0 and keyed < total:
        # Named, not failed: an opportunity with no published identifiers
        # legitimately has no keys, and the backfill is idempotent.
        gaps.append(
            f"opportunities_without_blocking_keys:{total - keyed}"
        )

    ready = all(conditions.values()) and not gaps

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_resolution_ready": bool(ready),
            "conditions": conditions,
            "named_gaps": sorted(set(gaps)),
            "notes": notes,
            "a_gap_must_be_named": (
                "an unnamed gap makes `ready` a way to pass while hiding "
                "anything"
            ),
        }
    )


def identity_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims readiness it did not measure."""
    fails: list[str] = []
    conditions = health.get("conditions") or {}

    unknown = sorted(set(conditions) - set(HEALTH_CONDITIONS))
    if unknown:
        fails.append(f"condition_outside_the_vocabulary:{unknown}")
    missing = sorted(set(HEALTH_CONDITIONS) - set(conditions))
    if missing:
        fails.append(f"condition_not_measured:{missing}")

    if health.get("identity_resolution_ready"):
        unmet = sorted(name for name, ok in conditions.items() if not ok)
        if unmet:
            fails.append(f"ready_with_unmet_conditions:{unmet}")
        if health.get("named_gaps"):
            fails.append(f"ready_with_named_gaps:{health.get('named_gaps')}")

    if not health.get("identity_resolution_ready") and not health.get("named_gaps"):
        if all(conditions.values()):
            fails.append("not_ready_without_naming_anything")

    return sorted(set(fails))
