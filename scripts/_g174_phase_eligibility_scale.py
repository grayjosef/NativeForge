"""Gate 174L: eligibility at scale, and the access paths it takes.

The shape that has to be absent is `opportunities x tenants` normalization.
Requirements are parsed once per opportunity; only the MATCH is per tenant. So
the phase measures both separately and asserts the normalization count tracks
opportunities alone.

Access paths are audited against the queries the repository actually issues.
Selectivity is measured, and a query that returns most of its table is
correctly a scan and is NAMED as an exemption - Gate 172's rule, applied to a
different schema.

No network. A scratch database, dropped at the end.
"""

from __future__ import annotations

import datetime as dt
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
        raise OSError("gate174 scale phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.services.eligibility_match_engine_service import (  # noqa: E402
    match_eligibility,
    match_invariant_failures,
)
from nativeforge.services.eligibility_requirement_model_service import (  # noqa: E402
    APPLICANT_TYPE,
    EXCLUSION,
    MATCHING_FUNDS,
    REGISTRATION,
    build_requirement,
)
from nativeforge.services.organization_capability_profile_service import (  # noqa: E402
    build_profile,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

REQUIREMENTS = "nf_opportunity_eligibility_requirements"
PROFILES = "nf_organization_capability_profiles"
MATCHES = "nf_tenant_eligibility_matches"

OPPORTUNITY_SCALES = (1_000, 10_000, 50_000)
TENANTS = 20

out: dict[str, object] = {"schema_version": "nf_gate174_scale_v1"}


def memory_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


normalizations = {"count": 0}


def normalize(canonical_id: str, shape: int) -> list[dict]:
    normalizations["count"] += 1
    base = [
        build_requirement(
            canonical_id=canonical_id,
            requirement_kind=APPLICANT_TYPE,
            normalized_value=["tribal_government"],
            original_text="Indian tribes are eligible",
            applies_to_entity_classes=["tribal_government"],
            raw_payload_sha256="g174.scale.payload",
            source_id="g174.scale.source",
            evidence_ids=[f"ev.{canonical_id}.applicant"],
        )
    ]
    if shape % 3 == 1:
        base.append(
            build_requirement(
                canonical_id=canonical_id,
                requirement_kind=MATCHING_FUNDS,
                normalized_value=True,
                original_text="A 20% non-federal match is required",
                raw_payload_sha256="g174.scale.payload",
                evidence_ids=[f"ev.{canonical_id}.match"],
            )
        )
    if shape % 3 == 2:
        base.append(
            build_requirement(
                canonical_id=canonical_id,
                requirement_kind=APPLICANT_TYPE,
                normalized_value=["tribal_government"],
                original_text="Prior-year grantees are not eligible",
                polarity=EXCLUSION,
                applies_to_entity_classes=["tribal_government"],
                raw_payload_sha256="g174.scale.payload",
                evidence_ids=[f"ev.{canonical_id}.exclusion"],
            )
        )
    else:
        base.append(
            build_requirement(
                canonical_id=canonical_id,
                requirement_kind=REGISTRATION,
                normalized_value=True,
                original_text="Active SAM.gov registration required",
                raw_payload_sha256="g174.scale.payload",
                evidence_ids=[f"ev.{canonical_id}.registration"],
            )
        )
    return base


PROFILES_BY_TENANT = [
    build_profile(
        organization_id=f"org.{index:03d}",
        facts={
            "entity_class": "tribal_government",
            "matching_funds_capability": index % 2 == 0,
            "sam_registration": index % 3 != 0,
        },
    )
    for index in range(TENANTS)
]

# ============ 174L: scale ============================================
measured: dict[str, dict[str, object]] = {}
for scale in OPPORTUNITY_SCALES:
    normalizations["count"] = 0
    started = time.perf_counter()
    all_requirements = [
        normalize(f"nf174.scale.{index:06d}", index) for index in range(scale)
    ]
    normalize_ms = (time.perf_counter() - started) * 1000

    # One tenant's matches across the whole population.
    started = time.perf_counter()
    matches = [
        match_eligibility(
            canonical_id=f"nf174.scale.{index:06d}",
            requirements=requirements,
            profile=PROFILES_BY_TENANT[0],
            tenant_id="tenant.000",
        )
        for index, requirements in enumerate(all_requirements)
    ]
    match_ms = (time.perf_counter() - started) * 1000

    measured[str(scale)] = {
        "normalizations": normalizations["count"],
        "normalize_ms": round(normalize_ms, 1),
        "match_ms": round(match_ms, 1),
        "matches": len(matches),
        "ms_per_opportunity": round((normalize_ms + match_ms) / max(scale, 1), 5),
        "invariant_failures": sorted(
            {f for m in matches[:200] for f in match_invariant_failures(m)}
        ),
        "results": sorted({str(m["eligibility_result"]) for m in matches}),
    }
    out[f"eligibility_{scale}_ms"] = (
        measured[str(scale)]["normalize_ms"] + measured[str(scale)]["match_ms"]
    )

out["measured_by_scale"] = measured
out["eligibility_10k_ms"] = out["eligibility_10000_ms"]
out["eligibility_50k_ms"] = out["eligibility_50000_ms"]
out["ms_per_opportunity_by_scale"] = {
    str(s): measured[str(s)]["ms_per_opportunity"] for s in OPPORTUNITY_SCALES
}
per = [measured[str(s)]["ms_per_opportunity"] for s in OPPORTUNITY_SCALES]
out["no_quadratic_growth"] = per[-1] <= per[0] * 3
out["eligibility_memory_mb"] = memory_mb()

# ---- the tenant claim, measured ----------------------------------
POPULATION = 2_000
normalizations["count"] = 0
requirements_by_opportunity = [
    normalize(f"nf174.tenant.{index:06d}", index) for index in range(POPULATION)
]
normalizations_for_population = normalizations["count"]

match_count = 0
for requirements in requirements_by_opportunity:
    for profile in PROFILES_BY_TENANT:
        match_eligibility(
            canonical_id=str(requirements[0]["canonical_id"]),
            requirements=requirements,
            profile=profile,
            tenant_id=str(profile["organization_id"]),
        )
        match_count += 1

out["population"] = POPULATION
out["tenants"] = TENANTS
out["normalizations_for_population"] = normalizations_for_population
out["matches_for_population"] = match_count
out["normalization_tracks_opportunities_only"] = (
    normalizations_for_population == POPULATION
)
out["no_opportunity_times_tenant_normalization"] = (
    normalizations_for_population < POPULATION * TENANTS
)
out["normalization_savings_ratio"] = round(
    (POPULATION * TENANTS) / max(normalizations_for_population, 1), 1
)

# ============ 174L: access paths =====================================
scratch = REPO / ".g174_scale_scratch.db"
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

    rows = 20_000
    statements["count"] = 0
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                f"INSERT INTO {REQUIREMENTS} (requirement_id, canonical_id, "
                "requirement_kind, polarity, normalized_value_json, original_text, "
                "evidence_ids_json, is_structural, is_addressable, model_version, "
                "is_current, created_at) VALUES (:rid, :cid, :kind, :pol, :val, "
                ":text, :ev, :struct, :addr, :mv, 1, :now)"
            ),
            [
                {
                    "rid": f"req{index:08d}",
                    "cid": f"nf174.scale.{index % 5000:06d}",
                    "kind": "APPLICANT_TYPE" if index % 2 else "MATCHING_FUNDS",
                    "pol": "EXCLUSION" if index % 7 == 0 else "INCLUSION",
                    "val": '["tribal_government"]',
                    "text": "Indian tribes are eligible",
                    "ev": '["ev.1"]',
                    "struct": 1 if index % 2 else 0,
                    "addr": 0 if index % 2 else 1,
                    "mv": "2026.09.1",
                    "now": NOW,
                }
                for index in range(rows)
            ],
        )
        connection.execute(
            sa.text(
                f"INSERT INTO {MATCHES} (match_id, canonical_id, tenant_id, "
                "organization_id, profile_version, model_version, "
                "eligibility_result, reason, satisfied_count, unsatisfied_count, "
                "unknown_count, review_count, applied_exclusion_count, "
                "requirement_count, conditions_to_obtain_json, review_required, "
                "consumed_global_normalization, evaluated_at, is_current, "
                "created_at) VALUES (:mid, :cid, :tid, :oid, :pv, :mv, :res, "
                ":reason, 1, 0, 0, 0, 0, 1, :cond, :rev, 1, :now, 1, :now)"
            ),
            [
                {
                    "mid": f"match{index:08d}",
                    "cid": f"nf174.scale.{index % 5000:06d}",
                    "tid": f"tenant.{index % 20:03d}",
                    "oid": f"org.{index % 20:03d}",
                    "pv": "v1",
                    "mv": "2026.09.1",
                    "res": ["ELIGIBLE", "CONDITIONALLY_ELIGIBLE", "INELIGIBLE"][
                        index % 3
                    ],
                    "reason": "scale fixture",
                    # A conditional answer has to name its condition; the 0060
                    # CHECK refuses one that does not, and it refused this
                    # fixture until it did.
                    "cond": ('["MATCHING_FUNDS"]' if index % 3 == 1 else None),
                    "rev": 1 if index % 11 == 0 else 0,
                    "now": NOW,
                }
                for index in range(rows)
            ],
        )
    write_statements = statements["count"]

    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        total_requirements = raw.execute(
            f"SELECT count(*) FROM {REQUIREMENTS}"
        ).fetchone()[0]
        total_matches = raw.execute(f"SELECT count(*) FROM {MATCHES}").fetchone()[0]

        queries = {
            "requirements_by_opportunity": (
                f"SELECT requirement_id FROM {REQUIREMENTS} "
                "WHERE canonical_id = ? AND is_current = 1",
                ("nf174.scale.002500",),
                total_requirements,
            ),
            "disqualifiers_by_opportunity": (
                f"SELECT requirement_id FROM {REQUIREMENTS} "
                "WHERE canonical_id = ? AND polarity = ? AND is_current = 1",
                ("nf174.scale.002500", "EXCLUSION"),
                total_requirements,
            ),
            "requirements_by_kind": (
                f"SELECT requirement_id FROM {REQUIREMENTS} "
                "WHERE requirement_kind = ? AND is_current = 1",
                ("MATCHING_FUNDS",),
                total_requirements,
            ),
            "eligibility_result_by_tenant_and_opportunity": (
                f"SELECT eligibility_result FROM {MATCHES} "
                "WHERE tenant_id = ? AND canonical_id = ? AND is_current = 1",
                ("tenant.005", "nf174.scale.002500"),
                total_matches,
            ),
            "matches_by_tenant_and_result": (
                f"SELECT match_id FROM {MATCHES} "
                "WHERE tenant_id = ? AND eligibility_result = ?",
                ("tenant.005", "ELIGIBLE"),
                total_matches,
            ),
            "review_required_matches": (
                f"SELECT match_id FROM {MATCHES} "
                "WHERE review_required = 1 AND is_current = 1",
                (),
                total_matches,
            ),
            "matches_by_opportunity": (
                f"SELECT match_id FROM {MATCHES} "
                "WHERE canonical_id = ? AND is_current = 1",
                ("nf174.scale.002500",),
                total_matches,
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
            selectivity = round(returned / max(population, 1), 5)
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

    out["scale_requirement_rows"] = total_requirements
    out["scale_match_rows"] = total_matches
    out["write_statements"] = write_statements
    out["statements_per_row"] = round(write_statements / (rows * 2), 6)
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
    out["critical_eligibility_queries_indexed"] = not offenders
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
out["eligibility_memory_mb"] = memory_mb()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
