"""Gate 161 verifier phase: remove this run's rows, then count what is left.

THE LAST PHASE. Gate 158 found Gate 157's verifier cleaning up before invoking
a script that committed 100 more rows, and reporting zero residue about a
database that had just gained a hundred. Nothing that writes may run after this.

`counted_actual_rows` is separate from `residue` on purpose. A cleanup that
reports "0 remaining" because it counted nothing is indistinguishable from one
that removed everything, so the count is taken by selecting rows rather than by
trusting the DELETE's own rowcount.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

PREFIX = "nf161-verify-%"

#: Children before parents. The attempts and payloads point at jobs.
TABLES = (
    "nf_source_collection_execution_attempts",
    "nf_source_collection_raw_payloads",
    "nf_source_collection_job_leases",
    "nf_source_collection_jobs",
)

out: dict[str, object] = {}
detail: list[str] = []
removed = 0
residue = 0
counted = False

session = SessionLocal()
try:
    for table in TABLES:
        try:
            result = session.execute(
                sa.text(f"DELETE FROM {table} WHERE job_id LIKE :p"),
                {"p": PREFIX},
            )
            removed += int(result.rowcount or 0)
        except Exception as exc:  # noqa: BLE001
            detail.append(f"{table}:{type(exc).__name__}")
            session.rollback()
    session.commit()

    # Counted by LOOKING, not by trusting the rowcount above. A cleanup that
    # reports nothing remaining because it never looked reads identically to
    # one that removed everything.
    for table in TABLES:
        try:
            left = session.execute(
                sa.text(f"SELECT count(*) FROM {table} WHERE job_id LIKE :p"),
                {"p": PREFIX},
            ).scalar()
            residue += int(left or 0)
            counted = True
        except Exception as exc:  # noqa: BLE001
            detail.append(f"count:{table}:{type(exc).__name__}")
            counted = False
            session.rollback()
except Exception as exc:  # noqa: BLE001
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
    session.rollback()
    counted = False
finally:
    session.close()

out["removed"] = removed
out["residue"] = residue
out["counted_actual_rows"] = bool(counted)
out["tables"] = list(TABLES)
out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
