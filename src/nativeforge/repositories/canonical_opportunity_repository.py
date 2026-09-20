"""The canonical opportunity write path (Gate 167D/E/F).

One entry point: `record_observation`. A source says it saw a record, and the
graph absorbs that without losing what it already knew.

## Every identifier is derived, never allocated

```text
canonical_id    L1:{normalized_number}|{doc_type}   or  L4:{fuzzy_key}
observation_id  sha256(source_id | source_record_id | payload_sha256)
version_id      sha256(canonical_id | content_fingerprint)
provenance_id   sha256(version_id | field_name)
```

A random UUID would make the same evidence produce different rows on every
run, and Gate 167M has to rebuild this graph from evidence alone and get the
SAME identities back. Derivation is what makes that possible - and it is also
what makes replay idempotent without a single comparison in application code,
because the second write collides with the first on its own primary key.

## What the writer will not do

It never updates a version in place, never deletes an observation, and never
overwrites a canonical field whose provenance came from another source. A
disagreement between two sources is recorded as two provenance rows sharing a
`conflict_group`, because the alternative - last writer wins - throws away the
fact that anyone disagreed, and that fact is often the interesting one.

It never touches `nf_source_collection_raw_payloads`. The payload store is the
evidence ledger; this graph references it and adds nothing to it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_canonical_opportunity_repository_v1"

CANONICAL = "nf_canonical_opportunities"
OBSERVATIONS = "nf_opportunity_source_observations"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

#: How this observation relates to what the graph already holds. Gate 167D
#: names these; the writer reports which one it decided and why.
SAME_SOURCE_SAME_RECORD = "same_source_same_record"
SAME_OPPORTUNITY_DIFFERENT_SOURCE = "same_opportunity_different_source"
AMENDMENT_OR_VERSION = "amendment_or_version"
RECURRING_PROGRAM = "recurring_program"
NEW_OPPORTUNITY = "new_opportunity"
UNCERTAIN_IDENTITY = "uncertain_identity"

IDENTITY_OUTCOMES: tuple[str, ...] = (
    SAME_SOURCE_SAME_RECORD,
    SAME_OPPORTUNITY_DIFFERENT_SOURCE,
    AMENDMENT_OR_VERSION,
    RECURRING_PROGRAM,
    NEW_OPPORTUNITY,
    UNCERTAIN_IDENTITY,
)

#: Fields that are true OF A SOURCE rather than of the opportunity.
#:
#: Two sources calling one opportunity by different internal ids are not
#: disagreeing about the world - Grants.gov's numeric id and another
#: publisher's record key are different namespaces, and flagging that as a
#: conflict would make every multi-source opportunity permanently contested
#: while telling a reader nothing.
#:
#: They still get provenance rows, because "source B calls it B-77" is worth
#: recording. They simply never conflict and never reach a canonical column.
SOURCE_SCOPED_FIELDS: frozenset[str] = frozenset({"source_record_id"})

#: Canonical fields that map onto a column of the canonical row. Everything
#: else lives in the version's normalized field set and in provenance.
CANONICAL_COLUMN_FOR_FIELD: dict[str, str] = {
    "title": "title",
    "funder_agency_code": "funder_agency_code",
    "funder_agency_name": "funder_agency_name",
    "open_date": "current_open_date",
    "close_date": "current_close_date",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_canonical_id(
    *, identity_layer: str, composite_key: Any = None, fuzzy_key: Any = None
) -> str:
    """Readable and deterministic. The layer is part of the id on purpose.

    An L4 row that is later promoted to L1 gets a DIFFERENT canonical id, and
    that is correct: promotion is a change of identity basis, not a rename, and
    hiding it behind one id would make the promotion unobservable.
    """
    if str(identity_layer) == "L4":
        return f"L4:{fuzzy_key}"
    return f"L1:{composite_key}"


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


def record_observation(
    *,
    connection: Any,
    source_id: Any,
    normalized: dict[str, Any],
    raw_payload_sha256: Any,
    raw_payload_attempt_id: Any = None,
    source_authority_host: Any = None,
    observed_at: Any = None,
    http_status: Any = None,
    identity: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Absorb one source record. Idempotent for identical evidence.

    `identity` comes from `opportunity_identity_versioning_service`; it is not
    recomputed here so that the one identity model stays the one identity
    model. Passing an identity does not assert anything - every branch below
    reads the database to decide what actually happens.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    fields = dict(normalized.get("fields") or {})
    fingerprint = str(normalized.get("content_fingerprint") or "")
    sha = str(raw_payload_sha256 or "")

    identity = identity or {}
    layer = str(identity.get("identity_layer") or "L1")
    canonical_id = build_canonical_id(
        identity_layer=layer,
        composite_key=identity.get("composite_key"),
        fuzzy_key=identity.get("fuzzy_key"),
    )
    number = str(identity.get("normalized_opportunity_number") or "")
    doc_type = str(identity.get("doc_type") or fields.get("doc_type") or "unknown")

    canonical = _canonical_table()
    observations = _observations_table()
    versions = _versions_table()
    provenance = _provenance_table()

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "canonical_id": canonical_id,
        "source_id": str(source_id or ""),
        "raw_payload_sha256": sha,
        "wrote_canonical": False,
        "wrote_observation": False,
        "wrote_version": False,
        "provenance_rows_written": 0,
        "conflicts_detected": [],
    }

    existing = connection.execute(
        sa.select(canonical).where(canonical.c.canonical_id == canonical_id)
    ).mappings().first()

    # ---- 1. the canonical row ---------------------------------------
    if existing is None:
        connection.execute(
            sa.insert(canonical).values(
                canonical_id=canonical_id,
                normalized_opportunity_number=number,
                doc_type=doc_type,
                identity_layer=layer,
                is_provisional=bool(identity.get("is_provisional")),
                opportunity_number_group=number,
                surrogate_opportunity_id=identity.get("opportunity_id"),
                lifecycle_state=str(
                    normalized.get("lifecycle_state") or "unknown"
                ),
                first_seen_at=stamp,
                last_seen_at=stamp,
                observation_count=0,
                version_count=0,
                has_field_conflicts=False,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        result["wrote_canonical"] = True
        result["identity_outcome"] = NEW_OPPORTUNITY
    else:
        result["identity_outcome"] = None  # decided below

    # ---- 2. the observation ------------------------------------------
    record_id = str(fields.get("source_record_id") or "")
    observation_id = _digest(source_id, record_id, sha)
    seen = connection.execute(
        sa.select(observations).where(
            observations.c.observation_id == observation_id
        )
    ).mappings().first()

    if seen is None:
        connection.execute(
            sa.insert(observations).values(
                observation_id=observation_id,
                canonical_id=canonical_id,
                source_id=str(source_id or ""),
                source_record_id=record_id or None,
                source_opportunity_number=fields.get("opportunity_number"),
                source_authority_host=source_authority_host,
                raw_payload_sha256=sha,
                raw_payload_attempt_id=raw_payload_attempt_id,
                parser_name=str(normalized.get("parser_name") or "unknown"),
                parser_version=str(normalized.get("parser_version") or "0"),
                observed_at=observed_at or stamp,
                source_record_fingerprint=fingerprint,
                observation_state="recorded",
                # NULL stays NULL. Gate 163 never captured it.
                http_status=http_status,
                created_at=stamp,
            )
        )
        result["wrote_observation"] = True
    result["observation_id"] = observation_id

    # ---- 3. the version ----------------------------------------------
    version_id = _digest(canonical_id, fingerprint)
    prior = connection.execute(
        sa.select(versions)
        .where(versions.c.canonical_id == canonical_id)
        .order_by(versions.c.created_at)
    ).mappings().all()
    already = next(
        (row for row in prior if row["version_id"] == version_id), None
    )

    if already is None:
        previous = prior[-1] if prior else None
        changed = _changed_fields(previous, fields)
        # Materiality describes a CHANGE against a prior version. A first
        # sighting has no prior version, so every field reads as "changed" and
        # the deadline category would mark it material - which would fire an
        # "the deadline moved" signal at a Tribe on the day we first saw the
        # opportunity. First discovery is a different event with a different
        # audience, so it is recorded as not-material and says why.
        materiality = (
            _materiality(changed)
            if previous is not None
            else {"is_material": False, "material_categories": []}
        )
        connection.execute(
            sa.insert(versions).values(
                version_id=version_id,
                canonical_id=canonical_id,
                observation_id=observation_id,
                version_key=identity.get("version_key"),
                revision=identity.get("revision"),
                doc_type=doc_type,
                normalized_fields_json=json.dumps(fields, sort_keys=True),
                content_fingerprint=fingerprint,
                supersedes_version_id=(
                    previous["version_id"] if previous is not None else None
                ),
                superseded_by_version_id=None,
                is_material=materiality["is_material"],
                material_categories_json=json.dumps(
                    materiality["material_categories"], sort_keys=True
                ),
                # What this version established (first) or altered (later).
                changed_fields_json=json.dumps(sorted(changed), sort_keys=True),
                parser_version=str(normalized.get("parser_version") or "0"),
                created_at=stamp,
            )
        )
        if previous is not None:
            connection.execute(
                sa.update(versions)
                .where(versions.c.version_id == previous["version_id"])
                .values(superseded_by_version_id=version_id)
            )
        result["wrote_version"] = True
        result["changed_fields"] = sorted(changed)
        result["is_material"] = materiality["is_material"]
    result["version_id"] = version_id

    # ---- 4. field provenance ------------------------------------------
    written = 0
    conflicts: list[str] = []
    for name, value in sorted(fields.items()):
        text = json.dumps(value) if isinstance(value, list) else str(value)
        provenance_id = _digest(version_id, name)
        exists = connection.execute(
            sa.select(provenance.c.provenance_id).where(
                provenance.c.provenance_id == provenance_id
            )
        ).first()
        if exists is not None:
            continue

        # This source has made a new claim about this field, so its OWN
        # previous claim stops being current. Without this demotion a source
        # that moved a deadline leaves both dates marked current, and "the
        # current close date" has two answers from one source - which is not a
        # conflict, just a stale row pretending to be a fact.
        connection.execute(
            sa.update(provenance)
            .where(
                sa.and_(
                    provenance.c.canonical_id == canonical_id,
                    provenance.c.field_name == name,
                    provenance.c.source_id == str(source_id or ""),
                    provenance.c.is_current_canonical.is_(True),
                )
            )
            .values(is_current_canonical=False)
        )

        # Does another SOURCE still assert a different value for this field?
        # Read AFTER the demotion, so this source's own superseded rows can
        # never be mistaken for somebody disagreeing.
        others = connection.execute(
            sa.select(provenance).where(
                sa.and_(
                    provenance.c.canonical_id == canonical_id,
                    provenance.c.field_name == name,
                    provenance.c.is_current_canonical.is_(True),
                )
            )
        ).mappings().all()
        disagreeing = (
            []
            if name in SOURCE_SCOPED_FIELDS
            else [
                row
                for row in others
                if row["field_value"] != text
                and str(row["source_id"]) != str(source_id or "")
            ]
        )
        conflict_group = _digest(canonical_id, name) if disagreeing else None
        if disagreeing:
            conflicts.append(name)
            # The incumbent keeps its group label so both sides of the
            # disagreement are findable by one indexed lookup.
            for row in disagreeing:
                connection.execute(
                    sa.update(provenance)
                    .where(provenance.c.provenance_id == row["provenance_id"])
                    .values(conflict_group=conflict_group)
                )

        connection.execute(
            sa.insert(provenance).values(
                provenance_id=provenance_id,
                canonical_id=canonical_id,
                version_id=version_id,
                observation_id=observation_id,
                field_name=name,
                field_value=text,
                source_id=str(source_id or ""),
                raw_payload_sha256=sha,
                selection_rule=(
                    "conflicting_sources_retained_no_automatic_winner"
                    if disagreeing
                    else "single_source_latest_observation"
                ),
                # A value that disagrees with an existing current value does
                # NOT become current by arriving second. Nothing is overwritten
                # and no winner is picked here; Gate 167I requires the
                # disagreement to survive, not to be resolved.
                is_current_canonical=not disagreeing,
                conflict_group=conflict_group,
                created_at=stamp,
            )
        )
        written += 1

    result["provenance_rows_written"] = written
    result["conflicts_detected"] = sorted(set(conflicts))

    # ---- 5. advance the canonical row --------------------------------
    counts = connection.execute(
        sa.select(
            sa.func.count(sa.distinct(observations.c.observation_id))
        ).where(observations.c.canonical_id == canonical_id)
    ).scalar()
    version_total = connection.execute(
        sa.select(sa.func.count(sa.distinct(versions.c.version_id))).where(
            versions.c.canonical_id == canonical_id
        )
    ).scalar()

    updates: dict[str, Any] = {
        "current_version_id": version_id,
        "last_seen_at": stamp,
        "observation_count": int(counts or 0),
        "version_count": int(version_total or 0),
        "updated_at": stamp,
    }
    if conflicts:
        updates["has_field_conflicts"] = True
    # Lifecycle is derived from `status`, so it inherits that field's
    # contested-ness. Advancing it while two sources disagree about the status
    # would resolve the disagreement by arrival order in the one column a
    # reader is most likely to trust.
    if (
        normalized.get("lifecycle_state") not in (None, "unknown")
        and "status" not in conflicts
    ):
        updates["lifecycle_state"] = normalized["lifecycle_state"]
    # The surrogate is set once, by the first source to supply one, and is
    # never rewritten by a later source's own record key - those are different
    # namespaces and the second would silently replace the first.
    if fields.get("source_record_id") and not (
        existing and existing.get("surrogate_opportunity_id")
    ):
        updates["surrogate_opportunity_id"] = fields["source_record_id"]

    # Only fields whose provenance row is current may reach the canonical row.
    for name, column in CANONICAL_COLUMN_FOR_FIELD.items():
        if name not in fields or name in conflicts:
            continue
        updates[column] = fields[name]

    connection.execute(
        sa.update(canonical)
        .where(canonical.c.canonical_id == canonical_id)
        .values(**updates)
    )

    # ---- 6. what this observation turned out to be -------------------
    if result["identity_outcome"] is None:
        prior_sources = connection.execute(
            sa.select(sa.distinct(observations.c.source_id)).where(
                observations.c.canonical_id == canonical_id
            )
        ).scalars().all()
        if bool(identity.get("is_provisional")):
            result["identity_outcome"] = UNCERTAIN_IDENTITY
        elif not result["wrote_version"] and not result["wrote_observation"]:
            result["identity_outcome"] = SAME_SOURCE_SAME_RECORD
        elif len({str(s) for s in prior_sources}) > 1:
            result["identity_outcome"] = SAME_OPPORTUNITY_DIFFERENT_SOURCE
        elif result["wrote_version"]:
            result["identity_outcome"] = AMENDMENT_OR_VERSION
        else:
            result["identity_outcome"] = SAME_SOURCE_SAME_RECORD

    connection.commit()
    return _json_safe(result)


def _changed_fields(previous: Any, fields: dict[str, Any]) -> list[str]:
    if previous is None:
        return sorted(fields)
    try:
        before = json.loads(previous["normalized_fields_json"] or "{}")
    except Exception:  # noqa: BLE001 - an unreadable prior version compares as empty
        before = {}
    names = set(before) | set(fields)
    return sorted(
        name
        for name in names
        if json.dumps(before.get(name), sort_keys=True)
        != json.dumps(fields.get(name), sort_keys=True)
    )


def _materiality(changed: list[str]) -> dict[str, Any]:
    """Materiality from the Gate 92G model, over canonical field names.

    The amendment model categorizes an agency's own `modified_fields` strings.
    Canonical field names are fed through the same categorizer so one rule
    decides what counts as material, rather than a second list here.
    """
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
