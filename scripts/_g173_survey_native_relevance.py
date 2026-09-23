"""Gate 173A: what already exists for Native relevance and coverage.

NativeForge has had Native relevance code since Stage 6 and coverage-gap code
since the discovery campaign. The question this gate has to answer BEFORE
writing anything is not "does relevance code exist" - it does - but:

```text
is it wired to the canonical opportunity graph, or does it only ever see
fixture dictionaries?
```

That distinction decides whether Gate 173 reuses, bridges, or rebuilds, and
getting it wrong in either direction is expensive: rebuilding working
deterministic logic wastes it, and reusing an unwired module as though it were
authoritative produces an intelligence layer that classifies nothing real.

So every classification here is DERIVED from four measurements - does the
module import the database, does it import the Gate 167+ canonical spine, how
many other modules import it, and how many rows does its table hold - rather
than from what a docstring claims about itself.

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
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate173 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
SERVICES = REPO / "src" / "nativeforge" / "services"
DB = REPO / "nativeforge.local.db"

#: Importing any of these means the module can reach durable state.
DB_MARKERS = (
    "from nativeforge.db",
    "from nativeforge.repositories",
    "import sqlalchemy",
    "sqlalchemy as sa",
)

#: Importing any of these means the module can reach the Gate 167-172 spine -
#: the canonical opportunity graph and the source fabric that feeds it. A
#: relevance classifier that cannot reach this cannot classify a real
#: opportunity, whatever its logic is worth.
CANONICAL_MARKERS = (
    "canonical_opportunity",
    "cross_source_identity",
    "opportunity_change",
    "source_adapter_contract",
    "source_fleet_",
    "opportunity_field_provenance",
)

#: (key, kind, target, concern). Modules are paths under services/; tables are
#: SQLite names. The concerns are the ones Gate 173 names in its survey list.
PRIMITIVES: tuple[tuple[str, str, str, str], ...] = (
    # ---- the canonical spine Gate 173 must classify AGAINST --------
    ("canonical_opportunity_graph", "table", "nf_canonical_opportunities", "graph"),
    ("opportunity_versions", "table", "nf_opportunity_versions", "graph"),
    ("source_observations", "table", "nf_opportunity_source_observations", "graph"),
    ("field_provenance", "table", "nf_opportunity_field_provenance", "provenance"),
    ("field_conflicts", "table", "nf_opportunity_field_conflicts", "provenance"),
    ("change_events", "table", "nf_opportunity_change_events", "change"),
    (
        "identity_relationships",
        "table",
        "nf_opportunity_identity_relationships",
        "identity",
    ),
    (
        "collected_raw_payloads",
        "table",
        "nf_source_collection_raw_payloads",
        "evidence",
    ),
    ("active_sources", "table", "nf_active_opportunity_sources", "source_registry"),
    (
        "source_operations_events",
        "table",
        "nf_source_operations_events",
        "fleet_health",
    ),
    # ---- earlier-campaign structures that may or may not be live ---
    ("legacy_source_registry", "table", "nf_opportunity_sources", "source_registry"),
    ("source_watchlist", "table", "nf_source_watchlist_entries", "coverage"),
    ("discovery_review_items", "table", "nf_discovery_review_items", "coverage"),
    (
        "discovery_intake_candidates",
        "table",
        "nf_discovery_intake_candidates",
        "coverage",
    ),
    ("legacy_raw_payloads", "table", "nf_raw_source_payloads", "evidence"),
    ("nofo_extraction_runs", "table", "nf_nofo_extraction_runs", "documents"),
    ("award_documents", "table", "nf_award_documents", "documents"),
    ("evidence_intake_records", "table", "nf_evidence_intake_records", "evidence"),
    ("tribal_profiles", "table", "nf_tribal_profiles", "organization_profile"),
    ("spark_scores", "table", "nf_spark_scores", "eligibility"),
    # ---- Stage 6 Native relevance -----------------------------------
    (
        "relevance_label_vocabulary",
        "module",
        "native_relevance_classification_label_vocabulary_service",
        "relevance_ontology",
    ),
    (
        "relevance_evaluator",
        "module",
        "native_relevance_classification_evaluator_service",
        "relevance_classification",
    ),
    (
        "relevance_confidence",
        "module",
        "native_relevance_classification_confidence_service",
        "relevance_confidence",
    ),
    (
        "relevance_review_trigger",
        "module",
        "native_relevance_classification_human_review_trigger_service",
        "relevance_review",
    ),
    (
        "relevance_overclaim_guard",
        "module",
        "native_relevance_classification_overclaim_guard_service",
        "relevance_guard",
    ),
    (
        "relevance_over_filter_guard",
        "module",
        "native_relevance_classification_over_filter_guard_service",
        "relevance_guard",
    ),
    (
        "relevance_explanation",
        "module",
        "native_relevance_classification_explanation_builder_service",
        "relevance_explanation",
    ),
    (
        "relevance_record",
        "module",
        "native_relevance_classification_record_service",
        "relevance_storage",
    ),
    (
        "relevance_discovery_bridge",
        "module",
        "native_relevance_classification_discovery_bridge_service",
        "relevance_bridge",
    ),
    (
        "real_grant_relevance_record",
        "module",
        "real_grant_native_relevance_record_service",
        "relevance_real_projection",
    ),
    # ---- eligibility signals that are NOT keywords -------------------
    (
        "native_eligibility_codes",
        "module",
        "native_eligibility_code_classification_service",
        "applicant_eligibility",
    ),
    (
        "federal_native_eligibility",
        "module",
        "federal_native_eligibility_service",
        "applicant_eligibility",
    ),
    (
        "grants_gov_eligibility_parser",
        "module",
        "grants_gov_eligibility_parser_service",
        "applicant_eligibility",
    ),
    (
        "nofo_eligibility_parser",
        "module",
        "nofo_eligibility_parser_service",
        "applicant_eligibility",
    ),
    (
        "recognition_tier_gate",
        "module",
        "recognition_tier_eligibility_gate_service",
        "entity_classes",
    ),
    (
        "sc_recognition_geography",
        "module",
        "sc_native_recognition_and_geography_service",
        "geography",
    ),
    # ---- organization profile ----------------------------------------
    (
        "org_applicant_profile_schema",
        "module",
        "org_applicant_profile_schema_service",
        "organization_profile",
    ),
    (
        "matching_profile_provenance",
        "module",
        "matching_profile_provenance_service",
        "organization_profile",
    ),
    # ---- coverage -----------------------------------------------------
    (
        "discovery_coverage_gap",
        "module",
        "discovery_coverage_gap_service",
        "coverage_gaps",
    ),
    (
        "source_coverage_plan",
        "module",
        "source_coverage_plan_service",
        "coverage_universe",
    ),
    (
        "national_coverage_assembler",
        "module",
        "national_coverage_assembler_service",
        "coverage_universe",
    ),
    (
        "coverage_ranking_contract",
        "module",
        "coverage_ranking_contract_service",
        "coverage_ranking",
    ),
    # ---- discovery ----------------------------------------------------
    (
        "native_opportunity_discovery",
        "module",
        "native_opportunity_discovery_service",
        "candidate_detection",
    ),
)

#: One owner per fact. A fact with two owners is the duplication this survey
#: exists to prevent, and a fact with none is something Gate 173 must build.
FACT_OWNERS: dict[str, str] = {
    "what a canonical opportunity IS": "canonical_opportunity_graph",
    "which source said which field": "field_provenance",
    "when a field disagreed across sources": "field_conflicts",
    "what changed and when": "change_events",
    "the bytes a claim came from": "collected_raw_payloads",
    "which sources we collect from": "active_sources",
    "whether a source is healthy": "source_operations_events",
    "the Native relevance label vocabulary": "relevance_label_vocabulary",
    "how a label is chosen from signals": "relevance_evaluator",
    "how confident a label is": "relevance_confidence",
    "when a human must look": "relevance_review_trigger",
    "refusing a claim the evidence does not support": "relevance_overclaim_guard",
    "refusing to discard a plausible opportunity": "relevance_over_filter_guard",
    "why a label was chosen, in words": "relevance_explanation",
    "what an applicant eligibility CODE implies": "native_eligibility_codes",
    "what a NOFO's eligibility text says": "nofo_eligibility_parser",
    "what an organization can do": "org_applicant_profile_schema",
    "where coverage is missing": "discovery_coverage_gap",
}

#: The facts Gate 173 needs and no existing primitive owns. Each is a claim
#: this survey must SUBSTANTIATE by finding no owner, not a wish list.
REQUIRED_FACTS: tuple[str, ...] = (
    "a relevance classification bound to a canonical opportunity id",
    "relevance evidence rows with a typed evidence kind",
    "relevance evidence bound to the payload bytes that produced it",
    "a distinct Native entity class vocabulary",
    "an extensible sector taxonomy",
    "a high-recall candidate stage separate from classification",
    "global relevance kept separate from tenant match",
    "a source-family coverage universe with coverage states",
    "durable coverage gap signals",
    "a gold corpus with measured recall and precision",
)


def module_facts(name: str) -> dict[str, object]:
    path = SERVICES / f"{name}.py"
    if not path.is_file():
        return {"exists": False}
    text = path.read_text(encoding="utf-8")
    importers = 0
    for other in (REPO / "src").rglob("*.py"):
        if other == path:
            continue
        if name in other.read_text(encoding="utf-8", errors="ignore"):
            importers += 1
    return {
        "exists": True,
        "lines": text.count("\n") + 1,
        "db_wired": any(marker in text for marker in DB_MARKERS),
        "canonical_wired": any(marker in text for marker in CANONICAL_MARKERS),
        "imported_by": importers,
        "public_callables": len(re.findall(r"^def [a-z]", text, re.MULTILINE)),
    }


def _spine_modules() -> tuple[set[str], dict[str, str]]:
    """Every service module, and which of them can reach the Gate 167+ spine.

    Computed once. A table referenced only by modules that cannot see the
    canonical graph is being read by the past, not the present.
    """
    # The WHOLE package, not just services/. Table access lives in
    # repositories/, and scanning only services/ retired Gate 169's identity
    # tables as unwired when the repository layer reads them every time.
    package = REPO / "src" / "nativeforge"
    texts: dict[str, str] = {}
    spine: set[str] = set()
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        key = str(path.relative_to(package))
        texts[key] = text
        if any(marker in text for marker in CANONICAL_MARKERS):
            spine.add(key)
    return spine, texts


SPINE_MODULES, SERVICE_TEXTS = _spine_modules()


def table_facts(connection: sqlite3.Connection, name: str) -> dict[str, object]:
    row = connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    if not row or not row[0]:
        return {"exists": False}
    columns = [c[1] for c in connection.execute(f"PRAGMA table_info({name})")]
    total = connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]

    # A table whose every row is archived is not a live structure, and
    # counting it as one is how a legacy surface gets treated as authority.
    archived = None
    for column in ("archived_at", "watchlist_state", "archived"):
        if column in columns:
            if column == "watchlist_state":
                archived = connection.execute(
                    f"SELECT count(*) FROM {name} WHERE {column} = 'archived'"
                ).fetchone()[0]
            elif column == "archived":
                archived = connection.execute(
                    f"SELECT count(*) FROM {name} WHERE {column} = 1"
                ).fetchone()[0]
            else:
                archived = connection.execute(
                    f"SELECT count(*) FROM {name} WHERE {column} IS NOT NULL"
                ).fetchone()[0]
            break
    readers = sorted(module for module, text in SERVICE_TEXTS.items() if name in text)
    spine_readers = sorted(set(readers) & SPINE_MODULES)
    return {
        "exists": True,
        "columns": len(columns),
        "rows": total,
        "archived_rows": archived,
        "live_rows": total if archived is None else total - archived,
        "referenced_by_modules": len(readers),
        "referenced_by_current_spine": len(spine_readers),
        "spine_readers": spine_readers[:6],
    }


def classify(kind: str, facts: dict[str, object]) -> tuple[str, str]:
    """One classification, derived, with the measurement that produced it."""
    if not facts.get("exists"):
        return "UNKNOWN", "not_found_on_disk"

    if kind == "table":
        rows = int(facts.get("rows") or 0)
        live = facts.get("live_rows")
        live = rows if live is None else int(live)
        readers = int(facts.get("referenced_by_modules") or 0)
        spine = int(facts.get("referenced_by_current_spine") or 0)

        # Empty is not a verdict about the code. A table the current spine
        # writes to has simply not had its first row yet, and calling that
        # UNWIRED would retire three working Gate 169/170/172 structures.
        if rows == 0:
            if spine:
                return (
                    "READY_UNPOPULATED",
                    f"no_rows_yet_but_{spine}_spine_modules_use_it",
                )
            return "UNWIRED", f"empty_and_{readers}_modules_reference_it"
        if live == 0:
            return "LEGACY", f"all_{rows}_rows_archived"
        # Rows without a current reader is a superseded structure. This is
        # what tells nf_opportunity_sources from nf_active_opportunity_sources
        # when both hold data.
        if spine == 0:
            return "LEGACY", f"{live}_live_rows_but_no_current_spine_module_reads_it"
        return "AUTHORITATIVE", f"{live}_live_rows_read_by_{spine}_spine_modules"

    importers = int(facts.get("imported_by") or 0)
    if importers == 0:
        return "UNWIRED", "no_other_module_imports_it"
    if facts.get("db_wired") and facts.get("canonical_wired"):
        return "AUTHORITATIVE", f"db_and_canonical_wired_imported_by_{importers}"
    if facts.get("db_wired"):
        # Durable, but it cannot see the Gate 167+ graph. Useful, and not a
        # place to put a fact about a canonical opportunity.
        return "REUSABLE", f"db_wired_but_not_canonical_wired_imported_by_{importers}"
    return "REUSABLE", f"pure_logic_imported_by_{importers}"


out: dict[str, object] = {"schema_version": "nf_gate173_survey_v1"}

connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    surveyed: dict[str, dict[str, object]] = {}
    for key, kind, target, concern in PRIMITIVES:
        facts = (
            table_facts(connection, target) if kind == "table" else module_facts(target)
        )
        verdict, why = classify(kind, facts)
        surveyed[key] = {
            "kind": kind,
            "target": target,
            "concern": concern,
            "classification": verdict,
            "because": why,
            **facts,
        }
finally:
    connection.close()

out["surveyed"] = surveyed
out["primitives_surveyed"] = len(surveyed)

by_class: dict[str, list[str]] = {}
for key, entry in sorted(surveyed.items()):
    by_class.setdefault(str(entry["classification"]), []).append(key)
out["by_classification"] = by_class
out["counts_by_classification"] = {k: len(v) for k, v in sorted(by_class.items())}

# ---- one owner per fact ------------------------------------------------
owner_counts: dict[str, int] = {}
for fact, owner in FACT_OWNERS.items():
    owner_counts[fact] = 1 if owner in surveyed else 0
out["facts_mapped"] = len(FACT_OWNERS)
out["facts_without_a_surveyed_owner"] = sorted(
    fact for fact, count in owner_counts.items() if count == 0
)
out["every_fact_has_exactly_one_owner"] = not out["facts_without_a_surveyed_owner"]

owners = list(FACT_OWNERS.values())
out["owners_claiming_more_than_one_fact"] = sorted(
    {owner for owner in owners if owners.count(owner) > 1}
)

# ---- the finding that decides the gate ---------------------------------
relevance_modules = {
    key: entry
    for key, entry in surveyed.items()
    if str(entry["concern"]).startswith("relevance")
}
out["relevance_modules_found"] = len(relevance_modules)
out["relevance_modules_wired_to_the_canonical_graph"] = sorted(
    key for key, entry in relevance_modules.items() if entry.get("canonical_wired")
)
out["relevance_modules_that_only_see_fixtures"] = sorted(
    key
    for key, entry in relevance_modules.items()
    if entry.get("exists") and not entry.get("canonical_wired")
)
# This is the load-bearing survey fact. Stage 6 relevance is real, deterministic
# and guarded - and none of it can reach a canonical opportunity.
out["existing_relevance_is_unwired_from_canonical_graph"] = not out[
    "relevance_modules_wired_to_the_canonical_graph"
]

out["canonical_opportunities_available_for_real_projection"] = int(
    surveyed["canonical_opportunity_graph"].get("rows") or 0
)
out["provenance_rows_available"] = int(surveyed["field_provenance"].get("rows") or 0)

# ---- what must be built -------------------------------------------------
owned_facts = set(FACT_OWNERS)
out["gate173_must_build"] = [fact for fact in REQUIRED_FACTS if fact not in owned_facts]
out["gate173_must_reuse"] = sorted(
    key
    for key, entry in surveyed.items()
    if entry["classification"] in {"AUTHORITATIVE", "REUSABLE"}
)
out["gate173_must_not_duplicate"] = sorted(
    {
        FACT_OWNERS[fact]
        for fact in (
            "which source said which field",
            "when a field disagreed across sources",
            "what changed and when",
            "the bytes a claim came from",
            "which sources we collect from",
        )
    }
)

# ---- the classifier must be able to say it does not know ---------------
# A survey that returns a confident verdict for everything, including things
# that do not exist, is not measuring anything.
out["planted_missing_module"] = classify(
    "module", module_facts("nf_gate173_module_that_does_not_exist")
)[0]
out["planted_missing_table"] = classify(
    "table", table_facts(sqlite3.connect(":memory:"), "nf_gate173_absent_table")
)[0]
out["survey_can_report_unknown"] = (
    out["planted_missing_module"] == "UNKNOWN"
    and out["planted_missing_table"] == "UNKNOWN"
)

# Empty-but-wired is a distinct answer from nothing-uses-this, and Gate 169,
# 170 and 172 each own a structure that is correctly empty today.
out["ready_unpopulated"] = sorted(by_class.get("READY_UNPOPULATED", []))
out["empty_is_distinguished_from_unwired"] = bool(out["ready_unpopulated"])

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
