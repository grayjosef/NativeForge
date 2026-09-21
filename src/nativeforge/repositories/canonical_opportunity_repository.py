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

    Delegates to `persist_observations` with a batch of one (Gate 168C). The
    rules that decide identity, lineage, conflict and currency live in exactly
    one place; keeping a second copy here for the single-record case would be
    two encodings of the same semantics, and the one that drifted would not
    announce itself.

    Gate 167 measured this path at 49 SQL statements. The batch writer folds
    the per-field provenance loop into set operations, so the same single
    record now costs a fixed handful - without changing what gets written.

    `identity` comes from `opportunity_identity_versioning_service`; it is not
    recomputed here so that the one identity model stays the one identity
    model. Passing an identity does not assert anything: every branch reads
    the database to decide what actually happens.
    """
    from nativeforge.repositories.canonical_opportunity_batch_repository import (
        INSERTED,
        NormalizedSourceObservation,
        persist_observations,
    )

    outcome = persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=str(source_id or ""),
                normalized=dict(normalized or {}),
                raw_payload_sha256=str(raw_payload_sha256 or ""),
                identity=dict(identity or {}),
                raw_payload_attempt_id=raw_payload_attempt_id,
                source_authority_host=source_authority_host,
                observed_at=observed_at,
                http_status=http_status,
            )
        ],
        now=now,
    )

    record = (outcome.get("results") or [{}])[0]
    metrics = outcome.get("metrics") or {}
    result_outcome = str(record.get("outcome") or "")

    # The Gate 167 result shape, preserved. Callers read these keys.
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "canonical_id": record.get("canonical_id"),
        "source_id": str(source_id or ""),
        "raw_payload_sha256": str(raw_payload_sha256 or ""),
        "observation_id": record.get("observation_id"),
        "version_id": record.get("version_id"),
        "wrote_canonical": bool(metrics.get("canonical_created")),
        "wrote_observation": result_outcome == INSERTED,
        "wrote_version": bool(metrics.get("versions_inserted")),
        "provenance_rows_written": int(
            metrics.get("provenance_rows_inserted") or 0
        ),
        "conflicts_detected": list(record.get("conflicts") or []),
        "rejected_reasons": list(record.get("reasons") or []),
    }
    if result["wrote_version"]:
        result["changed_fields"] = list(record.get("changed_fields") or [])
        result["is_material"] = bool(record.get("is_material"))

    result["identity_outcome"] = _identity_outcome(
        connection=connection,
        canonical_id=record.get("canonical_id"),
        source_id=source_id,
        identity=identity or {},
        outcome=result_outcome,
        created_canonical=result["wrote_canonical"],
    )
    return _json_safe(result)


def _identity_outcome(
    *,
    connection: Any,
    canonical_id: Any,
    source_id: Any,
    identity: dict[str, Any],
    outcome: str,
    created_canonical: bool,
) -> str:
    """What this observation turned out to be, relative to what was known.

    Read after the write, because "is this the same opportunity another source
    already described" is a question about the graph, not about the record.
    """
    from nativeforge.repositories.canonical_opportunity_batch_repository import (
        IDEMPOTENT,
        REJECTED,
    )

    if outcome == REJECTED:
        return UNCERTAIN_IDENTITY
    if bool(identity.get("is_provisional")):
        return UNCERTAIN_IDENTITY
    if created_canonical:
        return NEW_OPPORTUNITY
    if outcome == IDEMPOTENT:
        return SAME_SOURCE_SAME_RECORD

    try:
        observations = _observations_table()
        sources = connection.execute(
            sa.select(sa.distinct(observations.c.source_id)).where(
                observations.c.canonical_id == str(canonical_id)
            )
        ).scalars().all()
    except Exception:  # noqa: BLE001 - an unreadable graph classifies nothing
        return UNCERTAIN_IDENTITY

    if len({str(s) for s in sources}) > 1:
        return SAME_OPPORTUNITY_DIFFERENT_SOURCE
    return AMENDMENT_OR_VERSION


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
