"""Gate 169A: what identity machinery already exists? Reads only, no network.

Gate 165 found a well-researched identity model with zero production callers;
Gate 167 wired L1 in. Before building a cross-source resolver, this establishes
exactly which layers are live, which are advisory, and what normalization
already exists - because a second identity system beside a sound one is the
worst possible outcome of this gate.
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

AUTHORITATIVE = "AUTHORITATIVE"
REUSABLE = "REUSABLE"
ADVISORY = "ADVISORY"
UNWIRED = "UNWIRED"
UNKNOWN = "UNKNOWN"

#: The primitives Gate 169A names, plus what to look for in each.
PRIMITIVES: dict[str, dict[str, object]] = {
    "opportunity_identity_versioning_service": {
        "expect": ("build_opportunity_identity", "build_version_key",
                   "build_fuzzy_fallback_key", "normalize_opportunity_number"),
    },
    "discovery_intake_dedupe_fingerprint_service": {
        "expect": ("candidate_dedupe_fingerprints_from_raw",),
    },
    "notice_ingestion_pipeline_service": {"expect": ("ingest_notice_artifact",)},
    "opportunity_deadline_and_amendment_model_service": {
        "expect": ("classify_amendment", "categorize_modified_field"),
    },
    "canonical_opportunity_normalizer_service": {
        "expect": ("normalize_record", "content_fingerprint"),
    },
    "opportunity_discovery_service": {
        "expect": ("compute_duplicate_key", "compute_structural_duplicate_fingerprint"),
    },
}


def public_functions(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sorted(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    )


def importers(module: str) -> list[str]:
    """Who actually calls this, excluding itself and tests."""
    found: list[str] = []
    for folder in ("src", "scripts"):
        for path in (REPO / folder).rglob("*.py"):
            if path.name == f"{module}.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            if module in text:
                found.append(str(path.relative_to(REPO)))
    return sorted(found)


out: dict[str, object] = {}
detail: dict[str, object] = {}

for module, spec in PRIMITIVES.items():
    path = SERVICES / f"{module}.py"
    if not path.is_file():
        detail[module] = {"classification": UNKNOWN, "reason": "module_not_found"}
        continue
    functions = public_functions(path)
    expected = [name for name in spec["expect"] if name in functions]
    missing = [name for name in spec["expect"] if name not in functions]
    callers = importers(module)
    production_callers = [c for c in callers if c.startswith("src/")]

    if not production_callers:
        classification = UNWIRED
    elif module.endswith("dedupe_fingerprint_service"):
        classification = ADVISORY
    elif module in (
        "opportunity_identity_versioning_service",
        "opportunity_deadline_and_amendment_model_service",
    ):
        classification = AUTHORITATIVE
    else:
        classification = REUSABLE

    detail[module] = {
        "classification": classification,
        "public_functions": functions,
        "expected_present": expected,
        "expected_missing": missing,
        "production_callers": production_callers,
        "caller_count": len(callers),
    }

out["primitives"] = detail
out["classifications"] = {
    module: info.get("classification") for module, info in sorted(detail.items())
}
out["unwired"] = sorted(
    m for m, i in detail.items() if i.get("classification") == UNWIRED
)
out["authoritative"] = sorted(
    m for m, i in detail.items() if i.get("classification") == AUTHORITATIVE
)

# ---- which identity layers are actually reachable today? ------------
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    IDENTITY_LAYERS,
    PROVISIONAL_LAYERS,
)

out["identity_layers_declared"] = sorted(IDENTITY_LAYERS)
out["provisional_layers"] = sorted(PROVISIONAL_LAYERS)

# The canonical store's CHECK only admits two of the four.
migration = (
    REPO / "alembic" / "versions" / "0053_canonical_opportunity_graph.py"
).read_text(encoding="utf-8")
tree = ast.parse(migration)
admitted: list[str] = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if getattr(target, "id", "") == "IDENTITY_LAYERS":
                admitted = [
                    n.value
                    for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
out["identity_layers_admitted_by_the_store"] = sorted(admitted)
out["layers_declared_but_not_storable"] = sorted(
    set(IDENTITY_LAYERS) - set(admitted)
)

# ---- what normalization already exists? -----------------------------
normalizers: dict[str, list[str]] = {}
for path in SERVICES.rglob("*.py"):
    try:
        functions = public_functions(path)
    except Exception:  # noqa: BLE001
        continue
    hits = [
        name
        for name in functions
        if name.startswith("normalize_") or name.endswith("_fingerprint")
    ]
    if hits:
        normalizers[path.stem] = hits
out["existing_normalizers"] = dict(sorted(normalizers.items()))
out["normalizer_module_count"] = len(normalizers)

# ---- what is MISSING for cross-source identity ----------------------
existing_tables_migration = (REPO / "alembic" / "versions")
relationship_tables = [
    p.name
    for p in existing_tables_migration.glob("*.py")
    if "relationship" in p.read_text(encoding="utf-8").lower()
    and "nf_opportunity" in p.read_text(encoding="utf-8")
]
out["existing_relationship_tables"] = relationship_tables
out["missing_for_cross_source_identity"] = [
    "a relationship table (SAME_AS / VERSION_OF / RECURRENCE_OF / FORECAST_OF)",
    "a reviewable provisional candidate table",
    "indexed blocking keys for bounded candidate generation",
    "agency and program name normalization",
    "an explicit match decision vocabulary",
]

print(json.dumps(out, indent=2, sort_keys=True, default=str))
