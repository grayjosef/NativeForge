# 768 — Gate 147: the demo organization is not production proof

## The refusal

```text
demo_organization_is_never_a_verified_operational_binding
```

In any environment. With any approval. With any principal. With the
organization listed in the injectable authorized set. This is the one refusal in
the whole boundary whose owner is **nobody**, because nothing clears it.

## Why it is categorical rather than conditional

A verified operational binding is a row asserting that a named person verified
that a named organization is who it claims to be. The demo organization is a
fixture. There is no Tribe behind it to verify, so a row saying somebody
verified it would be false in the only way that matters — it would look exactly
like a true one.

Making the refusal conditional would mean there exists some approval under which
a fixture can be certified as a real customer. There is no such approval, so
there is no such condition.

## It is derived, not declared

```text
organizations.org_type   ->  'demo'
```

Read from the database. A caller passing `is_demo=False` or `org_type='real'`
does not change the answer, and the refused keys are reported by name rather
than silently dropped:

```text
offered_classification_keys_refused   ['is_demo', 'org_type']
offered_authority_keys_refused        ['customer_org_id',
                                       'organization_profile_id',
                                       'profile_id', 'tenant_id']
```

Gates 110–113 spent four gates on exactly this substitution: a label offered as
authority, accepted, and then indistinguishable from a fact. The refusal is
restated at every new entry point because each one is a fresh chance to make the
same mistake.

## The one existing row, and why it proves nothing

```text
organization      the demo org
binding_status    demo_fixture
is_demo           1
verifier          none
active            yes
```

`demo_fixture` is not in `VERIFIER_REQUIRED_STATUSES`, so the row asserts no
verification at all. That is exactly what a fixture should be, and reading it as
evidence of a verified binding is listed among the refused shortcuts.

The distinction matters because the row *is* active and *is* a binding. A reader
counting active bindings finds one. A reader asking whether anything has been
verified finds nothing, and the two questions have different answers on purpose.

## What a demo proves and what it does not

```text
proves        the code path works
              the refusals fire
              the repository writes and reads correctly
              a route enforces an organization context

does not      that any real organization has been verified
prove         that anyone is authorized to verify one
              that a customer exists
              that production is ready
```

Gate 137 proved the first column against fixtures, which is the right way to
prove it. Gate 147 exists so nobody reads the first column as the second.

## The fifth conflation, at a new subject

Gate 145 named it:

```text
the demo organization   is not   a customer organization
```

Gate 146 applied it to identity — a demo org membership is not a customer
signing in. Gate 147 applies it to binding: a demo org fixture is not a verified
operational binding, and no amount of approval makes it one.

## What this means for a customer conversation

```text
say      "this is a controlled demonstration in a demo environment"
say      "no organization has been verified, and the binding path refuses
          this one by design"

avoid    "your organization is set up in our system"
avoid    "we have verified your organization"
avoid    "the binding is in place, we just need an approval"
```

The last one is the dangerous one, because it is nearly true and entirely wrong:
the approval is not what is missing. A real customer organization is.
