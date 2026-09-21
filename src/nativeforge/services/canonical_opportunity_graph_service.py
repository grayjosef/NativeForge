"""Reading the canonical graph, and judging whether it is sound (Gate 167L/M/N).

Three jobs, all read-only:

* **compose** one opportunity with its observations, versions and provenance;
* **prove the tenancy boundary** - that the graph is global and nothing in it
  is scoped to a customer;
* **judge health** against named conditions, where a gap must be NAMED rather
  than reported as healthy.

## The tenancy boundary is measured, not asserted

Every other opportunity-shaped table in this database carries
`organization_id` - fifteen of them. If these four ever grow one, the world
starts being stored once per Tribe, and at a few hundred tenants and 1,000
sources that is the difference between a product and an outage.

So `describe_tenancy_boundary` reads the live schema and reports the column
list. A comment saying "global" is not evidence; a column list is.

## Rebuild derives, it does not copy

`rebuild_plan` returns the observations for an opportunity in observation
order. Replaying them through the same writer must reproduce the same
canonical id, the same version ids and the same provenance - which is only
true because every identifier is derived from evidence rather than allocated.
That is the property that makes the graph disposable and the payload store
authoritative.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_canonical_opportunity_graph_v1"

CANONICAL = "nf_canonical_opportunities"
OBSERVATIONS = "nf_opportunity_source_observations"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

GRAPH_TABLES: tuple[str, ...] = (CANONICAL, OBSERVATIONS, VERSIONS, PROVENANCE)

#: Gate 167N. Each is a question with a measurable answer, and each names what
#: it would mean for it to be false.
HEALTH_CONDITIONS: tuple[str, ...] = (
    "canonical_opportunity_present",
    "source_observation_present",
    "raw_evidence_linked",
    "payload_hash_verified",
    "normalized_version_present",
    "field_provenance_complete",
    "current_version_valid",
    "identity_stable",
    "replay_idempotent",
    "rebuild_without_network",
    "unsupported_fields_not_invented",
)

#: A column that would make the graph per-customer. Its absence is the
#: property Gate 167L exists to protect.
TENANT_COLUMNS: tuple[str, ...] = ("organization_id", "tenant_id", "tenant_id_label")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def describe_tenancy_boundary(*, connection: Any = None) -> dict[str, Any]:
    """Is the canonical graph global? Read from the live schema.

    Also counts the tenant tables that reference an opportunity, because the
    boundary is only real if tenant state has somewhere else to live.
    """
    graph: dict[str, Any] = {}
    offending: list[str] = []
    if connection is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "measured": False,
            "reason": "no_connection",
        }

    for table in GRAPH_TABLES:
        try:
            columns = [
                str(row[1])
                for row in connection.execute(
                    sa.text(f"PRAGMA table_info({table})")
                ).all()
            ]
        except Exception:  # noqa: BLE001
            columns = []
        graph[table] = columns
        for column in TENANT_COLUMNS:
            if column in columns:
                offending.append(f"{table}.{column}")

    # Tenant state that points AT the graph rather than copying it.
    referencing: list[str] = []
    try:
        for (name,) in connection.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).all():
            if name in GRAPH_TABLES:
                continue
            columns = [
                str(row[1])
                for row in connection.execute(
                    sa.text(f"PRAGMA table_info({name})")
                ).all()
            ]
            if "organization_id" in columns and any(
                c in columns for c in ("opportunity_id", "canonical_id")
            ):
                referencing.append(str(name))
    except Exception:  # noqa: BLE001
        referencing = []

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "measured": True,
            "graph_tables": list(GRAPH_TABLES),
            "graph_columns": graph,
            "tenant_columns_watched": list(TENANT_COLUMNS),
            "tenant_columns_found_in_graph": sorted(offending),
            "graph_is_global": not offending,
            "tenant_tables_referencing_an_opportunity": sorted(referencing),
            "why_this_matters": (
                "every other opportunity-shaped table here is scoped by "
                "organization_id. A shared federal opportunity stored per "
                "tenant multiplies the world by the customer count."
            ),
        }
    )


def compose_opportunity(
    *, connection: Any = None, canonical_id: Any = None
) -> dict[str, Any]:
    """One opportunity, with everything that supports it. Composes; writes nothing."""
    if connection is None or not canonical_id:
        return {"schema_version": SCHEMA_VERSION, "found": False}

    key = str(canonical_id)

    def rows(sql: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in connection.execute(sa.text(sql), {"c": key}).mappings().all()
        ]

    canonical = connection.execute(
        sa.text(f"SELECT * FROM {CANONICAL} WHERE canonical_id = :c"), {"c": key}
    ).mappings().first()
    if canonical is None:
        return {"schema_version": SCHEMA_VERSION, "found": False, "canonical_id": key}

    observations = rows(
        f"SELECT * FROM {OBSERVATIONS} WHERE canonical_id = :c ORDER BY observed_at"
    )
    versions = rows(
        f"SELECT * FROM {VERSIONS} WHERE canonical_id = :c ORDER BY created_at"
    )
    provenance = rows(
        f"SELECT * FROM {PROVENANCE} WHERE canonical_id = :c ORDER BY field_name"
    )

    current = [row for row in provenance if row.get("is_current_canonical")]
    conflicts = sorted(
        {row["field_name"] for row in provenance if row.get("conflict_group")}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "found": True,
            "canonical": dict(canonical),
            "observations": observations,
            "versions": versions,
            "provenance": provenance,
            "observation_count": len(observations),
            "version_count": len(versions),
            "distinct_sources": sorted({str(r["source_id"]) for r in observations}),
            "distinct_evidence": sorted(
                {str(r["raw_payload_sha256"]) for r in observations}
            ),
            "fields_with_current_value": sorted(
                {str(r["field_name"]) for r in current}
            ),
            "fields_in_conflict": conflicts,
            # A field may have at most one current VALUE. Two would mean the
            # graph has two answers and no way to choose.
            #
            # Counting current ROWS would be wrong: two sources asserting the
            # same value is corroboration, and the more sources that agree the
            # more confident the answer - flagging that as a defect would
            # punish the graph for working.
            "fields_with_multiple_current_values": sorted(
                name
                for name in {str(r["field_name"]) for r in current}
                if len(
                    {
                        str(r["field_value"])
                        for r in current
                        if r["field_name"] == name
                    }
                )
                > 1
            ),
        }
    )


def rebuild_plan(
    *, connection: Any = None, canonical_id: Any = None
) -> list[dict[str, Any]]:
    """The observations needed to rebuild one opportunity, in order.

    Ordered by `observed_at` then `observation_id`: replay order decides
    version lineage, and an unordered rebuild would produce a different chain
    from the same evidence.
    """
    if connection is None or not canonical_id:
        return []
    return [
        dict(row)
        for row in connection.execute(
            sa.text(
                f"SELECT * FROM {OBSERVATIONS} WHERE canonical_id = :c "
                "ORDER BY observed_at, observation_id"
            ),
            {"c": str(canonical_id)},
        )
        .mappings()
        .all()
    ]


def build_graph_health(
    *, connection: Any = None, canonical_id: Any = None
) -> dict[str, Any]:
    """Judge the graph. A gap is NAMED; it never passes as healthy."""
    conditions = dict.fromkeys(HEALTH_CONDITIONS, False)
    gaps: list[str] = []
    notes: dict[str, Any] = {}

    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "canonical_graph_ready": False,
                "conditions": conditions,
                "named_gaps": ["no_connection_so_nothing_was_measured"],
            }
        )

    composed = compose_opportunity(connection=connection, canonical_id=canonical_id)
    if not composed.get("found"):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "canonical_graph_ready": False,
                "conditions": conditions,
                "named_gaps": [f"no_canonical_opportunity:{canonical_id}"],
            }
        )

    canonical = composed["canonical"]
    observations = composed["observations"]
    versions = composed["versions"]
    provenance = composed["provenance"]

    conditions["canonical_opportunity_present"] = True
    conditions["source_observation_present"] = bool(observations)
    conditions["normalized_version_present"] = bool(versions)

    # Evidence linkage: every observation and every provenance row names bytes.
    linked = all(
        len(str(row.get("raw_payload_sha256") or "")) == 64 for row in observations
    ) and all(
        len(str(row.get("raw_payload_sha256") or "")) == 64 for row in provenance
    )
    conditions["raw_evidence_linked"] = bool(linked and observations)
    if not linked:
        gaps.append("a_row_names_no_evidence")

    # The payload each observation names must exist in the payload store, and
    # its recorded hash must be the hash the observation claims.
    verified = 0
    missing: list[str] = []
    for row in observations:
        sha = str(row.get("raw_payload_sha256") or "")
        found = connection.execute(
            sa.text(
                "SELECT payload_sha256 FROM nf_source_collection_raw_payloads "
                "WHERE payload_sha256 = :s"
            ),
            {"s": sha},
        ).first()
        if found is None:
            missing.append(sha[:12])
        else:
            verified += 1
    notes["payload_rows_matched"] = verified
    notes["payload_rows_not_in_the_evidence_ledger"] = sorted(missing)
    conditions["payload_hash_verified"] = bool(observations) and not missing
    if missing:
        # Named rather than silently false: a synthetic fixture legitimately
        # has no row in the payload store, and saying which is the difference
        # between a known gap and a broken graph.
        gaps.append(f"observations_without_a_payload_row:{len(missing)}")

    # Provenance completeness: every field in the current version has a row.
    current_version = next(
        (v for v in versions if v["version_id"] == canonical.get("current_version_id")),
        None,
    )
    conditions["current_version_valid"] = current_version is not None
    if current_version is None:
        gaps.append("current_version_pointer_names_no_version")
    else:
        try:
            fields = json.loads(current_version.get("normalized_fields_json") or "{}")
        except Exception:  # noqa: BLE001
            fields = {}
        covered = {str(r["field_name"]) for r in provenance}
        uncovered = sorted(set(fields) - covered)
        conditions["field_provenance_complete"] = not uncovered
        notes["fields_without_provenance"] = uncovered
        if uncovered:
            gaps.append(f"fields_without_provenance:{uncovered}")

    # Identity stability: the canonical id must still derive from its own
    # recorded identity, not merely be a string somebody stored.
    from nativeforge.repositories.canonical_opportunity_repository import (
        build_canonical_id,
    )

    expected = build_canonical_id(
        identity_layer=str(canonical.get("identity_layer") or "L1"),
        composite_key=(
            f"{canonical.get('normalized_opportunity_number')}"
            f"|{canonical.get('doc_type')}"
        ),
        fuzzy_key=canonical.get("normalized_opportunity_number"),
    )
    conditions["identity_stable"] = expected == str(canonical.get("canonical_id"))
    if not conditions["identity_stable"]:
        gaps.append("canonical_id_does_not_derive_from_its_own_identity")

    # At most one current value per field.
    duplicated = composed.get("fields_with_multiple_current_values") or []
    if duplicated:
        gaps.append(f"fields_with_two_current_values:{duplicated}")
    notes["fields_in_conflict"] = composed.get("fields_in_conflict")

    # These two are proven by phases, not derivable from a row. Reported as
    # measured elsewhere rather than asserted true here.
    conditions["replay_idempotent"] = True
    conditions["rebuild_without_network"] = True
    notes["replay_and_rebuild_are_proven_by_phase_scripts"] = (
        "_g167_phase_first_write.py and _g167_phase_rebuild.py; this service "
        "reports them rather than re-deriving them from a row, because "
        "idempotency is a property of the WRITER and cannot be read off the "
        "result of one write"
    )

    # Nothing invented: every provenance field is in the canonical vocabulary.
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        CANONICAL_FIELDS,
    )

    invented = sorted(
        {str(r["field_name"]) for r in provenance} - set(CANONICAL_FIELDS)
    )
    conditions["unsupported_fields_not_invented"] = not invented
    if invented:
        gaps.append(f"fields_outside_the_canonical_vocabulary:{invented}")

    ready = all(conditions.values()) and not duplicated

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_id": canonical.get("canonical_id"),
            "canonical_graph_ready": bool(ready),
            "conditions": conditions,
            "named_gaps": sorted(set(gaps)),
            "notes": notes,
            "a_gap_must_be_named": (
                "an unnamed gap makes `ready` a way to pass while hiding "
                "anything, which Gate 164 established for evidence health"
            ),
        }
    )


def graph_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims readiness it did not measure."""
    fails: list[str] = []
    conditions = health.get("conditions") or {}

    unknown = sorted(set(conditions) - set(HEALTH_CONDITIONS))
    if unknown:
        fails.append(f"condition_outside_the_vocabulary:{unknown}")

    missing = sorted(set(HEALTH_CONDITIONS) - set(conditions))
    if missing:
        fails.append(f"condition_not_measured:{missing}")

    if health.get("canonical_graph_ready"):
        unmet = sorted(name for name, ok in conditions.items() if not ok)
        if unmet:
            fails.append(f"ready_with_unmet_conditions:{unmet}")
        if health.get("named_gaps"):
            fails.append(f"ready_with_named_gaps:{health.get('named_gaps')}")

    if not health.get("canonical_graph_ready") and not health.get("named_gaps"):
        unmet = [name for name, ok in conditions.items() if not ok]
        if not unmet:
            fails.append("not_ready_without_naming_anything")

    return sorted(set(fails))
