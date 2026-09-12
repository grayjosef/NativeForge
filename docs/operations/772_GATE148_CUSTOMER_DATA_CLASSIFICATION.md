# 772 — Gate 148: what counts as customer data

## Nine classes

```text
demo_fixture                         not customer data
synthetic_test                       not customer data
operator_runtime_input               not customer data
customer_identifying_data            customer data
customer_operational_data            customer data
customer_document_body               customer data, plus object storage
customer_contact_or_recipient        customer data, plus email delivery
provider_identity_secret_or_subject  never stored, with or without consent
unknown                              blocked
```

## `unknown` is blocked, and that is the important one

A data class nobody has classified is refused. It does not inherit permission
from a neighbouring class, and it is not quietly treated as operator input.
Adding a new kind of customer data is therefore a decision somebody makes rather
than an omission that defaults open.

This is why `classify()` with nothing supplied returns `unknown` and not
something benign: the safe answer to "what is this?" is "I don't know, so no".

## What is not customer data

```text
demo_fixture     a fixture row, labelled as one AND forced by the route
synthetic_test   data a hermetic test invented; it refers to nobody
operator_runtime_input
                 a cadence, a role, a period key, a source id
```

The non-examples matter more than the examples, because that is where a
misclassification happens:

```text
a row a Tribe supplied that somebody labelled demo_fixture
    is not a fixture. The label is forced by the route, not accepted from a
    caller, and a declared `demo_fixture` is only honoured when the row's own
    fact_status or is_demo agrees.

a real organization id used in a test
    is the real organization, whatever the test calls it.

an address an operator typed
    is contact data whoever typed it.

a Tribe name an operator typed
    is identifying data.
```

## The derived half is not the value

```text
recipient_fingerprint    safe    not a recipient
recipient_domain         safe    not an address
email_digest             safe
organization_id          safe    an id is not a name

recipient_email          contact data
contact_address          contact data
```

Gate 142 built the delivery table around exactly this distinction — the table
has a fingerprint and a domain half and no column for an address, so a dry run
cannot quietly become a send. The classifier preserves it.

## A bug worth recording: word boundaries do not exist at underscores

The first version matched field names with `\b(email|address|recipient|...)\b`.
In `recipient_email` there is no word boundary before `email`, because `_` is a
word character. So the pattern matched **nothing at all** on every
underscore-separated field name in this codebase — which is all of them.

Every hint silently failed to fire, and every field came back `unknown`. Because
`unknown` is blocked, the guard was still *safe* — it refused everything — but
it was refusing for the wrong reason and would have refused a fixture write too
had the fixture path depended on field matching.

The fix is tokenisation: the field name is split on non-alphanumerics and
matched against token sets. A token match is exact, which also avoids the
substring problem this campaign has hit repeatedly — `subject` matches
`provider_subject` and not `subject_line`, and `subject_line` is listed as a
known-safe name besides.

## Two classes need a capability as well as consent

```text
customer_document_body         also needs object_store_configured
customer_contact_or_recipient  also needs email_delivery
```

Neither substitutes for the other. Consent with the capability off is refused,
and the capability on with no consent is refused.

## One class is never stored

```text
provider_identity_secret_or_subject
```

A provider subject, token, cookie, state, PKCE verifier or secret is not a data
class anybody can be asked to agree to. It is refused with every approval
granted, and the refusal never clears.

## Next

`773` on consent and the beta scope, `774` on the write guard, `775` on the
delta.
