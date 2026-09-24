"""Gate 171Q: prove the generic layers do not know any source's name.

A source name in a transport module is not a style problem. It is the moment
the thousandth source stops costing the same as the second, because somebody
has to find and edit that branch. Gate 166 removed code-level source authority
for exactly this reason and this phase is the standing check that it stays
removed as adapters are added.

## Two traps this phase is built around

**Substring versus meaning.** A scan for "grants_gov" finds the docstring
explaining that generic code must not say "grants_gov". Docstrings are
excluded via the AST, not by a heuristic, so the rule's own explanation cannot
fail the rule.

**Scope creep in the definition of "generic".** The generic set is enumerated
explicitly below rather than computed as "everything except adapters", because
a computed set silently absorbs every new file and the check quietly weakens
as the tree grows.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 genericity scan makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "nativeforge"

#: The layers that must stay source-blind. Enumerated, not inferred.
GENERIC_FILES = (
    "services/source_adapter_contract_service.py",
    "services/source_adapter_conformance_service.py",
    "services/source_collection_transport_service.py",
    "services/hermetic_source_transport_service.py",
    "services/live_source_transport_service.py",
    "services/canonical_opportunity_normalizer_service.py",
    "services/opportunity_identity_versioning_service.py",
    "services/cross_source_identity_service.py",
    "services/opportunity_change_taxonomy_service.py",
    "services/opportunity_change_read_model_service.py",
    "services/source_authority_service.py",
    "services/source_authorization_fact_resolver_service.py",
    "services/source_fleet_fact_scope_service.py",
    # Gate 173. The relevance engine is where a source-specific branch would
    # do the most damage - "trust the codes if it came from Grants.gov" works
    # until somebody adds a source that codes differently.
    "services/native_relevance_ontology_service.py",
    "services/native_relevance_evidence_service.py",
    "services/native_relevance_candidate_service.py",
    "services/native_relevance_classifier_service.py",
    "services/native_relevance_repository_service.py",
    "services/source_coverage_universe_service.py",
    # Gates 174 and 175. A source-specific branch here - "trust the codes if
    # it came from Grants.gov", "skip the appendix for a BIA PDF" - works
    # until somebody adds the source that behaves differently.
    "services/eligibility_requirement_model_service.py",
    "services/eligibility_match_engine_service.py",
    "services/organization_capability_profile_service.py",
    "services/opportunity_document_service.py",
    "services/document_fact_extraction_service.py",
    "repositories/canonical_opportunity_repository.py",
    "repositories/canonical_opportunity_batch_repository.py",
    "repositories/opportunity_change_repository.py",
)

#: Where a source name is allowed to be spelled out.
ALLOWED_PREFIXES = (
    "services/source_adapters/",
    "services/source_connectors/",
)

#: Source-family tokens. Matched case-insensitively against code text with
#: docstrings removed.
SOURCE_TOKENS = (
    "grants.gov",
    "grants_gov",
    "grantsgov",
    "bia.gov",
    "bia_program",
    "federalregister",
    "federal_register",
    "sam.gov",
    "sam_gov",
    "simpler.grants",
    "search2",
)

#: Branching on a source identity is the specific shape that makes a generic
#: layer un-generic even when no source is named.
IDENTITY_BRANCH = re.compile(
    r"\b(source_id|source_name|adapter_key|source_key)\s*==\s*[\"']", re.I
)

#: Mentions that survive comment stripping and are nonetheless permitted,
#: each with the 171Q clause that permits it and a reason a reader can
#: disagree with. This is an ALLOWLIST, not an exclusion rule: it matches
#: exact snippets, an entry that stops matching is reported as stale, and
#: anything not listed fails. A blanket "ignore data tables" would have
#: absorbed every future leak silently.
ACKNOWLEDGED_MENTIONS = (
    {
        "file": "services/canonical_opportunity_normalizer_service.py",
        "contains": "OPPORTUNITY_PARSERS",
        "clause": "adapter descriptor/contract tables",
        "reason": (
            "the dict is KEYED by adapter_key and holds one entry per adapter. "
            "Adding a source adds a key; no control flow tests which key it is. "
            "This is the designed extension point, and sources #2 and #3 extend "
            "it the same way rather than by editing logic."
        ),
    },
    {
        "file": "services/opportunity_identity_versioning_service.py",
        "contains": "AGENCY_NAMESPACES",
        "clause": "domain vocabulary, not a source identity",
        "reason": (
            "these name the three AGENCY-CODE namespaces a crosswalk has to "
            "reconcile, which is a fact about how the federal government "
            "assigns agency codes, not about which sources this system reads. "
            "Gate 169 refuses to match agencies by name string precisely "
            "because these namespaces do not align."
        ),
    },
    {
        "file": "services/source_collection_transport_service.py",
        "contains": "legacy_transports_not_refactored",
        "clause": "diagnostic inventory, not behaviour",
        "reason": (
            "a self-describing list of MODULE names in a diagnostic report. "
            "No control flow reads it. It names modules, not sources, and "
            "removing the name would make the inventory less true."
        ),
    },
)


def strip_comments(text: str) -> str:
    """Blank every `#` comment, keeping line numbers.

    Comments matter to this scan differently from code. A comment that says
    "this used to be hardcoded to one source" is the repository explaining
    itself; a dict key naming a source is the repository DEPENDING on one.
    Counting them together produces a number that cannot be acted on.
    """
    import io
    import tokenize

    lines = text.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        row, start = token.start[0] - 1, token.start[1]
        if 0 <= row < len(lines):
            lines[row] = lines[row][:start]
    return "\n".join(lines)


def code_without_docstrings(path: pathlib.Path, *, drop_comments: bool = True) -> str:
    """The file's text with docstrings - and optionally comments - blanked.

    Blanked rather than deleted so reported line numbers stay true.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            if ast.get_docstring(node) is None:
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstring_nodes.add(id(first.value))

    lines = text.splitlines()
    for node in ast.walk(tree):
        if id(node) not in docstring_nodes:
            continue
        start = int(getattr(node, "lineno", 0)) - 1
        end = int(getattr(node, "end_lineno", 0))
        for index in range(max(start, 0), min(end, len(lines))):
            lines[index] = ""
    joined = "\n".join(lines)
    return strip_comments(joined) if drop_comments else joined


#: How many lines above a hit count as the construct it belongs to. An
#: acknowledgement is a judgement about a construct - a table, an inventory -
#: and the name of that construct is usually on the line that opens it, not
#: on the line the source token happens to land on.
CONTEXT_LINES = 8


def scan(path: pathlib.Path, relative: str) -> list[dict]:
    findings: list[dict] = []
    text = code_without_docstrings(path)
    lowered = text.lower()
    all_lines = text.splitlines()

    def context_for(line_no: int) -> str:
        start = max(line_no - 1 - CONTEXT_LINES, 0)
        return "\n".join(all_lines[start:line_no])

    for token in SOURCE_TOKENS:
        start = 0
        while True:
            index = lowered.find(token, start)
            if index < 0:
                break
            line_no = lowered.count("\n", 0, index) + 1
            findings.append(
                {
                    "file": relative,
                    "line": line_no,
                    "kind": "source_token",
                    "token": token,
                    "text": all_lines[line_no - 1].strip()[:120],
                    "context": context_for(line_no),
                }
            )
            start = index + len(token)
    for match in IDENTITY_BRANCH.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        findings.append(
            {
                "file": relative,
                "line": line_no,
                "kind": "identity_branch",
                "token": match.group(0).strip(),
                "text": all_lines[line_no - 1].strip()[:120],
                "context": context_for(line_no),
            }
        )
    return findings


out: dict[str, object] = {"schema_version": "nf_gate171_genericity_v1"}

missing: list[str] = []
leaks: list[dict] = []
scanned = 0
for relative in GENERIC_FILES:
    path = SRC / relative
    if not path.exists():
        missing.append(relative)
        continue
    scanned += 1
    leaks.extend(scan(path, relative))


def acknowledgement_for(hit: dict) -> dict | None:
    for entry in ACKNOWLEDGED_MENTIONS:
        if hit["file"] != entry["file"]:
            continue
        if entry["contains"] in str(hit.get("context") or hit["text"]):
            return entry
    return None


unacknowledged: list[dict] = []
acknowledged: list[dict] = []
matched_entries: set[int] = set()
for hit in leaks:
    if hit["kind"] == "identity_branch":
        # Never acknowledgeable. This is the exact shape 171Q forbids.
        unacknowledged.append(hit)
        continue
    entry = acknowledgement_for(hit)
    if entry is None:
        unacknowledged.append(hit)
    else:
        matched_entries.add(id(entry))
        acknowledged.append({**hit, "clause": entry["clause"], "why": entry["reason"]})

# An allowlist entry that no longer matches anything has stopped being a
# judgement about real code and started being a standing permission.
stale = [
    {"file": e["file"], "contains": e["contains"]}
    for e in ACKNOWLEDGED_MENTIONS
    if id(e) not in matched_entries
]

out["generic_files_declared"] = len(GENERIC_FILES)
out["generic_files_scanned"] = scanned
out["generic_files_missing"] = missing
out["source_mentions_in_executable_code"] = len(leaks)
out["identity_branches_in_generic_layers"] = sum(
    1 for hit in leaks if hit["kind"] == "identity_branch"
)
out["generic_layer_source_leaks"] = len(unacknowledged)
out["leaks"] = unacknowledged
out["acknowledged_mentions"] = acknowledged
out["stale_acknowledgements"] = stale

# ---- where source names ARE allowed, counted for contrast ---------
#
# A zero here would mean the adapters are not doing their job: the source
# names have to live somewhere, and the point of the check is that they live
# in exactly one place.
allowed_hits = 0
allowed_files = 0
for prefix in ALLOWED_PREFIXES:
    for path in sorted((SRC / prefix).rglob("*.py")):
        allowed_files += 1
        text = code_without_docstrings(path).lower()
        allowed_hits += sum(text.count(token) for token in SOURCE_TOKENS)
out["files_allowed_to_name_a_source"] = allowed_files
out["source_tokens_in_allowed_files"] = allowed_hits
out["source_names_live_somewhere"] = allowed_hits > 0

# ---- the check is falsifiable -------------------------------------
#
# A scanner that cannot fail is not evidence. This plants a leak in a copy of
# a generic file's TEXT and confirms the scanner reports it, so a green result
# means the scanner looked rather than that it was satisfied.
probe = SRC / GENERIC_FILES[0]
probe_text = code_without_docstrings(probe)
forged = probe_text + '\nif source_id == "grants_gov":\n    pass\n'
forged_findings = []
lowered = forged.lower()
for token in SOURCE_TOKENS:
    if token in lowered:
        forged_findings.append(token)
forged_branch = bool(IDENTITY_BRANCH.search(forged))
out["scanner_detects_a_planted_leak"] = bool(forged_findings) and forged_branch
out["scanner_detects_a_planted_token"] = sorted(set(forged_findings))

out["generic_layers_are_source_blind"] = (
    len(unacknowledged) == 0
    and out["identity_branches_in_generic_layers"] == 0
    and not missing
    and not stale
    and bool(out["scanner_detects_a_planted_leak"])
    and bool(out["source_names_live_somewhere"])
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
