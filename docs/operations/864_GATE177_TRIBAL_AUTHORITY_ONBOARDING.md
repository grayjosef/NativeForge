# 864 — Gate 177: Tribal authority, onboarding and tenant administration

## The principle

```text
IDENTITY VERIFIED     we know who this person is
AFFILIATION VERIFIED  we know they belong to this organisation
AUTHORITY VERIFIED    we know they may ACT for it
```

Three questions. Never one boolean.

## What the survey found

```text
nf_authority_proof_records   COLLAPSED
    governs_authority_through_['state']_naming_only_2_of_3
nf_membership_invites        COLLAPSED
    governs_authority_through_['approval_state']_naming_only_2_of_3
```

One `state` column decided whether somebody could act for a Tribal
government, so "verified" could not say verified *as what*.

It also found three things worth stating plainly:

| Measurement | Value |
| --- | --- |
| Real organisation active members | **0** |
| Real organisation authority records | **0** |
| `controlling_company` phrase anywhere in the package | **absent** |
| Distinct roles in use | **1** (`org_owner`) |

So adversarial case 11 — "organisation has no authorised administrator" — is
not a scenario in this gate. It is the current state of the real tenant.

## Why collapsing the three is not a modelling preference

A person with a working `@tribe.gov` mailbox has proven control of a mailbox.
That is identity evidence, and possibly affiliation evidence. It says nothing
about whether the Council has authorised them to establish a tenant, invite
staff, and represent a sovereign government to federal funders.

A system that treats the three as one boolean will let a summer intern speak
for a nation. It will do so silently, because from the inside that looks
exactly like success.

## What was built

| Concern | Module |
| --- | --- |
| Three independent states, scope, revocation | `tribal_authority_model_service.py` |
| Typed evidence, decisions, manual verification | `tribal_authority_evidence_service.py` |
| Roles, the boundary, tenancy, invitations | `tenant_administration_service.py` |
| Versioned profile, the phrase rule | `organization_profile_service.py` |
| Branding, org defaults, personal overrides | `organization_customization_service.py` |
| 15 adversarial cases | `tribal_authority_gold_corpus_service.py` |
| 9 named detectors and their proofs | `tribal_authority_self_health_service.py` |
| Durable state and its CHECKs | `alembic/versions/0063_*.py` |

## The load-bearing properties

### Authority may not outrank its foundations

`may_administer_tenant` asks three questions independently and returns three
sub-answers, so a refusal names *which* dimension failed. Migration 0063 makes
the inconsistency unrepresentable:

```text
ck_..._authority_may_not_outrank_affiliation
ck_..._authority_may_not_outrank_identity
ck_..._verified_authority_is_signed
```

A sufficient authority resting on `SELF_ASSERTED` affiliation cannot be
stored by any writer, however careless.

### No single evidence type is sufficient for all Tribes

574 federally recognised Tribes, plus state-recognised Tribes and Native
non-profits, do not share one governance structure. Demanding a council
resolution would exclude organisations that never issue one. Accepting a
matching email domain would accept anyone who can register a lookalike.

So evidence is typed, plural and extensible, and each type states which
dimension it can speak to. `ORGANIZATION_EMAIL_DOMAIN` and
`OFFICIAL_TRIBAL_WEBSITE` are absent from `ESTABLISHES_AUTHORITY` in the model
and refused by CHECK in the schema.

Evidence records a **reference** — never the artifact's bytes, never a
credential. A field or value that looks like a secret is refused.

### The controlling-company boundary is a different ladder

`CONTROLLING_COMPANY_ADMIN` is not the top of the customer role ladder.
`ASSIGNABLE_BY` never lists a customer role as able to confer it, so there is
no sequence of legitimate actions that reaches it. Three separate routes were
tested and all refused: the action, an invitation, and the function itself.

Tenancy is checked **before** privilege, so a genuine administrator of one
Tribe is refused at another before their role is even consulted.

### An unauthorised invitation never exists

Refused at issue, not filtered at acceptance. A pending invitation is a claim
about who NativeForge thinks may speak for a Tribe, and it should not be
possible to create one without the standing to do so.

### Revocation removes authority and nothing else

Not the organisation, not the historical work, not the audit trail, and not
ordinary membership unless that is asked for separately. A council member who
loses signing authority is still a member of the Tribe.

### The phrase rule

Organisations describe themselves in their own words. Four outcomes stay
distinct:

| Outcome | Classes | Asks for review |
| --- | --- | --- |
| `RECOGNIZED` | one or more | no |
| `AMBIGUOUS` | none asserted, candidates kept | yes |
| `LOOKUP_MISS` | none | **yes** |
| `EXPLICITLY_EMPTY` | none | no |

A Tribe writing "language revitalization" must never be treated as though
they left the field blank. `LOOKUP_MISS` and `EXPLICITLY_EMPTY` both yield
zero classes and are still distinguishable — only one sends somebody to look.

### A personal override never moves the org default

The failure here is quiet and expensive: somebody reorders their own tiles and
the whole organisation's layout changes. `apply_personal_override` deep-copies
before merging and **returns proof** that the default is byte-identical
afterwards, because "we do not mutate" is exactly the kind of claim that
quietly stops being true.

The override table has no branding columns at all. One person's taste has
nowhere to become the Tribe's identity.

There is no free-form CSS or script field. "Let the customer theme it" plus a
text box is how a dashboard becomes a place to run somebody else's JavaScript.

## What the instruments found

**The revocation detector asked the function it was checking.** It called
`may_administer_tenant` and then re-read `revoked_at` — the very field that
function already applies at read time. The two could never disagree, so the
detector could never fire. It now compares the **revocation log** against the
grant row, which catches the partial write: the log says revoked, the row was
never updated, and a removed administrator keeps administering.

**A fixture broke two things at once.** The cross-tenant fixture initially
orphaned its evidence as a side effect, firing two detectors. Narrowed.

**The proof phase assumed the database was at head.** It is at 0061 — neither
0062 nor 0063 has been applied locally. The fix was to *measure* the drift and
report it, not to have the phase run `alembic upgrade`. A verifier that
changes the thing it is measuring is not a verifier.

## Scale and constraints

Migration 0063 round-trips clean with prior data preserved. Seventeen refusals
are rejected by the database itself, and each constraint is proven able to say
**yes** as well as no — an honest unverified grant, a resolution carrying
authority, controlling-company conferring its own role. A constraint that only
ever refuses proves as little as one that only ever accepts.

## What this gate does NOT claim

- **No real Tribe has been onboarded.** No authority has been verified for a
  real organisation.
- **The corpus is not the world.** Fifteen cases we thought of.
- **Recognition or status information is not authority verification**, and
  nothing here verifies Tribal authority automatically.
- **No email was sent, no invitation delivered, no network call made.**

## Running it

```bash
bash scripts/verify_nativeforge_tribal_onboarding_gate177.sh
```

The line that matters is asserted **false**:

```text
real_organization_has_an_authorized_admin=false
```

If it ever flips, somebody has been granted authority over a real Tribal
government's tenant — and that must be a decision a human made deliberately.
