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

#: Every gate's fixture source ids start with `nf1` followed by the gate
#: number - nf162, nf163, nf167, nf169, nf170. The real source id is
#: `nf-seed-2026-...`, which starts `nf-` and therefore cannot match.
#:
#: Widened from `nf167.%` because later gates introduced their own prefixes
#: and a cleanup that only knows about one gate's fixtures leaves the others
#: behind - which Gate 169 proved shows up as "versioning stopped working"
#: several phases later rather than as leftover rows.
FIXTURE_LIKE = "nf1%"
REAL_CANONICAL = "L1:OBJA2026172662|synopsis"
REAL_SOURCE = "nf-seed-2026-api-grants-gov-search2"

#: Gate 163's two real payloads, by content hash and exact byte count: the
#: robots.txt response and the one Search2 POST. Matched by HASH rather than
#: by size, so "unchanged" means the bytes are the same bytes.
GATE163_EVIDENCE: dict[str, int] = {
    "f249b63cb2fcb66b47e86f906c98f8fd912e82dd035b4e53d7e72fc1960cfd16": 42,
    "eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712": 11131,
}

#: Sources whose payloads may legitimately be in this ledger. Gate 171 added
#: two under explicit operator approval; anything else appearing here is a
#: collection nobody authorized, which is exactly what this check exists to
#: notice.
AUTHORIZED_LIVE_SOURCES: frozenset[str] = frozenset(
    {
        REAL_SOURCE,
        "nf-seed-2026-fed-007",
        "nf-seed-2026-api-federal-register-documents",
    }
)

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
    fixture_observations = (
        "SELECT observation_id FROM nf_opportunity_source_observations "
        "WHERE source_id LIKE :p"
    )
    statements = (
        # Gate 170 change events reference canonical, versions AND
        # observations, so they are the deepest child and go first. Deleting
        # a version out from under an event raises IntegrityError, which is
        # the schema correctly refusing to orphan a claim.
        (
            "nf_opportunity_change_events",
            "DELETE FROM nf_opportunity_change_events WHERE "
            f"observation_id IN ({fixture_observations})",
        ),
        (
            "nf_opportunity_field_provenance",
            "DELETE FROM nf_opportunity_field_provenance WHERE "
            "source_id LIKE :p",
        ),
        (
            "nf_opportunity_versions",
            "DELETE FROM nf_opportunity_versions WHERE observation_id IN "
            f"({fixture_observations})",
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
        # Conflict rows and blocking keys both hang off a canonical id, so
        # both precede the canonical delete.
        ("nf_opportunity_field_conflicts", "canonical_id"),
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
                "SELECT payload_sha256, payload_size_bytes, source_id FROM "
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

    # ---- Gate 163's two payloads, checked BY HASH ---------------------
    #
    # This asserted `sizes == [42, 11131]` - correct while Grants.gov was the
    # only live source, and false the moment Gate 171 collected two more. The
    # rule the campaign settled is that when reality legitimately changes, the
    # check moves from "this never happens" to "this happens only under the
    # authorized condition"; widening the list to four sizes would have done
    # neither, because a size is not an identity.
    #
    # So the two original payloads are matched by CONTENT HASH, which is
    # strictly stronger than the size comparison it replaces, and every
    # additional payload must belong to a source the operator approved.
    by_hash = {
        str(r["payload_sha256"]): int(r["payload_size_bytes"] or 0)
        for r in payloads
    }
    gate163_present = all(
        by_hash.get(digest) == size
        for digest, size in GATE163_EVIDENCE.items()
    )
    out["gate163_evidence"] = {
        digest: {"expected_bytes": size, "found_bytes": by_hash.get(digest)}
        for digest, size in GATE163_EVIDENCE.items()
    }
    out["gate163_evidence_present_and_byte_identical"] = gate163_present

    extra = [
        str(r["source_id"])
        for r in payloads
        if str(r["payload_sha256"]) not in GATE163_EVIDENCE
    ]
    out["additional_payload_sources"] = sorted(set(extra))
    out["additional_payloads_are_authorized"] = all(
        source in AUTHORIZED_LIVE_SOURCES for source in extra
    )
    out["live_evidence_unchanged"] = bool(
        gate163_present and out["additional_payloads_are_authorized"]
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["detail"] = sorted(set(detail))
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
