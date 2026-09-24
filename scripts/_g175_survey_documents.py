"""Gate 175A: the document substrate, and which lifecycle stage it serves.

Gate 173's survey already established one finding this gate has to act on:

```text
nf_award_documents holds 876 archived demo rows of financial_report and
award_letter, hanging off awarded_grant_id and award_requirement_id.
```

Those are POST-AWARD compliance artifacts. A NOFO, an appendix and an FAQ are
PRE-AWARD evidence about an opportunity nobody has won yet. Reusing the award
table would conflate the two lifecycle stages and put a funder's eligibility
language in a table keyed by a grant that does not exist.

So the question here is not "is there a document table" - there is - but:

```text
does anything store a document as VERSIONED EVIDENCE about a canonical
opportunity, and can a missing parser be told apart from an empty result?
```

The second half is the one that hurts. A document whose parser does not
support its media type must not report "no requirements found", because that
is indistinguishable from a NOFO that genuinely imposes none.

Same derived classifier as Gates 173 and 174, including READY_UNPOPULATED and
the falsifiability check.

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
        raise OSError("gate175 survey makes no network request")


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

#: Reaching the current spine. Named individually, because Gate 174 learned
#: that a prefix matches the old unwired stack too.
CANONICAL_MARKERS = (
    "canonical_opportunity",
    "cross_source_identity",
    "opportunity_change",
    "source_adapter_contract",
    "source_fleet_",
    "opportunity_field_provenance",
    "native_relevance_ontology_service",
    "native_relevance_evidence_service",
    "native_relevance_classifier_service",
    "eligibility_requirement_model_service",
    "eligibility_match_engine_service",
    "organization_capability_profile_service",
)

PRIMITIVES: tuple[tuple[str, str, str, str], ...] = (
    # ---- evidence substrate that already works ---------------------
    (
        "collected_raw_payloads",
        "table",
        "nf_source_collection_raw_payloads",
        "raw_evidence",
    ),
    ("legacy_raw_payloads", "table", "nf_raw_source_payloads", "raw_evidence"),
    (
        "field_provenance",
        "table",
        "nf_opportunity_field_provenance",
        "provenance",
    ),
    (
        "field_conflicts",
        "table",
        "nf_opportunity_field_conflicts",
        "conflicts",
    ),
    ("change_events", "table", "nf_opportunity_change_events", "change"),
    ("opportunity_versions", "table", "nf_opportunity_versions", "versions"),
    # ---- document tables, and which stage they serve ----------------
    ("award_documents", "table", "nf_award_documents", "post_award_documents"),
    ("nofo_extraction_runs", "table", "nf_nofo_extraction_runs", "nofo_extraction"),
    ("evidence_intake_records", "table", "nf_evidence_intake_records", "evidence"),
    ("review_artifacts", "table", "nf_review_artifacts", "review"),
    # ---- what Gate 174 built, which documents must feed -------------
    (
        "eligibility_requirements",
        "table",
        "nf_opportunity_eligibility_requirements",
        "eligibility",
    ),
    (
        "relevance_evidence",
        "table",
        "nf_opportunity_relevance_evidence",
        "relevance",
    ),
    # ---- extraction and parsing -------------------------------------
    (
        "document_text_extraction",
        "module",
        "grant_document_text_extraction_service",
        "text_extraction",
    ),
    (
        "attachment_inventory",
        "module",
        "grant_document_attachment_inventory_service",
        "document_inventory",
    ),
    (
        "amendment_detector",
        "module",
        "nofo_amendment_detector_service",
        "amendments",
    ),
    (
        "nofo_eligibility_parser",
        "module",
        "nofo_eligibility_parser_service",
        "fact_extraction",
    ),
    (
        "reporting_requirement_extraction",
        "module",
        "grant_reporting_requirement_extraction_service",
        "fact_extraction",
    ),
    (
        "html_card_listing_extractor",
        "module",
        "html_card_listing_extractor_service",
        "fact_extraction",
    ),
    (
        "attachment_form_intake_planner",
        "module",
        "attachment_form_intake_planner_service",
        "attachments",
    ),
    (
        "forms_attachments_mapper",
        "module",
        "forms_attachments_mapper_service",
        "attachments",
    ),
    # ---- storage and safety ------------------------------------------
    (
        "document_storage_readiness",
        "module",
        "document_storage_readiness_service",
        "object_storage",
    ),
    (
        "award_document_store_repository",
        "module",
        "award_document_store_repository_service",
        "post_award_documents",
    ),
    (
        "no_live_nofo_state",
        "module",
        "no_live_nofo_state_service",
        "retrieval_safety",
    ),
    (
        "source_authorization_fact_resolver",
        "module",
        "source_authorization_fact_resolver_service",
        "retrieval_safety",
    ),
    # ---- the layers documents must feed ------------------------------
    (
        "eligibility_requirement_model",
        "module",
        "eligibility_requirement_model_service",
        "eligibility",
    ),
    (
        "relevance_evidence_contract",
        "module",
        "native_relevance_evidence_service",
        "relevance",
    ),
    (
        "change_taxonomy",
        "module",
        "opportunity_change_taxonomy_service",
        "change",
    ),
)

FACT_OWNERS: dict[str, str] = {
    "the bytes a claim came from": "collected_raw_payloads",
    "which source said which field": "field_provenance",
    "when a field disagreed across sources": "field_conflicts",
    "what changed and when": "change_events",
    "how text comes out of a document": "document_text_extraction",
    "what attachments an opportunity has": "attachment_inventory",
    "whether a notice was amended": "amendment_detector",
    "what a NOFO's eligibility text says": "nofo_eligibility_parser",
    "whether live NOFO fetching is permitted": "no_live_nofo_state",
    "whether a source is authorized": "source_authorization_fact_resolver",
    "what a funder requires": "eligibility_requirement_model",
    "the evidence a relevance claim rests on": "relevance_evidence_contract",
    "post-award compliance documents": "award_document_store_repository",
}

REQUIRED_FACTS: tuple[str, ...] = (
    "a document as versioned evidence about a canonical opportunity",
    "a document state that separates unsupported from empty",
    "a fact extracted from a document, bound to its page or section",
    "a conflict between what two documents say",
    "an amendment chain with supersession",
    "a citation an operator can be shown",
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
        "column_names": columns,
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


out: dict[str, object] = {"schema_version": "nf_gate175_survey_v1"}

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

# ---- the lifecycle-stage finding -------------------------------------
award = surveyed["award_documents"]
award_columns = set(award.get("column_names") or [])
out["award_document_table_is_post_award"] = bool(
    {"awarded_grant_id", "award_requirement_id", "proof_event_id"} & award_columns
)
out["award_document_table_classification"] = award["classification"]
out["award_document_table_binds_to"] = sorted(
    column for column in award_columns if column.endswith("_id") and "award" in column
)
out["no_table_binds_a_document_to_a_canonical_opportunity"] = not any(
    "canonical_id" in set(entry.get("column_names") or [])
    for key, entry in surveyed.items()
    if entry["kind"] == "table" and "document" in str(entry["concern"])
)

# ---- can a missing parser be told from an empty result? --------------
extraction_text = (
    PACKAGE_TEXTS.get("services/grant_document_text_extraction_service.py") or ""
)
out["extraction_reports_blocked_reasons"] = "blocked" in extraction_text.lower()
out["extraction_distinguishes_unsupported_from_empty"] = (
    "unsupported" in extraction_text.lower()
)

out["gate175_must_build"] = [
    fact for fact in REQUIRED_FACTS if fact not in set(FACT_OWNERS)
]
out["gate175_must_reuse"] = sorted(
    key
    for key, entry in surveyed.items()
    if entry["classification"] in {"AUTHORITATIVE", "REUSABLE"}
)
out["gate175_must_not_duplicate"] = sorted(
    {
        FACT_OWNERS[fact]
        for fact in (
            "the bytes a claim came from",
            "which source said which field",
            "what changed and when",
            "how text comes out of a document",
            "whether a notice was amended",
        )
    }
)

# ---- falsifiability ---------------------------------------------------
out["planted_missing_module"] = classify(
    "module", module_facts("nf_gate175_module_that_does_not_exist")
)[0]
out["planted_missing_table"] = classify(
    "table", table_facts(sqlite3.connect(":memory:"), "nf_gate175_absent_table")
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
