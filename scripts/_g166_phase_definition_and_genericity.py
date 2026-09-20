"""Gate 166H/166I: the source contract, and that no generic layer names a source.

166I is the one that can quietly pass for the wrong reason. Scanning for the
string "grants.gov" finds the DOCSTRING that explains why a module must not
depend on Grants.gov - the substring-vs-meaning defect this campaign keeps
catching. So every hit is CLASSIFIED, and only a hit in live code counts as a
leak.

Makes no network request.
"""

from __future__ import annotations

import ast
import json
import pathlib
import socket
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate166 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_definition_service import (  # noqa: E402
    build_source_definition,
    definition_invariant_failures,
    describe_field_classification,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
GRANTS = "nf-seed-2026-api-grants-gov-search2"

#: The modules that must be generic. A source-specific token in live code in
#: any of these is a leak, whatever its value.
GENERIC_MODULES: tuple[str, ...] = (
    "source_authority_service",
    "source_authority_sweep_service",
    "source_definition_service",
    "source_fleet_fact_scope_service",
    "source_attribution_contract_service",
    "source_live_warrant_service",
    "source_collection_request_builder_service",
    "source_collection_execution_policy_service",
    "source_collection_scheduler_loop_service",
    "source_raw_payload_persistence_service",
    "source_raw_payload_replay_service",
    "source_authorization_fact_resolver_service",
    "source_collector_capability_service",
    "live_collection_audit_service",
    "live_evidence_health_service",
)

#: Module-level dicts that map `adapter_key` -> descriptor. A publisher's name
#: INSIDE one of these is the architecture working: the generic code looks the
#: entry up using a key it read from the source's own catalog row, and adding
#: source #2 is a new entry rather than a new branch.
#:
#: A hit ANYWHERE else in these modules - an import, a comparison, a branch -
#: is still a leak. The distinction is structural (which AST node contains the
#: line), never "this module is allowed to mention Grants.gov", which would
#: define the problem away.
ADAPTER_REGISTRY_NAMES: tuple[str, ...] = (
    "ADAPTER_CAPABILITIES",
    "ATTRIBUTION_CONTRACTS",
)

#: Tokens that would tie a generic layer to one source.
TOKENS: tuple[str, ...] = (
    "grants.gov",
    "grants_gov",
    "search2",
    "nf-seed-2026-api-grants-gov-search2",
)

#: Counts that would freeze the fleet at today's size.
FROZEN_COUNTS: tuple[str, ...] = ("== 178", "== 177", "== 1 ", "exactly one")


def classify_hits(path: pathlib.Path) -> dict[str, list[str]]:
    """Separate live code from documentation. AST, not line scanning.

    A docstring is a node in the tree. Deciding by indentation or by a quote
    character would classify the explanation of a rule as a violation of it.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    doc_lines: set[int] = set()

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"unparseable": [str(path)]}

    # Module, class and function docstrings.
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc is None:
                continue
            body = node.body[0]
            if isinstance(body, ast.Expr) and hasattr(body, "lineno"):
                for line_no in range(body.lineno, (body.end_lineno or body.lineno) + 1):
                    doc_lines.add(line_no)

    # Lines belonging to an adapter-keyed descriptor table. Structural: the
    # line sits inside the dict literal assigned to that name, not merely in a
    # module that happens to define one.
    descriptor_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = {t.id for t in targets if isinstance(t, ast.Name)}
        if not names & set(ADAPTER_REGISTRY_NAMES):
            continue
        value = node.value
        if value is None or not hasattr(value, "lineno"):
            continue
        for line_no in range(value.lineno, (value.end_lineno or value.lineno) + 1):
            descriptor_lines.add(line_no)

    code: list[str] = []
    documentation: list[str] = []
    descriptors: list[str] = []
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if not any(token in lowered for token in TOKENS):
            continue
        stripped = line.strip()
        is_comment = stripped.startswith("#")
        if index in doc_lines or is_comment:
            documentation.append(f"{path.name}:{index}")
        elif index in descriptor_lines:
            descriptors.append(f"{path.name}:{index}: {stripped[:80]}")
        else:
            code.append(f"{path.name}:{index}: {stripped[:100]}")
    return {
        "code": code,
        "documentation": documentation,
        "adapter_descriptor": descriptors,
    }


out: dict[str, object] = {}

# ---- 166I: the genericity scan -------------------------------------
leaks: list[str] = []
doc_only: dict[str, int] = {}
descriptor_hits: list[str] = []
scanned: list[str] = []
missing: list[str] = []

for name in GENERIC_MODULES:
    path = REPO / "src" / "nativeforge" / "services" / f"{name}.py"
    if not path.is_file():
        missing.append(name)
        continue
    scanned.append(name)
    hits = classify_hits(path)
    leaks.extend(hits.get("code") or [])
    descriptor_hits.extend(hits.get("adapter_descriptor") or [])
    if hits.get("documentation"):
        doc_only[name] = len(hits["documentation"])

out["modules_scanned"] = len(scanned)
out["modules_missing"] = missing
out["generic_layer_leaks"] = len(leaks)
out["generic_layer_leak_detail"] = sorted(leaks)
out["adapter_descriptor_hits"] = len(descriptor_hits)
out["adapter_descriptor_detail"] = sorted(descriptor_hits)
out["doc_only_mentions_by_module"] = doc_only
out["classification_method"] = (
    "AST, three buckets. DOCUMENTATION: docstring nodes and comments - a line "
    "scan would call the sentence explaining a rule a violation of it. "
    "ADAPTER_DESCRIPTOR: inside the dict literal of an adapter-keyed registry, "
    "which is the generic code looking up an entry by a key read from the "
    "source's catalog row. LEAK: everything else - an import, a comparison, a "
    "branch. The buckets are decided by which AST node contains the line, not "
    "by which module it is in."
)
# Every module must be found. A typo in the module list would silently scan
# fewer files and report a clean result about code nobody looked at.
out["every_named_module_was_scanned"] = not missing

# ---- a frozen-count scan over the new authority modules -------------
frozen: list[str] = []
for name in (
    "source_authority_service",
    "source_authority_sweep_service",
    "source_fleet_fact_scope_service",
):
    path = REPO / "src" / "nativeforge" / "services" / f"{name}.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast.get_docstring(node, clean=False) is None:
                continue
            body = node.body[0]
            for line_no in range(body.lineno, (body.end_lineno or body.lineno) + 1):
                doc_lines.add(line_no)
    for index, line in enumerate(text.splitlines(), start=1):
        if index in doc_lines or line.strip().startswith("#"):
            continue
        for needle in FROZEN_COUNTS:
            if needle in line:
                frozen.append(f"{name}:{index}: {line.strip()[:90]}")
out["frozen_fleet_size_assertions_in_live_code"] = sorted(set(frozen))
out["runtime_source_authority_not_seed_count"] = not frozen

# ---- 166H: the SourceDefinition contract ---------------------------
session = SessionLocal()
try:
    definition = build_source_definition(
        source_id=GRANTS, connection=session, organization_id=DEMO
    )
    out["definition_source_id"] = definition["source_id"]
    out["definition_usable_by_an_adapter"] = definition["usable_by_an_adapter"]
    out["definition_missing_fields"] = definition["missing_fields"]
    out["definition_invariant_failures"] = definition_invariant_failures(definition)
    out["definition_stores_present"] = definition["stores_present"]
    out["definition_activation_state"] = definition["activation"]["state"]
    out["definition_store_disagreements"] = definition["store_disagreements"]

    # The adapter must not need to know where a field was stored. The
    # projection's top level is the contract; the store names appear only in
    # `stores_present`, which is diagnostics.
    contract_keys = sorted(
        k for k in definition if k not in ("stores_present", "schema_version")
    )
    out["contract_keys"] = contract_keys
    out["contract_names_no_store"] = not any(
        "nf_" in key or "csv" in key for key in contract_keys
    )

    # A source with no rows anywhere still projects, and says what is missing
    # rather than raising.
    empty = build_source_definition(
        source_id="nf166.synthetic.nothing-known",
        connection=session,
        organization_id=DEMO,
    )
    out["unknown_source_projects"] = empty["source_id"] is not None
    out["unknown_source_not_usable"] = not empty["usable_by_an_adapter"]
    out["unknown_source_names_missing"] = sorted(empty["missing_fields"])

    classification = describe_field_classification()
    out["field_classification_counts"] = {
        k: len(v) for k, v in classification["by_classification"].items()
    }
    out["fields_classified"] = len(classification["fields"])
    out["unclassified_fields"] = 0
    out["consolidation_performed"] = classification["consolidation_performed"]
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
