"""Gate 171W: the invariants migration 0056 exists to protect. No network.

Gate 167's unique index was correct for a world where every source published
an opportunity number:

```sql
UNIQUE (normalized_opportunity_number, doc_type)
```

Every L4 provisional row stores `''` and `'unknown'`, so the graph could hold
exactly ONE provisional opportunity. The real BIA page took the slot and the
next document-shaped record was an IntegrityError - which, because a failure
rolls back its batch, took 500 valid records with it.

This phase proves the fix and, more importantly, proves the fix did not buy
room by weakening anything:

```text
must now WORK        many L4 rows, distinct canonical ids, all provisional
must STILL REFUSE    a second L1 with the same published number + doc_type
must STILL HOLD      no L4 gains a fake number; L3/L4 never machine-settle
```

Runs against a COPY. Writes nothing real.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 l4 invariants make no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402,E501
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.cross_source_identity_service import (  # noqa: E402
    MACHINE_SETTLEABLE,
    PROVISIONAL_MATCH,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    identity_for_normalized,
    normalized_envelope_for,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    bia_program_page_html as bia,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    federal_register_documents_json as fr,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
INDEX_NAME = "uq_nf_canonical_opportunities_identity"
CANONICAL = "nf_canonical_opportunities"

out: dict[str, object] = {"schema_version": "nf_gate171_l4_invariants_v1"}


def html(title: str, slug: str) -> bytes:
    return (
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"
        f"<p>Program page {slug}.</p></body></html>"
    ).encode()


def json_page(number: str) -> bytes:
    return json.dumps(
        {
            "count": 1,
            "next_page_url": None,
            "results": [
                {
                    "document_number": number,
                    "title": f"Notice {number}",
                    "type": "Notice",
                    "publication_date": "2026-09-01",
                    "agencies": [{"name": "Department of the Interior"}],
                    "html_url": f"https://www.federalregister.gov/d/{number}",
                    "comments_close_on": "2026-11-01",
                }
            ],
        }
    ).encode("utf-8")


def observation_from_html(title: str, slug: str) -> NormalizedSourceObservation:
    records = bia.read_records(
        descriptor=bia.build_descriptor(
            source_id="nf171.inv.document",
            source_url=f"https://www.bia.gov/service/grants/{slug}",
        ),
        body_bytes=html(title, slug),
        media_type="text/html",
        cursor=PageCursor(max_pages=1, max_records=1),
    )
    envelope = normalized_envelope_for(records[0], adapter_key=bia.ADAPTER_KEY)
    return NormalizedSourceObservation(
        source_id="nf171.inv.document",
        normalized=envelope,
        raw_payload_sha256=f"{abs(hash(slug)) % (10**60):064x}",
        identity=identity_for_normalized(envelope, source_id="nf171.inv.document"),
        source_authority_host="inv.invalid",
    )


def observation_from_json(
    number: str, *, source_id: str = "nf171.inv.api"
) -> NormalizedSourceObservation:
    records = fr.read_records(
        descriptor=fr.build_descriptor(source_id=source_id),
        body_bytes=json_page(number),
        media_type="application/json",
        cursor=PageCursor(max_pages=1, max_records=20),
    )
    envelope = normalized_envelope_for(records[0], adapter_key=fr.ADAPTER_KEY)
    return NormalizedSourceObservation(
        source_id=source_id,
        normalized=envelope,
        raw_payload_sha256=f"{abs(hash(number + source_id)) % (10**60):064x}",
        identity=identity_for_normalized(envelope, source_id=source_id),
        source_authority_host="inv.invalid",
    )


session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf171_inv_")
copy_path = os.path.join(work, "inv.db")
shutil.copy2(REPO / db_path, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

canonical = sa.Table(
    CANONICAL,
    sa.MetaData(),
    sa.Column("canonical_id", sa.Text()),
    sa.Column("identity_layer", sa.Text()),
    sa.Column("is_provisional", sa.Boolean()),
    sa.Column("normalized_opportunity_number", sa.Text()),
    sa.Column("doc_type", sa.Text()),
)

with engine.connect() as connection:
    # ---- the index, read from the database itself -----------------
    index_sql = connection.execute(
        sa.text(
            "select sql from sqlite_master where type='index' and name=:name"
        ),
        {"name": INDEX_NAME},
    ).scalar()
    out["index_sql"] = index_sql
    out["index_is_partial"] = bool(
        index_sql and "where" in str(index_sql).lower()
    )
    out["published_identity_unique_index_preserved"] = bool(
        index_sql
        and "unique" in str(index_sql).lower()
        and "normalized_opportunity_number" in str(index_sql)
        and "doc_type" in str(index_sql)
    )

    # ---- many L4 rows -------------------------------------------
    provisional = [
        observation_from_html(f"Program {n}", f"p{n}") for n in range(1, 6)
    ]
    result = persist_observations(connection=connection, observations=provisional)
    outcomes = [str(r.get("outcome")) for r in result.get("results") or []]
    out["l4_write_outcomes"] = outcomes
    out["l4_rows_attempted"] = len(provisional)
    out["l4_rows_inserted"] = outcomes.count("inserted")
    out["multiple_l4_provisional_opportunities_supported"] = (
        outcomes.count("inserted") == len(provisional)
    )
    out["second_l4_record_does_not_collide_with_first"] = (
        len(outcomes) > 1 and outcomes[1] == "inserted"
    )

    rows = (
        connection.execute(
            sa.select(canonical).where(canonical.c.identity_layer == "L4")
        )
        .mappings()
        .all()
    )
    ids = [str(r["canonical_id"]) for r in rows]
    out["l4_rows_in_graph"] = len(rows)
    out["l4_canonical_ids_distinct"] = len(set(ids)) == len(ids)
    out["every_l4_row_is_provisional"] = all(bool(r["is_provisional"]) for r in rows)
    out["no_l4_row_gained_a_number"] = all(
        str(r["normalized_opportunity_number"] or "") == "" for r in rows
    )
    out["every_l4_doc_type_unknown"] = all(
        str(r["doc_type"]) == "unknown" for r in rows
    )

    # ---- L1 uniqueness STILL enforced ----------------------------
    #
    # Two different sources reporting the SAME published number must land on
    # one canonical record, not two. That is the guarantee migration 0056 had
    # to keep, and the only way to know it kept it is to try.
    first = observation_from_json("2026-555001", source_id="nf171.inv.api")
    second = observation_from_json("2026-555001", source_id="nf171.inv.api.two")
    first_result = persist_observations(connection=connection, observations=[first])
    second_result = persist_observations(connection=connection, observations=[second])

    first_row = (first_result.get("results") or [{}])[0]
    second_row = (second_result.get("results") or [{}])[0]
    out["l1_first_outcome"] = str(first_row.get("outcome"))
    out["l1_second_outcome"] = str(second_row.get("outcome"))
    out["l1_same_canonical_id"] = str(first_row.get("canonical_id")) == str(
        second_row.get("canonical_id")
    )
    same_number_rows = connection.execute(
        sa.select(sa.func.count()).select_from(canonical).where(
            sa.and_(
                canonical.c.normalized_opportunity_number == "2026555001",
                canonical.c.doc_type == "notice",
            )
        )
    ).scalar()
    # `notice` is not in the canonical doc vocabulary, so the real stored
    # doc_type is whatever the normalizer mapped it to. Count by number alone
    # as well, which is the claim that matters.
    by_number = connection.execute(
        sa.select(sa.func.count()).select_from(canonical).where(
            canonical.c.normalized_opportunity_number == "2026555001"
        )
    ).scalar()
    out["l1_rows_for_one_published_number"] = int(by_number or 0)
    out["l1_rows_for_number_and_doc_type"] = int(same_number_rows or 0)
    out["l1_published_uniqueness_still_enforced"] = int(by_number or 0) == 1

    # ---- L3/L4 still cannot machine-settle -----------------------
    out["machine_settleable_decisions"] = sorted(MACHINE_SETTLEABLE)
    out["provisional_match_is_not_machine_settleable"] = (
        PROVISIONAL_MATCH not in MACHINE_SETTLEABLE
    )

engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["l4_invariants_hold"] = all(
    [
        out["multiple_l4_provisional_opportunities_supported"],
        out["second_l4_record_does_not_collide_with_first"],
        out["published_identity_unique_index_preserved"],
        out["l4_canonical_ids_distinct"],
        out["every_l4_row_is_provisional"],
        out["no_l4_row_gained_a_number"],
        out["l1_published_uniqueness_still_enforced"],
        out["provisional_match_is_not_machine_settleable"],
    ]
)
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
