"""Gate 179A: what a real customer can actually be shown, and from what.

Gate 179's mission is to make the system usable by a real customer, and its
sharpest instruction is a prohibition:

    "Do not have the buyer workspace depend on hand-created demo sparks."

So the first question this survey answers is whether the customer-facing feed
is fed by the CANONICAL GRAPH - the opportunity store, Native relevance,
eligibility and documents built in gates 167-175 - or by fixtures somebody
wrote by hand for a demo. A workspace built on hand-made sparks demonstrates
beautifully and tells you nothing about whether the intelligence works.

Four questions decide Gate 179's shape:

```text
1. is there a buyer-facing recommendation read model at all, and is it
   sourced from the canonical graph or from demo fixtures?
2. do watch / dismiss / pursue exist as DURABLE state, or only as UI?
3. are customer and operator capabilities separated, or does one API
   surface both?
4. what does the database actually prove about concurrency? 179K forbids
   claiming Postgres row-level concurrency that was never measured.
```

No network. No writes.
"""

from __future__ import annotations

import json
import pathlib
import re
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate179 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
API = REPO / "src" / "nativeforge" / "api"
SERVICES = REPO / "src" / "nativeforge" / "services"
PACKAGE = REPO / "src" / "nativeforge"
DB = REPO / "nativeforge.local.db"

#: The canonical intelligence built in gates 167-175. A customer feed that
#: imports none of these is not showing the customer what the system knows.
CANONICAL_MODULES = (
    "native_relevance_classifier_service",
    "native_relevance_evidence_service",
    "eligibility_match_engine_service",
    "opportunity_document_service",
    "document_fact_extraction_service",
    "canonical_opportunity_store_service",
)

#: Modules whose names suggest hand-built demo content. Named individually,
#: because Gate 173 learned that a name prefix lies.
DEMO_FIXTURE_MODULES = (
    "grant_spark_demo_fixture_service",
    "stage12_demo_fixture_service",
    "sc_customer_demo_fixture_service",
    "nm_wa_operator_demo_service",
)

#: Operator-only capabilities. 179G says a customer must not see these.
OPERATOR_CAPABILITIES = {
    "source_activation": re.compile(r"activat(e|ion)", re.I),
    "demo_real_toggle": re.compile(r"\bplane\b|demo_or_real|is_demo_toggle", re.I),
    "source_authorization_mutation": re.compile(
        r"source_authorization|authorize_source", re.I
    ),
    "verifier_surface": re.compile(r"verifier|readiness_lane", re.I),
    "entitlement_override": re.compile(
        r"forgive|paid_through|relicense|grant_benefit_extension", re.I
    ),
}

#: Tables that would hold durable customer decisions.
DECISION_TABLES = (
    "nf_source_watchlist_entries",
    "nf_tenant_source_watchlist",
    "nf_tenant_pursuit_suppressions",
    "nf_grant_pursuits",
)

SOURCE_TABLES = (
    "nf_opportunity_sources",
    "nf_active_opportunity_sources",
    "nf_source_collection_jobs",
)

API_SOURCES = {p.name: p.read_text(encoding="utf-8") for p in API.glob("*.py")}
SERVICE_SOURCES = {p.stem: p.read_text(encoding="utf-8") for p in SERVICES.glob("*.py")}
PACKAGE_SOURCES = {
    str(p.relative_to(PACKAGE)): p.read_text(encoding="utf-8")
    for p in PACKAGE.rglob("*.py")
}


def _imports(module: str) -> list[str]:
    marker = f"import {module}"
    alt = f"from nativeforge.services.{module} import"
    return sorted(
        name
        for name, body in PACKAGE_SOURCES.items()
        if (marker in body or alt in body) and not name.endswith(f"{module}.py")
    )


def main() -> int:
    out: dict[str, object] = {"schema_version": "nf_gate179_survey_v1"}

    # ---- question 1: what feeds the customer? -----------------------
    customer_routes = sorted(
        name
        for name in API_SOURCES
        if re.search(r"workspace|spark|digest|pursuit|opportunit", name, re.I)
    )
    out["customer_facing_route_modules"] = customer_routes

    canonical_wired = {m: _imports(m) for m in CANONICAL_MODULES}
    out["canonical_modules_imported_by"] = {
        m: len(v) for m, v in canonical_wired.items()
    }
    out["canonical_modules_with_no_importer"] = sorted(
        m for m, v in canonical_wired.items() if not v
    )

    # Does any API route reach the canonical intelligence, directly or
    # through a service it imports?
    api_blob = "\n".join(API_SOURCES.values())
    out["api_imports_canonical_intelligence"] = any(
        m in api_blob for m in CANONICAL_MODULES
    )

    demo_present = {m: bool(SERVICE_SOURCES.get(m)) for m in DEMO_FIXTURE_MODULES}
    out["demo_fixture_modules_present"] = sorted(
        m for m, present in demo_present.items() if present
    )
    out["api_references_demo_fixtures"] = sorted(
        name
        for name, body in API_SOURCES.items()
        if re.search(r"demo_fixture|demo_spark|seed_demo", body, re.I)
    )
    out["buyer_feed_depends_on_hand_made_sparks"] = (
        bool(out["api_references_demo_fixtures"])
        and not out["api_imports_canonical_intelligence"]
    )

    # ---- question 2: durable decisions ------------------------------
    tables: dict[str, object] = {}
    source_counts: dict[str, int] = {}
    if DB.exists():
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            present = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            for table in DECISION_TABLES:
                if table in present:
                    rows = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
                    tables[table] = {
                        "rows": rows,
                        "records_actor": any(
                            c in cols for c in ("actor_id", "identity_id", "created_by")
                        ),
                        "records_time": any(
                            c in cols for c in ("created_at", "recorded_at")
                        ),
                        "records_reason": "reason" in cols,
                        "records_state_history": any(
                            c in cols for c in ("state", "status", "revoked_at")
                        ),
                    }
                else:
                    tables[table] = {"exists": False}
            for table in SOURCE_TABLES:
                if table in present:
                    source_counts[table] = conn.execute(
                        f"SELECT count(*) FROM {table}"
                    ).fetchone()[0]
        finally:
            conn.close()

    out["decision_tables"] = tables
    out["watch_dismiss_pursue_durable"] = all(
        isinstance(v, dict) and v.get("records_actor") and v.get("records_time")
        for v in tables.values()
        if isinstance(v, dict) and v.get("exists") is not False
    )
    out["source_counts"] = source_counts
    out["live_source_count"] = max(source_counts.values()) if source_counts else 0
    # 179I asks for a fleet of at least a thousand. Whatever is here now is
    # the baseline the rehearsal has to reach from.
    out["thousand_source_rehearsal_needed"] = out["live_source_count"] < 1000

    # ---- question 3: customer vs operator ---------------------------
    leaks: dict[str, list[str]] = {}
    for label, pattern in OPERATOR_CAPABILITIES.items():
        hits = sorted(
            name
            for name in customer_routes
            if pattern.search(API_SOURCES.get(name, ""))
        )
        if hits:
            leaks[label] = hits
    out["operator_capability_mentions_in_customer_routes"] = leaks
    # A mention is not a leak - a route may name a concept in a comment or a
    # guard. This measures where to LOOK, and 179G decides what to build.
    out["customer_operator_separation_needs_a_contract"] = bool(leaks)

    # ---- question 4: what does the database prove? ------------------
    postgres_modules = sorted(
        name
        for name, body in PACKAGE_SOURCES.items()
        if re.search(r"psycopg|postgresql://|postgres_dsn", body, re.I)
    )
    out["postgres_referencing_modules"] = postgres_modules
    harness = sorted(
        str(p.relative_to(REPO))
        for p in REPO.rglob("*postgres*")
        if p.is_file() and ".venv" not in str(p) and p.suffix in {".py", ".sh", ".yml"}
    )
    out["postgres_harness_files"] = harness
    out["database_in_use"] = "sqlite"
    # 179K: do not claim what was not measured.
    out["postgres_concurrency_status"] = "UNKNOWN_NOT_MEASURED"
    out["why_postgres_concurrency_unknown"] = (
        "the local database is SQLite. SQLite proves single-writer "
        "serialisation and that the schema's constraints hold; it proves "
        "nothing about Postgres row-level locking under concurrent writers, "
        "and no such harness has been run here"
    )

    out["network_requests"] = _NETWORK["attempts"]
    out["wrote_nothing"] = True

    out["gate179_must_build"] = sorted(
        item
        for item, needed in {
            "buyer_recommendation_read_model": not out[
                "api_imports_canonical_intelligence"
            ],
            "explanation_contract": True,
            "watch_dismiss_pursue_contract": True,
            "customer_dashboard_read_models": True,
            "customer_operator_surface_contract": True,
            "trust_experience_contract": True,
            "thousand_source_rehearsal": out["thousand_source_rehearsal_needed"],
            "demo_customer_story": True,
            "ux_smoke_checklist": True,
        }.items()
        if needed
    )

    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
