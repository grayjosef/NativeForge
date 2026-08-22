"""Gate 37: demo reliability + claim-boundary helpers."""

from __future__ import annotations

import re
import socket

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    DistNotReady,
)

PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 5175

JOURNAL_HINT = "journalctl --user -u nativeforge-demo-preview.service -n 80 --no-pager"

FORBIDDEN_VISIBLE_CLAIMS = (
    "production-ready",
    "pilot-ready",
    "login live",
    "pen-test passed",
    "production storage",
    "customer access live",
    "customer persistence",
)

# "secure" as a standalone word, not "security".
SECURE_WORD_RE = re.compile(r"\bsecure\b", re.IGNORECASE)

NEGATION_MARKERS = (
    "stay",
    "stays",
    "absent",
    "only",
    "local/dev",
    "not ",
    "no ",
    "never ",
    "false",
    "do not",
    "don't",
    "remain",
    "blocked",
    "pending",
    "below",
    "without",
    "forbidden",
    "fake",
    "un-",
    "isn't",
    "is not",
)


ALLOWED_DEMO_LANGUAGE = (
    "Limited external demo",
    "Dev-domain demo",
    "Evidence-backed Native-relevant opportunity workflow",
    "Customer pilot pending auth/storage/security gates",
    "Production rollout blocked until gates pass",
)


def require_preview_port_free(
    host: str = PREVIEW_HOST,
    port: int = PREVIEW_PORT,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        in_use = sock.connect_ex((host, port)) == 0
    if in_use:
        raise DistNotReady(f"port {port} already in use on {host}")


def require_loopback_serve_contract(script_text: str) -> None:
    if "--host 127.0.0.1" not in script_text:
        raise DistNotReady("serve script missing loopback --host 127.0.0.1")
    if "--port 5175" not in script_text:
        raise DistNotReady("serve script missing --port 5175")
    if "--strictPort" not in script_text:
        raise DistNotReady("serve script missing --strictPort")
    if "0.0.0.0" in script_text:
        raise DistNotReady("serve script must not bind 0.0.0.0")
    if "npm run dev" in script_text or "npm --prefix frontend run dev" in script_text:
        raise DistNotReady("serve script must not use npm run dev")


def _line_negated(line: str) -> bool:
    lowered = line.lower()
    return any(m in lowered for m in NEGATION_MARKERS)


def unnegated_forbidden_hits(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines()
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if "<h2>" in lowered or "data-testid" in lowered:
            continue
        window = " ".join(lines[max(0, i - 1) : min(len(lines), i + 2)])
        if _line_negated(window):
            continue
        for phrase in FORBIDDEN_VISIBLE_CLAIMS:
            if phrase in lowered:
                hits.append(f"{phrase}: {line[:160]}")
        if SECURE_WORD_RE.search(line) and "security" not in lowered:
            hits.append(f"secure: {line[:160]}")
    return hits


def require_claim_boundary_source(text: str) -> None:
    hits = unnegated_forbidden_hits(text)
    if hits:
        raise DistNotReady("unnegated forbidden claim: " + hits[0])
    blob = text
    for marker in ALLOWED_DEMO_LANGUAGE:
        if marker not in blob:
            raise DistNotReady(f"missing allowed demo language: {marker}")
