"""Gate 171A: survey the registered source corpus before building anything.

"Registered" is not "authorized" and this phase is built so the two cannot be
confused: the registry is read for SHAPE, the Gate 166 authority model is read
for PERMISSION, and a candidate is classified by what has actually been
established about it rather than by what is plausible.

Every classification here is derived from persisted rows or from files already
in the repository. Nothing in this phase touches a network, including the
candidates' own hosts - fetching robots.txt to "check" a candidate is exactly
the probe Gate 171 forbids before approval.
"""

from __future__ import annotations

import json
import pathlib
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"

#: 171A's vocabulary. A candidate lands in exactly one.
PUBLIC_UNAUTHENTICATED = "PUBLIC_UNAUTHENTICATED"
PUBLIC_AUTHENTICATED = "PUBLIC_AUTHENTICATED"
TERMS_REVIEW_REQUIRED = "TERMS_REVIEW_REQUIRED"
ROBOTS_REVIEW_REQUIRED = "ROBOTS_REVIEW_REQUIRED"
UNKNOWN = "UNKNOWN"
UNSUITABLE = "UNSUITABLE_FOR_GATE171"

#: Decision kinds the Gate 166 authority model recognises for a source.
REQUIRED_DECISIONS = ("terms", "human_review", "live_fetch")


def rows(connection: sqlite3.Connection, sql: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    return [dict(r) for r in connection.execute(sql)]


def classify(
    source: dict, decisions: dict[str, dict], *, joinable: bool
) -> tuple[str, list[str]]:
    """What has been ESTABLISHED about this source, not what is likely.

    `joinable` is load-bearing. The first cut of this classifier read an
    empty decision set as "no terms decision on file" and reported all 40
    rows as TERMS_REVIEW_REQUIRED - a confident answer produced by a join
    that could never match, because nf_opportunity_sources.seed_id is empty
    on every row. "Nobody reviewed this" and "I cannot tell who reviewed
    this" are different facts and only one of them is about the source.
    """
    why: list[str] = []
    url = str(source.get("source_url") or "")

    if not url or not url.startswith("http"):
        return UNSUITABLE, ["no_usable_endpoint_recorded"]

    if not joinable:
        return UNKNOWN, ["registry_row_carries_no_key_to_join_authorization_on"]

    live = decisions.get("live_fetch")
    terms = decisions.get("terms")

    if live and str(live.get("decision")) == "approved":
        why.append("live_fetch_decision_approved")
        return PUBLIC_UNAUTHENTICATED, why

    if terms is None:
        why.append("no_terms_decision_on_file")
        return TERMS_REVIEW_REQUIRED, why
    if str(terms.get("decision")) != "approved":
        why.append("terms_decision_is_" + str(terms.get("decision")))
        return TERMS_REVIEW_REQUIRED, why

    why.append("terms_on_file_but_no_robots_evidence")
    return ROBOTS_REVIEW_REQUIRED, why


def shape_of(source: dict) -> str:
    """The WORKLOAD shape, which is what 171B's heterogeneity test needs."""
    method = str(source.get("check_method") or "").lower()
    url = str(source.get("source_url") or "").lower()
    if "api" in method or "/api/" in url or url.endswith(".json"):
        return "api_structured"
    if url.endswith(".xml") or "rss" in url or "atom" in url or "/feed" in url:
        return "feed_xml"
    if url.endswith(".pdf"):
        return "document_pdf"
    if url.startswith("http"):
        return "html_listing"
    return "unknown"


out: dict[str, object] = {"schema_version": "nf_gate171_source_survey_v1"}

connection = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)
try:
    registry = rows(
        connection,
        "select seed_id, source_name, source_type, source_url, publisher_name,"
        " check_method, verification_status, is_active, reliability_rating,"
        " priority_level, native_relevance_notes, canonical_source_id"
        " from nf_opportunity_sources order by source_name",
    )
    decision_rows = rows(
        connection,
        "select source_id, decision_kind, decision, guard_status, reviewed_by,"
        " review_authority, fact_status from nf_source_authorization_decisions",
    )
    active = rows(
        connection,
        "select source_id, source_name, source_lane, collection_method,"
        " source_status, source_health_status, disabled_at"
        " from nf_active_opportunity_sources",
    )
    robots = rows(
        connection,
        "select host, fetched_for_source_id, http_status, decision,"
        " payload_sha256 from nf_source_robots_evidence",
    )
    payloads = rows(
        connection,
        "select source_id, response_status, payload_size_bytes, payload_sha256,"
        " live_fetch_performed from nf_source_collection_raw_payloads",
    )
finally:
    connection.close()

by_source: dict[str, dict[str, dict]] = {}
for row in decision_rows:
    by_source.setdefault(str(row["source_id"]), {})[str(row["decision_kind"])] = row

# ---- the corpus, classified ---------------------------------------
classified: list[dict] = []
unjoinable = 0
for source in registry:
    seed = str(source.get("seed_id") or source.get("canonical_source_id") or "")
    joinable = bool(seed)
    if not joinable:
        unjoinable += 1
    decisions = by_source.get(seed, {})
    classification, why = classify(source, decisions, joinable=joinable)
    classified.append(
        {
            "seed_id": seed,
            "source_name": source.get("source_name"),
            "source_type": source.get("source_type"),
            "publisher": source.get("publisher_name"),
            "url": source.get("source_url"),
            "check_method": source.get("check_method"),
            "workload_shape": shape_of(source),
            "classification": classification,
            "why": why,
            "decisions_on_file": sorted(decisions),
            "native_relevance_notes": source.get("native_relevance_notes"),
        }
    )

counts: dict[str, int] = {}
shapes: dict[str, int] = {}
for entry in classified:
    counts[str(entry["classification"])] = (
        counts.get(str(entry["classification"]), 0) + 1
    )
    shapes[str(entry["workload_shape"])] = (
        shapes.get(str(entry["workload_shape"]), 0) + 1
    )

out["registered_sources"] = len(registry)
out["classification_counts"] = dict(sorted(counts.items()))
out["workload_shape_counts"] = dict(sorted(shapes.items()))
out["corpus"] = classified

# ---- registered is NOT authorized ---------------------------------
authorized = sorted(
    seed
    for seed, decisions in by_source.items()
    if all(
        str(decisions.get(kind, {}).get("decision")) == "approved"
        for kind in REQUIRED_DECISIONS
    )
)
out["authorization_decisions_on_file"] = len(decision_rows)
out["fully_authorized_source_ids"] = authorized
out["fully_authorized_source_count"] = len(authorized)
out["registered_but_not_authorized"] = len(registry) - len(authorized)
out["registered_is_not_authorized"] = len(registry) > len(authorized)

out["active_source_rows"] = active
out["robots_evidence_rows"] = robots
out["real_payloads"] = payloads
out["real_payload_sizes"] = sorted(
    int(p["payload_size_bytes"]) for p in payloads if p["payload_size_bytes"]
)

# ---- what the repository already has, by adapter family -----------
#
# An adapter family that already exists is a reuse candidate; one that does
# not is new work. Either is fine - what is not fine is discovering after
# approval that the shape has no home.
services = REPO / "src" / "nativeforge" / "services"
adapter_modules = sorted(
    p.name
    for p in services.glob("*adapter*.py")
    if "storage" not in p.name and "auth_context" not in p.name
)
out["existing_adapter_modules"] = adapter_modules
out["existing_adapter_module_count"] = len(adapter_modules)

# ---- the code seed catalog, which is a SECOND corpus ---------------
#
# The federal seed catalog names only entry points that are a matter of
# public record and marks every one `robots_terms_status="unreviewed"` with
# `monitoring_allowed=False`. It is where an API-shaped candidate has to come
# from, because the database registry has none.
try:
    from nativeforge.services.federal_source_seed_catalog import (  # noqa: E402
        FEDERAL_SEED_LANES,
        FEDERAL_SEEDS,
    )

    seeds = list(FEDERAL_SEEDS)
    out["code_seed_lanes"] = list(FEDERAL_SEED_LANES)
    out["code_seeds"] = [
        {
            "catalog_key": s.get("catalog_key"),
            "lane": s.get("lane"),
            "family": s.get("family"),
            "url": s.get("url"),
            "agency": s.get("agency"),
            "access_method": s.get("access_method"),
            "scope": s.get("scope"),
            "native_expected": s.get("native_expected"),
            "has_public_record_url": bool(s.get("url")),
        }
        for s in seeds
    ]
    out["code_seed_read_error"] = None
except Exception as exc:  # noqa: BLE001
    out["code_seeds"] = []
    out["code_seed_read_error"] = f"{type(exc).__name__}: {exc}"

# ---- findings, stated rather than left for a reader to infer -------
api_shaped_in_db = sum(
    1 for e in classified if e["workload_shape"] == "api_structured"
)
out["findings"] = {
    "registry_rows_without_a_join_key": unjoinable,
    "authorized_source_absent_from_nf_opportunity_sources": (
        "nf-seed-2026-api-grants-gov-search2"
        not in {str(e["seed_id"]) for e in classified}
    ),
    "two_separate_registries": (
        "nf_opportunity_sources is a catalog of program PAGES; "
        "nf_active_opportunity_sources plus nf_source_authorization_decisions "
        "carry activation and permission. They share no key today."
    ),
    "api_shaped_candidates_in_db_registry": api_shaped_in_db,
    "api_candidate_must_come_from_code_catalog": api_shaped_in_db == 0,
}

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written"] = 0
print(json.dumps(out, sort_keys=True, default=str))
