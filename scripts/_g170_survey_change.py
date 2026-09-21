"""Gate 170A: what change logic already exists? Reads only, no network.

Gate 168 already computes `changed_fields` and a materiality verdict inside
the write path - it just throws them away after writing the version row. The
question this settles is whether that diff is the diff, or whether a second
one is needed.

A second diff beside a sound one is the worst outcome of this gate, so the
existing logic is inspected before anything is written.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

REPO = pathlib.Path(__file__).resolve().parents[1]
SERVICES = REPO / "src" / "nativeforge" / "services"
REPOS = REPO / "src" / "nativeforge" / "repositories"

AUTHORITATIVE = "AUTHORITATIVE"
REUSABLE = "REUSABLE"
UNWIRED = "UNWIRED"
ADVISORY = "ADVISORY"
DUPLICATED = "DUPLICATED"
LEGACY = "LEGACY"
UNKNOWN = "UNKNOWN"

TARGETS: dict[str, pathlib.Path] = {
    "opportunity_deadline_and_amendment_model_service": SERVICES
    / "opportunity_deadline_and_amendment_model_service.py",
    "opportunity_identity_versioning_service": SERVICES
    / "opportunity_identity_versioning_service.py",
    "deadline_normalization_service": SERVICES / "deadline_normalization_service.py",
    "canonical_opportunity_batch_repository": REPOS
    / "canonical_opportunity_batch_repository.py",
    "canonical_opportunity_repository": REPOS / "canonical_opportunity_repository.py",
    "canonical_opportunity_graph_service": SERVICES
    / "canonical_opportunity_graph_service.py",
    "cross_source_identity_service": SERVICES / "cross_source_identity_service.py",
    "tenant_nofo_digest_change_detection_service": SERVICES
    / "tenant_nofo_digest_change_detection_service.py",
    "tenant_nofo_digest_snapshot_service": SERVICES
    / "tenant_nofo_digest_snapshot_service.py",
}


def functions(path: pathlib.Path) -> list[str]:
    if not path.is_file():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sorted(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def production_callers(module: str) -> list[str]:
    found: list[str] = []
    for folder in ("src",):
        for path in (REPO / folder).rglob("*.py"):
            if path.stem == module:
                continue
            try:
                if module in path.read_text(encoding="utf-8"):
                    found.append(str(path.relative_to(REPO)))
            except Exception:  # noqa: BLE001
                continue
    return sorted(found)


out: dict[str, object] = {}
detail: dict[str, object] = {}

for module, path in TARGETS.items():
    if not path.is_file():
        detail[module] = {"classification": UNKNOWN, "reason": "not_found"}
        continue
    public = [f for f in functions(path) if not f.startswith("_")]
    private = [f for f in functions(path) if f.startswith("_")]
    callers = production_callers(module)

    if not callers and module not in ("canonical_opportunity_batch_repository",):
        classification = UNWIRED
    elif module in (
        "opportunity_deadline_and_amendment_model_service",
        "opportunity_identity_versioning_service",
    ):
        classification = AUTHORITATIVE
    elif module.startswith("tenant_nofo_digest"):
        # Change detection over NOFO snapshots, for the tenant digest. A
        # different subject from canonical-version diffing.
        classification = LEGACY
    else:
        classification = REUSABLE

    detail[module] = {
        "classification": classification,
        "public_functions": public,
        "private_helpers": private,
        "production_callers": callers,
    }

out["primitives"] = detail
out["classifications"] = {
    m: i.get("classification") for m, i in sorted(detail.items())
}

# ---- the diff that already exists ----------------------------------

out["existing_diff"] = {
    "function": "canonical_opportunity_batch_repository._changed_fields",
    "compares": "the prior version's normalized_fields_json against the new",
    "already_persisted": "changed_fields_json on the version row",
    "already_computed": "is_material and material_categories_json",
    "what_is_missing": [
        "a named change TYPE per field, not just the field name",
        "a materiality CLASS beyond a boolean",
        "the change as a queryable EVENT rather than a column on a version",
        "deadline shape awareness (dual, per_region, phased)",
        "conflict state over time",
        "multi-source corroboration of one semantic change",
    ],
    "decision": (
        "reuse `_changed_fields` and the Gate 92G categorizer; add a taxonomy, "
        "a materiality classifier and an event store on top. Building a "
        "second diff would put two answers in the graph, and the one that "
        "drifted would not announce itself."
    ),
}
out["existing_diff_is_reused_not_replaced"] = True

# ---- the deadline shapes already modelled --------------------------
from nativeforge.services.opportunity_deadline_and_amendment_model_service import (  # noqa: E402
    AMENDMENT_CATEGORIES,
    DEADLINE_LIFECYCLE_STATES,
    DEADLINE_PATTERNS,
    MATERIAL_CATEGORIES,
    MULTI_VALUED_PATTERNS,
)

out["deadline_patterns_available"] = sorted(DEADLINE_PATTERNS)
out["multi_valued_patterns"] = sorted(MULTI_VALUED_PATTERNS)
out["deadline_lifecycle_states"] = sorted(DEADLINE_LIFECYCLE_STATES)
out["amendment_categories"] = sorted(AMENDMENT_CATEGORIES)
out["material_categories"] = sorted(MATERIAL_CATEGORIES)
out["deadline_shapes_need_no_reinvention"] = len(DEADLINE_PATTERNS) >= 6

# ---- what the canonical store can currently answer -----------------
import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

session = SessionLocal()
try:
    tables = [
        str(row[0])
        for row in session.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).all()
    ]
    out["change_event_table_exists"] = any("change" in t for t in tables)
    out["conflict_table_exists"] = any("conflict" in t for t in tables)
    out["version_table_carries_changed_fields"] = "changed_fields_json" in [
        str(r[1])
        for r in session.execute(
            sa.text("PRAGMA table_info(nf_opportunity_versions)")
        ).all()
    ]
finally:
    session.close()

out["missing_for_change_intelligence"] = [
    "a change event table keyed deterministically on (version pair, field)",
    "a conflict state table with first_detected / last_observed",
    "a named change taxonomy",
    "a rule-backed materiality classifier",
    "a customer-safe read model",
]

print(json.dumps(out, indent=2, sort_keys=True, default=str))
