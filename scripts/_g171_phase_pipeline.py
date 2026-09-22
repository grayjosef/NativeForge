"""Gate 171J/K/N: the persisted payloads through the whole fabric. No network.

Reads the two Gate 171 payloads out of storage and pushes them through the
EXISTING path - Gate 167/168's canonical write, Gate 169's identity, Gate
170's change intelligence - rather than a parallel one built for new sources.
That is the actual claim of this gate: three heterogeneous source families
flow through ONE fabric.

## What it refuses to do

It does not fetch, it does not look for an overlap, and it does not force one.
`REAL_OVERLAP_OBSERVED` is whatever the identity layer says with no thumb on
the scale - Gate 171J says false is an acceptable answer, and an overlap
manufactured to make a report look better would be the one result in this
campaign that could not be trusted.

Idempotent: run twice and the second run writes nothing, because record ids
and version ids are derived from content rather than allocated.
"""

from __future__ import annotations

import importlib
import json
import socket
import sys
import time
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 pipeline makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402,E501
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.opportunity_change_repository import (  # noqa: E402
    describe_conflicts,
    list_change_events,
    sync_field_conflicts,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    identity_for_normalized,
    normalized_envelope_for,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
ADAPTER_PACKAGE = "nativeforge.services.source_adapters"

GATE171_SOURCES = (
    "nf-seed-2026-fed-007",
    "nf-seed-2026-api-federal-register-documents",
)
GRANTS_GOV = "nf-seed-2026-api-grants-gov-search2"

#: 171J's vocabulary. Every real observation lands in exactly one.
NEW_CANONICAL = "NEW_CANONICAL"
MATCH_EXISTING = "MATCH_EXISTING_CANONICAL"
PROVISIONAL_MATCH = "PROVISIONAL_MATCH"
RELATED = "RELATED"
DISTINCT = "DISTINCT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

PAYLOADS = sa.Table(
    "nf_source_collection_raw_payloads",
    sa.MetaData(),
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("attempt_id", sa.Text()),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("response_status", sa.Integer()),
    sa.Column("media_type", sa.Text()),
    sa.Column("body_bytes", sa.LargeBinary()),
    sa.Column("payload_size_bytes", sa.Integer()),
    sa.Column("payload_sha256", sa.Text()),
)

ACTIVE = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_name", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("activation_notes", sa.Text()),
)

OBSERVATIONS = "nf_opportunity_source_observations"
CANONICAL = "nf_canonical_opportunities"
PROVENANCE = "nf_opportunity_field_provenance"


def table(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


out: dict[str, object] = {"schema_version": "nf_gate171_pipeline_v1"}
timings: dict[str, float] = {}

session = SessionLocal()
try:
    # One handle. The repositories commit for themselves; a second
    # transaction wrapped around them is what went inactive.

    # ---- what the graph looked like BEFORE ------------------------
    canonical_t = table(
        CANONICAL,
        sa.Column("canonical_id", sa.Text()),
        sa.Column("identity_layer", sa.Text()),
    )
    observations_t = table(
        OBSERVATIONS,
        sa.Column("observation_id", sa.Text()),
        sa.Column("canonical_id", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("raw_payload_sha256", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
    )
    provenance_t = table(
        PROVENANCE,
        sa.Column("canonical_id", sa.Text()),
        sa.Column("source_id", sa.Text()),
        sa.Column("field_name", sa.Text()),
        sa.Column("is_current_canonical", sa.Boolean()),
    )

    before_ids = {
        str(r[0])
        for r in session.execute(sa.select(canonical_t.c.canonical_id))
    }
    out["canonical_before"] = len(before_ids)

    # ---- read, convert, write -------------------------------------
    per_source: list[dict] = []
    all_observations: list[NormalizedSourceObservation] = []
    read_started = time.perf_counter()

    for source_id in GATE171_SOURCES:
        payload = (
            session.execute(
                sa.select(PAYLOADS)
                .where(
                    sa.and_(
                        PAYLOADS.c.organization_id == DEMO_ORG,
                        PAYLOADS.c.source_id == source_id,
                    )
                )
                .order_by(PAYLOADS.c.received_at.desc())
            )
            .mappings()
            .first()
        )
        activation = (
            session.execute(
                sa.select(ACTIVE).where(
                    sa.and_(
                        ACTIVE.c.organization_id == DEMO_ORG,
                        ACTIVE.c.source_id == source_id,
                    )
                )
            )
            .mappings()
            .first()
        )
        adapter_key = str((activation or {}).get("collection_method") or "")
        adapter = importlib.import_module(f"{ADAPTER_PACKAGE}.{adapter_key}")
        descriptor = adapter.build_descriptor(
            source_id=source_id,
            source_url=str((activation or {}).get("source_url_or_search_target")),
        )
        body = bytes(payload.get("body_bytes") or b"")
        sha = str(payload.get("payload_sha256"))

        records = list(
            adapter.read_records(
                descriptor=descriptor,
                body_bytes=body,
                media_type=descriptor.expected_media_types[0],
                cursor=PageCursor(
                    max_pages=descriptor.max_pages,
                    max_records=descriptor.max_records,
                ),
            )
        )

        built = 0
        for record in records:
            normalized = normalized_envelope_for(record, adapter_key=adapter_key)
            if not normalized.get("parseable"):
                continue
            # The LAYER is chosen from what the record carries. A program page
            # that publishes no opportunity number is L4 provisional, not an
            # L1 with an empty key - which the write path refuses by name.
            identity = identity_for_normalized(normalized, source_id=source_id)
            all_observations.append(
                NormalizedSourceObservation(
                    source_id=source_id,
                    normalized=normalized,
                    raw_payload_sha256=sha,
                    identity=identity,
                    source_authority_host=str(descriptor.base_url)
                    .split("/")[2],
                )
            )
            built += 1

        per_source.append(
            {
                "source_id": source_id,
                "adapter_key": adapter_key,
                "source_name": (activation or {}).get("source_name"),
                "attribution_notice": (activation or {}).get("activation_notes"),
                "payload_sha256": sha,
                "payload_bytes": int(payload.get("payload_size_bytes") or 0),
                "http_status": payload.get("response_status"),
                "records_read": len(records),
                "observations_built": built,
                "documents_seen": sum(len(r.documents) for r in records),
            }
        )
    timings["read_and_convert_seconds"] = round(time.perf_counter() - read_started, 4)

    out["per_source"] = per_source
    out["observations_to_write"] = len(all_observations)

    # ---- the EXISTING canonical write path ------------------------
    write_started = time.perf_counter()
    result = persist_observations(
        connection=session, observations=all_observations
    )
    timings["canonical_write_seconds"] = round(time.perf_counter() - write_started, 4)

    out["write_metrics"] = {
        k: v
        for k, v in (result or {}).items()
        if isinstance(v, int | float | str | bool)
    }

    # ---- 171J: classify every real observation --------------------
    after_ids = {
        str(r[0])
        for r in session.execute(sa.select(canonical_t.c.canonical_id))
    }
    out["canonical_after"] = len(after_ids)
    new_ids = after_ids - before_ids

    rows = (
        session.execute(
            sa.select(
                observations_t.c.observation_id,
                observations_t.c.canonical_id,
                observations_t.c.source_id,
            ).where(observations_t.c.source_id.in_(list(GATE171_SOURCES)))
        )
        .mappings()
        .all()
    )

    # How many DISTINCT sources contribute to each canonical record. That is
    # what "overlap" means here, and it is read back from storage rather than
    # asserted by the writer that just ran.
    contributors: dict[str, set[str]] = {}
    for row in session.execute(
        sa.select(observations_t.c.canonical_id, observations_t.c.source_id)
    ).mappings():
        contributors.setdefault(str(row["canonical_id"]), set()).add(
            str(row["source_id"])
        )

    layers = {
        str(r["canonical_id"]): str(r["identity_layer"])
        for r in session.execute(
            sa.select(canonical_t.c.canonical_id, canonical_t.c.identity_layer)
        ).mappings()
    }

    classification: dict[str, int] = {}
    per_observation: list[dict] = []
    gate171 = set(GATE171_SOURCES)
    for row in rows:
        canonical_id = str(row["canonical_id"])
        sources = contributors.get(canonical_id, set())
        layer = layers.get(canonical_id, "unknown")
        if len(sources) > 1:
            # More than one source on one canonical record IS the overlap.
            # A probabilistic layer never settles, so it is provisional.
            verdict = (
                PROVISIONAL_MATCH if layer in ("L3", "L4") else MATCH_EXISTING
            )
        elif sources <= gate171:
            # Every observation on this record came from a Gate 171 source, so
            # this gate created it. Derived from CONTRIBUTORS rather than from
            # whether this particular run inserted it: a replay must classify
            # the same way it did the first time, and keying on `new_ids`
            # reported 21 MATCH_EXISTING the moment the rows already existed.
            verdict = NEW_CANONICAL
        else:
            verdict = MATCH_EXISTING
        classification[verdict] = classification.get(verdict, 0) + 1
        per_observation.append(
            {
                "source_id": str(row["source_id"]),
                "canonical_id": canonical_id,
                "identity_layer": layer,
                "contributing_sources": sorted(sources),
                "classification": verdict,
            }
        )

    for name in (
        NEW_CANONICAL,
        MATCH_EXISTING,
        PROVISIONAL_MATCH,
        RELATED,
        DISTINCT,
        REVIEW_REQUIRED,
    ):
        classification.setdefault(name, 0)

    out["classification_counts"] = dict(sorted(classification.items()))
    # Idempotency, stated separately from classification. A replay adds no
    # canonical records; the classification above is unchanged by that.
    out["canonical_added_this_run"] = len(new_ids)
    out["wrote_nothing_on_this_run"] = not new_ids
    out["observations_classified"] = len(per_observation)
    out["every_observation_classified"] = len(per_observation) == len(rows)

    multi = sorted(
        canonical_id
        for canonical_id, sources in contributors.items()
        if len(sources) > 1
    )
    out["real_overlap_observed"] = bool(multi)
    out["canonical_records_with_more_than_one_source"] = len(multi)

    # ---- 171K: independent provenance, all three sources ----------
    provenance_rows = (
        session.execute(
            sa.select(
                provenance_t.c.source_id,
                provenance_t.c.field_name,
                provenance_t.c.canonical_id,
                provenance_t.c.is_current_canonical,
            )
        )
        .mappings()
        .all()
    )
    by_source: dict[str, dict] = {}
    for row in provenance_rows:
        entry = by_source.setdefault(
            str(row["source_id"]),
            {"fields": set(), "canonical_ids": set(), "current": 0},
        )
        entry["fields"].add(str(row["field_name"]))
        entry["canonical_ids"].add(str(row["canonical_id"]))
        if row["is_current_canonical"]:
            entry["current"] += 1

    out["provenance_by_source"] = {
        source: {
            "distinct_fields": sorted(entry["fields"]),
            "canonical_records": len(entry["canonical_ids"]),
            "current_rows": entry["current"],
        }
        for source, entry in sorted(by_source.items())
    }
    out["all_three_sources_have_provenance"] = all(
        source in by_source
        for source in (GRANTS_GOV, *GATE171_SOURCES)
    )

    # ---- 171N: change intelligence on the REAL observations -------
    change_started = time.perf_counter()
    touched = sorted({str(r["canonical_id"]) for r in rows})
    # `sync_field_conflicts` commits for itself. A `session.commit()` after it
    # raises `This transaction is inactive` - the first run of this phase died
    # there, AFTER the canonical write had already committed, which is why the
    # graph held 20 rows and no report.
    for canonical_id in touched:
        sync_field_conflicts(connection=session, canonical_id=canonical_id)
    timings["change_and_conflict_seconds"] = round(
        time.perf_counter() - change_started, 4
    )

    # Both readers take a SINGULAR canonical_id and return a LIST. Read the
    # whole set once and filter here rather than issuing one query per
    # opportunity.
    touched_set = set(touched)
    event_rows = [
        e
        for e in list_change_events(connection=session, limit=100000)
        if str(e.get("canonical_id")) in touched_set
    ]
    conflict_rows = [
        c
        for c in describe_conflicts(connection=session, open_only=True)
        if str(c.get("canonical_id")) in touched_set
    ]
    out["real_change_events"] = len(event_rows)
    out["real_change_events_by_type"] = dict(
        sorted(
            {
                str(e.get("change_type")): sum(
                    1
                    for x in event_rows
                    if str(x.get("change_type")) == str(e.get("change_type"))
                )
                for e in event_rows
            }.items()
        )
    )
    out["real_conflicts"] = len(conflict_rows)
    out["real_corroborations"] = sum(
        1
        for e in event_rows
        if int(e.get("corroborating_source_count") or 1) > 1
    )

    out["timings_seconds"] = timings
    if all_observations and timings.get("canonical_write_seconds"):
        out["observations_per_second"] = round(
            len(all_observations) / timings["canonical_write_seconds"], 1
        )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
