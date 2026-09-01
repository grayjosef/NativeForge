"""Gate 131B: encrypt the PKCE verifier at rest so the exchange can use it.

## Why this exists

Migration 0030 stored the verifier as a SHA-256 digest. That proves a returned
state matches the one issued, and it makes the exchange impossible: PKCE
requires the client to present the **raw** verifier to the token endpoint, and a
digest does not reverse.

Migration 0036 adds a retrievable column. This module is what puts something in
it that a database read alone cannot use.

## The threat this addresses, and the one it does not

```text
addresses      a dump of nf_auth_redirect_states. Ciphertext without the
               deployment's signing key is not a verifier.
does not       an attacker holding both the row and NF_SESSION_SIGNING_KEY.
               Nothing at this layer can, and a verifier is only useful for
               ten minutes against a code the attacker must also hold.
```

The key never enters the database. It is derived from `NF_SESSION_SIGNING_KEY`,
which lives in the environment, through HKDF with a fixed info label so the
derived key is distinct from anything else that key is used for — session
signing in particular. Two purposes, two keys, one secret.

## What is deliberately not here

No key rotation, no envelope encryption, no per-row key. A verifier lives for
ten minutes and is consumed once. `pkce_verifier_key_scheme` records which
derivation produced a row so a later scheme can be added without guessing at
old rows, and that is the whole of the versioning story.

## Never logged

`decrypt_verifier` returns the value. Every caller in this repository passes it
straight to the token exchange and holds it in a local. No result dict in this
module carries it, and `verifier_encryption_invariant_failures` refuses any that
does.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

SCHEMA_VERSION = "nf_pkce_verifier_encryption_v1"

#: Recorded on the row. `none` means a row written before 0036, or one written
#: with no signing key available.
SCHEME_NONE = "none"
SCHEME_FERNET_HKDF = "fernet_hkdf_sha256_v1"

KEY_SCHEMES: frozenset[str] = frozenset({SCHEME_NONE, SCHEME_FERNET_HKDF})

#: HKDF info label. Distinct from session signing so the derived key cannot be
#: interchanged with the one that signs cookies.
HKDF_INFO = b"nativeforge/pkce-verifier-encryption/v1"

SIGNING_KEY_ENV = "NF_SESSION_SIGNING_KEY"

#: Field names that would mean a verifier or a key had entered a result.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "code_verifier",
        "pkce_verifier",
        "verifier",
        "signing_key",
        "derived_key",
        "plaintext",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _signing_key() -> str:
    from nativeforge.lib.settings import auth_environment_overlay

    return (auth_environment_overlay().get(SIGNING_KEY_ENV) or "").strip()


def _hkdf_sha256(secret: bytes, *, info: bytes, length: int = 32) -> bytes:
    """HKDF-Expand over an extracted PRK. Salt is empty by RFC 5869 default."""
    prk = hmac.new(b"\x00" * 32, secret, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def encryption_available(signing_key: str | None = None) -> bool:
    """Can a verifier be encrypted here? Measured, not assumed."""
    key = signing_key if signing_key is not None else _signing_key()
    if not str(key or "").strip():
        return False
    try:
        import cryptography.fernet  # noqa: F401
    except ImportError:
        return False
    return True


def _fernet(signing_key: str | None = None):
    from cryptography.fernet import Fernet

    key = signing_key if signing_key is not None else _signing_key()
    if not str(key or "").strip():
        raise ValueError("no signing key")
    derived = _hkdf_sha256(str(key).encode("utf-8"), info=HKDF_INFO)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_verifier(
    verifier: Any,
    *,
    signing_key: str | None = None,
) -> dict[str, Any]:
    """Encrypt a verifier for storage. The value is never in the result."""
    raw = str(verifier or "")
    blocked_reasons: list[str] = []

    if not raw.strip():
        blocked_reasons.append("no_verifier_supplied")
    if not encryption_available(signing_key):
        blocked_reasons.append("no_signing_key_so_verifier_cannot_be_encrypted")

    ciphertext = ""
    scheme = SCHEME_NONE
    if not blocked_reasons:
        try:
            ciphertext = _fernet(signing_key).encrypt(raw.encode("utf-8")).decode()
            scheme = SCHEME_FERNET_HKDF
        except Exception:
            blocked_reasons.append("verifier_encryption_failed")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "encrypted": bool(ciphertext),
            "ciphertext": ciphertext,
            "key_scheme": scheme,
            # The integrity check the repository already stores. A decrypted
            # verifier must hash to this or it is not the one issued.
            "verifier_hash": (
                hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else ""
            ),
            "verifier_exposed": False,
            "blocked_reasons": sorted(blocked_reasons),
        }
    )


def decrypt_verifier(
    ciphertext: Any,
    *,
    key_scheme: str = SCHEME_FERNET_HKDF,
    expected_hash: str = "",
    signing_key: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Recover a verifier. Returns (verifier, report); the report never holds it.

    `expected_hash` is checked when supplied. A ciphertext that decrypts to
    something other than the value issued is a tampered or mis-keyed row, and
    presenting it to the provider would leak a failed-exchange signal for a
    verifier nobody issued.
    """
    blob = str(ciphertext or "").strip()
    scheme = str(key_scheme or SCHEME_NONE).strip()
    blocked_reasons: list[str] = []

    if not blob:
        blocked_reasons.append("no_ciphertext_stored")
    if scheme not in KEY_SCHEMES:
        blocked_reasons.append("unrecognised_key_scheme")
    elif scheme == SCHEME_NONE and blob:
        blocked_reasons.append("ciphertext_present_under_scheme_none")
    if blob and scheme == SCHEME_FERNET_HKDF and not encryption_available(signing_key):
        blocked_reasons.append("no_signing_key_so_verifier_cannot_be_decrypted")

    verifier = ""
    if not blocked_reasons:
        try:
            verifier = _fernet(signing_key).decrypt(blob.encode()).decode("utf-8")
        except Exception:
            blocked_reasons.append("verifier_decryption_failed")

    hash_matches = False
    if verifier and expected_hash:
        actual = hashlib.sha256(verifier.encode("utf-8")).hexdigest()
        hash_matches = hmac.compare_digest(actual, str(expected_hash))
        if not hash_matches:
            blocked_reasons.append("decrypted_verifier_does_not_match_stored_hash")
            verifier = ""
    elif verifier and not expected_hash:
        blocked_reasons.append("no_expected_hash_supplied_so_integrity_unchecked")

    report = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "decrypted": bool(verifier),
            "key_scheme": scheme,
            "hash_checked": bool(expected_hash),
            "hash_matches": hash_matches,
            "verifier_exposed": False,
            "blocked_reasons": sorted(blocked_reasons),
        }
    )
    return verifier, report


def verifier_encryption_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    for field in FORBIDDEN_VALUE_FIELDS:
        if field in result:
            fails.append(f"value_field_present:{field}")

    if result.get("verifier_exposed") is True:
        fails.append("verifier_exposed")

    # Encrypted without a scheme, or a scheme without ciphertext, would each
    # mean the row cannot be read back by the rules it claims to follow.
    if result.get("encrypted") and result.get("key_scheme") == SCHEME_NONE:
        fails.append("encrypted_under_scheme_none")
    if result.get("key_scheme") not in KEY_SCHEMES:
        fails.append("unrecognised_key_scheme")

    # A decrypt that succeeded without checking the hash is an unverified
    # verifier, which is the thing the hash column exists to prevent.
    if result.get("decrypted") and result.get("hash_checked") is False:
        fails.append("decrypted_without_an_integrity_check")

    return fails
