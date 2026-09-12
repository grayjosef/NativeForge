# 783 — Gate 150: what is safe to say to a prospective beta customer

Six claims. Each is true as measured today, and none asserts a capability that
is false.

## The six

```text
1  "this is a controlled demonstration in a demo environment"

2  "the awarded-grants workspace, requirements and audit trail work against
    fixture data"

3  "177 grant sources are catalogued; none is being monitored yet"

4  "nothing you see here is sent, monitored, or stored as your data"

5  "a weekly digest can be previewed in the product; it is not sent"

6  "we can show you exactly what would have to be true before your
    organization could use this, and who has to decide each part"
```

## Why each is safe

**1** names the scope. Every route response already carries
`scope: controlled_dev_demo`, so this is the same statement a machine makes.

**2** is the strongest true claim available. Gates 139–141 made these lanes
operational and the verifiers prove it on every run. The qualifier "against
fixture data" is doing real work and must not be dropped.

**3** is precise in both halves. 177 rows load and every one is classified
(Gate 143), and `source_monitoring_live` is false with no collector running.
Saying only the first half would be the unsafe version.

**4** covers the three capabilities that are off — email, monitoring, object
storage — in one sentence a non-technical listener can hold.

**5** is the one that usually gets mangled. A digest **preview** is a rendered
page somebody opens; it is not a delivery and needs no email activation. This
distinction is why email is not a pilot prerequisite.

**6** is what the 146–150 block actually bought, and it is the most useful thing
on this list.

## Why claim 6 matters most

A Tribal government evaluating a grants platform is being asked to trust a
vendor with award compliance. Most vendors in that conversation answer "when can
we start?" with optimism. This one can answer it with a list:

```text
a real customer organization has to exist
a second person from your organization has to sign in
somebody has to authorize binding your organization, and that is a decision
  with five separate refusals in front of it
somebody has to write down what we collect, retain, export and delete, and
  you have to agree to it
Mayhem has to approve the beta scope
somebody has to be named as your support contact and as the person who can
  end the pilot
```

Each with an owner, and each measurable. That is a more credible thing to say
than a date.

## The qualifiers that must not be dropped

```text
"in a demo environment"          on claim 1
"against fixture data"           on claim 2
"none is being monitored yet"    on claim 3
"it is not sent"                 on claim 5
```

Each of these four is the half that makes the claim true. A claim repeated
without its qualifier becomes one of the ten in doc 784.

## What this list is not

It is not marketing copy, and it is not a script. It is the set of statements
that survive contact with the verifiers. Anything outside it needs checking
against the measured state before it is said to a customer.

## Where the list lives

`customer_beta_reassessment_service.SAFE_CLAIMS`, reported by
`GET /v1/nf/demo/orgs/{org}/beta-reassessment/safe-claims`, and committed to
`artifacts/customer_beta_reassessment_gate150/safe_customer_facing_claims.json`.

A test asserts the list contains no phrase from the unsafe inventory and that
the "not sent" and "none is being monitored" qualifiers are present.
