# 865 — Gate 178: commercial entitlements and the persistent licence

## The approved model

This gate encodes a decision. It does not make one.

```text
Persistent organisational licence   $32,999
    includes the first 12 months of maintenance
Annual maintenance thereafter       $4,999 / year
Delinquent                          benefits freeze; NOTHING is deleted
3 continuous years delinquent       the persistent licence expires
Relicensing                         current full price; historical unpaid
                                    maintenance forgiven; history retained
Temporary benefit extensions        7 / 14 / 30 days, controlling company only
```

### On doc 570

`docs/operations/570_...PRICING_REQUIREMENT.md` contains different figures —
$34,999, $24,999, $14,995 and others. That document says of itself:

> "These figures are the operator's drafts, recorded verbatim as drafts"

They are not canonical. The survey asserts none of them is encoded as a
price, and the verifier checks the code against the **approved decision**
rather than against its own constants — a gate asserting "the price is
whatever we wrote" would pass with the wrong price in it.

## Three states, never one

```text
LICENCE STATE      do they own a licence, and is it still alive?
MAINTENANCE STATE  have they paid through today?
BENEFIT ACCESS     can they use the product right now?
```

Collapsing these is tempting because most of the time they agree. They come
apart exactly when it matters:

> A delinquent organisation with a live 14-day extension has a **held
> licence**, a **lapsed term**, and **full benefits** — all at once.

A single `is_active` flag cannot say that. A system with one will either deny
a customer the extension somebody granted them, or quietly forget they owe
money.

## The rule this gate turns on

> **An extension changes BENEFIT ACCESS and nothing else.**

It does not move the paid-through date. It does not reduce the delinquency
count. It does not pause the three-year clock. An organisation on day 400 of
delinquency with a 30-day extension is on day 400 of delinquency, has full
benefits, and is still 695 days from losing its licence.

Getting this wrong in the **generous** direction is worse than getting it
wrong in the harsh direction, because it is invisible. A vendor who quietly
forgives debt by granting extensions finds out at year end; the customer finds
out when somebody finally reconciles and sends them a bill nobody told them
was accruing.

So the extension row **records the delinquency it did not cure**, and
`ck_..._extension_records_its_delinquency` refuses an extension claiming the
customer was current.

## Frozen is not deleted. Expired is not deleted.

Available in **every** state, including years after expiry:

`AUTHENTICATE` · `VIEW_ORGANIZATION_IDENTITY` · `VIEW_ACCOUNT_STATUS` ·
`VIEW_LICENSE_STATUS` · `VIEW_MAINTENANCE_STATUS` · `VIEW_HISTORICAL_METADATA`
· `VIEW_RENEWAL_PATH` · `VIEW_REACTIVATION_PATH` · **`EXPORT_OWN_DATA`**

`EXPORT_OWN_DATA` is on that list deliberately. The difference between "your
workflows are paused" and "we have your data" is the difference between a
vendor and a hostage-taker.

## The three-year boundary

Expiry is **strictly greater** than 1095 days. At exactly three years the
licence is still held. The day count is fixed rather than computed from a
leap-aware calendar, because 178E requires that a licence never expire
because of clock ambiguity, and a calendar-derived count can drift by a day
depending on which years the delinquency spanned.

The schema refuses an expired row at or below the boundary:
`ck_..._expiry_needs_three_years`. Taking a licence away early is the most
expensive arithmetic error this system can make.

## The ledger

Append-only. Relicensing appends three events and removes none:

```text
RELICENSED                money in, at today's price
MAINTENANCE_FORGIVEN      the outstanding amount, NAMED
MAINTENANCE_TERM_STARTED  the twelve months the new licence includes
```

Forgiving a debt is a decision about what is **owed**. It is not a claim that
the debt never existed. A ledger that answered "why is this organisation
active again" by having no record of the delinquency would be answering by
having lost the question. Corrections are events, never edits.

`ledger_invariant_failures` compares by **event id**, not by count: a write
that removed one event and added two would pass a length check while having
destroyed evidence.

## Who may do what

No customer role — including `ORG_SUPER_ADMIN` — may forgive debt, move a
paid-through date, grant an extension, correct the ledger, or relicense
itself. Every customer role may always **see** its own standing; a refusal a
customer cannot even read would be its own failure.

## What the instruments found

**My draft-pricing detector was wrong in two ways at once.** It searched the
source text for `"2,999"`, `"24,999"` and `"34,999"`:

- `"2,999"` is a **substring of `"$32,999"`** — the canonical price set off a
  draft-price alarm.
- `"34,999"` genuinely appears, in the docstring that exists to say that
  figure is a draft we do not use.

A figure named in prose as a thing we are *not* doing is the opposite of a
figure encoded as a price. The detector now parses each module and collects
numeric **literals**: prose cannot produce one, and a literal cannot hide
inside a longer one. Proven falsifiable by planting `3499900` and watching it
fire, then removing it and watching it go silent.

**The zero-row rule caught a scale fixture.** Every "current" organisation in
the synthetic fleet had a maintenance term ending *after* the query cutoff, so
the expiring-maintenance queue returned nothing — and looked beautifully
indexed while proving nothing. That query's entire job is to find terms about
to lapse.

## Scale

5,000 organisations, 30,000 ledger events, 8,000 extensions. All eight read
paths index-backed, slowest **1.22 ms**.

Fleet questions ("which organisations are frozen") read the materialised
summary rather than replaying thousands of histories. That summary is a
cache, and a cache can go stale — which is why
`current_entitlement_disagrees_with_ledger` is one of the nine detectors. The
structure that makes the read fast also makes a new way to be wrong.

That detector compares **two independent sources** — the served entitlement
against a fresh derivation from the ledger — rather than asking the same
function twice and calling the agreement a proof. Gate 177 had to repair
exactly that mistake.

## What this gate does NOT claim

- **No money moved.** No invoice raised, no payment taken, no debt forgiven
  for any real organisation.
- **This is not legal advice.** The exact wording of the agreement remains
  with counsel. This verifies product semantics.
- **The corpus is not the world.** Twenty cases we thought of.

## Running it

```bash
bash scripts/verify_nativeforge_commercial_entitlements_gate178.sh
```
