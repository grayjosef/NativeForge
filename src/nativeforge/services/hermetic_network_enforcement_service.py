"""Hermetic network enforcement scanner (Gate 94F).

Scans ``src/nativeforge`` for code that can reach the network and reports
anything not on the approved list. A source-code safety helper — it never
fetches, and it never imports the modules it inspects.

## Why a scanner and not just a survey

Doc 530 is a snapshot: six egress sites, one guarded. A snapshot does not stop
the seventh. This runs in the test suite, so a new ``import httpx`` in a service
fails the build the day it lands rather than being discovered by the gate after
next.

## Parsed, not grepped

Everything here works on an ``ast`` parse. Gate 91 and Gate 92 both had guards
fire on their own docstrings, and a text search for ``httpx`` cannot tell a call
from the word appearing in prose — this module's own docstring is a case in
point. Imports come from ``ast.Import``/``ast.ImportFrom`` nodes and defaults
from ``ast.arg`` defaults.

## The approved list is a list, not a pattern

Each entry names a module, the reason it may reach the network, and the guard it
routes through. A module not on the list is a finding; there is no naming
convention that grants an exemption, because a convention is something a new
file can accidentally satisfy.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_hermetic_network_enforcement_v1"

# Libraries that can open a connection.
NETWORK_MODULES = frozenset(
    {
        "httpx",
        "requests",
        "aiohttp",
        "socket",
        "urllib3",
        "ftplib",
        "smtplib",
        "telnetlib",
        "websockets",
        "selenium",
        "playwright",
        "pycurl",
    }
)

# Submodules of urllib that fetch. urllib.parse does not.
NETWORK_URLLIB_SUBMODULES = frozenset({"urllib.request", "urllib.error"})

# urllib pieces that are pure string work and never touch a socket.
INERT_URLLIB_SUBMODULES = frozenset({"urllib.parse", "urllib.robotparser"})

# http.client / http.server open connections; http.HTTPStatus does not.
NETWORK_HTTP_SUBMODULES = frozenset({"http.client", "http.server", "http.cookiejar"})


class ApprovedSite:
    """One module permitted to reach the network, and why."""

    __slots__ = ("module", "reason", "guard")

    def __init__(self, module: str, reason: str, guard: str) -> None:
        self.module = module
        self.reason = reason
        self.guard = guard


# The complete approved list. Adding to it is a deliberate act with a reason
# attached; there is no wildcard.
APPROVED_NETWORK_SITES: tuple[ApprovedSite, ...] = (
    ApprovedSite(
        "grants_gov_search_api_adapter_service",
        "single choke point for Grants.gov Search2/fetchOpportunity",
        "hermetic_test_guard_service.assert_live_network_allowed (Gate 77B)",
    ),
    ApprovedSite(
        "polite_http_fetch_service",
        "the crawler transport for HTML sources",
        "live_network_guard_service.build_live_network_decision",
    ),
    ApprovedSite(
        "real_url_resolver_service",
        "URL liveness resolution",
        "live_network_guard_service.build_live_network_decision",
    ),
    ApprovedSite(
        "oidc_token_verification_service",
        "JWKS retrieval for identity verification",
        "live_network_guard_service (purpose=identity_verification); "
        "allow_network defaults False; https enforced before the request",
    ),
    ApprovedSite(
        "feedback_slack_alert_service",
        "operational alert webhook",
        "live_network_guard_service (purpose=operational_alert); "
        "off/dry_run/live mode plus a required out-of-repo webhook env var",
    ),
    ApprovedSite(
        "gate37_production_grade_hardening_service",
        "loopback port availability probe for the preview server; never egress",
        "not applicable - 127.0.0.1 only, no third-party contact",
    ),
)

APPROVED_MODULE_NAMES = frozenset(s.module for s in APPROVED_NETWORK_SITES)

# Modules permitted to define a user-agent string. Exactly one.
APPROVED_USER_AGENT_MODULES = frozenset({"nativeforge_user_agent_service"})

# Gate 92's governance module holds the forbidden-token list and Gate 94's
# guard re-exports the canonical string; neither defines a second one.
USER_AGENT_REFERENCE_MODULES = frozenset(
    {
        "source_crawler_governance_service",
        "live_network_guard_service",
        "polite_http_fetch_service",
    }
)

FINDING_KINDS = frozenset(
    {
        "unapproved_network_import",
        "allow_live_fetch_defaults_true",
        "second_user_agent_definition",
        "robots_fail_open",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _services_dir(repo_root: Path) -> Path:
    return repo_root / "src" / "nativeforge"


def _imported_network_modules(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                root = name.split(".")[0]
                if name in INERT_URLLIB_SUBMODULES:
                    continue
                if root in NETWORK_MODULES:
                    found.add(root)
                elif name in NETWORK_URLLIB_SUBMODULES:
                    found.add(name)
                elif name in NETWORK_HTTP_SUBMODULES:
                    found.add(name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            name = node.module
            root = name.split(".")[0]
            if name in INERT_URLLIB_SUBMODULES:
                continue
            if root in NETWORK_MODULES:
                found.add(root)
            elif name in NETWORK_URLLIB_SUBMODULES:
                found.add(name)
            elif name in NETWORK_HTTP_SUBMODULES:
                found.add(name)
            elif root == "urllib" and name not in INERT_URLLIB_SUBMODULES:
                found.add(name)
    return found


def _allow_live_fetch_true_defaults(tree: ast.AST) -> list[str]:
    """Functions whose `allow_live_fetch` parameter defaults to True."""
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        args = node.args
        # Positional-or-keyword defaults align to the tail of the arg list.
        pairs: list[tuple[ast.arg, ast.expr]] = []
        positional = args.posonlyargs + args.args
        if args.defaults:
            pairs.extend(
                zip(
                    positional[-len(args.defaults) :],
                    args.defaults,
                    strict=False,
                )
            )
        pairs.extend(
            (a, d)
            for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False)
            if d is not None
        )
        for arg, default in pairs:
            if arg.arg != "allow_live_fetch":
                continue
            if isinstance(default, ast.Constant) and default.value is True:
                findings.append(node.name)
    return findings


def _user_agent_definitions(tree: ast.AST) -> list[str]:
    """Module-level assignments whose value looks like a UA string.

    Module level only, via `tree.body` rather than `ast.walk`. A local variable
    inside a function is not a definition anyone can import, and walking the
    whole tree made this scanner flag its own detection heuristic - the third
    time in this campaign a guard has fired on the code implementing it.
    """
    findings: list[str] = []
    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
            value = node.value
        else:
            continue
        if value is None:
            continue
        text = "".join(
            sub.value
            for sub in ast.walk(value)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
        )
        if not text:
            continue
        # A user-agent string identifies a product and carries a contact.
        looks_like_ua = ("bot/" in text.lower() or "nativeforge/" in text.lower()) and (
            "+http" in text.lower() or "mailto:" in text.lower()
        )
        if looks_like_ua:
            findings.extend(names)
    return findings


def scan_for_network_call_sites(
    *, repo_root: Path | str | None = None
) -> dict[str, Any]:
    """Scan src/nativeforge and report every finding. Reads files only."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    base = _services_dir(root)

    findings: list[dict[str, Any]] = []
    network_sites: list[dict[str, Any]] = []
    scanned = 0

    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        stem = path.stem
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            findings.append(
                {
                    "kind": "unapproved_network_import",
                    "module": stem,
                    "file": rel,
                    "detail": "file could not be parsed",
                }
            )
            continue
        scanned += 1

        imports = _imported_network_modules(tree)
        if imports:
            network_sites.append(
                {
                    "module": stem,
                    "file": rel,
                    "libraries": sorted(imports),
                    "approved": stem in APPROVED_MODULE_NAMES,
                }
            )
            if stem not in APPROVED_MODULE_NAMES:
                findings.append(
                    {
                        "kind": "unapproved_network_import",
                        "module": stem,
                        "file": rel,
                        "detail": f"imports {', '.join(sorted(imports))}",
                    }
                )

        for func in _allow_live_fetch_true_defaults(tree):
            findings.append(
                {
                    "kind": "allow_live_fetch_defaults_true",
                    "module": stem,
                    "file": rel,
                    "detail": f"{func}() defaults allow_live_fetch=True",
                }
            )

        if stem not in APPROVED_USER_AGENT_MODULES:
            for name in _user_agent_definitions(tree):
                findings.append(
                    {
                        "kind": "second_user_agent_definition",
                        "module": stem,
                        "file": rel,
                        "detail": f"{name} defines a user-agent string",
                    }
                )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "files_scanned": scanned,
            "network_call_sites": network_sites,
            "network_call_site_count": len(network_sites),
            "approved_count": sum(1 for s in network_sites if s["approved"]),
            "unapproved_count": sum(1 for s in network_sites if not s["approved"]),
            "findings": findings,
            "finding_count": len(findings),
            "clean": not findings,
            "approved_sites": [
                {"module": s.module, "reason": s.reason, "guard": s.guard}
                for s in APPROVED_NETWORK_SITES
            ],
            # This scanner reads source. It never runs it and never fetches.
            "fetch_performed": False,
            "modules_imported": 0,
            "fabricated": False,
        }
    )


def enforcement_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if report.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if report.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if report.get("fetch_performed") is not False:
        fails.append("scanner_claimed_a_fetch")
    if report.get("modules_imported"):
        fails.append("scanner_imported_the_modules_it_scans")

    if not report.get("files_scanned"):
        fails.append("scanner_scanned_nothing")

    for finding in report.get("findings") or []:
        if finding.get("kind") not in FINDING_KINDS:
            fails.append(f"finding_kind_out_of_vocabulary:{finding.get('kind')}")
        if not finding.get("file"):
            fails.append("finding_without_a_file")

    # `clean` is derived, never asserted beside the findings.
    if report.get("clean") != (not report.get("findings")):
        fails.append("clean_flag_disagrees_with_findings")

    # Every approved site must name a guard and a reason.
    for site in report.get("approved_sites") or []:
        if not site.get("guard") or not site.get("reason"):
            fails.append(f"approved_site_without_justification:{site.get('module')}")

    return fails
