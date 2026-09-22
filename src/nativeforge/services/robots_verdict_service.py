"""Robots verdicts, RFC 9309 (Gate 171G, promoted from Gate 163).

This logic was written for the first live source and lived in that gate's
runner. A second and third source need the same verdicts, and the wrong way to
get them is a second parser: two robots implementations would eventually
disagree, and the one that disagreed in the permitting direction would be the
one nobody noticed.

So it is MOVED here verbatim rather than reimplemented, and the move is
checked against evidence rather than asserted - the 403 that Gate 163 stored
for the first source still re-derives to `unavailable` through this module.

It remains deliberately small and deliberately conservative. Anything it
cannot parse confidently returns `unparseable`, which does not permit.

And it authorizes nothing. RFC 9309 section 2 is explicit that robots rules
are not a form of access authorization, and this campaign treats a permitting
verdict as the removal of one objection, never as permission.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "nf_robots_verdict_v1"

#: RFC 9309 section 2.3.1. Each status class means something different, and
#: the first live fetch of this campaign landed in the gap the old mapping
#: missed.
#:
#: `unavailable` PERMITS - section 2.3.1.3, "crawlers MAY access any
#: resources". It is NOT `unreachable`, which section 2.3.1.4 says MUST be
#: treated as a complete disallow.
ROBOTS_VERDICT_PERMITS: frozenset[str] = frozenset(
    {"allowed", "absent", "unavailable"}
)


def derive_robots_verdict(*, status: Any, body: bytes, path: str) -> dict:
    """The verdict for one status and one body, per RFC 9309 section 2.3.1.

    PURE: status and bytes in, verdict out. That is what lets a verdict be
    RE-DERIVED from stored evidence without refetching, which is how the 4xx
    correction was applied to the 403 already on disk.
    """
    if status is None:
        # Network failure, DNS failure or timeout. Section 2.3.1.4.
        return {
            "decision": "unreachable",
            "rfc_class": "network_failure",
            "restricts_collection": True,
            "matched_group": None,
            "rules": [],
        }

    code = int(status)

    if 200 <= code < 300:
        parsed = parse_robots(body, path=path, agent="*")
        parsed["rfc_class"] = "successful"
        parsed["restricts_collection"] = parsed["decision"] == "disallowed"
        return parsed

    if 300 <= code < 400:
        # This transport follows no redirect by design: a redirect is a
        # different URL than the one authorized. Unfetched does not permit.
        return {
            "decision": "unreachable",
            "rfc_class": "redirect_not_followed",
            "restricts_collection": True,
            "matched_group": None,
            "rules": [],
        }

    if code == 404:
        # Definitively no file. Distinct from 4xx in general, where the file
        # could not be retrieved and we cannot say whether it exists.
        return {
            "decision": "absent",
            "rfc_class": "unavailable",
            "restricts_collection": False,
            "matched_group": None,
            "rules": [],
        }

    if 400 <= code < 500:
        # Section 2.3.1.3, "Unavailable". The robots protocol adds NO
        # restriction for this authority. It authorizes nothing - section 2
        # is explicit that robots rules are not a form of access
        # authorization.
        return {
            "decision": "unavailable",
            "rfc_class": "unavailable",
            "restricts_collection": False,
            "matched_group": None,
            "rules": [],
        }

    # 5xx. Section 2.3.1.4, "Unreachable" - a complete disallow.
    return {
        "decision": "unreachable",
        "rfc_class": "unreachable",
        "restricts_collection": True,
        "matched_group": None,
        "rules": [],
    }


def parse_robots(body: bytes, *, path: str, agent: str = "*") -> dict:
    """Minimal RFC 9309 evaluation for one path under the wildcard agent.

    Deliberately small and deliberately CONSERVATIVE: anything it cannot parse
    confidently returns `unparseable`, which does not permit. A robots parser
    that guesses is a robots parser that eventually guesses wrong in the
    permitting direction.
    """
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"decision": "unparseable", "matched_group": None, "rules": []}

    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    current_agents: list[str] = []
    current_rules: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if current_rules:
                groups.append((current_agents, current_rules))
                current_agents, current_rules = [], []
            current_agents.append(value.lower())
        elif field in {"allow", "disallow"}:
            current_rules.append((field, value))
    if current_agents or current_rules:
        groups.append((current_agents, current_rules))

    matched = None
    for agents, rules in groups:
        if agent.lower() in agents:
            matched = (agents, rules)
            break
    if matched is None:
        for agents, rules in groups:
            if "*" in agents:
                matched = (agents, rules)
                break

    if matched is None:
        # No group applies to us. RFC 9309: absent rules mean no restriction.
        return {"decision": "allowed", "matched_group": None, "rules": []}

    agents, rules = matched
    best: tuple[int, str] | None = None
    for field, value in rules:
        if value == "":
            # An empty Disallow permits everything; an empty Allow is a no-op.
            if field == "disallow":
                candidate = (0, "allow")
                if best is None or candidate[0] >= best[0]:
                    best = candidate
            continue
        if path.startswith(value):
            candidate = (len(value), "allow" if field == "allow" else "disallow")
            # Longest match wins; Allow wins ties.
            if (
                best is None
                or candidate[0] > best[0]
                or (candidate[0] == best[0] and candidate[1] == "allow")
            ):
                best = candidate

    decision = "allowed" if best is None or best[1] == "allow" else "disallowed"
    return {
        "decision": decision,
        "matched_group": agents,
        "rules": [f"{f}: {v}" for f, v in rules],
    }
