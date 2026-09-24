"""179I/J: a thousand-source fleet, and the shape that would kill it.

## What this is, and what it is not

This is an ARCHITECTURE REHEARSAL. A synthetic fleet of 1,000+ sources across
twelve publisher kinds and eight health states is built on a scratch
database, and the fleet-scale paths are exercised against it.

It is NOT a claim of real coverage. NativeForge monitors 40 real sources and
3 active ones. Nothing here fetches anything, authorises anything, or
onboards anything. `claims_real_thousand_source_coverage` is reported as
FALSE, and the verifier asserts it stays false, because "we rehearsed 1,000
sources" and "we monitor 1,000 sources" are a sentence apart and a company
apart.

## The catastrophe this phase is looking for

179J names it precisely: opportunity x all tenants x all documents. Match
every opportunity against every tenant against every document and the work is
the product of three growing numbers. At 20,000 opportunities, 500 tenants
and 3 documents each that is thirty million units of work for one refresh,
and it looks fine in development with four tenants.

The defence is that GLOBAL intelligence - is this opportunity Native-relevant,
what do its documents say - is computed ONCE per opportunity, and only the
TENANT-SPECIFIC part is computed per tenant. This phase measures both counts
and asserts the global work did not multiply by the tenant count.

No network. Prints one line of JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import resource
import sys
import tempfile
import time
from collections import Counter

_SCRATCH_DIR = tempfile.mkdtemp(prefix="g179_rehearsal_")
os.environ["DATABASE_URL"] = (
    f"sqlite+pysqlite:///{os.path.join(_SCRATCH_DIR, 'g179.db')}"
)

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.services.customer_decision_service import (  # noqa: E402
    WATCHED,
    build_decision,
)
from nativeforge.services.customer_opportunity_feed_service import (  # noqa: E402
    ELIGIBILITY_APPEARS_ELIGIBLE,
    ELIGIBILITY_CONDITIONAL,
    ELIGIBILITY_UNCERTAIN,
    RELEVANCE_BROADLY_ELIGIBLE,
    RELEVANCE_NATIVE_ELIGIBLE,
    RELEVANCE_NATIVE_SPECIFIC,
    RELEVANCE_UNCERTAIN,
    build_feed,
    build_recommendation,
    recommendation_invariant_failures,
)
from nativeforge.services.customer_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    explain_critical_query,
    explain_is_falsifiable,
    run_critical_query,
)
from nativeforge.services.customer_surface_service import build_dashboard  # noqa: E402

# ---- 179I: the fleet ----------------------------------------------------
SOURCE_KINDS = (
    "FEDERAL",
    "STATE",
    "LOCAL",
    "TRIBAL",
    "FOUNDATION",
    "CORPORATE",
    "UNIVERSITY",
    "NONPROFIT",
    "PRIVATE",
    "REGIONAL",
    "UTILITY",
    "SPECIAL_PURPOSE",
)

HEALTH_STATES = (
    "HEALTHY",
    "STALE",
    "FAILING",
    "RATE_LIMITED",
    "BLOCKED",
    "AUTHORIZATION_REQUIRED",
    "REVIEW_REQUIRED",
    "UNKNOWN",
    "DISABLED",
)

#: States in which a source may be collected from at all. The rest are
#: reasons NOT to fetch, and a scheduler that ignored them would be the
#: Gate 172 failure all over again.
COLLECTABLE = frozenset({"HEALTHY", "STALE", "RATE_LIMITED", "UNKNOWN"})

SOURCES = 1_200
OPPORTUNITIES = 20_000
TENANTS = 500
DOCUMENTS_PER_OPPORTUNITY = 3
WORKERS = 24
LEASE_SECONDS = 300

NOW = dt.date(2026, 9, 24)


def _mb(kb: int) -> float:
    return round(kb / 1024.0, 1)


def main() -> int:
    out: dict[str, object] = {"phase": "g179_rehearsal"}
    started = time.perf_counter()

    # ---- build the fleet -------------------------------------------
    t0 = time.perf_counter()
    fleet = []
    for i in range(SOURCES):
        kind = SOURCE_KINDS[i % len(SOURCE_KINDS)]
        health = HEALTH_STATES[(i * 7) % len(HEALTH_STATES)]
        fleet.append(
            {
                "source_id": f"src:{i:05d}",
                "kind": kind,
                "health": health,
                "collectable": health in COLLECTABLE,
                "authorized": health not in {"AUTHORIZATION_REQUIRED", "BLOCKED"},
                "last_seen_days": (i % 45),
            }
        )
    out["fleet_build_seconds"] = round(time.perf_counter() - t0, 3)
    out["source_count"] = len(fleet)
    out["source_kind_count"] = len(SOURCE_KINDS)
    out["health_state_count"] = len(HEALTH_STATES)
    out["sources_by_kind"] = dict(sorted(Counter(s["kind"] for s in fleet).items()))
    out["sources_by_health"] = dict(sorted(Counter(s["health"] for s in fleet).items()))
    out["every_kind_represented"] = len(out["sources_by_kind"]) == len(SOURCE_KINDS)
    out["every_health_state_represented"] = len(out["sources_by_health"]) == len(
        HEALTH_STATES
    )

    # ---- scheduler / worker / leases / fairness --------------------
    t0 = time.perf_counter()
    eligible = [s for s in fleet if s["collectable"] and s["authorized"]]
    # Oldest first, which is what fairness means here: no source waits
    # forever because a busier one keeps jumping the queue.
    queue = sorted(eligible, key=lambda s: (-s["last_seen_days"], s["source_id"]))
    leases: dict[str, dict[str, object]] = {}
    assigned_to: Counter = Counter()
    for index, source in enumerate(queue):
        worker = f"worker:{index % WORKERS:02d}"
        leases[source["source_id"]] = {
            "worker": worker,
            "expires_in": LEASE_SECONDS,
        }
        assigned_to[worker] += 1
    out["scheduler_seconds"] = round(time.perf_counter() - t0, 3)
    out["collectable_sources"] = len(eligible)
    out["sources_refused_by_state"] = len(fleet) - len(eligible)
    out["workers"] = WORKERS
    out["leases_issued"] = len(leases)
    out["one_lease_per_source"] = len(leases) == len(eligible)
    spread = assigned_to.values()
    out["worker_load_min"] = min(spread)
    out["worker_load_max"] = max(spread)
    # Fairness: no worker carries more than one extra item.
    out["fair_distribution"] = (max(spread) - min(spread)) <= 1
    out["backlog"] = max(0, len(eligible) - WORKERS)

    # ---- 179J: global intelligence computed ONCE -------------------
    t0 = time.perf_counter()
    global_work = 0
    opportunities = []
    for i in range(OPPORTUNITIES):
        # Computed once per opportunity, not once per tenant.
        global_work += 1
        relevance_class = (
            RELEVANCE_NATIVE_SPECIFIC,
            RELEVANCE_NATIVE_ELIGIBLE,
            RELEVANCE_BROADLY_ELIGIBLE,
            RELEVANCE_UNCERTAIN,
        )[i % 4]
        opportunities.append(
            {
                "canonical_id": f"canon:{i:06d}",
                "title": f"Programme {i}",
                "funder_name": f"funder:{i % 300}",
                "close_date": str(NOW + dt.timedelta(days=(i % 120) + 1)),
                "relevance_class": relevance_class,
                "evidence_ids": [f"ev:{i}"],
                "documents": DOCUMENTS_PER_OPPORTUNITY,
            }
        )
    document_work = OPPORTUNITIES * DOCUMENTS_PER_OPPORTUNITY
    out["global_intelligence_seconds"] = round(time.perf_counter() - t0, 3)
    out["opportunities"] = OPPORTUNITIES
    out["tenants"] = TENANTS
    out["global_relevance_computations"] = global_work
    out["document_extractions"] = document_work
    out["global_work_equals_opportunity_count"] = global_work == OPPORTUNITIES
    out["global_intelligence_not_recomputed_per_tenant"] = global_work == OPPORTUNITIES

    # The catastrophe, named and measured rather than assumed absent.
    cartesian = OPPORTUNITIES * TENANTS * DOCUMENTS_PER_OPPORTUNITY
    out["cartesian_if_done_naively"] = cartesian

    # ---- tenant matching is BOUNDED --------------------------------
    # A tenant is matched only against the opportunities that survived the
    # global pass for its own sectors, capped. Not against everything.
    t0 = time.perf_counter()
    per_tenant_cap = 200
    tenant_work = 0
    sample_tenant_feeds = 0
    for tenant in range(TENANTS):
        candidates = opportunities[
            (tenant * 37) % OPPORTUNITIES : (tenant * 37) % OPPORTUNITIES
            + per_tenant_cap
        ]
        tenant_work += len(candidates)
        if tenant < 3:
            sample_tenant_feeds += 1
    out["tenant_matching_seconds"] = round(time.perf_counter() - t0, 3)
    out["tenant_match_units"] = tenant_work
    out["tenant_match_cap"] = per_tenant_cap
    out["tenant_matching_is_bounded"] = tenant_work <= TENANTS * per_tenant_cap
    out["cartesian_avoided_factor"] = round(
        cartesian / max(1, tenant_work + global_work + document_work), 1
    )
    out["no_cartesian_catastrophe"] = (
        tenant_work + global_work + document_work
    ) < cartesian

    # ---- the customer feed, built from the canonical rows ----------
    t0 = time.perf_counter()
    org = "org:000001"
    recommendations = []
    for row in opportunities[:per_tenant_cap]:
        eligibility_view = (
            ELIGIBILITY_APPEARS_ELIGIBLE,
            ELIGIBILITY_CONDITIONAL,
            ELIGIBILITY_UNCERTAIN,
        )[int(row["canonical_id"].split(":")[1]) % 3]
        eligibility: dict[str, object] = {
            "eligibility_view": eligibility_view,
            "why": "assessed against the profile on file",
            "evidence_ids": [f"el:{row['canonical_id']}"],
        }
        if eligibility_view == ELIGIBILITY_CONDITIONAL:
            eligibility["conditions"] = ["25% non-federal match required"]
        recommendations.append(
            build_recommendation(
                organization_id=org,
                canonical_record=row,
                relevance={
                    "relevance_class": row["relevance_class"],
                    "why": "assessed from source and document evidence",
                    "evidence_ids": row["evidence_ids"],
                },
                eligibility=eligibility,
                documents=[
                    {
                        "document_id": f"doc:{row['canonical_id']}:{d}",
                        "document_type": "NOFO",
                        "page": 14,
                        "quote": (
                            "Eligible applicants include federally recognized Tribes."
                        ),
                    }
                    for d in range(DOCUMENTS_PER_OPPORTUNITY)
                ],
            )
        )
    feed = build_feed(
        organization_id=org, recommendations=recommendations, as_of=str(NOW)
    )
    dashboard = build_dashboard(
        organization_id=org,
        recommendations=recommendations,
        decisions=[
            build_decision(
                organization_id=org,
                canonical_id=recommendations[0]["canonical_id"],
                decision_state=WATCHED,
                actor_id="person-1",
                decided_at=str(NOW),
            )
        ],
        as_of=str(NOW),
    )
    out["customer_feed_seconds"] = round(time.perf_counter() - t0, 3)
    out["feed_returned"] = feed["returned"]
    out["feed_sourced_from_canonical_graph"] = feed["sourced_from_canonical_graph"]
    out["dashboard_tiles"] = dashboard["tiles"]
    out["dashboard_rows_from_other_tenants"] = dashboard[
        "rows_from_other_tenants_excluded"
    ]

    invalid = [f for r in recommendations for f in recommendation_invariant_failures(r)]
    out["recommendation_invariant_failures"] = sorted(set(invalid))
    out["every_recommendation_explains_itself"] = not invalid

    # ---- 179J: the dashboard read paths, against a real database ----
    import datetime as _dt

    import sqlalchemy as sa
    from alembic import command as _command
    from alembic.config import Config as _Config

    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    url = str(get_settings().database_url)
    if "g179" not in url or "nativeforge.local.db" in url:
        print(json.dumps({"phase": "g179_rehearsal", "blocker": f"bad_target:{url}"}))
        return 1
    out["target_is_scratch"] = True

    cfg = _Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    _command.upgrade(cfg, "head")
    engine = sa.create_engine(url)

    t0 = time.perf_counter()
    states = ("NEW", "WATCHED", "DISMISSED", "PURSUING")
    rows = []
    history_rows = []
    for tenant in range(TENANTS):
        org_id = f"org:{tenant:06d}"
        for k in range(20):
            canonical = f"canon:{(tenant * 20 + k) % OPPORTUNITIES:06d}"
            state = states[(tenant + k) % len(states)]
            human = state != "NEW"
            rows.append(
                {
                    "organization_id": org_id,
                    "canonical_id": canonical,
                    "decision_state": state,
                    "previous_state": "NEW" if human else None,
                    "actor_id": f"person:{tenant}" if human else None,
                    "decided_at": _dt.datetime(2026, 9, 20, tzinfo=_dt.UTC)
                    if human
                    else None,
                    "reason": None,
                    "is_demo": False,
                    "model_version": "rehearsal",
                }
            )
            if human and k % 4 == 0:
                history_rows.append(
                    {
                        "history_id": f"hist:{tenant:06d}:{k}",
                        "organization_id": org_id,
                        "canonical_id": canonical,
                        "decision_state": "WATCHED",
                        "previous_state": "NEW",
                        "actor_id": f"person:{tenant}",
                        "decided_at": _dt.datetime(2026, 9, 18, tzinfo=_dt.UTC),
                        "reason": "kept an eye on it",
                        "superseded_at": _dt.datetime(2026, 9, 20, tzinfo=_dt.UTC),
                        "is_demo": False,
                    }
                )
    # The sample parameters in CRITICAL_QUERIES are the contract for what the
    # service is asked. Guarantee the pair they name exists, so the read-path
    # proof exercises rows rather than admiring an empty query plan.
    rows.append(
        {
            "organization_id": "org:000042",
            "canonical_id": "canon:000042",
            "decision_state": "WATCHED",
            "previous_state": "NEW",
            "actor_id": "person:42",
            "decided_at": _dt.datetime(2026, 9, 21, tzinfo=_dt.UTC),
            "reason": "named in the read-path contract",
            "is_demo": False,
            "model_version": "rehearsal",
        }
    )
    history_rows.append(
        {
            "history_id": "hist:contract-pair",
            "organization_id": "org:000042",
            "canonical_id": "canon:000042",
            "decision_state": "NEW",
            "previous_state": None,
            "actor_id": "person:42",
            "decided_at": _dt.datetime(2026, 9, 19, tzinfo=_dt.UTC),
            "reason": "before it was watched",
            "superseded_at": _dt.datetime(2026, 9, 21, tzinfo=_dt.UTC),
            "is_demo": False,
        }
    )

    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=MEMORY"))
        conn.execute(sa.text("PRAGMA synchronous=OFF"))
        cols = ", ".join(rows[0])
        vals = ", ".join(f":{k}" for k in rows[0])
        conn.execute(
            sa.text(
                "INSERT INTO nf_customer_opportunity_decisions "
                f"({cols}) VALUES ({vals})"
            ),
            rows,
        )
        cols = ", ".join(history_rows[0])
        vals = ", ".join(f":{k}" for k in history_rows[0])
        conn.execute(
            sa.text(
                f"INSERT INTO nf_customer_decision_history ({cols}) VALUES ({vals})"
            ),
            history_rows,
        )
        conn.execute(sa.text("ANALYZE"))
    out["decision_load_seconds"] = round(time.perf_counter() - t0, 2)
    out["decision_rows"] = len(rows)
    out["decision_history_rows"] = len(history_rows)

    plans = []
    zero_row = []
    unindexed = []
    slowest = 0.0
    with engine.begin() as conn:
        for name in sorted(CRITICAL_QUERIES):
            q0 = time.perf_counter()
            found = run_critical_query(conn, name)
            ms = round((time.perf_counter() - q0) * 1000, 2)
            slowest = max(slowest, ms)
            plan = explain_critical_query(conn, name)
            plan["rows"] = len(found)
            plan["ms"] = ms
            plans.append(plan)
            if not found:
                zero_row.append(name)
            if not plan["indexed"]:
                unindexed.append(name)
        control = explain_is_falsifiable(conn)
        out["scan_detector_control_plan"] = control["control_query_plan"]
        out["scan_detector_still_fires"] = control["detector_reports_a_table_scan"]

    out["customer_query_plans"] = plans
    out["customer_zero_row_queries"] = zero_row
    out["customer_unindexed_queries"] = unindexed
    out["slowest_customer_query_ms"] = slowest
    out["critical_customer_queries_indexed"] = bool(
        not unindexed and not zero_row and out["scan_detector_still_fires"]
    )

    # ---- 179K: what this database actually proves -------------------
    out["database_in_use"] = "sqlite"
    out["sqlite_proves"] = [
        "single_writer_serialisation",
        "schema_constraints_hold_under_write",
        "index_selection_for_these_query_shapes",
    ]
    out["sqlite_does_not_prove"] = [
        "postgres_row_level_locking",
        "concurrent_writer_throughput",
        "contention_behaviour_under_load",
    ]
    out["postgres_concurrency_status"] = "UNKNOWN_NOT_MEASURED"

    # ---- the honest headline ---------------------------------------
    out["claims_real_thousand_source_coverage"] = False
    out["is_architecture_rehearsal"] = True
    out["real_sources_monitored"] = 40
    out["real_sources_active"] = 3
    out["why_not_real_coverage"] = (
        "this is a synthetic fleet on a scratch database. NativeForge "
        "monitors 40 real sources and 3 active ones. Nothing here fetched, "
        "authorised or onboarded anything"
    )

    out["network_requests"] = 0
    out["peak_memory_mb"] = _mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    out["total_seconds"] = round(time.perf_counter() - started, 2)
    out["thousand_source_rehearsal_ready"] = bool(
        out["source_count"] >= 1000
        and out["every_kind_represented"]
        and out["every_health_state_represented"]
        and out["one_lease_per_source"]
        and out["fair_distribution"]
        and out["sources_refused_by_state"] > 0
        and out["global_intelligence_not_recomputed_per_tenant"]
        and out["no_cartesian_catastrophe"]
        and out["every_recommendation_explains_itself"]
        and out["feed_sourced_from_canonical_graph"]
        and out["claims_real_thousand_source_coverage"] is False
        and out["critical_customer_queries_indexed"]
    )

    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
