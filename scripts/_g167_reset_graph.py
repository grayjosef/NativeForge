"""Clear the canonical graph tables. Gate 167 working tool; touches nothing else.

Deliberately narrow. It reports what it is about to remove and REFUSES if the
rows reference a payload this gate did not write, so a future run cannot
quietly discard evidence-linked rows somebody else created.

It never touches `nf_source_collection_raw_payloads`. That is the evidence
ledger; this tool only removes the derived graph, which Gate 167M proves can
be rebuilt from that evidence.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

TABLES = (
    "nf_opportunity_field_provenance",
    "nf_opportunity_versions",
    "nf_opportunity_source_observations",
    "nf_canonical_opportunities",
)

#: Only rows derived from these payloads may be cleared by this tool.
KNOWN_PAYLOADS = {
    "eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712",
}
SYNTHETIC_PREFIX = "nf167.fixture."

out: dict[str, object] = {}
session = SessionLocal()
try:
    before = {
        table: int(
            session.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for table in TABLES
    }
    out["before"] = before

    # Authority is decided by SOURCE, not by payload hash. A synthetic
    # fixture's hash is a real digest of its own bytes and is therefore
    # indistinguishable from any other hash - the first version of this guard
    # keyed on the hash, recognised nothing, and silently refused to clear,
    # which made a later run collide with rows it believed it had removed.
    rows = (
        session.execute(
            sa.text(
                "SELECT DISTINCT source_id, raw_payload_sha256 FROM "
                "nf_opportunity_source_observations"
            )
        )
        .mappings()
        .all()
    )
    unknown = [
        f"{row['source_id']}:{row['raw_payload_sha256'][:12]}"
        for row in rows
        if not str(row["source_id"]).startswith(SYNTHETIC_PREFIX)
        and str(row["raw_payload_sha256"]) not in KNOWN_PAYLOADS
    ]
    out["observations_present"] = len(rows)
    out["sources_present"] = sorted({str(row["source_id"]) for row in rows})
    out["unrecognised_rows"] = sorted(unknown)

    if unknown:
        out["cleared"] = False
        out["refused_because"] = (
            "the graph references payloads this tool does not recognise"
        )
    else:
        for table in TABLES:
            session.execute(sa.text(f"DELETE FROM {table}"))
        session.commit()
        out["cleared"] = True
        out["after"] = {
            table: int(
                session.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
                or 0
            )
            for table in TABLES
        }

    payload = (
        session.execute(
            sa.text(
                "SELECT count(*) FROM nf_source_collection_raw_payloads"
            )
        ).scalar()
        or 0
    )
    out["raw_payload_rows_untouched"] = int(payload)
finally:
    session.close()

print(json.dumps(out, sort_keys=True, default=str))
