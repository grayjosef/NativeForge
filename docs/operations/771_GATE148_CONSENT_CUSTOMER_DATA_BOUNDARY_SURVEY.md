# 771 — Gate 148: the consent and customer data boundary, surveyed

Read-only. No consent was created, no customer data written, no organization
touched.

## The finding that makes this gate necessary

Every post-award repository derives a production write and gates it on exactly
two things:

```python
demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
production_write = not demo_fixture

if production_write and not customer_auth_live:
    blocked_reasons.append("production_..._write_requires_live_customer_auth")
if production_write and not verified_operational_binding:
    blocked_reasons.append("production_..._write_requires_a_verified_operational_binding")
```

Two checks. Both are identity facts. **Neither is consent.**

`customer_auth_live` says somebody can sign in. `verified_operational_binding`
says somebody verified an organization is who it claims to be. Gates 146 and 147
are working to make both true. The moment they are, a production customer write
becomes permitted — and nothing anywhere in this repository records that the
tenant asked for any of it.

That is the gap Gate 142 named and deliberately did not fill, stated precisely:
the boundary is not missing a check somewhere, it is missing an entire concept,
and the two checks that exist will stop guarding the door the moment the
campaign succeeds at its current objective.

## Is there a consent boundary today?

No.

```text
consent table in any migration          none
consent service                         none
consent artifact                        none
consent field on any customer table     none
```

The word appears in this repository only in planning packets and in Gate 146's
artifact, which names its absence.

## Is there a customer beta scope approval?

No. Gate 145 lists `customer_beta_scope_approved` as one of four approvals the
controlled customer beta needs, and it is absent in the same way — named as
required, recorded nowhere.

## Can real customer data be distinguished from fixture data?

Mechanically, yes — and the vocabulary already exists:

```text
fact_status     demo_fixture | tenant_supplied | verified | unknown
is_demo         boolean
production_write = not demo_fixture
```

`tenant_supplied` is the system's existing name for data a Tribe supplied. It is
permitted by the database CHECK constraints on every post-award table:

```text
fact_status IN ('verified', 'tenant_supplied', 'demo_fixture', ...)
```

So the schema is already open to real customer data. What keeps it out today is
not the schema.

## Which write paths accept fixture data only?

The four post-award routes, and they are safe for a reason worth stating: the
label is **forced, not accepted**.

```text
is_demo      True          forced
fact_status  demo_fixture  forced
```

`CALLER_MAY_NOT_SET` refuses `is_demo`, `fact_status`, `organization_id`,
`tenant_id`, `customer_org_id`, `organization_profile_id`, `customer_auth_live`,
`verified_operational_binding` and `object_store_configured` by name. A caller
supplying any of them gets a named refusal rather than an override — the rule
Gate 137 arrived at after a verified binding was written onto the demo
organization because the caller said it was not one.

## Which write paths would be dangerous with real customer data?

Not the routes as they stand. The danger is one layer down and one gate ahead:
any *future* write path that sets `fact_status='tenant_supplied'` reaches a
repository whose only production gate is the two identity checks above.

```text
today        no path writes tenant_supplied, so the gap is unreachable
after 146    customer_auth_live true - one of the two checks passes
after 147    verified_operational_binding true - both pass
then         a production customer write proceeds, consent unrecorded
```

The boundary has to exist before those lanes turn, not after.

## What already protects specific data classes

Three classes are protected by their capability being off, which is a different
thing from being protected by a boundary:

```text
document bodies      object_store_configured false; the metadata path refuses
                     a body with a named reason (Gate 141)
recipients           the delivery table has recipient_fingerprint and
                     recipient_domain and no column for an address, so a
                     dry run cannot quietly become a send (Gate 142)
source data          source_monitoring_live false; no collector runs (Gate 143)
```

Each is real protection. None is consent, and each disappears the moment its
capability is activated.

## Can consent be inferred from login, membership or an invite?

No, and this must be stated rather than assumed, because all three are about to
become available and each one looks like agreement:

```text
a login          says a person authenticated. Not that they agreed to anything.
a membership     says somebody was added to an organization, by an owner, not
                 by themselves.
an accepted      says a person accepted a seat. Gate 146's invite carries a
invite           role and an expiry and no terms.
an operator note says an operator wrote something down.
a verbal yes     is not in the system at all.
```

None of the four is a record that a Tribe was told what would be collected,
retained, exported and deleted, and agreed to it. Treating any of them as
consent would be the substitution this campaign has spent forty gates
preventing, applied to the one subject where it does legal as well as technical
damage.

## What safe pre-consent storage is allowed

```text
allowed     demo_fixture rows in the demo organization, controlled_dev_demo
            synthetic test data in hermetic tests
            operator runtime input that names no customer
            fingerprints and domain halves, never the value

blocked     anything a Tribe supplied
            anything identifying a Tribe, a person, or an award
            document bodies
            contact addresses
            provider subjects and secrets
            anything whose class is unknown
```

## What must remain blocked

```text
controlled_customer_pilot      false
customer_beta_scope_approved   false
consent_boundary_documented    false
real customer data writes      refused
the real organization          untouched
```

## Exact human approvals and actions required

```text
1  decide what NativeForge collects, retains, exports and deletes
     a document, not a code change. Nothing can be built correctly before
     this exists, which is why Gate 142 declined to build it.

2  decide how a Tribe records agreement to that
     and what it looks like when they withdraw it

3  Mayhem approves the controlled customer beta scope
     Gate 145's fourth approval

4  then, and only then, a consent record per organization
```

Steps 1 and 2 are not engineering. Gate 148 builds the boundary that will
enforce them and reports their absence honestly; it does not invent what they
should say.

## What Gate 148 builds

A data classification service, a consent and beta-scope boundary service, a
write guard that future paths must consult, routes, a verifier, artifacts and
docs. It activates nothing, creates no consent, and writes no customer data.

The guard's most important property is that it is **deny-by-default on an
unknown class**: a data class nobody has classified is refused, so adding a new
kind of customer data cannot silently inherit permission.
