"""Gate 168A: attribute every SQL statement in one observation write.

Gate 167 measured 49 statements per observation and stopped there. "49" is a
number; "40 of them are a per-field SELECT/UPDATE/SELECT/INSERT loop" is a
design finding. Optimizing unidentified work is how a fast wrong thing gets
built, so nothing changes until every statement has a class.

Statements are captured by a SQLAlchemy `before_cursor_execute` hook against a
COPY of the database, then classified by shape - the table they touch and the
verb - not by the order they happened to run in.

Makes no network request. Writes only to a temporary copy.
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
        raise OSError("gate168 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]

CANONICAL = "nf_canonical_opportunities"
OBSERVATIONS = "nf_opportunity_source_observations"
VERSIONS = "nf_opportunity_versions"
PROVENANCE = "nf_opportunity_field_provenance"

#: Statement classes Gate 168A asks for. A statement that matches none of them
#: is UNKNOWN and is reported as such rather than quietly bucketed.
IDENTITY_LOOKUP = "IDENTITY_LOOKUP"
CANONICAL_INSERT_OR_UPDATE = "CANONICAL_INSERT_OR_UPDATE"
OBSERVATION_INSERT = "OBSERVATION_INSERT"
VERSION_INSERT = "VERSION_INSERT"
PROVENANCE_INSERT = "PROVENANCE_INSERT"
PROVENANCE_LOOKUP = "PROVENANCE_LOOKUP"
CURRENT_VERSION_UPDATE = "CURRENT_VERSION_UPDATE"
CONFLICT_LOOKUP = "CONFLICT_LOOKUP"
LINEAGE_LOOKUP = "LINEAGE_LOOKUP"
IDEMPOTENCY_CHECK = "IDEMPOTENCY_CHECK"
#: Gate 169P added one bulk insert of blocking keys per NEW opportunity, so
#: cross-source candidate generation is an indexed lookup. It is named rather
#: than folded into an existing class: the point of this profile is that no
#: statement is unattributed, and a new statement must announce itself.
BLOCKING_KEY_INSERT = "BLOCKING_KEY_INSERT"
#: The existence check that stops an orphaned key from failing the batch on a
#: primary-key collision. One set query per batch, and only when there is
#: something to insert.
BLOCKING_KEY_LOOKUP = "BLOCKING_KEY_LOOKUP"
REDUNDANT = "REDUNDANT"
UNKNOWN = "UNKNOWN"


def record_for(index: int, *, variant: int = 0) -> dict:
    return {
        "id": f"P-{index}",
        "number": f"O-NF168P-{index:06d}",
        "title": f"Profile fixture {index}" + (" (amended)" if variant else ""),
        "agency": "Synthetic Agency",
        "agencyCode": "NF168-PR",
        "openDate": "01/05/2027",
        "closeDate": "08/01/2027" if variant else "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": ["12.345"],
    }


def classify(statement: str) -> str:
    """One statement -> one class, from its shape."""
    text = " ".join(statement.split())
    upper = text.upper()

    def touches(table: str) -> bool:
        return table in text

    if upper.startswith("INSERT"):
        if touches("nf_opportunity_blocking_keys"):
            return BLOCKING_KEY_INSERT
        if touches(CANONICAL):
            return CANONICAL_INSERT_OR_UPDATE
        if touches(OBSERVATIONS):
            return OBSERVATION_INSERT
        if touches(VERSIONS):
            return VERSION_INSERT
        if touches(PROVENANCE):
            return PROVENANCE_INSERT
        return UNKNOWN

    if upper.startswith("UPDATE"):
        if touches(CANONICAL):
            return CURRENT_VERSION_UPDATE
        if touches(VERSIONS):
            return LINEAGE_LOOKUP
        if touches(PROVENANCE):
            return CONFLICT_LOOKUP
        return UNKNOWN

    if upper.startswith("SELECT"):
        if touches("nf_opportunity_blocking_keys"):
            return BLOCKING_KEY_LOOKUP
        if touches(PROVENANCE):
            # A single-row probe on the primary key is an idempotency check;
            # a filtered read of current values is conflict detection.
            if "provenance_id =" in text:
                return IDEMPOTENCY_CHECK
            if "is_current_canonical" in text:
                return CONFLICT_LOOKUP
            return PROVENANCE_LOOKUP
        if touches(OBSERVATIONS):
            if "count(" in text.lower():
                return CURRENT_VERSION_UPDATE
            return IDEMPOTENCY_CHECK
        if touches(VERSIONS):
            if "count(" in text.lower():
                return CURRENT_VERSION_UPDATE
            return LINEAGE_LOOKUP
        if touches(CANONICAL):
            return IDENTITY_LOOKUP
        return UNKNOWN

    if upper.startswith(("BEGIN", "COMMIT", "ROLLBACK", "PRAGMA", "SAVEPOINT")):
        return REDUNDANT
    return UNKNOWN


out: dict[str, object] = {}

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf168_profile_")
copy_path = os.path.join(work, "profile.db")
shutil.copy2(REPO / db_path, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

captured: list[str] = []


@sa.event.listens_for(engine, "before_cursor_execute")
def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    captured.append(statement)


from nativeforge.repositories.canonical_opportunity_repository import (  # noqa: E402
    record_observation,
)


def write_one(connection, index: int, *, variant: int = 0) -> None:
    record = record_for(index, variant=variant)
    normalized = normalize_record(record=record, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    record_observation(
        connection=connection,
        source_id="nf168.profile.source",
        normalized=normalized,
        raw_payload_sha256=f"{index + variant * 10**7:064x}",
        source_authority_host="profile.invalid",
        identity=identity,
    )


with engine.connect() as connection:
    # ---- 1. a FIRST observation of a new opportunity ----------------
    captured.clear()
    write_one(connection, 1)
    first = list(captured)

    # ---- 2. the SAME observation again (idempotent replay) ----------
    captured.clear()
    write_one(connection, 1)
    replay = list(captured)

    # ---- 3. a CHANGED observation of the same opportunity -----------
    captured.clear()
    write_one(connection, 1, variant=1)
    amended = list(captured)

engine.dispose()
shutil.rmtree(work, ignore_errors=True)


def summarize(statements: list[str]) -> dict:
    by_class: dict[str, int] = {}
    for statement in statements:
        name = classify(statement)
        by_class[name] = by_class.get(name, 0) + 1
    verbs = {"queries": 0, "inserts": 0, "updates": 0, "deletes": 0, "other": 0}
    for statement in statements:
        head = statement.strip().split()[0].upper() if statement.strip() else ""
        if head == "SELECT":
            verbs["queries"] += 1
        elif head == "INSERT":
            verbs["inserts"] += 1
        elif head == "UPDATE":
            verbs["updates"] += 1
        elif head == "DELETE":
            verbs["deletes"] += 1
        else:
            verbs["other"] += 1
    return {
        "statements_per_observation": len(statements),
        "statements_by_class": dict(sorted(by_class.items())),
        **verbs,
        "unknown_statements": sorted(
            {
                " ".join(s.split())[:110]
                for s in statements
                if classify(s) == UNKNOWN
            }
        ),
    }


out["first_observation"] = summarize(first)
out["idempotent_replay"] = summarize(replay)
out["amended_observation"] = summarize(amended)

# ---- the per-field fanout, measured -------------------------------
#
# The fixture has ten supported fields. If provenance work is per-field, the
# provenance-touching statement count divides by ten exactly.
FIELD_COUNT = 10
provenance_classes = (
    PROVENANCE_INSERT,
    PROVENANCE_LOOKUP,
    IDEMPOTENCY_CHECK,
    CONFLICT_LOOKUP,
)
first_provenance = sum(
    out["first_observation"]["statements_by_class"].get(name, 0)
    for name in provenance_classes
)
out["fields_in_fixture"] = FIELD_COUNT
out["provenance_related_statements_first_write"] = first_provenance
out["statements_per_field"] = round(first_provenance / FIELD_COUNT, 2)
out["per_field_fanout_present"] = first_provenance >= FIELD_COUNT * 2

out["replay_is_cheaper_than_first_ingest"] = (
    out["idempotent_replay"]["statements_per_observation"]
    < out["first_observation"]["statements_per_observation"]
)

out["all_statements_classified"] = not any(
    summary["unknown_statements"]
    for summary in (
        out["first_observation"],
        out["idempotent_replay"],
        out["amended_observation"],
    )
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
