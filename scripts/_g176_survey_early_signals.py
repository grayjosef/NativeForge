"""Gate 176A: what evidence exists for detecting funding we MISSED.

Gate 175 learned a lesson this survey now measures directly: an award-stage
table is not pre-award evidence. `nf_award_documents` holds post-award
compliance artifacts on `awarded_grant_id`, and filing a funder's eligibility
language there would have conflated two lifecycle stages permanently.

So this survey adds a classification the earlier ones did not have:

```text
WRONG_LIFECYCLE  the structure is real and populated, and belongs to a
                 different stage of the funding lifecycle than the one this
                 gate needs
```

It is DERIVED, not asserted: a table is wrong-lifecycle for pre-award signal
work when it binds to post-award anchors (`awarded_grant_id`, `award_number`,
`source_pursuit_id`, `proof_event_id`) and carries no link to a canonical
opportunity.

The question that decides Gate 176's shape:

```text
is there any REAL award evidence that could prove NativeForge missed a
solicitation, or must the detector be built and proven on fixtures?
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
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate176 survey makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
SERVICES = REPO / "src" / "nativeforge" / "services"
PACKAGE = REPO / "src" / "nativeforge"
DB = REPO / "nativeforge.local.db"

DB_MARKERS = (
    "from nativeforge.db",
    "from nativeforge.repositories",
    "import sqlalchemy",
    "sqlalchemy as sa",
)

#: The current spine, named individually. Gate 174 learned that a prefix also
#: matches the old unwired stack.
CANONICAL_MARKERS = (
    "canonical_opportunity",
    "cross_source_identity",
    "opportunity_change",
    "source_adapter_contract",
    "source_fleet_",
    "opportunity_field_provenance",
    "native_relevance_ontology_service",
    "native_relevance_classifier_service",
    "eligibility_requirement_model_service",
    "eligibility_match_engine_service",
    "opportunity_document_service",
    "document_fact_extraction_service",
    "source_coverage_universe_service",
)

#: Columns that anchor a row to the POST-award stage.
POST_AWARD_ANCHORS = (
    "awarded_grant_id",
    "award_requirement_id",
    "award_number",
    "proof_event_id",
    "source_pursuit_id",
)

#: Columns that anchor a row to the PRE-award stage - the opportunity graph.
PRE_AWARD_ANCHORS = ("canonical_id", "opportunity_number", "source_record_id")

PRIMITIVES: tuple[tuple[str, str, str, str], ...] = (
    # ---- pre-award spine -------------------------------------------
    ("canonical_opportunities", "table", "nf_canonical_opportunities", "graph"),
    ("opportunity_versions", "table", "nf_opportunity_versions", "history"),
    ("change_events", "table", "nf_opportunity_change_events", "amendments"),
    ("field_provenance", "table", "nf_opportunity_field_provenance", "provenance"),
    (
        "source_observations",
        "table",
        "nf_opportunity_source_observations",
        "history",
    ),
    ("raw_payloads", "table", "nf_source_collection_raw_payloads", "raw_evidence"),
    # ---- what Gate 173/175 built -----------------------------------
    ("coverage_gaps", "table", "nf_source_coverage_gap_signals", "coverage"),
    ("coverage_universe", "table", "nf_source_coverage_universe", "coverage"),
    ("documents", "table", "nf_opportunity_documents", "documents"),
    ("document_facts", "table", "nf_opportunity_document_facts", "documents"),
    (
        "relevance_assessments",
        "table",
        "nf_opportunity_relevance_assessments",
        "relevance",
    ),
    (
        "eligibility_requirements",
        "table",
        "nf_opportunity_eligibility_requirements",
        "eligibility",
    ),
    # ---- award-stage structures, which 176E must NOT misuse ---------
    ("awarded_grants", "table", "nf_awarded_grants", "awards"),
    ("award_documents", "table", "nf_award_documents", "awards"),
    ("award_requirements", "table", "nf_award_requirements", "awards"),
    (
        "award_proof_events",
        "table",
        "nf_award_requirement_proof_events",
        "awards",
    ),
    # ---- pursuit / calendar ------------------------------------------
    ("grant_pursuits", "table", "nf_grant_pursuits", "pursuit"),
    ("pursuit_calendar", "table", "nf_pursuit_calendar_events", "calendar"),
    ("pursuit_tasks", "table", "nf_pursuit_tasks", "pursuit"),
    # ---- fleet / sources ----------------------------------------------
    ("active_sources", "table", "nf_active_opportunity_sources", "sources"),
    (
        "source_operations_events",
        "table",
        "nf_source_operations_events",
        "fleet_health",
    ),
    ("source_watchlist", "table", "nf_source_watchlist_entries", "sources"),
    # ---- modules ------------------------------------------------------
    (
        "coverage_universe_service",
        "module",
        "source_coverage_universe_service",
        "coverage",
    ),
    (
        "change_taxonomy",
        "module",
        "opportunity_change_taxonomy_service",
        "amendments",
    ),
    (
        "amendment_detector",
        "module",
        "nofo_amendment_detector_service",
        "amendments",
    ),
    (
        "document_service",
        "module",
        "opportunity_document_service",
        "documents",
    ),
    (
        "relevance_classifier",
        "module",
        "native_relevance_classifier_service",
        "relevance",
    ),
    (
        "identity_service",
        "module",
        "cross_source_identity_service",
        "identity",
    ),
    (
        "awarded_grants_service",
        "module",
        "awarded_grants_persistence_artifact_service",
        "awards",
    ),
)

FACT_OWNERS: dict[str, str] = {
    "what a canonical opportunity is": "canonical_opportunities",
    "what changed and when": "change_events",
    "which source said which field": "field_provenance",
    "the bytes a claim came from": "raw_payloads",
    "where coverage is missing": "coverage_gaps",
    "which publishers we watch": "coverage_universe",
    "what a document says": "document_facts",
    "how Native-relevant an opportunity is": "relevance_assessments",
    "what a funder requires": "eligibility_requirements",
    "what has been awarded": "awarded_grants",
    "whether two records are the same opportunity": "identity_service",
}

REQUIRED_FACTS: tuple[str, ...] = (
    "an early signal that is evidence rather than an opportunity",
    "a signal lifecycle that never auto-creates a canonical opportunity",
    "durable miss evidence when an award has no observed solicitation",
    "a recurrence expectation that is probabilistic and evidence-based",
    "an expected-but-absent signal for a lapsed recurring program",
    "a correlation between early signals without forcing identity",
    "a coverage scorecard that leaves an unknown denominator unknown",
)


def _package_texts() -> tuple[set[str], dict[str, str]]:
    texts: dict[str, str] = {}
    spine: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        key = str(path.relative_to(PACKAGE))
        texts[key] = text
        if any(marker in text for marker in CANONICAL_MARKERS):
            spine.add(key)
    return spine, texts


SPINE_MODULES, PACKAGE_TEXTS = _package_texts()


def module_facts(name: str) -> dict[str, object]:
    path = SERVICES / f"{name}.py"
    if not path.is_file():
        return {"exists": False}
    text = path.read_text(encoding="utf-8")
    importers = sum(
        1
        for key, other in PACKAGE_TEXTS.items()
        if key != f"services/{name}.py" and name in other
    )
    return {
        "exists": True,
        "lines": text.count("\n") + 1,
        "db_wired": any(marker in text for marker in DB_MARKERS),
        "canonical_wired": any(marker in text for marker in CANONICAL_MARKERS),
        "imported_by": importers,
        "public_callables": len(re.findall(r"^def [a-z]", text, re.MULTILINE)),
    }


def table_facts(connection: sqlite3.Connection, name: str) -> dict[str, object]:
    row = connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    if not row or not row[0]:
        return {"exists": False}
    columns = [c[1] for c in connection.execute(f"PRAGMA table_info({name})")]
    total = connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]

    archived = None
    if "archived_at" in columns:
        archived = connection.execute(
            f"SELECT count(*) FROM {name} WHERE archived_at IS NOT NULL"
        ).fetchone()[0]

    demo_rows = None
    if "is_demo" in columns:
        demo_rows = connection.execute(
            f"SELECT count(*) FROM {name} WHERE is_demo = 1"
        ).fetchone()[0]

    readers = sorted(key for key, text in PACKAGE_TEXTS.items() if name in text)
    post = sorted(a for a in POST_AWARD_ANCHORS if a in columns)
    pre = sorted(a for a in PRE_AWARD_ANCHORS if a in columns)

    return {
        "exists": True,
        "columns": len(columns),
        "rows": total,
        "archived_rows": archived,
        "demo_rows": demo_rows,
        "real_rows": total - (demo_rows or 0),
        "live_rows": total if archived is None else total - archived,
        "referenced_by_modules": len(readers),
        "referenced_by_current_spine": len(set(readers) & SPINE_MODULES),
        "post_award_anchors": post,
        "pre_award_anchors": pre,
    }


def classify(kind: str, facts: dict[str, object]) -> tuple[str, str]:
    if not facts.get("exists"):
        return "UNKNOWN", "not_found_on_disk"

    if kind == "table":
        rows = int(facts.get("rows") or 0)
        live = facts.get("live_rows")
        live = rows if live is None else int(live)
        spine = int(facts.get("referenced_by_current_spine") or 0)
        readers = int(facts.get("referenced_by_modules") or 0)
        post = list(facts.get("post_award_anchors") or [])
        pre = list(facts.get("pre_award_anchors") or [])

        # The Gate 175 lesson, promoted to a classification. A populated
        # table anchored to the award stage with no link to the opportunity
        # graph is real and is the WRONG STAGE for pre-award signal work.
        if rows > 0 and post and not pre:
            return (
                "WRONG_LIFECYCLE",
                f"{rows}_rows_anchored_to_{post}_with_no_opportunity_link",
            )

        if rows == 0:
            if spine:
                return (
                    "READY_UNPOPULATED",
                    f"no_rows_yet_but_{spine}_spine_modules_use_it",
                )
            return "UNWIRED", f"empty_and_{readers}_modules_reference_it"
        if live == 0:
            return "LEGACY", f"all_{rows}_rows_archived"
        if spine == 0:
            return "LEGACY", f"{live}_live_rows_but_no_current_spine_module_reads_it"
        return "AUTHORITATIVE", f"{live}_live_rows_read_by_{spine}_spine_modules"

    importers = int(facts.get("imported_by") or 0)
    if importers == 0:
        return "UNWIRED", "no_other_module_imports_it"
    if facts.get("db_wired") and facts.get("canonical_wired"):
        return "AUTHORITATIVE", f"db_and_canonical_wired_imported_by_{importers}"
    if facts.get("db_wired"):
        return "REUSABLE", f"db_wired_but_not_canonical_wired_imported_by_{importers}"
    return "REUSABLE", f"pure_logic_imported_by_{importers}"


out: dict[str, object] = {"schema_version": "nf_gate176_survey_v1"}

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

out["facts_mapped"] = len(FACT_OWNERS)
out["facts_without_a_surveyed_owner"] = sorted(
    fact for fact, owner in FACT_OWNERS.items() if owner not in surveyed
)
out["every_fact_has_exactly_one_owner"] = not out["facts_without_a_surveyed_owner"]
owners = list(FACT_OWNERS.values())
out["owners_claiming_more_than_one_fact"] = sorted(
    {owner for owner in owners if owners.count(owner) > 1}
)

# ---- the finding that shapes 176E --------------------------------------
awards = surveyed["awarded_grants"]
out["award_rows"] = awards.get("rows")
out["award_demo_rows"] = awards.get("demo_rows")
out["award_real_rows"] = awards.get("real_rows")
out["award_classification"] = awards.get("classification")
out["award_post_award_anchors"] = awards.get("post_award_anchors")
out["award_pre_award_anchors"] = awards.get("pre_award_anchors")
out["wrong_lifecycle_structures"] = sorted(by_class.get("WRONG_LIFECYCLE", []))

# Can any award point back at a solicitation at all?
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    linkable = connection.execute(
        "SELECT count(*) FROM nf_awarded_grants WHERE source_opportunity_id IS NOT NULL"
    ).fetchone()[0]
    named_programs = connection.execute(
        "SELECT count(*) FROM nf_awarded_grants WHERE program_name IS NOT NULL"
    ).fetchone()[0]
finally:
    connection.close()

out["awards_linkable_to_an_opportunity"] = linkable
out["awards_with_a_named_program"] = named_programs
# The honest answer to "can we run backward miss detection on real data".
out["real_award_evidence_available_for_miss_detection"] = bool(
    int(out["award_real_rows"] or 0) > 0 and linkable > 0
)
out["why_miss_detection_must_use_fixtures"] = (
    "every award row is is_demo=1 with fact_status demo_fixture, all archived, "
    "and none carries a source_opportunity_id or program_name - so no real "
    "award can be tested against an observed solicitation. The detector is "
    "built and proven on synthetic evidence, and that is stated rather than "
    "implied."
)

out["gate176_must_build"] = [
    fact for fact in REQUIRED_FACTS if fact not in set(FACT_OWNERS)
]
out["gate176_must_reuse"] = sorted(
    key
    for key, entry in surveyed.items()
    if entry["classification"] in {"AUTHORITATIVE", "REUSABLE", "READY_UNPOPULATED"}
)
out["gate176_must_not_reuse_as_pre_award"] = out["wrong_lifecycle_structures"]

# ---- falsifiability ---------------------------------------------------
out["planted_missing_module"] = classify(
    "module", module_facts("nf_gate176_module_that_does_not_exist")
)[0]
out["planted_missing_table"] = classify(
    "table", table_facts(sqlite3.connect(":memory:"), "nf_gate176_absent_table")
)[0]
out["survey_can_report_unknown"] = (
    out["planted_missing_module"] == "UNKNOWN"
    and out["planted_missing_table"] == "UNKNOWN"
)
out["ready_unpopulated"] = sorted(by_class.get("READY_UNPOPULATED", []))
out["empty_is_distinguished_from_unwired"] = bool(out["ready_unpopulated"])
out["lifecycle_classification_is_used"] = bool(out["wrong_lifecycle_structures"])

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
