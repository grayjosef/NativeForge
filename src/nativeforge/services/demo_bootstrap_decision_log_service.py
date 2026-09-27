"""One structured line saying why the first-membership bootstrap did or did not happen.

Controlled-live lands a verified Google identity on `?view=onboarding` and
issues no session. Every stage of that is individually proven - the token
verifies, the identity persists, and the tenant-context gate plus the insert
both work on a real PostgreSQL as a NOSUPERUSER/NOBYPASSRLS role. The one
fact nobody has is what the deployed instance decided, because the callback
reports it only to a non-HTML caller and a browser always asks for HTML.

So the decision goes to the log instead.

## What may not appear here, ever

This runs inside the OAuth callback, which is holding an authorization code,
an ID token, a client secret and a session cookie. None of them is an input
to this function and none can reach the output: it takes booleans, enums and
reason codes, and `emit` refuses any value that is not one of those.

That refusal is structural rather than a convention. A future caller that
passes an email, a token or a URL gets `UNSAFE_VALUE_WITHHELD` in the log
line instead of the value, and a test asserts it.

## Three-valued on purpose

`FOUND` / `NOT_FOUND` / `ACCESS_DENIED` / `UNKNOWN` are kept apart because
under row-level security a refused read and an absent row both return nothing.
Collapsing them is exactly how a bootstrap that cannot see its organization
would report that the organization does not exist, and send whoever reads the
log looking for the wrong bug.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

SCHEMA_VERSION = "nf_demo_bootstrap_decision_log_v1"

EVENT = "nativeforge.auth.demo_bootstrap_decision"

LOGGER = logging.getLogger(EVENT)

UNKNOWN = "UNKNOWN"
WITHHELD = "UNSAFE_VALUE_WITHHELD"

#: The vocabulary a value may use. Anything else is withheld rather than
#: logged, because this line is emitted from a request that is holding
#: credentials and "probably fine" is not a property you can test.
SAFE_ENUMS: frozenset[str] = frozenset(
    {
        "FOUND",
        "NOT_FOUND",
        "ACCESS_DENIED",
        "UNKNOWN",
        "SKIPPED",
        "PASS",
        "FAIL",
    }
)

#: The exact fields this event carries, in the order an operator reads them:
#: preconditions, then the reads, then the context, then the insert, then what
#: the callback concluded.
FIELDS: tuple[str, ...] = (
    "correlation_id",
    "bootstrap_attempted",
    "bootstrap_org_env_present",
    "target_org_matches_configured_demo_org",
    "identity_validated",
    "identity_persisted",
    "self_bind_verified",
    "target_org_lookup",
    "target_org_is_demo",
    "membership_count_lookup",
    "existing_membership_count_zero",
    "tenant_context_open_attempted",
    "tenant_context_opened",
    "tenant_context_blocked_reasons",
    "insert_attempted",
    "insert_succeeded",
    "insert_blocked_reasons",
    "membership_verified_after_insert",
    "organization_id_resolved",
    "callback_session_allowed",
)

#: A reason code is a short machine token. Anything longer, or carrying an
#: `@`, a `://` or whitespace, is not a reason code and does not belong in a
#: log line emitted from a credential-holding request.
MAX_REASON_LENGTH = 96

#: What a reason code may look like, as an ALLOWLIST.
#:
#: The first version of this denied things that looked secret - an `@`, a
#: `://`, an `ey` prefix - and its own tests walked straight through it with
#: `GOCSPX-...`, `4/0Aean...` and `nf1.eyJ...`. Enumerating what a secret
#: looks like is a losing game. Enumerating what a reason code looks like is
#: a short list.
#:
#: A snake_case token, optionally followed by one `:detail`. Every reason this
#: codebase emits fits it; none of the credential shapes the callback is
#: holding does.
REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}(:[A-Za-z0-9_.\-]{1,40})?$")


def _safe_scalar(value: Any) -> Any:
    """Booleans, small ints, and known enums. Everything else is withheld."""
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and -1 <= value <= 10_000:
        return value
    if isinstance(value, str):
        if value in SAFE_ENUMS:
            return value
        return _safe_reason(value)
    return WITHHELD


def _safe_reason(value: Any) -> str:
    """A reason code, or a statement that one was withheld.

    Matched against `REASON_CODE` rather than screened for things that look
    dangerous. The screening version let three credential shapes through in
    its own tests, which is the argument for allowlisting in one line.
    """
    text = str(value)
    if len(text) > MAX_REASON_LENGTH:
        return WITHHELD
    return text if REASON_CODE.match(text) else WITHHELD


def build_decision_event(**fields: Any) -> dict[str, Any]:
    """The event, with every field present and every value safe.

    Missing fields become `UNKNOWN` rather than being omitted: an operator
    reading this needs to tell "we did not reach that stage" from "nobody
    wrote that down", and an absent key says neither.
    """
    event: dict[str, Any] = {"event": EVENT, "schema_version": SCHEMA_VERSION}
    for name in FIELDS:
        raw = fields.get(name)
        if name.endswith("_reasons"):
            if raw is None:
                event[name] = UNKNOWN
            else:
                event[name] = [_safe_reason(r) for r in list(raw)][:12]
        else:
            event[name] = _safe_scalar(raw)
    return event


def emit(**fields: Any) -> dict[str, Any]:
    """Build the event, log it as one JSON line, and return it.

    Returned as well as logged so a caller can assert on it, and so the
    callback's own response body and the log line cannot drift apart.

    Logging never raises into the auth path: an observability failure must not
    become an authentication failure.
    """
    event = build_decision_event(**fields)
    try:
        LOGGER.info(json.dumps(event, sort_keys=True))
    except Exception:  # pragma: no cover - logging must never break auth
        pass
    return event
