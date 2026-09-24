"""Gate 175L: documents at scale, and the access paths an operator takes.

Multi-document opportunities are the normal case, not the exception: a NOFO,
an appendix, application instructions, two amendments and an FAQ is six
documents and perhaps forty facts for ONE opportunity. The queries that matter
are therefore per-opportunity and per-document, and the version chain has to
be walkable without reading every document in the system.

Selectivity is measured, and a query returning most of its table is correctly
a scan and is NAMED as an exemption.

No network. A scratch database, dropped at the end.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import resource
import socket
import sys
import time

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate175 scale phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.services.document_fact_extraction_service import (  # noqa: E402
    DEADLINE,
    ELIGIBILITY,
    build_fact,
    detect_conflicts,
)
from nativeforge.services.opportunity_document_service import (  # noqa: E402
    AMENDMENT,
    APPENDIX,
    FAQ,
    NOFO,
    PARSED,
    WEBPAGE,
    build_document,
    build_version_chain,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

DOCUMENTS = "nf_opportunity_documents"
FACTS = "nf_opportunity_document_facts"
CONFLICTS = "nf_opportunity_document_conflicts"

#: Six documents per opportunity, which is an ordinary federal NOFO package.
SHAPES = (NOFO, APPENDIX, "APPLICATION_INSTRUCTIONS", AMENDMENT, FAQ, WEBPAGE)
SCALES = (500, 2_000, 10_000)

out: dict[str, object] = {"schema_version": "nf_gate175_document_scale_v1"}


def memory_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def build_package(canonical_id: str) -> tuple[list[dict], list[dict]]:
    """One opportunity's document package and its facts."""
    documents: list[dict] = []
    previous: str | None = None
    for ordinal, kind in enumerate(SHAPES, start=1):
        body = f"{canonical_id}:{kind}:body"
        documents.append(
            build_document(
                canonical_id=canonical_id,
                document_type=kind,
                content_sha256=hashlib.sha256(body.encode()).hexdigest(),
                size_bytes=len(body) * 40,
                page_count=12,
                document_state=PARSED,
                extraction_method="synthetic_fixture_parser",
                version_ordinal=ordinal,
                supersedes_document_id=previous if kind == AMENDMENT else None,
                observed_at=NOW,
            )
        )
        if kind == AMENDMENT:
            previous = documents[-1]["document_id"]
        elif kind == NOFO:
            previous = documents[-1]["document_id"]

    facts = []
    for document in documents:
        facts.append(
            build_fact(
                canonical_id=canonical_id,
                document=document,
                fact_kind=ELIGIBILITY,
                value=["tribal_government"],
                source_text="Federally recognized Indian tribes are eligible",
                section_ref="Eligibility",
                page_ref=3,
            )
        )
        facts.append(
            build_fact(
                canonical_id=canonical_id,
                document=document,
                fact_kind=DEADLINE,
                # The amendment disagrees, on purpose.
                value="2026-12-15"
                if document["document_type"] == AMENDMENT
                else "2026-11-15",
                source_text="Applications are due",
                page_ref=1,
            )
        )
    return documents, facts


# ============ scale =================================================
measured: dict[str, dict[str, object]] = {}
for scale in SCALES:
    started = time.perf_counter()
    packages = [build_package(f"nf175.scale.{i:06d}") for i in range(scale)]
    build_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    chains = [build_version_chain(documents) for documents, _ in packages]
    chain_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    conflicts = [detect_conflicts(facts) for _, facts in packages]
    conflict_ms = (time.perf_counter() - started) * 1000

    total = build_ms + chain_ms + conflict_ms
    measured[str(scale)] = {
        "opportunities": scale,
        "documents": sum(len(d) for d, _ in packages),
        "facts": sum(len(f) for _, f in packages),
        "build_ms": round(build_ms, 1),
        "chain_ms": round(chain_ms, 1),
        "conflict_ms": round(conflict_ms, 1),
        "total_ms": round(total, 1),
        "ms_per_opportunity": round(total / max(scale, 1), 5),
        "valid_chains": sum(1 for c in chains if c["chain_is_valid"]),
        "conflicts_found": sum(c["conflict_count"] for c in conflicts),
    }
    out[f"documents_{scale}_ms"] = measured[str(scale)]["total_ms"]

out["measured_by_scale"] = measured
out["documents_per_opportunity"] = len(SHAPES)
out["documents_10k_ms"] = measured["10000"]["total_ms"]
out["ms_per_opportunity_by_scale"] = {
    str(s): measured[str(s)]["ms_per_opportunity"] for s in SCALES
}
per = [measured[str(s)]["ms_per_opportunity"] for s in SCALES]
out["no_quadratic_growth"] = per[-1] <= per[0] * 3
out["all_chains_valid_at_scale"] = (
    measured["10000"]["valid_chains"] == measured["10000"]["opportunities"]
)
out["document_memory_mb"] = memory_mb()

# ============ access paths ==========================================
scratch = REPO / ".g175_scale_scratch.db"
scratch.unlink(missing_ok=True)

from nativeforge.lib.settings import get_settings  # noqa: E402

previous_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = f"sqlite:///{scratch}"
get_settings.cache_clear()

engine = sa.create_engine(f"sqlite:///{scratch}")
statements = {"count": 0}


def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    statements["count"] += 1


sa.event.listen(engine, "before_cursor_execute", _count)

try:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO / "alembic.ini")), "head")
    assert get_settings().database_url == f"sqlite:///{scratch}"

    opportunities = 5_000
    doc_rows = opportunities * len(SHAPES)
    statements["count"] = 0
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                f"INSERT INTO {DOCUMENTS} (document_id, canonical_id, "
                "document_type, content_sha256, size_bytes, page_count, "
                "document_state, extraction_method, version_ordinal, "
                "supersedes_document_id, absence_is_meaningful, is_latest, "
                "model_version, created_at) VALUES (:did, :cid, :kind, :sha, "
                "4000, 12, 'PARSED', 'fixture', :ord, :sup, 1, :latest, "
                "'2026.09.1', :now)"
            ),
            [
                {
                    "did": f"doc{index:09d}",
                    "cid": f"nf175.scale.{index // len(SHAPES):06d}",
                    "kind": SHAPES[index % len(SHAPES)],
                    "sha": hashlib.sha256(str(index).encode()).hexdigest(),
                    "ord": (index % len(SHAPES)) + 1,
                    "sup": (
                        f"doc{index - 1:09d}"
                        if SHAPES[index % len(SHAPES)] == AMENDMENT
                        else None
                    ),
                    "latest": 1 if index % len(SHAPES) == len(SHAPES) - 1 else 0,
                    "now": NOW,
                }
                for index in range(doc_rows)
            ],
        )
        connection.execute(
            sa.text(
                f"INSERT INTO {FACTS} (fact_id, canonical_id, document_id, "
                "document_type, fact_kind, value_json, source_text, page_ref, "
                "extraction_method, confidence, is_material, created_at) VALUES "
                "(:fid, :cid, :did, :kind, :fkind, :val, :text, 3, "
                "'EXTRACTED_BY_PARSER', 'MEDIUM', 1, :now)"
            ),
            [
                {
                    "fid": f"fact{index:09d}",
                    "cid": f"nf175.scale.{index // len(SHAPES):06d}",
                    "did": f"doc{index:09d}",
                    "kind": SHAPES[index % len(SHAPES)],
                    "fkind": "ELIGIBILITY" if index % 2 else "DEADLINE",
                    "val": '["tribal_government"]',
                    "text": "Federally recognized Indian tribes are eligible",
                    "now": NOW,
                }
                for index in range(doc_rows)
            ],
        )
        connection.execute(
            sa.text(
                f"INSERT INTO {CONFLICTS} (conflict_id, canonical_id, fact_kind, "
                "fact_id_a, fact_id_b, value_a_json, value_b_json, "
                "resolution_rule, winning_fact_id, why, is_material, "
                "review_required, created_at) VALUES (:cfid, :cid, 'DEADLINE', "
                ":a, :b, :va, :vb, :rule, :win, 'scale fixture', 1, :rev, :now)"
            ),
            [
                {
                    "cfid": f"conf{index:09d}",
                    "cid": f"nf175.scale.{index:06d}",
                    "a": f"fact{index * len(SHAPES):09d}",
                    "b": f"fact{index * len(SHAPES) + 3:09d}",
                    "va": '"2026-11-15"',
                    "vb": '"2026-12-15"',
                    "rule": "AMENDMENT_SUPERSEDES" if index % 2 else "UNRESOLVED",
                    "win": (
                        f"fact{index * len(SHAPES) + 3:09d}" if index % 2 else None
                    ),
                    "rev": 0 if index % 2 else 1,
                    "now": NOW,
                }
                for index in range(opportunities)
            ],
        )
    write_statements = statements["count"]

    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        totals = {
            DOCUMENTS: raw.execute(f"SELECT count(*) FROM {DOCUMENTS}").fetchone()[0],
            FACTS: raw.execute(f"SELECT count(*) FROM {FACTS}").fetchone()[0],
            CONFLICTS: raw.execute(f"SELECT count(*) FROM {CONFLICTS}").fetchone()[0],
        }

        queries = {
            "documents_by_opportunity": (
                f"SELECT document_id FROM {DOCUMENTS} WHERE canonical_id = ?",
                ("nf175.scale.002500",),
                totals[DOCUMENTS],
            ),
            "latest_document_versions": (
                f"SELECT document_id FROM {DOCUMENTS} "
                "WHERE canonical_id = ? AND is_latest = 1",
                ("nf175.scale.002500",),
                totals[DOCUMENTS],
            ),
            "documents_by_type": (
                f"SELECT document_id FROM {DOCUMENTS} "
                "WHERE canonical_id = ? AND document_type = ?",
                ("nf175.scale.002500", "AMENDMENT"),
                totals[DOCUMENTS],
            ),
            "amendment_chain": (
                f"SELECT document_id FROM {DOCUMENTS} WHERE supersedes_document_id = ?",
                ("doc000015000",),
                totals[DOCUMENTS],
            ),
            "document_by_content_hash": (
                f"SELECT document_id FROM {DOCUMENTS} WHERE content_sha256 = ?",
                (hashlib.sha256(b"12345").hexdigest(),),
                totals[DOCUMENTS],
            ),
            "facts_by_document": (
                f"SELECT fact_id FROM {FACTS} WHERE document_id = ?",
                ("doc000015000",),
                totals[FACTS],
            ),
            "facts_by_opportunity": (
                f"SELECT fact_id FROM {FACTS} WHERE canonical_id = ?",
                ("nf175.scale.002500",),
                totals[FACTS],
            ),
            "citations_by_requirement_kind": (
                f"SELECT fact_id FROM {FACTS} WHERE canonical_id = ? AND fact_kind = ?",
                ("nf175.scale.002500", "ELIGIBILITY"),
                totals[FACTS],
            ),
            "conflicts_by_opportunity": (
                f"SELECT conflict_id FROM {CONFLICTS} WHERE canonical_id = ?",
                ("nf175.scale.002500",),
                totals[CONFLICTS],
            ),
            "conflicts_needing_review": (
                f"SELECT conflict_id FROM {CONFLICTS} "
                "WHERE review_required = 1 AND is_material = 1",
                (),
                totals[CONFLICTS],
            ),
        }

        access: dict[str, object] = {}
        for name, (sql, params, population) in queries.items():
            plan = [
                row[3]
                for row in raw.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
            ]
            returned = len(raw.execute(sql, params).fetchall())
            scans = any(step.strip().startswith("SCAN") for step in plan)
            selectivity = round(returned / max(population, 1), 6)
            started = time.perf_counter()
            raw.execute(sql, params).fetchall()
            access[name] = {
                "plan": plan,
                "scans": scans,
                "rows_returned": returned,
                "selectivity": selectivity,
                "index_required": selectivity < 0.5,
                "index_used_where_required": (not scans) or selectivity >= 0.5,
                "ms": round((time.perf_counter() - started) * 1000, 3),
            }

    out["scale_document_rows"] = totals[DOCUMENTS]
    out["scale_fact_rows"] = totals[FACTS]
    out["scale_conflict_rows"] = totals[CONFLICTS]
    out["write_statements"] = write_statements
    out["statements_per_row"] = round(
        write_statements / (totals[DOCUMENTS] + totals[FACTS] + totals[CONFLICTS]), 7
    )
    out["access_paths"] = access
    out["query_selectivity"] = {
        name: entry["selectivity"] for name, entry in sorted(access.items())
    }
    out["query_ms"] = {name: entry["ms"] for name, entry in sorted(access.items())}
    offenders = sorted(
        name for name, entry in access.items() if not entry["index_used_where_required"]
    )
    exempt = sorted(
        name
        for name, entry in access.items()
        if entry["scans"] and not entry["index_required"]
    )
    out["selective_queries_that_scan"] = offenders
    out["queries_exempt_because_they_return_most_rows"] = exempt
    out["critical_document_queries_indexed"] = not offenders
    out["queries_audited"] = sorted(access)
finally:
    sa.event.remove(engine, "before_cursor_execute", _count)
    engine.dispose()
    scratch.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        pathlib.Path(str(scratch) + suffix).unlink(missing_ok=True)
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url
    get_settings.cache_clear()

out["scratch_database_removed"] = not scratch.exists()
out["document_memory_mb"] = memory_mb()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
