"""Gate 167: remove this gate's fixture rows, then count what is left.

THE LAST PHASE. Gate 158 found Gate 157's verifier cleaning up before invoking
a script that committed a hundred more rows, and reporting zero residue about a
database that had just gained a hundred. Nothing that writes may run after this.

The REAL canonical opportunity is deliberately NOT removed. Gate 167E's whole
point is that it becomes the first canonical opportunity written from the live
collection substrate, so it stays - and this phase asserts it survived rather
than quietly deleting everything.

Residue is counted by SELECTing rows, not by trusting a DELETE's rowcount: a
cleanup that reports zero because it counted nothing is indistinguishable from
one that worked.

Makes no network request.
"""

from __future__ import annotations

import json
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate167 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

FIXTURE_LIKE = "nf167.%"
REAL_CANONICAL = "L1:OBJA2026172662|synopsis"
REAL_SOURCE = "nf-seed-2026-api-grants-gov-search2"

out: dict[str, object] = {}
detail: list[str] = []
removed = 0

session = SessionLocal()
try:
    # Which canonical rows exist only because of fixture observations?
    fixture_canonicals = [
        str(row[0])
        for row in session.execute(
            sa.text(
                "SELECT DISTINCT canonical_id FROM "
                "nf_opportunity_source_observations WHERE source_id LIKE :p"
            ),
            {"p": FIXTURE_LIKE},
        ).all()
    ]
    out["fixture_canonical_ids"] = sorted(fixture_canonicals)

    # Never remove the real one, whatever else is true.
    targets = [c for c in fixture_canonicals if c != REAL_CANONICAL]
    out["refused_to_remove_the_real_opportunity"] = REAL_CANONICAL not in targets

    # Order matters and is not obvious: versions carry a foreign key to
    # observations, so deleting observations first fails with an
    # IntegrityError - which is the schema correctly refusing to orphan a
    # version. Children first, and versions selected BY the fixture
    # observations rather than by orphan-hood, because nothing is orphaned
    # until after the observations are gone.
    statements = (
        (
            "nf_opportunity_field_provenance",
            "DELETE FROM nf_opportunity_field_provenance WHERE "
            "source_id LIKE :p",
        ),
        (
            "nf_opportunity_versions",
            "DELETE FROM nf_opportunity_versions WHERE observation_id IN "
            "(SELECT observation_id FROM nf_opportunity_source_observations "
            "WHERE source_id LIKE :p)",
        ),
        (
            "nf_opportunity_source_observations",
            "DELETE FROM nf_opportunity_source_observations WHERE "
            "source_id LIKE :p",
        ),
    )
    for table, sql in statements:
        try:
            result = session.execute(sa.text(sql), {"p": FIXTURE_LIKE})
            removed += int(result.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            detail.append(f"{table}:{type(exc).__name__}")
            session.rollback()

    # Gate 169 added blocking keys, which carry a foreign key to the canonical
    # row - so they go FIRST, selected by the same orphan predicate the
    # canonical delete uses, evaluated while the observations are already gone
    # but the canonical rows are not. Deleting canonical first raises
    # IntegrityError, which is the schema correctly refusing to orphan a key.
    #
    # Leaving them behind is not merely untidy: the next run re-creates the
    # same canonical id, the write path inserts its keys again, and the batch
    # dies on a primary-key collision - surfacing three phases later as
    # "versioning stopped working". Found by the post-commit battery, which is
    # the only place two runs happen back to back.
    orphaned = (
        "NOT IN (SELECT canonical_id FROM nf_opportunity_source_observations)"
    )
    for table, column in (
        ("nf_opportunity_blocking_keys", "canonical_id"),
        ("nf_canonical_opportunities", "canonical_id"),
    ):
        try:
            result = session.execute(
                sa.text(f"DELETE FROM {table} WHERE {column} {orphaned}")
            )
            removed += int(result.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            detail.append(f"{table}:{type(exc).__name__}")
            session.rollback()

    session.commit()
    out["rows_removed"] = removed

    # ---- count, by LOOKING -------------------------------------------
    residue = 0
    counted = True
    try:
        residue += int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_opportunity_source_observations "
                    "WHERE source_id LIKE :p"
                ),
                {"p": FIXTURE_LIKE},
            ).scalar()
            or 0
        )
        residue += int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_opportunity_field_provenance "
                    "WHERE source_id LIKE :p"
                ),
                {"p": FIXTURE_LIKE},
            ).scalar()
            or 0
        )
        residue += int(
            session.execute(
                sa.text(
                    "SELECT count(*) FROM nf_canonical_opportunities WHERE "
                    "canonical_id NOT IN (SELECT canonical_id FROM "
                    "nf_opportunity_source_observations)"
                )
            ).scalar()
            or 0
        )
    except Exception as exc:  # noqa: BLE001
        detail.append(f"count:{type(exc).__name__}")
        counted = False
    out["fixture_residue"] = residue
    out["residue_was_counted"] = counted

    # ---- the real opportunity survived --------------------------------
    real = (
        session.execute(
            sa.text(
                "SELECT canonical_id, current_version_id, observation_count "
                "FROM nf_canonical_opportunities WHERE canonical_id = :c"
            ),
            {"c": REAL_CANONICAL},
        )
        .mappings()
        .first()
    )
    out["real_opportunity_present"] = real is not None
    out["real_opportunity"] = dict(real) if real else None

    real_provenance = int(
        session.execute(
            sa.text(
                "SELECT count(*) FROM nf_opportunity_field_provenance "
                "WHERE source_id = :s"
            ),
            {"s": REAL_SOURCE},
        ).scalar()
        or 0
    )
    out["real_opportunity_provenance_rows"] = real_provenance

    # ---- the evidence ledger is untouched ------------------------------
    payloads = (
        session.execute(
            sa.text(
                "SELECT payload_sha256, payload_size_bytes FROM "
                "nf_source_collection_raw_payloads ORDER BY payload_sha256"
            )
        )
        .mappings()
        .all()
    )
    out["raw_payload_rows"] = len(payloads)
    out["raw_payload_bytes"] = sorted(
        int(r["payload_size_bytes"] or 0) for r in payloads
    )
    out["live_evidence_unchanged"] = sorted(
        int(r["payload_size_bytes"] or 0) for r in payloads
    ) == [42, 11131]
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["detail"] = sorted(set(detail))
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
