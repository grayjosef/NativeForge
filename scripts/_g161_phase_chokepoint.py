"""Gate 161 verifier phase: the chokepoint, and whether it can fail.

`the_scan_catches_an_injected_import` is the load-bearing key. A scan that
always reports clean passes every hermetic test and proves nothing, so this
copies the tree, writes a real `import httpx` into an envelope module, and
requires the scan to fail on it.

`no_substring_search_was_used` is measured by parsing the chokepoint module
itself for calls to the string-search functions. Asserting it in prose would be
the very defect it is asserting the absence of.

Writes nothing to the database. The copy is made in a temp directory and
removed.
"""

from __future__ import annotations

import ast
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, "src")

from nativeforge.services.source_collection_execution_chokepoint_service import (  # noqa: E402,E501
    INJECTION_POINTS,
    chokepoint_invariant_failures,
    scan_execution_chokepoint,
)

out: dict[str, object] = {}
detail: list[str] = []

ROOT = pathlib.Path(".").resolve()

# ---- the real tree ------------------------------------------------------
real = scan_execution_chokepoint()
fails = chokepoint_invariant_failures(real)
if fails:
    detail.append(f"real:{fails}")

out["envelope_imports_no_network_module"] = bool(
    real["clean"] and not real["modules_that_reach_a_host"]
)
out["envelope_reaches_no_host"] = bool(real["envelope_reaches_no_host"])
out["every_module_was_found"] = bool(
    real["modules_found"] == len(real["modules_expected"])
)
out["transport_is_injected_not_imported"] = bool(
    len(real["injection_points"]) == len(INJECTION_POINTS)
    and not any(
        f["kind"] == "injection_point_does_not_take_a_transport"
        for f in real["findings"]
    )
)

# ---- a tree with a real violation written into it -----------------------
tmp = pathlib.Path(tempfile.mkdtemp(prefix="nf161-chokepoint-"))
try:
    shutil.copytree(ROOT / "src", tmp / "src")

    victim = (
        tmp
        / "src/nativeforge/services/source_collection_execution_proof_service.py"
    )
    victim.write_text("import httpx\n" + victim.read_text(), encoding="utf-8")

    removed = (
        tmp
        / "src/nativeforge/services/source_collection_execution_retry_service.py"
    )
    removed.unlink()

    broken = scan_execution_chokepoint(repo_root=tmp)
    kinds = {f["kind"] for f in broken["findings"]}

    out["the_scan_catches_an_injected_import"] = bool(
        "envelope_module_imports_a_network_module" in kinds
        and not broken["clean"]
        and not broken["envelope_reaches_no_host"]
    )
    out["the_scan_catches_a_missing_module"] = bool(
        "envelope_module_missing" in kinds
        and broken["modules_found"] < len(broken["modules_expected"])
    )
    if not kinds:
        detail.append("the doctored tree produced NO findings")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- and the scan does not use a substring search ----------------------
#
# Parsed, not grepped. Asserting "no substring search" with a substring search
# would be the thirteenth occurrence of the defect, in the check for it.
SEARCH_CALLS = {"search", "findall", "match", "fullmatch", "finditer"}

source = (
    ROOT
    / "src/nativeforge/services/source_collection_execution_chokepoint_service.py"
)
tree = ast.parse(source.read_text(encoding="utf-8"))
suspect: list[str] = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    func = node.func
    if isinstance(func, ast.Attribute):
        # `re.search(...)` and friends. `text.startswith(...)` is allowed:
        # it compares a whole segment against a known constant rather than
        # looking for a fragment inside arbitrary text.
        if func.attr in SEARCH_CALLS and isinstance(func.value, ast.Name) and (
            func.value.id == "re"
        ):
            suspect.append(f"re.{func.attr}")
    if isinstance(func, ast.Name) and func.id in SEARCH_CALLS:
        suspect.append(func.id)

# `in` against a whole string would also be a substring test. Comparisons
# against sets and tuples are membership, which is a different thing.
for node in ast.walk(tree):
    if isinstance(node, ast.Compare):
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if isinstance(op, ast.In | ast.NotIn) and isinstance(
                comparator, ast.Constant
            ) and isinstance(comparator.value, str):
                suspect.append(f"in {comparator.value!r}")

out["no_substring_search_was_used"] = not suspect
if suspect:
    detail.append(f"substring calls: {sorted(set(suspect))}")

for key in (
    "envelope_imports_no_network_module", "envelope_reaches_no_host",
    "every_module_was_found", "transport_is_injected_not_imported",
    "the_scan_catches_an_injected_import", "the_scan_catches_a_missing_module",
    "no_substring_search_was_used",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
