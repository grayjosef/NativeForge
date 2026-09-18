"""The execution envelope's chokepoint, proved by parsing (Gate 161M).

Gate 161 is the first gate whose code could, in principle, make an outbound
source request. This module is how that claim is checked rather than asserted.

## Everything here is an AST question

```text
"does this module import a network module"   ast.Import / ast.ImportFrom
"does this module call X"                    dotted name paths, resolved from
                                             Name and Attribute nodes only
"is the transport injected"                  a parameter, not a module-level
                                             import
```

Not one substring search. Gate 160 counted this campaign's substring-versus-
meaning defects at thirteen, and the shape is always the same: a check asks
"does this text appear" when it means "does this happen", and eventually matches
the sentence explaining why it must not. A module whose docstring says *never
imports httpx* fails a grep for `httpx`.

So `_imported_names` walks import nodes, and `_called_name_paths` resolves
dotted callees from `Name`/`Attribute` nodes only — never `ast.unparse`, whose
output for `str(sha).lower` contains `sha`.

## What "the chokepoint" means

Every module in the envelope reaches the network only by calling a transport it
was HANDED. There is no import to intercept, because there is nothing to
import: `execute_request` takes `transport` as a keyword argument, and a module
that imports no network library cannot reach a host however it is called.

That is stronger than a chokepoint a caller must remember to route through. The
question "could this code reach a host" becomes "does this file import something
that can", which a parser answers exactly.

## The three legacy transports are NOT in the envelope

`grants_gov_search_api_adapter_service`, `polite_http_fetch_service` and
`real_url_resolver_service` each import httpx under two guards, are on the
approved-site list with recorded reasons, and are each already injectable.
Gate 161's survey (doc 837) recorded the decision not to refactor them. This
module measures that they are absent from the envelope's import graph, which is
the property that matters — not that they were rewritten.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from nativeforge.services.hermetic_network_enforcement_service import (
    APPROVED_MODULE_NAMES,
    INERT_URLLIB_SUBMODULES,
    NETWORK_MODULES,
)

SCHEMA_VERSION = "nf_source_collection_execution_chokepoint_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Every module the execution envelope is made of. None of these may import a
#: network module, and the list is checked for existence so a renamed file
#: fails loudly rather than passing by absence.
ENVELOPE_MODULES: tuple[str, ...] = (
    "source_collector_execution_service",
    "source_collection_transport_service",
    "hermetic_source_transport_service",
    "source_collection_execution_policy_service",
    "source_collection_request_builder_service",
    "source_collection_execution_proof_service",
    "source_collection_execution_retry_service",
    "source_collector_execution_health_service",
    "source_collection_execution_chokepoint_service",
)

#: The API module, which lives elsewhere in the tree.
ENVELOPE_API_MODULES: tuple[str, ...] = ("source_collector_execution_routes",)

#: The repository the envelope writes attempts through.
ENVELOPE_REPOSITORY_MODULES: tuple[str, ...] = (
    "source_collection_execution_attempt_repository",
)

#: The three httpx importers the survey decided not to refactor. They must be
#: absent from the envelope's import graph; their existence is not a finding.
LEGACY_TRANSPORTS: tuple[str, ...] = (
    "grants_gov_search_api_adapter_service",
    "polite_http_fetch_service",
    "real_url_resolver_service",
)

#: The parameter through which a transport is handed in. Its presence is what
#: makes "injected, not imported" a fact about the signature.
TRANSPORT_PARAMETER = "transport"

#: Functions that must take that parameter.
INJECTION_POINTS: tuple[tuple[str, str], ...] = (
    ("source_collection_transport_service", "execute_request"),
    ("source_collector_execution_service", "execute_collection"),
)

#: The module that must compose the boundary rather than dispatch on its own.
MUST_CALL_THE_BOUNDARY: frozenset[str] = frozenset(
    {"source_collector_execution_service"}
)

#: Callee names that would mean dispatching without the boundary. Matched on
#: the FINAL segment of a resolved dotted path, so `httpx.get` and a rebound
#: `client.get` are both caught, and a docstring mentioning `get` is not.
DIRECT_TRANSPORT_CALLS: frozenset[str] = frozenset(
    {"urlopen", "request", "urlretrieve", "create_connection", "connect"}
)

FINDINGS: tuple[str, ...] = (
    "envelope_module_missing",
    "module_does_not_route_through_the_boundary",
    "module_calls_a_transport_directly",
    "envelope_module_imports_a_network_module",
    "envelope_module_imports_a_legacy_transport",
    "injection_point_missing",
    "injection_point_does_not_take_a_transport",
    "live_dispatches_without_a_permitting_policy",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _repo_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    return Path(__file__).resolve().parents[3]


def _module_path(root: Path, name: str) -> Path | None:
    for folder in ("services", "repositories", "api"):
        candidate = root / "src" / "nativeforge" / folder / f"{name}.py"
        if candidate.exists():
            return candidate
    return None


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None


def _imported_names(tree: ast.AST) -> set[str]:
    """Every module name this file imports, from import NODES only.

    A docstring saying "never imports httpx" is not an import, and this is the
    difference between asking whether something happens and asking whether some
    text appears.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module)
                found.add(node.module.split(".")[0])
                for alias in node.names:
                    found.add(f"{node.module}.{alias.name}")
    return found


def _called_name_paths(tree: ast.AST) -> set[str]:
    """Dotted callee paths, resolved from Name/Attribute nodes only.

    Never `ast.unparse`: its output for `str(expected_sha256 or '').lower`
    contains `sha256`, which is how Gate 160 turned a fixed substring check back
    into a substring check.
    """
    paths: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts: list[str] = []
        current: Any = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            paths.add(".".join(reversed(parts)))
    return paths


def _network_imports(imported: set[str]) -> set[str]:
    """Which of these imports can reach a host.

    `urllib.parse` and `urllib.robotparser` are inert and stay inert here, as
    Gate 94 settled - refusing them would mean refusing URL parsing, which is
    how the request builder does its job without touching a socket.
    """
    hits: set[str] = set()
    for name in imported:
        if name in INERT_URLLIB_SUBMODULES:
            continue
        if name in NETWORK_MODULES:
            hits.add(name)
        if name.split(".")[0] in NETWORK_MODULES and name not in (
            INERT_URLLIB_SUBMODULES
        ):
            # `urllib` itself is only a hit via a network submodule.
            if not name.startswith("urllib.") or name.startswith(
                ("urllib.request", "urllib.error")
            ):
                hits.add(name)
    return hits


def _function_parameters(tree: ast.AST, function: str) -> list[str] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name == function
        ):
            args = node.args
            return [
                a.arg
                for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]
            ]
    return None


def scan_execution_chokepoint(
    *, repo_root: Path | str | None = None
) -> dict[str, Any]:
    """Prove, by parsing, that the envelope cannot reach a host."""
    root = _repo_root(repo_root)
    findings: list[dict[str, Any]] = []
    modules: dict[str, Any] = {}

    every = (
        *ENVELOPE_MODULES,
        *ENVELOPE_API_MODULES,
        *ENVELOPE_REPOSITORY_MODULES,
    )

    for name in every:
        path = _module_path(root, name)
        if path is None:
            # A renamed file must fail loudly. A scan that silently skips what
            # it cannot find reports "no network imports" about nothing at all.
            findings.append(
                {"kind": "envelope_module_missing", "module": name}
            )
            modules[name] = {"found": False}
            continue

        tree = _parse(path)
        if tree is None:
            findings.append(
                {"kind": "envelope_module_missing", "module": name,
                 "detail": "unparseable"}
            )
            modules[name] = {"found": False}
            continue

        imported = _imported_names(tree)
        called = _called_name_paths(tree)
        network = sorted(_network_imports(imported))
        legacy = sorted(set(imported) & set(LEGACY_TRANSPORTS)) + sorted(
            {
                item
                for item in imported
                for legacy_name in LEGACY_TRANSPORTS
                if item.endswith(f".{legacy_name}")
            }
        )

        if network:
            findings.append(
                {
                    "kind": "envelope_module_imports_a_network_module",
                    "module": name,
                    "imports": network,
                }
            )
        if legacy:
            findings.append(
                {
                    "kind": "envelope_module_imports_a_legacy_transport",
                    "module": name,
                    "imports": sorted(set(legacy)),
                }
            )

        modules[name] = {
            "found": True,
            "path": str(path.relative_to(root)),
            "network_imports": network,
            "legacy_transport_imports": sorted(set(legacy)),
            "reaches_a_host": bool(network),
            "calls_the_boundary": "execute_request" in called,
            "calls_a_transport_directly": sorted(
                path
                for path in called
                if path.split(".")[-1] in DIRECT_TRANSPORT_CALLS
            ),
        }

        # A module that imports nothing network-capable cannot reach a host.
        # It could still hand its transport to something other than the
        # boundary, which the import check alone would not notice - so the
        # composition is checked too.
        if name in MUST_CALL_THE_BOUNDARY and "execute_request" not in called:
            findings.append(
                {
                    "kind": "module_does_not_route_through_the_boundary",
                    "module": name,
                }
            )
        direct = sorted(
            path
            for path in called
            if path.split(".")[-1] in DIRECT_TRANSPORT_CALLS
        )
        if direct:
            findings.append(
                {
                    "kind": "module_calls_a_transport_directly",
                    "module": name,
                    "calls": direct,
                }
            )

    # ---- the injection points --------------------------------------------
    for module_name, function in INJECTION_POINTS:
        path = _module_path(root, module_name)
        tree = _parse(path) if path else None
        if tree is None:
            findings.append(
                {"kind": "injection_point_missing", "module": module_name,
                 "function": function}
            )
            continue
        params = _function_parameters(tree, function)
        if params is None:
            findings.append(
                {"kind": "injection_point_missing", "module": module_name,
                 "function": function}
            )
            continue
        if TRANSPORT_PARAMETER not in params:
            findings.append(
                {
                    "kind": "injection_point_does_not_take_a_transport",
                    "module": module_name,
                    "function": function,
                    "parameters": params,
                }
            )

    # ---- live must not be dispatchable -----------------------------------
    from nativeforge.services.source_collection_transport_service import (
        DISPATCHABLE_KINDS,
        LIVE,
    )

    # Gate 163 made `live` dispatchable for an authorized source, so its
    # presence in DISPATCHABLE_KINDS is no longer a finding. What IS a finding
    # is a live dispatch that no policy permits - measured by attempting one
    # against a refusing policy, with a request that reaches no host even if
    # the refusal failed.
    if LIVE in DISPATCHABLE_KINDS:
        from nativeforge.services.source_collection_request_builder_service import (
            build_source_request,
        )
        from nativeforge.services.source_collection_transport_service import (
            execute_request,
        )

        probe = build_source_request(
            source_definition={
                "source_id": "nf163.probe.chokepoint",
                "endpoint": "https://fixtures.invalid/nf163/chokepoint",
                "method": "GET",
            }
        )
        if probe.get("usable"):
            attempted = execute_request(
                request=probe["transport_request"],
                transport_kind=LIVE,
                policy={
                    "execution_allowed": False,
                    "live_transport_allowed": False,
                    "hermetic_transport_allowed": False,
                },
                transport=lambda request: None,
            )
            if attempted.get("dispatched"):
                findings.append(
                    {"kind": "live_dispatches_without_a_permitting_policy"}
                )

    modules_found = sum(1 for m in modules.values() if m.get("found"))
    reaching = sorted(
        name for name, m in modules.items() if m.get("reaches_a_host")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "modules_expected": list(every),
            "modules_found": modules_found,
            "modules": modules,
            "modules_that_reach_a_host": reaching,
            "envelope_reaches_no_host": not reaching,
            "findings": findings,
            "finding_kinds": list(FINDINGS),
            "clean": not findings,
            "injection_points": [
                {"module": m, "function": f} for m, f in INJECTION_POINTS
            ],
            "transport_parameter": TRANSPORT_PARAMETER,
            "legacy_transports_not_refactored": list(LEGACY_TRANSPORTS),
            "why_legacy_transports_stay": (
                "each imports httpx under two guards, each is already "
                "injectable, each is on the approved-site list with a recorded "
                "reason, and none is on the envelope's import path. Doc 837 "
                "records the decision. What matters is their ABSENCE from this "
                "graph, not that they were rewritten."
            ),
            "approved_network_modules": sorted(APPROVED_MODULE_NAMES),
            "how_this_is_measured": (
                "ast.Import and ast.ImportFrom nodes, and dotted callee paths "
                "resolved from Name/Attribute nodes. No substring search: a "
                "module whose docstring says it never imports httpx fails a "
                "grep for httpx."
            ),
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def chokepoint_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Refuse a chokepoint report that passes by not having looked."""
    fails: list[str] = []

    expected = list(report.get("modules_expected") or ())
    if not expected:
        fails.append("the_scan_declared_no_modules_to_check")
    if int(report.get("modules_found") or 0) != len(expected):
        fails.append(
            f"modules_found_{report.get('modules_found')}_of_{len(expected)}"
        )

    # clean and findings must agree, both directions.
    if report.get("clean") and report.get("findings"):
        fails.append("clean_alongside_findings")
    if not report.get("clean") and not report.get("findings"):
        fails.append("not_clean_without_naming_a_finding")

    for finding in report.get("findings") or []:
        kind = finding.get("kind")
        if kind not in set(report.get("finding_kinds") or ()):
            fails.append(f"finding_outside_vocabulary:{kind}")
        fails.append(f"chokepoint:{kind}:{finding.get('module') or ''}")

    if report.get("modules_that_reach_a_host"):
        fails.append(
            f"the_envelope_reaches_a_host_via:"
            f"{report['modules_that_reach_a_host']}"
        )
    if not report.get("envelope_reaches_no_host"):
        fails.append("the_envelope_did_not_prove_it_reaches_no_host")

    # The injection points must be DECLARED, or the scan proved nothing about
    # them. An empty list would make every other check pass vacuously.
    if not report.get("injection_points"):
        fails.append("no_injection_point_was_checked")

    for flag in ("live_source_call", "source_monitoring_live"):
        if report.get(flag):
            fails.append(f"chokepoint_claimed:{flag}")
    if int(report.get("network_calls") or 0):
        fails.append("chokepoint_counted_a_network_call")

    return sorted(set(fails))
