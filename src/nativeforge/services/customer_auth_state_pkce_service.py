"""Customer auth state and PKCE (Gate 117D).

Local generation and validation of the two values that make an OIDC redirect
flow safe against replay and interception. No provider is contacted and nothing
generated here is a secret in the sense that matters — but a *predictable* state
or verifier is worse than no secret at all, so the entropy is real.

## What each one stops

```text
state           the browser that started the flow is the browser that finished
                it. Without it, an attacker completes a flow in your browser
                using their authorization code, and you end up logged in as them.

PKCE verifier   the client that started the flow is the client that redeems the
                code. Without it, an intercepted authorization code can be
                exchanged by whoever captured it.
```

Gate 117A found neither exists anywhere in NativeForge: zero occurrences of
`code_verifier`, `code_challenge`, `token_urlsafe` or `urandom` outside Gate
116's docstring explaining their absence. The `S256` matches in the repository
are `RS256`, the JWT signing algorithm, which is a different thing.

## Generation is injectable, and that is a safety feature and a hazard

Tests need determinism. Production must never have it. The generator is a
parameter, and `deterministic_generator_used` travels with every result — a
value produced by an injected generator says so, and an invariant refuses to
call such a result production-safe.

The default is `secrets.token_urlsafe`, which draws from the OS CSPRNG.

## Comparison is constant-time

`hmac.compare_digest` rather than `==`. A state comparison that returns early on
the first differing byte leaks the prefix to anyone who can time it, and the
whole point of state is that an attacker cannot produce it.

## Nothing here is committed

`build_fixture_state_pkce` produces obviously-fake values prefixed
`nf-demo-fixture-` for artifacts and demo cases. They are labelled, they fail
the entropy check on purpose, and an invariant fails any result that treats one
as production-safe.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_state_pkce_v1"

# RFC 7636 allows `plain` and `S256`. Only one of them is a defence: `plain`
# sends the verifier as the challenge, so an interceptor of the authorization
# request learns the value that would redeem the code.
CODE_CHALLENGE_METHOD = "S256"
ALLOWED_CHALLENGE_METHODS: frozenset[str] = frozenset({"S256"})

# RFC 7636 permits 43-128 characters for a verifier. 64 URL-safe bytes lands in
# range with room to spare.
VERIFIER_BYTES = 64
STATE_BYTES = 32

# Below this, a state is guessable in a way that makes it decorative. RFC 6749
# says only "non-guessable"; this is the floor at which that is true.
MIN_STATE_LENGTH = 32
MIN_VERIFIER_LENGTH = 43
MAX_VERIFIER_LENGTH = 128

# Values that appear in artifacts and demo fixtures. Deliberately recognisable,
# deliberately too short to pass the entropy check.
FIXTURE_PREFIX = "nf-demo-fixture-"
FIXTURE_STATE = f"{FIXTURE_PREFIX}state"
FIXTURE_VERIFIER = f"{FIXTURE_PREFIX}verifier"

RESULT_FIELDS: tuple[str, ...] = (
    "state_required",
    "state_generated",
    "state_length",
    "state_entropy_ok",
    "state_valid",
    "pkce_required",
    "code_verifier_generated",
    "code_challenge_generated",
    "code_challenge_method",
    "pkce_valid",
    "secrets_exposed",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _default_generator(nbytes: int) -> str:
    """The OS CSPRNG. Replaced only by an injected generator, which says so."""
    return secrets.token_urlsafe(nbytes)


def derive_code_challenge(code_verifier: str) -> str:
    """S256: BASE64URL(SHA256(ASCII(verifier))), unpadded, per RFC 7636."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _entropy_ok(value: str, minimum: int) -> bool:
    """Long enough, and not one of the fixture values.

    Length is a proxy for entropy and a poor one in general; it is adequate here
    because the only generators in play are a CSPRNG and an injected test
    generator, and the fixture values are excluded by name.
    """
    if not value or value.startswith(FIXTURE_PREFIX):
        return False
    return len(value) >= minimum


def generate_state_and_pkce(
    *,
    generator: Callable[[int], str] | None = None,
    production_mode: bool = False,
) -> dict[str, Any]:
    """Generate a state and a PKCE pair. Local only; no provider is contacted."""
    deterministic = generator is not None
    gen = generator or _default_generator

    state = str(gen(STATE_BYTES))
    code_verifier = str(gen(VERIFIER_BYTES))
    code_challenge = derive_code_challenge(code_verifier)

    blocked_reasons: list[str] = []

    state_entropy_ok = _entropy_ok(state, MIN_STATE_LENGTH)
    if not state_entropy_ok:
        blocked_reasons.append(f"state_shorter_than_{MIN_STATE_LENGTH}_characters")

    verifier_ok = (
        _entropy_ok(code_verifier, MIN_VERIFIER_LENGTH)
        and len(code_verifier) <= MAX_VERIFIER_LENGTH
    )
    if not verifier_ok:
        blocked_reasons.append(
            f"code_verifier_outside_{MIN_VERIFIER_LENGTH}_{MAX_VERIFIER_LENGTH}_range"
        )

    # A deterministic generator is a test tool. In production it means every
    # flow shares a state, which is the same as having none.
    if deterministic and production_mode:
        blocked_reasons.append("deterministic_generator_used_in_production_mode")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state_required": True,
            "state_generated": bool(state),
            "state": state,
            "state_length": len(state),
            "state_entropy_ok": state_entropy_ok,
            "state_valid": False,
            "pkce_required": True,
            "code_verifier_generated": bool(code_verifier),
            "code_verifier": code_verifier,
            "code_verifier_length": len(code_verifier),
            "code_challenge_generated": bool(code_challenge),
            "code_challenge": code_challenge,
            "code_challenge_method": CODE_CHALLENGE_METHOD,
            "pkce_valid": False,
            "deterministic_generator_used": deterministic,
            "production_mode": bool(production_mode),
            "production_safe": bool(
                state_entropy_ok and verifier_ok and not deterministic
            ),
            "is_fixture": state.startswith(FIXTURE_PREFIX),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: generated locally, sent nowhere, stored nowhere.
            "secrets_exposed": False,
            "provider_contacted": False,
            "network_calls": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def validate_state_and_pkce(
    *,
    expected_state: Any = None,
    returned_state: Any = None,
    code_verifier: Any = None,
    expected_code_challenge: Any = None,
    code_challenge_method: Any = CODE_CHALLENGE_METHOD,
) -> dict[str, Any]:
    """Validate a callback's state and PKCE. Deny by default."""
    expected = str(expected_state or "")
    returned = str(returned_state or "")
    verifier = str(code_verifier or "")
    challenge = str(expected_code_challenge or "")
    method = str(code_challenge_method or "").strip()

    blocked_reasons: list[str] = []

    if not expected:
        blocked_reasons.append("no_expected_state_to_compare_against")
    if not returned:
        blocked_reasons.append("callback_returned_no_state")

    # Constant-time. A comparison that returns early on the first differing byte
    # leaks the prefix to anyone who can time it, and the whole point of state
    # is that an attacker cannot produce it.
    state_matches = bool(
        expected and returned and hmac.compare_digest(expected, returned)
    )
    if expected and returned and not state_matches:
        blocked_reasons.append("state_mismatch")

    state_entropy_ok = _entropy_ok(expected, MIN_STATE_LENGTH)
    if expected and not state_entropy_ok:
        blocked_reasons.append("expected_state_has_insufficient_entropy")

    state_valid = bool(state_matches and state_entropy_ok)

    if method not in ALLOWED_CHALLENGE_METHODS:
        # `plain` sends the verifier as the challenge, so an interceptor of the
        # authorization request learns the value that redeems the code.
        blocked_reasons.append(f"code_challenge_method_not_allowed:{method}")

    if not verifier:
        blocked_reasons.append("no_code_verifier_supplied")
    if not challenge:
        blocked_reasons.append("no_expected_code_challenge_to_compare_against")

    verifier_ok = (
        _entropy_ok(verifier, MIN_VERIFIER_LENGTH)
        and len(verifier) <= MAX_VERIFIER_LENGTH
    )
    if verifier and not verifier_ok:
        blocked_reasons.append("code_verifier_has_insufficient_entropy")

    pkce_matches = False
    if verifier and challenge and method in ALLOWED_CHALLENGE_METHODS:
        pkce_matches = hmac.compare_digest(derive_code_challenge(verifier), challenge)
        if not pkce_matches:
            blocked_reasons.append("code_challenge_mismatch")

    pkce_valid = bool(pkce_matches and verifier_ok)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state_required": True,
            "state_generated": bool(expected),
            "state_length": len(expected),
            "state_entropy_ok": state_entropy_ok,
            "state_valid": state_valid,
            "pkce_required": True,
            "code_verifier_generated": bool(verifier),
            "code_challenge_generated": bool(challenge),
            "code_challenge_method": method,
            "pkce_valid": pkce_valid,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: no value is echoed back out of a validation.
            "secrets_exposed": False,
            "provider_contacted": False,
            "network_calls": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def build_fixture_state_pkce() -> dict[str, Any]:
    """Obviously-fake values for artifacts and demo cases.

    Prefixed so they are recognisable, and short enough that the entropy checks
    refuse them. A fixture that could pass for a real state is a fixture that
    could be mistaken for one in a committed file.
    """
    result = generate_state_and_pkce(
        generator=lambda n: FIXTURE_STATE if n == STATE_BYTES else FIXTURE_VERIFIER
    )
    result["is_fixture"] = True
    result["fixture_label"] = "demo_fixture"
    return result


def state_pkce_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"state_pkce_missing_field:{field}")

    for constant in (
        "secrets_exposed",
        "provider_contacted",
        "network_calls",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"state_pkce_claimed:{constant}")

    # Both are required, always. Neither has a safe false branch.
    if result.get("state_required") is not True:
        fails.append("state_not_required")
    if result.get("pkce_required") is not True:
        fails.append("pkce_not_required")

    # Only S256. `plain` is a defence in name only.
    method = result.get("code_challenge_method")
    if result.get("pkce_valid") and method not in ALLOWED_CHALLENGE_METHODS:
        fails.append(f"pkce_valid_with_a_disallowed_method:{method}")

    # A validated state is one that matched and had entropy behind it.
    if result.get("state_valid"):
        if not result.get("state_entropy_ok"):
            fails.append("state_valid_without_sufficient_entropy")
        if result.get("blocked_reasons"):
            fails.append("state_valid_despite_blocked_reasons")

    if result.get("pkce_valid") and result.get("blocked_reasons"):
        fails.append("pkce_valid_despite_blocked_reasons")

    # A deterministic generator is a test tool, never a production one.
    if result.get("production_safe"):
        if result.get("deterministic_generator_used"):
            fails.append("production_safe_with_a_deterministic_generator")
        if result.get("is_fixture"):
            fails.append("production_safe_fixture_value")
        if not result.get("state_entropy_ok"):
            fails.append("production_safe_without_state_entropy")

    # A fixture may never be production-safe, whatever else it says.
    if result.get("is_fixture") and result.get("production_safe"):
        fails.append("fixture_reported_as_production_safe")

    # A refusal must name itself.
    if (
        result.get("state_valid") is False
        and result.get("pkce_valid") is False
        and not result.get("blocked_reasons")
        and result.get("state_generated")
        and result.get("code_verifier_generated")
        and "state" not in result
    ):
        fails.append("validation_refused_without_a_reason")

    return fails
