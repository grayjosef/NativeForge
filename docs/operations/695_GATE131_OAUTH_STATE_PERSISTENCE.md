# 695 — Gate 131: OAuth state persistence

## The blocker that made this a schema gate

Migration 0030 stored the PKCE verifier as `pkce_verifier_hash`. For a table
that only ever *validated* a returned state that was right — a digest proves a
value was the one issued without keeping the value.

It is fatal for a table that must also *complete* an exchange. PKCE works by the
client presenting the **raw** `code_verifier` to the token endpoint, where the
provider hashes it and compares against the `code_challenge` it already holds.
SHA-256 does not reverse, so the verifier was unrecoverable and token exchange
was impossible — not by policy, by schema.

```text
code_challenge          public; it travels in the authorization URL
pkce_verifier_hash      proves a match, useless for exchange
raw code_verifier       generated at /login, lost on return
```

## Migration 0036

Two columns on `nf_auth_redirect_states`:

```text
pkce_verifier_encrypted    Text, nullable
pkce_verifier_key_scheme   Text, not null, default 'none'
```

Nullable deliberately. A row written before 0036 has no ciphertext, and a
verifier that cannot be recovered must fail the *exchange* rather than block the
*migration*. There is no NOT NULL and no CHECK requiring ciphertext: either
would make 0036 un-appliable to a database holding 0030-era rows.

The scheme CHECK is PostgreSQL-only, for the reason migration 0025 recorded —
SQLite cannot ALTER a constraint in, and `batch_alter_table` would rebuild the
table by copy-and-move, dropping the partial unique index 0030 created and
silently weakening replay detection. The Core table restates it, so a test that
builds the table from Python still enforces it.

Rows affected by 0036: zero. Nothing but a demo fixture had ever written to this
table.

## Encrypted, not raw

The verifier is a bearer secret for the length of one redirect: whoever holds it
and an intercepted code can complete the exchange. Plaintext would make a
database read sufficient.

```text
cipher        Fernet (AES-128-CBC + HMAC-SHA256)
key           HKDF-SHA256 over NF_SESSION_SIGNING_KEY
info label    nativeforge/pkce-verifier-encryption/v1
```

The info label makes the derived key distinct from the one that signs sessions —
two purposes, two keys, one secret. The key never enters the database, so a dump
of this table alone yields nothing.

`pkce_verifier_hash` stays NOT NULL and becomes an integrity check: the
decrypted verifier must hash to it, or the row is refused rather than presented
to the provider.

What this does not defend against: an attacker holding both the row and
`NF_SESSION_SIGNING_KEY`. Nothing at this layer can, and the verifier is useful
for ten minutes against a code the attacker must also hold.

## What the store guarantees

Measured against a real migrated database, not asserted:

```text
raw state in the row          no - sha256 digest
raw verifier in the row       no - ciphertext plus digest
one-time use                  yes - consumed in the same call that finds it
expiry                        yes - refused past expires_at
replay                        yes - detected, recorded, and refused
unknown state                 refused by name
```

There is no window in which a caller holds a valid unconsumed match: the row is
marked `consumed_at` in the same call, and a second presentation sets
`replay_detected`.

## The two services with similar names

```text
customer_auth_redirect_state_store_service        the contract. Scopes:
                                                  contract_only (stores
                                                  nothing), in_memory_test.
customer_auth_redirect_state_repository_service   the repository. Real inserts,
                                                  hashes, expiry, replay.
```

`/login` called the first with `storage_scope="contract_only"` and therefore
kept nothing. It calls the repository with `storage_scope="database"` now.

One defect found and left named rather than fixed here: the *contract* service
accepts `database` as a valid scope, implements no branch for it, and returns
`stored: False` with **no blocked reason**. A silent no-op for the one scope
that matters. It is not on the login path any more, but a future caller asking
that service for durable storage would get silence.

## The verifier leaves the repository exactly once

`consume_redirect_state(return_verifier=True)` is the only way out, it is off by
default, and the result carries `verifier_returned_by_request`. The invariant
checker permits a `code_verifier` key **only** under that flag.

Guarded rather than removed from the forbidden list. Gate 126 settled this: an
invariant that fires on its own permitted branch gets ignored, and an ignored
invariant reads as coverage. A verifier appearing without the flag is still a
leak and still fires.
