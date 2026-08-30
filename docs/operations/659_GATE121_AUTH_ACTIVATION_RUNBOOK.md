# 659 — Gate 121D: the auth activation runbook

`src/nativeforge/services/customer_auth_activation_runbook_service.py`

## Generated, not written

A checklist in a document goes stale the moment a gate moves, and nobody
notices, because a document cannot fail a test. Every item here carries a
`status` derived from a live measurement — the environment preflight, the
provider readiness, and the activation gate — so an item that says `done` says
it because something checked.

Twenty-eight items across nine sections:

```text
environment_variables   4    provider keys, secret, signing key, public origin
provider_console        3    application, redirect URI, JWKS
database                2    migrate to 0030, re-run the RLS proof
security                2    replace the dev header, cookie policy
callback_smoke          3    session, org binding, invite binding
role_mapping            2    define in the provider, map explicitly
verified_binding        2    a verifier identity, the first binding
rollback                4    withdraw, rotate, revoke, deregister
do_not_do               6    prohibitions
```

Sixteen block activation. None is `done`.

## Verification commands never print a value

```text
allowed     test -n "${OIDC_CLIENT_SECRET:-}" && echo present || echo missing
forbidden   echo "$OIDC_CLIENT_SECRET"
```

An operator copies these out of a JSON file, runs them, and pastes the output
into a ticket. A command that echoes a variable turns a checklist into a leak
with a two-step delay.

`command_is_secret_safe` refuses six shapes: `echo $`, `printf` with `%s "$`,
bare `env`, `printenv`, `set -x`, and `cat` of a dotfile. A test feeds it all
six and asserts each is refused, then feeds it two safe commands and asserts
both pass — a scanner that cannot fire proves nothing about what it passed.

Commands that could produce long output write to `/tmp` and print only the tail
and the path.

### The scanner caught one of my own commands

The first `env.provider` item used a shell loop with
`printf "%s %s\n" "$k" "$s"`. Both variables hold a *key name* and the word
`set` or `missing` — no value could ever be printed — and the scanner refused it
anyway, because a scanner cannot tell a name from a value.

The fix was not to loosen the rule. The item now asks the preflight instead:

```text
uv run python -c "... print(b()['provider_env_missing_keys'])"
```

which returns key names and is already tested for exactly that guarantee.

## blocks_activation is not the same as risk

```text
blocks_activation   auth cannot go live until this is done
risk                what goes wrong if it is done badly
```

The four rollback items block nothing and carry the highest risk in the list.
They are what an operator needs *after* something has gone wrong, and an item
that only appeared once activation had failed would appear too late to have been
read.

```text
rollback.unset_approval        withdraw the owner's signature
rollback.rotate_signing_key    a signed session cannot be revoked before it
                               expires; rotating invalidates every outstanding
                               session at once
rollback.revoke_bindings       revoke, never delete - Gate 120's revoke is an
                               UPDATE and the history stays
rollback.provider_redirect     remove the redirect URI provider-side
```

## The six prohibitions

Phrased as prohibitions rather than warnings because a warning invites a
judgement call and these are not judgement calls. Each names a specific shortcut
somebody under time pressure would otherwise take:

```text
never.dev_header               do not leave X-NF-Org-Id enabled alongside live
                               customer auth
never.tenant_id_anchor         do not use tenant_id as an RLS authority
never.customer_org_id_anchor   do not use customer_org_id as an RLS authority
never.profile_id_anchor        do not use organization_profile_id as an
                               organization_id
never.fake_binding             do not insert a verified binding without a real
                               verifier identity
never.fake_session             do not sign a production session with the
                               committed fixture key
```

Every one of them is something the code already refuses. They are in the runbook
because a person with database access can do all six by hand.

## What it changes

Nothing.

```text
activation_performed   false
environment_mutated    false
provider_contacted     false
customer_auth_live     false
```

The runbook is deterministic: two builds produce byte-identical output, which is
what lets a committed artifact be compared against a fresh generation and fail
when it goes stale.
