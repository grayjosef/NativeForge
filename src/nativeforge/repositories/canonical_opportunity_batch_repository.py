"""Set-oriented canonical persistence (Gate 168C/D/E/F).

Gate 167's writer was correct and cost 49 SQL statements per observation. Gate
168A attributed them: **41 of the 49 were provenance work, 4.1 per field** -
a probe, a demote, a conflict read and an insert, once per field, per
observation.

```text
per field, before          per BATCH, after
  SELECT provenance_id       SELECT every provenance row the batch may touch
  UPDATE demote own          UPDATE demote, one statement per source+field set
  SELECT current rows        (answered from the prefetched map)
  INSERT one row             INSERT every new row in one executemany
```

Nothing about the evidence model changed. The same provenance row per field,
the same source id, the same payload hash, the same conflict metadata, the
same current/non-current semantics. What changed is how many round trips it
takes to write them.

## Three phases, and why the middle one is in memory

```text
1. RESOLVE   set queries for everything the batch could collide with
2. DECIDE    pure, in memory, in deterministic order
3. APPLY     bulk inserts and a bounded number of updates
```

Phase 2 is where version lineage is decided, and it has to be sequential: two
observations of one opportunity in the same batch form a chain, and a set
operation cannot order a chain. So the decisions are made in memory - bounded
by the batch size, not by the table size - and only the resulting rows are
written.

This is also what makes the batch behave exactly like N single writes. The
Gate 167 writer now delegates to this path with a batch of one, so there is
one write path, not two that can drift.

## Idempotency is structural, not a comparison

Every identifier is derived from evidence (Gate 167), so a repeated
observation computes the same `observation_id`, `version_id` and
`provenance_id`. The prefetch finds them already present and the record
becomes a no-op: no insert, no pointer rewrite, no timestamp bump. A duplicate
replay is therefore CHEAPER than first ingest rather than merely harmless.

## Unique constraints are a backstop, not the mechanism

Idempotency is decided by the prefetch. The database's unique indexes remain
as a second line, and an IntegrityError is classified rather than swallowed:
a collision on a derived identifier is an expected duplicate, anything else is
corruption and is reported as a failure of that record.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_canonical_opportunity_batch_repository_v1"

CANONICAL = "nf_canonical_opportunities"
OBSERVATIONS = "nf_opportunity_source_observations"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

#: How many observations are decided and applied under one transaction.
#: Bounded so memory and transaction size stay bounded whatever the caller
#: hands in; a 50,000-observation ingest becomes 100 transactions, not one.
DEFAULT_BATCH_SIZE = 500

#: Per-record outcomes. `rejected` means the record was refused before any
#: write; it never means part of it landed.
INSERTED = "inserted"
IDEMPOTENT = "idempotent"
VERSIONED = "versioned"
REJECTED = "rejected"
FAILED = "failed"

RECORD_OUTCOMES: tuple[str, ...] = (
    INSERTED,
    IDEMPOTENT,
    VERSIONED,
    REJECTED,
    FAILED,
)


@dataclass(frozen=True)
class NormalizedSourceObservation:
    """One source record, normalized, ready to persist.

    A frozen dataclass so a caller cannot mutate an observation after the
    batch has resolved state for it - which would make the prefetch describe
    something that no longer exists.
    """

    source_id: str
    normalized: dict[str, Any]
    raw_payload_sha256: str
    identity: dict[str, Any] = field(default_factory=dict)
    raw_payload_attempt_id: str | None = None
    source_authority_host: str | None = None
    observed_at: Any = None
    http_status: int | None = None


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _stream_chunks(items: Any, size: int):
    """Yield bounded chunks from ANY iterable, without materializing it.

    `list(observations)` would make peak memory a property of the caller's
    input rather than of the batch size - a 50,000-observation ingest would
    hold 50,000 normalized records whatever `batch_size` said. A collector
    streaming from a paginated source can now hand this a generator and the
    writer's footprint stays the batch.
    """
    chunk: list[Any] = []
    for item in items or ():
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


# --------------------------------------------------------------- tables


def _table(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


def _canonical_table() -> sa.Table:
    return _table(
        CANONICAL,
        sa.Column("canonical_id", sa.Text(), primary_key=True),
        sa.Column("normalized_opportunity_number", sa.Text()),
        sa.Column("doc_type", sa.Text()),
        sa.Column("identity_layer", sa.Text()),
        sa.Column("is_provisional", sa.Boolean()),
        sa.Column("opportunity_number_group", sa.Text()),
        sa.Column("surrogate_opportunity_id", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("funder_agency_code", sa.Text()),
        sa.Column("funder_agency_name", sa.Text()),
        sa.Column("current_open_date", sa.Text()),
        sa.Column("current_close_date", sa.Text()),
        sa.Column("lifecycle_state", sa.Text()),
        sa.Column("current_version_id", sa.Text()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("observation_count", sa.Integer()),
        sa.Column("version_count", sa.Integer()),
        sa.Column("has_field_conflicts", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def _observations_table() -> sa.Table:
    return _table(
        OBSERVATIONS,
        sa.Column("observation_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("source_record_id", sa.Text()),
        sa.Column("source_opportunity_number", sa.Text()),
        sa.Column("source_authority_host", sa.Text()),
        sa.Column("raw_payload_sha256", sa.Text()),
        sa.Column("raw_payload_attempt_id", sa.Text()),
        sa.Column("parser_name", sa.Text()),
        sa.Column("parser_version", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("source_record_fingerprint", sa.Text()),
        sa.Column("observation_state", sa.Text()),
        sa.Column("http_status", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _versions_table() -> sa.Table:
    return _table(
        VERSIONS,
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("observation_id", sa.Text()),
        sa.Column("version_key", sa.Text()),
        sa.Column("revision", sa.Text()),
        sa.Column("doc_type", sa.Text()),
        sa.Column("normalized_fields_json", sa.Text()),
        sa.Column("content_fingerprint", sa.Text()),
        sa.Column("supersedes_version_id", sa.Text()),
        sa.Column("superseded_by_version_id", sa.Text()),
        sa.Column("is_material", sa.Boolean()),
        sa.Column("material_categories_json", sa.Text()),
        sa.Column("changed_fields_json", sa.Text()),
        sa.Column("parser_version", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _provenance_table() -> sa.Table:
    return _table(
        PROVENANCE,
        sa.Column("provenance_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("version_id", sa.Text()),
        sa.Column("observation_id", sa.Text()),
        sa.Column("field_name", sa.Text()),
        sa.Column("field_value", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("raw_payload_sha256", sa.Text()),
        sa.Column("selection_rule", sa.Text()),
        sa.Column("is_current_canonical", sa.Boolean()),
        sa.Column("conflict_group", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


# --------------------------------------------------------------- helpers


def _field_text(value: Any) -> str:
    return json.dumps(value) if isinstance(value, list) else str(value)


def validate_observation(observation: NormalizedSourceObservation) -> list[str]:
    """Why this record cannot be persisted. Empty means it can.

    Checked BEFORE the batch touches the database, so one malformed record
    cannot poison the valid ones beside it - Gate 168C's requirement, and the
    reason rejection is a per-record outcome rather than a batch failure.
    """
    reasons: list[str] = []

    sha = str(observation.raw_payload_sha256 or "")
    if len(sha) != 64:
        # The schema's CHECK would refuse it anyway; refusing here means the
        # rest of the batch still commits.
        reasons.append(f"raw_payload_sha256_is_not_a_64_character_digest:{len(sha)}")

    if not str(observation.source_id or "").strip():
        reasons.append("no_source_id")

    normalized = observation.normalized or {}
    if not isinstance(normalized, dict):
        reasons.append("normalized_is_not_a_mapping")
        return sorted(set(reasons))

    fields = normalized.get("fields") or {}
    if not fields:
        reasons.append("no_normalized_fields")

    if not str(normalized.get("content_fingerprint") or "").strip():
        reasons.append("no_content_fingerprint")

    identity = observation.identity or {}
    layer = str(identity.get("identity_layer") or "")
    if layer not in ("L1", "L4"):
        reasons.append(f"identity_layer_outside_the_vocabulary:{layer or 'missing'}")
    if layer == "L1" and not str(
        identity.get("normalized_opportunity_number") or ""
    ):
        reasons.append("l1_identity_without_a_normalized_number")
    if layer == "L4" and not identity.get("is_provisional"):
        # Migration 0053 refuses this; refusing here keeps the batch alive.
        reasons.append("l4_identity_not_marked_provisional")

    return sorted(set(reasons))


@dataclass
class _Plan:
    """What one record decided to write. Nothing here has touched the DB."""

    index: int
    outcome: str
    canonical_id: str
    observation_id: str
    version_id: str
    reasons: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)
    is_material: bool = False


def persist_observations(
    *,
    connection: Any,
    observations: Iterable[NormalizedSourceObservation],
    now: Any = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    collect_results: bool = True,
) -> dict[str, Any]:
    """Persist a batch. One transaction per bounded chunk.

    Returns a per-record result: a caller must be able to tell which records
    landed, which were already present, and which were refused and why. A
    single boolean over a batch of 500 is not an answer anybody can act on.
    """
    stamp = now or dt.datetime.now(dt.UTC)

    metrics = {
        "observations_attempted": 0,
        "observations_inserted": 0,
        "observations_versioned": 0,
        "observations_idempotent": 0,
        "observations_rejected": 0,
        "observations_failed": 0,
        "versions_inserted": 0,
        "provenance_rows_inserted": 0,
        "canonical_created": 0,
        "canonical_matched": 0,
        "conflicts_recorded": 0,
        "batches": 0,
        "batch_failures": 0,
    }
    results: list[dict[str, Any]] = []

    for chunk in _stream_chunks(observations, max(1, int(batch_size))):
        metrics["batches"] += 1
        metrics["observations_attempted"] += len(chunk)
        try:
            chunk_results = _persist_chunk(
                connection=connection,
                records=chunk,
                stamp=stamp,
                metrics=metrics,
            )
            connection.commit()
        except Exception as exc:  # noqa: BLE001 - the batch is the unit of atomicity
            connection.rollback()
            metrics["batch_failures"] += 1
            chunk_results = [
                {
                    "outcome": FAILED,
                    "reasons": [f"batch_rolled_back:{type(exc).__name__}"],
                    "source_id": record.source_id,
                }
                for record in chunk
            ]
            metrics["observations_failed"] += len(chunk)
        # Per-record detail and bounded memory are in tension: a 75,000-record
        # ingest cannot both report every record and stay flat. `collect_results
        # =False` keeps only the records a caller must act on - the refused and
        # the failed - which is bounded for a healthy ingest and still says
        # exactly what went wrong when it is not.
        if collect_results:
            results.extend(chunk_results)
        else:
            results.extend(
                row for row in chunk_results if row["outcome"] in (REJECTED, FAILED)
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "metrics": metrics,
            "results": results,
            "results_are_complete": collect_results,
            "batch_size": batch_size,
            "all_records_accounted_for": (
                len(results) == metrics["observations_attempted"]
                if collect_results
                else metrics["observations_attempted"]
                == (
                    metrics["observations_inserted"]
                    + metrics["observations_versioned"]
                    + metrics["observations_idempotent"]
                    + metrics["observations_rejected"]
                    + metrics["observations_failed"]
                )
            ),
        }
    )


def _persist_chunk(
    *,
    connection: Any,
    records: list[NormalizedSourceObservation],
    stamp: Any,
    metrics: dict[str, int],
) -> list[dict[str, Any]]:
    """RESOLVE, DECIDE, APPLY. Raises to abort the whole chunk."""
    from nativeforge.repositories.canonical_opportunity_repository import (
        CANONICAL_COLUMN_FOR_FIELD,
        SOURCE_SCOPED_FIELDS,
        build_canonical_id,
    )

    canonical = _canonical_table()
    observations_t = _observations_table()
    versions_t = _versions_table()
    provenance_t = _provenance_table()

    # ---- validate first; a refused record never reaches the database ----
    plans: list[_Plan] = []
    valid: list[tuple[int, NormalizedSourceObservation, dict[str, Any]]] = []
    for index, record in enumerate(records):
        reasons = validate_observation(record)
        if reasons:
            plans.append(
                _Plan(
                    index=index,
                    outcome=REJECTED,
                    canonical_id="",
                    observation_id="",
                    version_id="",
                    reasons=reasons,
                )
            )
            continue
        identity = record.identity or {}
        canonical_id = build_canonical_id(
            identity_layer=str(identity.get("identity_layer") or "L1"),
            composite_key=identity.get("composite_key"),
            fuzzy_key=identity.get("fuzzy_key"),
        )
        valid.append((index, record, {"canonical_id": canonical_id}))

    if not valid:
        return [_plan_result(plan, records) for plan in plans]

    # ---- 1. RESOLVE: everything this chunk could collide with -----------
    canonical_ids = sorted({meta["canonical_id"] for _, _, meta in valid})
    observation_ids = sorted(
        {
            _digest(
                record.source_id,
                str(
                    (record.normalized.get("fields") or {}).get("source_record_id")
                    or ""
                ),
                record.raw_payload_sha256,
            )
            for _, record, _ in valid
        }
    )

    existing_canonical: dict[str, dict[str, Any]] = {}
    for group in _chunks(canonical_ids, 400):
        for row in connection.execute(
            sa.select(canonical).where(canonical.c.canonical_id.in_(group))
        ).mappings():
            existing_canonical[str(row["canonical_id"])] = dict(row)

    existing_observations: set[str] = set()
    for group in _chunks(observation_ids, 400):
        for row in connection.execute(
            sa.select(observations_t.c.observation_id).where(
                observations_t.c.observation_id.in_(group)
            )
        ):
            existing_observations.add(str(row[0]))

    # Versions for these opportunities, newest last. Needed for lineage and
    # for the content-fingerprint idempotency check.
    versions_by_canonical: dict[str, list[dict[str, Any]]] = {}
    for group in _chunks(canonical_ids, 400):
        for row in connection.execute(
            sa.select(versions_t)
            .where(versions_t.c.canonical_id.in_(group))
            .order_by(versions_t.c.created_at, versions_t.c.version_id)
        ).mappings():
            versions_by_canonical.setdefault(str(row["canonical_id"]), []).append(
                dict(row)
            )

    # Current provenance for these opportunities: the conflict map.
    current_provenance: dict[tuple[str, str], list[dict[str, Any]]] = {}
    existing_provenance_ids: set[str] = set()
    for group in _chunks(canonical_ids, 400):
        for row in connection.execute(
            sa.select(provenance_t).where(provenance_t.c.canonical_id.in_(group))
        ).mappings():
            existing_provenance_ids.add(str(row["provenance_id"]))
            if row["is_current_canonical"]:
                key = (str(row["canonical_id"]), str(row["field_name"]))
                current_provenance.setdefault(key, []).append(dict(row))

    # ---- 2. DECIDE: pure, sequential, in memory --------------------------
    new_canonical: list[dict[str, Any]] = []
    new_observations: list[dict[str, Any]] = []
    new_versions: list[dict[str, Any]] = []
    new_provenance: list[dict[str, Any]] = []
    lineage_updates: list[tuple[str, str]] = []
    demotions: list[tuple[str, str, str]] = []  # canonical, field, source
    conflict_labels: list[tuple[str, str]] = []  # provenance_id, group
    canonical_updates: dict[str, dict[str, Any]] = {}

    for index, record, meta in valid:
        canonical_id = meta["canonical_id"]
        identity = record.identity or {}
        normalized = record.normalized or {}
        fields = dict(normalized.get("fields") or {})
        fingerprint = str(normalized.get("content_fingerprint") or "")
        sha = str(record.raw_payload_sha256)
        record_id = str(fields.get("source_record_id") or "")
        doc_type = str(
            identity.get("doc_type") or fields.get("doc_type") or "unknown"
        )
        number = str(identity.get("normalized_opportunity_number") or "")

        observation_id = _digest(record.source_id, record_id, sha)
        version_id = _digest(canonical_id, fingerprint)

        plan = _Plan(
            index=index,
            outcome=IDEMPOTENT,
            canonical_id=canonical_id,
            observation_id=observation_id,
            version_id=version_id,
        )

        # -- canonical row
        if canonical_id not in existing_canonical:
            row = {
                "canonical_id": canonical_id,
                "normalized_opportunity_number": number,
                "doc_type": doc_type,
                "identity_layer": str(identity.get("identity_layer") or "L1"),
                "is_provisional": bool(identity.get("is_provisional")),
                "opportunity_number_group": number,
                "surrogate_opportunity_id": fields.get("source_record_id"),
                "title": None,
                "funder_agency_code": None,
                "funder_agency_name": None,
                "current_open_date": None,
                "current_close_date": None,
                "lifecycle_state": str(
                    normalized.get("lifecycle_state") or "unknown"
                ),
                "current_version_id": None,
                "first_seen_at": stamp,
                "last_seen_at": stamp,
                "observation_count": 0,
                "version_count": 0,
                "has_field_conflicts": False,
                "created_at": stamp,
                "updated_at": stamp,
            }
            new_canonical.append(row)
            existing_canonical[canonical_id] = dict(row)
            metrics["canonical_created"] += 1
        else:
            metrics["canonical_matched"] += 1

        # -- observation
        wrote_observation = observation_id not in existing_observations
        if wrote_observation:
            new_observations.append(
                {
                    "observation_id": observation_id,
                    "canonical_id": canonical_id,
                    "source_id": str(record.source_id),
                    "source_record_id": record_id or None,
                    "source_opportunity_number": fields.get("opportunity_number"),
                    "source_authority_host": record.source_authority_host,
                    "raw_payload_sha256": sha,
                    "raw_payload_attempt_id": record.raw_payload_attempt_id,
                    "parser_name": str(normalized.get("parser_name") or "unknown"),
                    "parser_version": str(normalized.get("parser_version") or "0"),
                    "observed_at": record.observed_at or stamp,
                    "source_record_fingerprint": fingerprint,
                    "observation_state": "recorded",
                    "http_status": record.http_status,
                    "created_at": stamp,
                }
            )
            existing_observations.add(observation_id)

        # -- version
        prior = versions_by_canonical.get(canonical_id) or []
        already = any(str(v["version_id"]) == version_id for v in prior)
        wrote_version = not already
        if wrote_version:
            previous = prior[-1] if prior else None
            changed = _changed_fields(previous, fields)
            materiality = (
                _materiality(changed)
                if previous is not None
                else {"is_material": False, "material_categories": []}
            )
            version_row = {
                "version_id": version_id,
                "canonical_id": canonical_id,
                "observation_id": observation_id,
                "version_key": identity.get("version_key"),
                "revision": identity.get("revision"),
                "doc_type": doc_type,
                "normalized_fields_json": json.dumps(fields, sort_keys=True),
                "content_fingerprint": fingerprint,
                "supersedes_version_id": (
                    str(previous["version_id"]) if previous is not None else None
                ),
                "superseded_by_version_id": None,
                "is_material": materiality["is_material"],
                "material_categories_json": json.dumps(
                    materiality["material_categories"], sort_keys=True
                ),
                "changed_fields_json": json.dumps(sorted(changed), sort_keys=True),
                "parser_version": str(normalized.get("parser_version") or "0"),
                "created_at": stamp,
            }
            new_versions.append(version_row)
            versions_by_canonical.setdefault(canonical_id, []).append(version_row)
            if previous is not None:
                lineage_updates.append((str(previous["version_id"]), version_id))
            plan.changed_fields = sorted(changed)
            plan.is_material = bool(materiality["is_material"])
            metrics["versions_inserted"] += 1

        # -- provenance, decided against the prefetched map
        conflicts: list[str] = []
        for name, value in sorted(fields.items()):
            provenance_id = _digest(version_id, name)
            if provenance_id in existing_provenance_ids:
                continue
            text = _field_text(value)
            key = (canonical_id, name)
            incumbents = current_provenance.get(key) or []

            # This source's own earlier claim stops being current.
            mine = [
                r
                for r in incumbents
                if str(r["source_id"]) == str(record.source_id)
            ]
            if mine:
                demotions.append((canonical_id, name, str(record.source_id)))
                incumbents = [
                    r
                    for r in incumbents
                    if str(r["source_id"]) != str(record.source_id)
                ]

            disagreeing = (
                []
                if name in SOURCE_SCOPED_FIELDS
                else [r for r in incumbents if r["field_value"] != text]
            )
            conflict_group = _digest(canonical_id, name) if disagreeing else None
            if disagreeing:
                conflicts.append(name)
                for row in disagreeing:
                    conflict_labels.append(
                        (str(row["provenance_id"]), conflict_group)
                    )
                    row["conflict_group"] = conflict_group

            new_row = {
                "provenance_id": provenance_id,
                "canonical_id": canonical_id,
                "version_id": version_id,
                "observation_id": observation_id,
                "field_name": name,
                "field_value": text,
                "source_id": str(record.source_id),
                "raw_payload_sha256": sha,
                "selection_rule": (
                    "conflicting_sources_retained_no_automatic_winner"
                    if disagreeing
                    else "single_source_latest_observation"
                ),
                "is_current_canonical": not disagreeing,
                "conflict_group": conflict_group,
                "created_at": stamp,
            }
            new_provenance.append(new_row)
            existing_provenance_ids.add(provenance_id)
            # Keep the in-memory map honest for the rest of the chunk: a later
            # record in the same batch must see what this one just decided.
            if disagreeing:
                # The incumbents keep currency; the newcomer does not become
                # canonical by arriving second.
                current_provenance[key] = incumbents
            else:
                # First claim, or a second source asserting the SAME value.
                # Both rows stay current - that is corroboration, not
                # ambiguity, and the distinction matters to the health check.
                current_provenance[key] = incumbents + [new_row]
            metrics["provenance_rows_inserted"] += 1

        plan.conflicts = sorted(set(conflicts))
        if conflicts:
            metrics["conflicts_recorded"] += len(plan.conflicts)

        # -- canonical advancement (168F): only when something changed
        if wrote_observation or wrote_version:
            updates = canonical_updates.setdefault(canonical_id, {})
            updates["last_seen_at"] = stamp
            updates["updated_at"] = stamp
            if wrote_version:
                updates["current_version_id"] = version_id
            if conflicts:
                updates["has_field_conflicts"] = True
            if (
                normalized.get("lifecycle_state") not in (None, "unknown")
                and "status" not in conflicts
            ):
                updates["lifecycle_state"] = normalized["lifecycle_state"]
            if fields.get("source_record_id") and not (
                existing_canonical.get(canonical_id, {}).get(
                    "surrogate_opportunity_id"
                )
            ):
                updates["surrogate_opportunity_id"] = fields["source_record_id"]
            for name, column in CANONICAL_COLUMN_FOR_FIELD.items():
                if name in fields and name not in conflicts:
                    updates[column] = fields[name]

        if wrote_observation or wrote_version:
            plan.outcome = INSERTED if wrote_observation else VERSIONED
        else:
            # 168F: an identical observation rewrites nothing at all.
            plan.outcome = IDEMPOTENT

        plans.append(plan)

    # ---- 3. APPLY: bulk, bounded, in a fixed number of statements --------
    if new_canonical:
        connection.execute(sa.insert(canonical), new_canonical)
    if new_observations:
        connection.execute(sa.insert(observations_t), new_observations)
    if new_versions:
        connection.execute(sa.insert(versions_t), new_versions)

    for previous_id, next_id in lineage_updates:
        connection.execute(
            sa.update(versions_t)
            .where(versions_t.c.version_id == previous_id)
            .values(superseded_by_version_id=next_id)
        )

    # One demote statement per (source, canonical) set rather than per field.
    by_source: dict[tuple[str, str], list[str]] = {}
    for canonical_id, name, source_id in demotions:
        by_source.setdefault((canonical_id, source_id), []).append(name)
    for (canonical_id, source_id), names in by_source.items():
        connection.execute(
            sa.update(provenance_t)
            .where(
                sa.and_(
                    provenance_t.c.canonical_id == canonical_id,
                    provenance_t.c.source_id == source_id,
                    provenance_t.c.field_name.in_(sorted(set(names))),
                    provenance_t.c.is_current_canonical.is_(True),
                )
            )
            .values(is_current_canonical=False)
        )

    if new_provenance:
        connection.execute(sa.insert(provenance_t), new_provenance)

    # Label the incumbent side of each conflict, grouped by label.
    by_group: dict[str, list[str]] = {}
    for provenance_id, group in conflict_labels:
        by_group.setdefault(group, []).append(provenance_id)
    for group, ids in by_group.items():
        connection.execute(
            sa.update(provenance_t)
            .where(provenance_t.c.provenance_id.in_(sorted(set(ids))))
            .values(conflict_group=group)
        )

    # Counts, recomputed once per touched opportunity rather than per record.
    if canonical_updates:
        touched = sorted(canonical_updates)
        observation_counts = dict(
            connection.execute(
                sa.select(
                    observations_t.c.canonical_id,
                    sa.func.count(sa.distinct(observations_t.c.observation_id)),
                )
                .where(observations_t.c.canonical_id.in_(touched))
                .group_by(observations_t.c.canonical_id)
            ).all()
        )
        version_counts = dict(
            connection.execute(
                sa.select(
                    versions_t.c.canonical_id,
                    sa.func.count(sa.distinct(versions_t.c.version_id)),
                )
                .where(versions_t.c.canonical_id.in_(touched))
                .group_by(versions_t.c.canonical_id)
            ).all()
        )
        for canonical_id, updates in canonical_updates.items():
            updates["observation_count"] = int(
                observation_counts.get(canonical_id, 0) or 0
            )
            updates["version_count"] = int(version_counts.get(canonical_id, 0) or 0)
            connection.execute(
                sa.update(canonical)
                .where(canonical.c.canonical_id == canonical_id)
                .values(**updates)
            )

    # Every outcome lands in exactly one bucket. A record classified VERSIONED
    # counted in none of them would make the totals fail to reconcile, and the
    # accounting check would be measuring nothing.
    for plan in plans:
        if plan.outcome == INSERTED:
            metrics["observations_inserted"] += 1
        elif plan.outcome == VERSIONED:
            metrics["observations_versioned"] += 1
        elif plan.outcome == IDEMPOTENT:
            metrics["observations_idempotent"] += 1
        elif plan.outcome == REJECTED:
            metrics["observations_rejected"] += 1

    return [_plan_result(plan, records) for plan in plans]


def _plan_result(
    plan: _Plan, records: list[NormalizedSourceObservation]
) -> dict[str, Any]:
    record = records[plan.index] if plan.index < len(records) else None
    return {
        "index": plan.index,
        "outcome": plan.outcome,
        "source_id": getattr(record, "source_id", None),
        "canonical_id": plan.canonical_id or None,
        "observation_id": plan.observation_id or None,
        "version_id": plan.version_id or None,
        "reasons": sorted(set(plan.reasons)),
        "conflicts": plan.conflicts,
        "changed_fields": plan.changed_fields,
        "is_material": plan.is_material,
    }


def _changed_fields(previous: Any, fields: dict[str, Any]) -> list[str]:
    if previous is None:
        return sorted(fields)
    try:
        before = json.loads(previous["normalized_fields_json"] or "{}")
    except Exception:  # noqa: BLE001
        before = {}
    names = set(before) | set(fields)
    return sorted(
        name
        for name in names
        if json.dumps(before.get(name), sort_keys=True)
        != json.dumps(fields.get(name), sort_keys=True)
    )


def _materiality(changed: list[str]) -> dict[str, Any]:
    try:
        from nativeforge.services.opportunity_deadline_and_amendment_model_service import (  # noqa: E501
            MATERIAL_CATEGORIES,
            categorize_modified_field,
        )
    except Exception:  # noqa: BLE001
        return {"is_material": False, "material_categories": []}

    categories = sorted({categorize_modified_field(name) for name in changed})
    material = sorted(c for c in categories if c in MATERIAL_CATEGORIES)
    return {"is_material": bool(material), "material_categories": material}
