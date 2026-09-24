"""Gate 174A: what already exists for eligibility, and what it can reach.

Gate 173's survey established the question worth asking, because asking the
obvious one produced a wrong answer. "Does eligibility code exist" is not
useful - NativeForge has a Stage 7 eligibility-fit stack, a Grants.gov
eligibility parser, a NOFO eligibility parser, an exclusion-evidence service
with real restriction phrases, and a recognition-tier gate. The useful
question is:

```text
can any of it reach a canonical opportunity, and does any of it treat a
negative requirement as a first-class fact?
```

The second half matters as much as the first. A layer that models eligibility
only as a list of who MAY apply will represent "Tribes are excluded" as the
absence of Tribes from a list, which is indistinguishable from "nobody wrote
the list down". Gate 174 needs those to be different facts.

Classification is derived from the same four measurements Gate 173 settled on,
including the distinction between a table that is empty because nothing uses
it and one that is empty because nothing has happened yet.

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
        raise OSError("gate174 survey makes no network request")


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

#: Reaching the Gate 167+ spine, now including Gate 173's relevance layer -
#: eligibility has to consume relevance, not restate it.
#:
#: The Gate 173 modules are named INDIVIDUALLY rather than by prefix. A
#: `native_relevance_` prefix also matches the Stage 6 stack
#: (`native_relevance_classification_record_service`,
#: `native_relevance_preview`), which Gate 173 established cannot reach a
#: canonical opportunity - so the prefix reported four Stage 7 modules as
#: spine-wired on the strength of an import of something that is itself
#: unwired. A naming convention is not a capability.
CANONICAL_MARKERS = (
    "canonical_opportunity",
    "cross_source_identity",
    "opportunity_change",
    "source_adapter_contract",
    "source_fleet_",
    "opportunity_field_provenance",
    "native_relevance_ontology_service",
    "native_relevance_evidence_service",
    "native_relevance_candidate_service",
    "native_relevance_classifier_service",
    "native_relevance_repository_service",
    "source_coverage_universe_service",
)

PRIMITIVES: tuple[tuple[str, str, str, str], ...] = (
    # ---- what Gate 173 just built, which 174 must consume ----------
    (
        "relevance_assessments",
        "table",
        "nf_opportunity_relevance_assessments",
        "relevance",
    ),
    ("relevance_evidence", "table", "nf_opportunity_relevance_evidence", "relevance"),
    (
        "relevance_ontology",
        "module",
        "native_relevance_ontology_service",
        "relevance",
    ),
    (
        "relevance_evidence_contract",
        "module",
        "native_relevance_evidence_service",
        "relevance",
    ),
    # ---- Stage 7 eligibility fit -------------------------------------
    (
        "fit_dimension_vocabulary",
        "module",
        "eligibility_fit_assessment_dimension_vocabulary_service",
        "eligibility_vocabulary",
    ),
    (
        "fit_evaluator",
        "module",
        "eligibility_fit_assessment_evaluator_service",
        "eligibility_evaluation",
    ),
    (
        "fit_dimension_evaluator",
        "module",
        "eligibility_fit_assessment_dimension_evaluator_service",
        "eligibility_evaluation",
    ),
    (
        "fit_confidence",
        "module",
        "eligibility_fit_assessment_confidence_service",
        "eligibility_confidence",
    ),
    (
        "fit_missing_data",
        "module",
        "eligibility_fit_assessment_missing_data_service",
        "eligibility_unknown",
    ),
    (
        "fit_blockers",
        "module",
        "eligibility_fit_assessment_blockers_service",
        "eligibility_blockers",
    ),
    (
        "fit_no_claim_without_evidence",
        "module",
        "eligibility_fit_assessment_no_claim_without_evidence_guard_service",
        "eligibility_guard",
    ),
    (
        "fit_record",
        "module",
        "eligibility_fit_assessment_record_service",
        "eligibility_storage",
    ),
    # ---- requirement and exclusion evidence ---------------------------
    (
        "eligibility_evidence_contract",
        "module",
        "eligibility_evidence_contract_service",
        "requirement_evidence",
    ),
    (
        "eligibility_evidence_quality",
        "module",
        "eligibility_evidence_quality_service",
        "requirement_evidence",
    ),
    (
        "eligibility_exclusion_evidence",
        "module",
        "eligibility_exclusion_evidence_service",
        "disqualifiers",
    ),
    (
        "grant_eligibility_conditions",
        "module",
        "grant_eligibility_conditions_service",
        "conditions",
    ),
    # ---- parsers ------------------------------------------------------
    (
        "grants_gov_eligibility_parser",
        "module",
        "grants_gov_eligibility_parser_service",
        "eligibility_parsing",
    ),
    (
        "grants_gov_eligibility_completeness",
        "module",
        "grants_gov_eligibility_completeness_service",
        "eligibility_parsing",
    ),
    (
        "nofo_eligibility_parser",
        "module",
        "nofo_eligibility_parser_service",
        "eligibility_parsing",
    ),
    (
        "native_eligibility_codes",
        "module",
        "native_eligibility_code_classification_service",
        "applicant_classes",
    ),
    (
        "federal_native_eligibility",
        "module",
        "federal_native_eligibility_service",
        "applicant_classes",
    ),
    (
        "recognition_tier_gate",
        "module",
        "recognition_tier_eligibility_gate_service",
        "recognition",
    ),
    # ---- organization profile -----------------------------------------
    (
        "org_applicant_profile_schema",
        "module",
        "org_applicant_profile_schema_service",
        "organization_profile",
    ),
    (
        "organization_evidence_eligibility",
        "module",
        "organization_evidence_eligibility_integration_service",
        "organization_profile",
    ),
    ("tribal_profiles", "table", "nf_tribal_profiles", "organization_profile"),
    ("spark_scores", "table", "nf_spark_scores", "eligibility_storage"),
    ("spark_requirements", "table", "nf_spark_requirements", "requirements"),
    # ---- change, which 174J must reuse rather than duplicate ----------
    ("change_events", "table", "nf_opportunity_change_events", "change"),
    (
        "change_taxonomy",
        "module",
        "opportunity_change_taxonomy_service",
        "change",
    ),
)

#: One owner per fact.
FACT_OWNERS: dict[str, str] = {
    "what an applicant eligibility CODE implies": "native_eligibility_codes",
    "what a Grants.gov eligibility record says": "grants_gov_eligibility_parser",
    "what a NOFO's eligibility text says": "nofo_eligibility_parser",
    "which applicant classes a restriction excludes": "eligibility_exclusion_evidence",
    "what federal recognition tier a class sits in": "recognition_tier_gate",
    "what an organization can do": "org_applicant_profile_schema",
    "how sure an eligibility claim is": "fit_confidence",
    "what is missing from an eligibility claim": "fit_missing_data",
    "refusing a claim with no evidence": "fit_no_claim_without_evidence",
    "how Native-relevant an opportunity is": "relevance_ontology",
    "the evidence a relevance claim rests on": "relevance_evidence_contract",
    "what changed and when": "change_events",
}

#: Facts Gate 174 needs. Substantiated by finding no owner above.
REQUIRED_FACTS: tuple[str, ...] = (
    "a normalized eligibility requirement bound to a canonical opportunity",
    "requirement kinds separated from their original text",
    "a disqualifier as a first-class row rather than an absence",
    "a six-valued eligibility result that is not a boolean",
    "a versioned organization capability profile",
    "an explainable match naming satisfied, unsatisfied and unknown requirements",
    "tribal entity classes that do not transfer eligibility between themselves",
    "a tenant match that consumes global normalization instead of reparsing",
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
    for column in ("archived_at", "archived"):
        if column in columns:
            predicate = (
                f"{column} IS NOT NULL" if column == "archived_at" else f"{column} = 1"
            )
            archived = connection.execute(
                f"SELECT count(*) FROM {name} WHERE {predicate}"
            ).fetchone()[0]
            break

    readers = sorted(key for key, text in PACKAGE_TEXTS.items() if name in text)
    return {
        "exists": True,
        "columns": len(columns),
        "rows": total,
        "archived_rows": archived,
        "live_rows": total if archived is None else total - archived,
        "referenced_by_modules": len(readers),
        "referenced_by_current_spine": len(set(readers) & SPINE_MODULES),
    }


def classify(kind: str, facts: dict[str, object]) -> tuple[str, str]:
    if not facts.get("exists"):
        return "UNKNOWN", "not_found_on_disk"

    if kind == "table":
        rows = int(facts.get("rows") or 0)
        live = facts.get("live_rows")
        live = rows if live is None else int(live)
        readers = int(facts.get("referenced_by_modules") or 0)
        spine = int(facts.get("referenced_by_current_spine") or 0)
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


out: dict[str, object] = {"schema_version": "nf_gate174_survey_v1"}

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

# ---- the two findings that shape the gate -----------------------------
eligibility_modules = {
    key: entry
    for key, entry in surveyed.items()
    if entry["kind"] == "module" and str(entry["concern"]).startswith("eligibility")
}
out["eligibility_modules_found"] = len(eligibility_modules)
out["eligibility_modules_wired_to_the_canonical_graph"] = sorted(
    key for key, entry in eligibility_modules.items() if entry.get("canonical_wired")
)
out["existing_eligibility_is_unwired_from_canonical_graph"] = not out[
    "eligibility_modules_wired_to_the_canonical_graph"
]
# Stage 7 consumes the STAGE 6 relevance preview, which is itself unwired.
# Reported separately so "eligibility already knows about relevance" cannot be
# mistaken for "eligibility can reach a canonical opportunity".
out["eligibility_modules_using_the_stage6_relevance_preview"] = sorted(
    key
    for key, entry in eligibility_modules.items()
    if "native_relevance_preview"
    in (PACKAGE_TEXTS.get(f"services/{entry['target']}.py") or "")
    or "native_relevance_classification_record_service"
    in (PACKAGE_TEXTS.get(f"services/{entry['target']}.py") or "")
)
out["stage7_consumes_an_unwired_stage6_preview"] = bool(
    out["eligibility_modules_using_the_stage6_relevance_preview"]
)

# Does anything already treat a negative requirement as a first-class fact?
exclusion = surveyed.get("eligibility_exclusion_evidence", {})
out["a_disqualifier_service_exists"] = bool(exclusion.get("exists"))
out["disqualifier_service_classification"] = exclusion.get("classification")
out["disqualifier_service_is_canonical_wired"] = bool(exclusion.get("canonical_wired"))

out["gate174_must_build"] = [
    fact for fact in REQUIRED_FACTS if fact not in set(FACT_OWNERS)
]
out["gate174_must_reuse"] = sorted(
    key
    for key, entry in surveyed.items()
    if entry["classification"] in {"AUTHORITATIVE", "REUSABLE"}
)
out["gate174_must_not_duplicate"] = sorted(
    {
        FACT_OWNERS[fact]
        for fact in (
            "what changed and when",
            "how Native-relevant an opportunity is",
            "the evidence a relevance claim rests on",
            "which applicant classes a restriction excludes",
        )
    }
)

# ---- the classifier must be able to say it does not know --------------
out["planted_missing_module"] = classify(
    "module", module_facts("nf_gate174_module_that_does_not_exist")
)[0]
out["planted_missing_table"] = classify(
    "table", table_facts(sqlite3.connect(":memory:"), "nf_gate174_absent_table")
)[0]
out["survey_can_report_unknown"] = (
    out["planted_missing_module"] == "UNKNOWN"
    and out["planted_missing_table"] == "UNKNOWN"
)
out["ready_unpopulated"] = sorted(by_class.get("READY_UNPOPULATED", []))
out["empty_is_distinguished_from_unwired"] = bool(out["ready_unpopulated"])

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
