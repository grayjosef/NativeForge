"""Persisting change events and conflict state (Gate 170C/G/H/I).

This does **not** diff. Gate 168's writer already compares consecutive
versions and stores `changed_fields_json`; that comparison stays the only
comparison. This reads it, types each field move through the taxonomy, and
records the result as a queryable event.

A second diff beside a sound one would put two answers in the graph, and the
one that drifted would not announce itself.

## Event identity is derived, so replay collides with itself

```text
change_event_id = sha256(canonical_id | prior_version_id | new_version_id | field)
```

Gate 170G requires zero duplicate events on replay. That is a primary-key
collision rather than a comparison somebody has to remember to write - the
same property that makes Gate 167's graph rebuildable.

## Corroboration is an update, not a second event

When a second source reports the same semantic change - same field, same
old value, same new value - it does not create a new event. It increments
`corroborating_source_count` and extends `last_reported_at`.

The alternative is an alert per source, which at thousands of sources means a
Tribe is told six times that one deadline moved. `first_reported_at` and
`last_reported_at` keep the timing of each report visible, so "who saw it
first" is still answerable.

## Conflict state has a duration

One row per contested field, with `first_detected_at` and `last_observed_at`.
Two sources flapping is one ongoing conflict with a moving timestamp, not a
new row per poll. A resolution needs a signer, a rule and evidence, and
migration 0055 refuses the alternative.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_opportunity_change_repository_v1"

EVENTS = "nf_opportunity_change_events"
CONFLICTS = "nf_opportunity_field_conflicts"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

NO_CONFLICT = "NO_CONFLICT"
OPEN_CONFLICT = "OPEN_CONFLICT"
RESOLVED_CONFLICT = "RESOLVED_CONFLICT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

CONFLICT_STATES: tuple[str, ...] = (
    NO_CONFLICT,
    OPEN_CONFLICT,
    RESOLVED_CONFLICT,
    REVIEW_REQUIRED,
)


class ChangeWriteRefused(RuntimeError):
    """Raised instead of writing something the model must not contain."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _table(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


def _events_table() -> sa.Table:
    return _table(
        EVENTS,
        sa.Column("change_event_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("prior_version_id", sa.Text()),
        sa.Column("new_version_id", sa.Text()),
        sa.Column("observation_id", sa.Text()),
        sa.Column("field_name", sa.Text()),
        sa.Column("change_type", sa.Text()),
        sa.Column("materiality", sa.Text()),
        sa.Column("materiality_rule", sa.Text()),
        sa.Column("prior_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("raw_payload_sha256", sa.Text()),
        sa.Column("deadline_shape", sa.Text()),
        sa.Column("detected_at", sa.DateTime(timezone=True)),
        sa.Column("effective_date", sa.Text()),
        sa.Column("corroborating_source_count", sa.Integer()),
        sa.Column("corroborated_by_json", sa.Text()),
        sa.Column("first_reported_at", sa.DateTime(timezone=True)),
        sa.Column("last_reported_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _conflicts_table() -> sa.Table:
    return _table(
        CONFLICTS,
        sa.Column("conflict_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("field_name", sa.Text()),
        sa.Column("conflict_state", sa.Text()),
        sa.Column("competing_values_json", sa.Text()),
        sa.Column("competing_source_count", sa.Integer()),
        sa.Column("first_detected_at", sa.DateTime(timezone=True)),
        sa.Column("last_observed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.Text()),
        sa.Column("resolution_rule", sa.Text()),
        sa.Column("resolution_evidence_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def build_change_event_id(
    *, canonical_id: Any, prior_version_id: Any, new_version_id: Any, field_name: Any
) -> str:
    return _digest(canonical_id, prior_version_id, new_version_id, field_name)


def detect_changes_for_version(
    *,
    connection: Any,
    canonical_id: Any,
    new_version_id: Any,
    deadline_shape: Any = None,
) -> list[dict[str, Any]]:
    """Type the field moves Gate 168 already recorded for this version.

    Reads `changed_fields_json` from the version row rather than recomputing a
    diff. Returns classified changes; writes nothing.
    """
    from nativeforge.services.opportunity_change_taxonomy_service import (
        classify_change,
    )

    versions = _table(
        VERSIONS,
        sa.Column("version_id", sa.Text()),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("observation_id", sa.Text()),
        sa.Column("normalized_fields_json", sa.Text()),
        sa.Column("changed_fields_json", sa.Text()),
        sa.Column("supersedes_version_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    row = connection.execute(
        sa.select(versions).where(versions.c.version_id == str(new_version_id))
    ).mappings().first()
    if row is None:
        return []

    def load(text: Any, default: Any) -> Any:
        try:
            return json.loads(text or "")
        except Exception:  # noqa: BLE001
            return default

    new_fields = load(row["normalized_fields_json"], {})
    changed = load(row["changed_fields_json"], [])
    prior_id = row["supersedes_version_id"]

    prior_fields: dict[str, Any] = {}
    if prior_id:
        prior_row = connection.execute(
            sa.select(versions.c.normalized_fields_json).where(
                versions.c.version_id == str(prior_id)
            )
        ).first()
        if prior_row is not None:
            prior_fields = load(prior_row[0], {})

    is_first = prior_id is None

    # The shape is DERIVABLE from the version's own fields, so a caller who
    # does not pass one still gets a shape on the event. The backfill is
    # exactly that caller, and without this every backfilled deadline change
    # carried no shape - which the health check named as
    # `deadline_change_with_no_recorded_shape` rather than letting pass.
    if deadline_shape is None:
        from nativeforge.repositories.canonical_opportunity_batch_repository import (
            deadline_shape_for,
        )

        deadline_shape = deadline_shape_for(new_fields)

    classified: list[dict[str, Any]] = []
    for field in sorted(changed):
        # Source-scoped fields are facts about a source, not the opportunity.
        # Gate 167 keeps them out of conflict detection; they stay out of
        # change events for the same reason.
        from nativeforge.repositories.canonical_opportunity_repository import (
            SOURCE_SCOPED_FIELDS,
        )

        if field in SOURCE_SCOPED_FIELDS:
            continue
        change = classify_change(
            field_name=field,
            prior_value=prior_fields.get(field),
            new_value=new_fields.get(field),
            is_first_observation=is_first,
            deadline_shape=deadline_shape,
        )
        change["canonical_id"] = str(canonical_id)
        change["prior_version_id"] = str(prior_id) if prior_id else None
        change["new_version_id"] = str(new_version_id)
        change["observation_id"] = str(row["observation_id"])
        classified.append(change)
    return classified


def backfill_change_events(
    *, connection: Any, limit: int = 100000, now: Any = None
) -> dict[str, Any]:
    """Classify versions that have no change events yet.

    The write path types changes when it CREATES a version, which leaves every
    version written before Gate 170 with no events - including the real
    Grants.gov opportunity's first version. Paying a read per observation to
    notice that would undo Gate 168's work, so the gap is closed by a backfill.

    Idempotent: it selects versions with no event and inserts in bulk, so a
    second run writes nothing.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    events = _events_table()
    versions = _table(
        VERSIONS,
        sa.Column("version_id", sa.Text()),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("observation_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    observations = _table(
        "nf_opportunity_source_observations",
        sa.Column("observation_id", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("raw_payload_sha256", sa.Text()),
    )

    missing = connection.execute(
        sa.select(versions)
        .where(
            ~versions.c.version_id.in_(
                sa.select(events.c.new_version_id).distinct()
            )
        )
        .order_by(versions.c.created_at, versions.c.version_id)
        .limit(limit)
    ).mappings().all()

    written = 0
    considered = 0
    for version in missing:
        changes = detect_changes_for_version(
            connection=connection,
            canonical_id=version["canonical_id"],
            new_version_id=version["version_id"],
        )
        considered += len(changes)
        if not changes:
            continue
        observation = connection.execute(
            sa.select(observations).where(
                observations.c.observation_id == str(version["observation_id"])
            )
        ).mappings().first()
        if observation is None:
            continue
        result = record_change_events(
            connection=connection,
            changes=changes,
            source_id=observation["source_id"],
            raw_payload_sha256=observation["raw_payload_sha256"],
            now=stamp,
        )
        written += int(result["events_inserted"])

    if written:
        connection.commit()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "versions_without_events": len(missing),
            "changes_considered": considered,
            "events_written": written,
            "is_idempotent": True,
        }
    )


def record_change_events(
    *,
    connection: Any,
    changes: list[dict[str, Any]],
    source_id: Any,
    raw_payload_sha256: Any,
    now: Any = None,
) -> dict[str, Any]:
    """Persist classified changes. Idempotent; corroboration is an update.

    Raises rather than writing a classification that cannot be argued with -
    migration 0055's CHECK refuses the same thing at rest, and this is the
    path callers use.
    """
    from nativeforge.services.opportunity_change_taxonomy_service import (
        change_invariant_failures,
    )

    stamp = now or dt.datetime.now(dt.UTC)
    sha = str(raw_payload_sha256 or "")
    table = _events_table()

    if changes and len(sha) != 64:
        raise ChangeWriteRefused(
            [f"a_change_event_must_name_its_evidence:sha_length_{len(sha)}"]
        )

    inserted = 0
    corroborated = 0
    already = 0
    written_ids: list[str] = []
    refusals: list[str] = []

    for change in changes or []:
        failures = change_invariant_failures(change)
        if failures:
            refusals.extend(failures)
            continue

        event_id = build_change_event_id(
            canonical_id=change["canonical_id"],
            prior_version_id=change.get("prior_version_id"),
            new_version_id=change["new_version_id"],
            field_name=change["field_name"],
        )
        written_ids.append(event_id)

        existing = connection.execute(
            sa.select(table).where(table.c.change_event_id == event_id)
        ).mappings().first()

        if existing is not None:
            # Same event. Either the same source replaying - which changes
            # nothing at all - or a different source corroborating it.
            if str(existing["source_id"]) == str(source_id):
                already += 1
                continue
            try:
                sources = set(
                    json.loads(existing["corroborated_by_json"] or "[]")
                )
            except Exception:  # noqa: BLE001
                sources = set()
            if str(source_id) in sources:
                already += 1
                continue
            sources.add(str(source_id))
            connection.execute(
                sa.update(table)
                .where(table.c.change_event_id == event_id)
                .values(
                    corroborating_source_count=len(sources) + 1,
                    corroborated_by_json=json.dumps(sorted(sources)),
                    last_reported_at=stamp,
                )
            )
            corroborated += 1
            continue

        connection.execute(
            sa.insert(table).values(
                change_event_id=event_id,
                canonical_id=change["canonical_id"],
                prior_version_id=change.get("prior_version_id"),
                new_version_id=change["new_version_id"],
                observation_id=change["observation_id"],
                field_name=change["field_name"],
                change_type=change["change_type"],
                materiality=change["materiality"],
                materiality_rule=change.get("materiality_rule"),
                prior_value=(
                    None
                    if change.get("prior_value") is None
                    else str(change["prior_value"])
                ),
                new_value=(
                    None
                    if change.get("new_value") is None
                    else str(change["new_value"])
                ),
                source_id=str(source_id),
                raw_payload_sha256=sha,
                deadline_shape=change.get("deadline_shape"),
                detected_at=stamp,
                effective_date=change.get("effective_date"),
                corroborating_source_count=1,
                corroborated_by_json=json.dumps([]),
                first_reported_at=stamp,
                last_reported_at=stamp,
                created_at=stamp,
            )
        )
        inserted += 1

    if refusals:
        raise ChangeWriteRefused(sorted(set(refusals)))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "events_inserted": inserted,
            "events_corroborated": corroborated,
            "events_already_present": already,
            "event_ids": sorted(set(written_ids)),
            "changes_considered": len(changes or []),
        }
    )


def sync_field_conflicts(
    *, connection: Any, canonical_id: Any, now: Any = None
) -> dict[str, Any]:
    """Refresh conflict state from the provenance rows that already exist.

    Composes, rather than keeping a second account of who disagrees. The facts
    stay in field provenance; this records the DISAGREEMENT - when it started,
    whether it is still live, and how many sources are on each side.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    key = str(canonical_id or "")
    conflicts = _conflicts_table()

    provenance = _table(
        PROVENANCE,
        sa.Column("canonical_id", sa.Text()),
        sa.Column("field_name", sa.Text()),
        sa.Column("field_value", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("is_current_canonical", sa.Boolean()),
        sa.Column("conflict_group", sa.Text()),
    )

    rows = connection.execute(
        sa.select(provenance).where(provenance.c.canonical_id == key)
    ).mappings().all()

    # A field is contested when two DIFFERENT sources assert different values
    # and at least one of them is still a live claim.
    by_field: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        if not row["conflict_group"]:
            continue
        field = str(row["field_name"])
        value = str(row["field_value"])
        by_field.setdefault(field, {}).setdefault(value, set()).add(
            str(row["source_id"])
        )

    opened = 0
    updated = 0
    resolved = 0

    for field, values in sorted(by_field.items()):
        competing = {v: sorted(s) for v, s in values.items() if s}
        source_count = len({s for sources in values.values() for s in sources})
        conflict_id = _digest(key, field)
        state = OPEN_CONFLICT if len(competing) > 1 else NO_CONFLICT

        existing = connection.execute(
            sa.select(conflicts).where(conflicts.c.conflict_id == conflict_id)
        ).mappings().first()

        payload = json.dumps(competing, sort_keys=True)

        if existing is None:
            if state == NO_CONFLICT:
                continue
            connection.execute(
                sa.insert(conflicts).values(
                    conflict_id=conflict_id,
                    canonical_id=key,
                    field_name=field,
                    conflict_state=state,
                    competing_values_json=payload,
                    competing_source_count=max(source_count, 2),
                    first_detected_at=stamp,
                    last_observed_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            opened += 1
            continue

        # An existing conflict row. `first_detected_at` is never rewritten -
        # it is the answer to "how long has this been wrong", and moving it
        # would erase the duration.
        if state == NO_CONFLICT and existing["conflict_state"] == OPEN_CONFLICT:
            connection.execute(
                sa.update(conflicts)
                .where(conflicts.c.conflict_id == conflict_id)
                .values(
                    conflict_state=RESOLVED_CONFLICT,
                    competing_values_json=payload,
                    last_observed_at=stamp,
                    resolved_at=stamp,
                    resolved_by="derived:sources_now_agree",
                    resolution_rule="sources_converged_without_human_intervention",
                    resolution_evidence_json=payload,
                    updated_at=stamp,
                )
            )
            resolved += 1
            continue

        if payload != str(existing["competing_values_json"] or ""):
            connection.execute(
                sa.update(conflicts)
                .where(conflicts.c.conflict_id == conflict_id)
                .values(
                    competing_values_json=payload,
                    competing_source_count=max(source_count, 2),
                    last_observed_at=stamp,
                    updated_at=stamp,
                )
            )
            updated += 1
        else:
            # Unchanged disagreement: only the "still true" timestamp moves.
            connection.execute(
                sa.update(conflicts)
                .where(conflicts.c.conflict_id == conflict_id)
                .values(last_observed_at=stamp)
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_id": key,
            "conflicts_opened": opened,
            "conflicts_updated": updated,
            "conflicts_resolved": resolved,
            "contested_fields": sorted(by_field),
        }
    )


def resolve_conflict(
    *,
    connection: Any,
    canonical_id: Any,
    field_name: Any,
    resolved_by: Any,
    rule: Any,
    evidence: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Record a deliberate resolution. Needs a signer, a rule and evidence."""
    stamp = now or dt.datetime.now(dt.UTC)
    if not str(resolved_by or "").strip() or not str(rule or "").strip():
        raise ChangeWriteRefused(["a_resolution_must_name_who_and_by_what_rule"])
    if not evidence:
        raise ChangeWriteRefused(["a_resolution_must_carry_evidence"])

    conflicts = _conflicts_table()
    conflict_id = _digest(str(canonical_id), str(field_name))
    result = connection.execute(
        sa.update(conflicts)
        .where(
            sa.and_(
                conflicts.c.conflict_id == conflict_id,
                conflicts.c.resolved_at.is_(None),
            )
        )
        .values(
            conflict_state=RESOLVED_CONFLICT,
            resolved_at=stamp,
            resolved_by=str(resolved_by),
            resolution_rule=str(rule),
            resolution_evidence_json=json.dumps(
                evidence, sort_keys=True, default=str
            ),
            last_observed_at=stamp,
            updated_at=stamp,
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "conflict_id": conflict_id,
            "resolved": int(result.rowcount or 0) == 1,
            "resolved_by": str(resolved_by),
            "rule": str(rule),
            "rows_deleted": 0,
            "competing_facts_preserved": True,
        }
    )


def list_change_events(
    *,
    connection: Any,
    canonical_id: Any = None,
    materiality: Any = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Change history, newest first. Indexed on both filters."""
    table = _events_table()
    query = sa.select(table)
    clauses = []
    if canonical_id:
        clauses.append(table.c.canonical_id == str(canonical_id))
    if materiality:
        clauses.append(table.c.materiality == str(materiality))
    if clauses:
        query = query.where(sa.and_(*clauses))
    return [
        dict(row)
        for row in connection.execute(
            query.order_by(table.c.detected_at.desc(), table.c.change_event_id)
            .limit(limit)
        )
        .mappings()
        .all()
    ]


def describe_conflicts(
    *, connection: Any, canonical_id: Any = None, open_only: bool = True
) -> list[dict[str, Any]]:
    table = _conflicts_table()
    query = sa.select(table)
    clauses = []
    if canonical_id:
        clauses.append(table.c.canonical_id == str(canonical_id))
    if open_only:
        clauses.append(table.c.conflict_state == OPEN_CONFLICT)
    if clauses:
        query = query.where(sa.and_(*clauses))
    return [
        dict(row)
        for row in connection.execute(query).mappings().all()
    ]
