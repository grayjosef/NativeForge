# 769 — Gate 147: what a real-org binding approval requires

## The real organization is refused twice

```text
organization_is_the_explicitly_refused_real_org
organization_is_not_in_the_authorized_real_org_list
```

`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` is refused by name, **and** absent from
an authorized list that is empty. Either refusal alone would hold. Both are kept
because Mayhem's standing authorization refuses `real org activation` and
refuses binding to that id by name, and a single refusal for two separate
prohibitions would lose one of them.

```text
binding rows for the real organization    0
rows asserting verification anywhere      0
```

## The escape hatch that was the hole

`build_real_org_binding_activation_decision` takes an injectable
`authorized_organization_ids` so the approved branch is reachable in a hermetic
test. Gate 137G's own test found the first version consulting it for **every**
id — so listing `aaaaaaaa-…` in it approved a real-org binding and wrote the row.

An escape hatch that reaches the one organization the module exists to refuse is
not an escape hatch. Both the demo and real ids are now stripped from the
injected set, and Gate 147's checklist strips them again at its own boundary
rather than trusting the layer below. A test smuggles the real org into the set
and asserts it stays refused.

## What an approval object must contain

Five fields, all of them:

```text
organization_id        the organization being authorized
authorized_by          who decided
authorization_scope    real_org_binding_activation | production_binding_activation
environment            where the decision applies
recorded_at            when
```

A partial object is not a weak approval. It is no approval, and the refusal
names it as such.

## Scope does not widen on its own

```text
real_org_binding_activation      local | dev | test
production_binding_activation    production | prod
```

The narrow scope does not reach production. Binding a real organization in dev
is a different decision from binding one in production, which is the distinction
Gate 133D had to introduce for logins after one variable had been gating both.

## No environment variable can grant

```text
can grant    (none)
can revoke   NF_REAL_ORG_BINDING_ACTIVATION_REVOKED
```

One variable exists in this path and it only turns activation off. Authorizing
an organization is a reviewed code change somebody reads — adding an id to
`AUTHORIZED_REAL_ORGANIZATION_IDS` — plus an approval object naming the same
organization. Two independent acts, deliberately.

## The verifier principal

```text
role            platform_admin | tenant_admin
authenticated   true
verified_org    true
```

All three. A role alone is not an authorization to bind a particular Tribe's
organization — the gap Gate 137A found, where the chain decided by role and
nothing checked which organization it was.

And the principal is not something a caller supplies: the dry-run route takes it
from the session context and ignores one in the request body. A caller naming
their own role would be choosing their own authority.

## `customer_auth_live` is required, and is false

```text
production_verified_binding_requires_live_customer_auth
```

A verified binding asserts somebody verified something. Writing one while nobody
can authenticate leaves that assertion sitting in a table with no verifier
behind it — which is what the `ck_nf_binding_verified_needs_verifier` constraint
exists to prevent and what a nullable-in-practice identity id would slip past.

Gate 146 measured `customer_auth_live` false, with the second person never
having signed in.

## No unresolved conflict

```text
more_than_one_active_binding_for_this_organization
active_binding_is_ambiguous
```

Two active rows contradicting each other is a conflict a person resolves, not a
coin toss the reader makes on their behalf — Gate 137D, which replaced a
`.first()` on an unordered query.

## The order, and the step that is further away than it looks

```text
1  a real customer organization has to exist
     there is none in this deployment other than the refused one

2  the second-person event                     Gate 146
     unlocks customer_auth_live

3  Mayhem authorizes that organization
     a reviewed code change

4  an approval object is recorded
     five fields, covering scope

5  a qualified verifier principal acts
```

Step 1 is the honest distance. The campaign has been describing this lane as
needing an owner decision, which made it sound like step 3 or 4 was the front of
the queue. It is not: there is nothing to approve yet.

## What must never be printed along the way

```text
the provider subject       the verifier identity resolves to one
the session cookie
the OAuth state and PKCE verifier
any address
```

Reported instead: counts, booleans, classification, and blocker names. Every
payload in this path is scanned for all four shapes, and the route refuses
rather than emits if one appears.
