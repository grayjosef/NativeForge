# 572 — Gate 103B/E: tenant beta profile contract

`src/nativeforge/services/tenant_beta_profile_service.py`
`src/nativeforge/services/tenant_beta_demo_fixture_service.py`

A beta Tribe/tenant profile, built without fabricating tenant facts.

## Every fact carries how it is known

```text
verified            checked against an authoritative source
tenant_supplied     the tenant told us
demo_fixture        invented for a demo, and labelled as such
unknown             nobody has established it
needs_human_review  established but disputed, or too consequential to assume
```

A profile field is never a bare value — it is a value **and** a status. A service
area the tenant told us and a service area invented for a screenshot carry
completely different weight, and the difference disappears the moment they are
stored the same way.

Absent input is `unknown`, never a plausible default. A value supplied with no
provenance becomes `needs_human_review` rather than being quietly trusted. A
value outside its vocabulary becomes `needs_human_review` rather than being
coerced to a neighbour — somebody wrote something this model cannot read, and
guessing which valid value they meant is how "probably federal" becomes
"federally recognized".

The overall `profile_fact_status` is the **weakest** tracked fact, so a profile
with one verified field and five unknown ones reports `unknown`.

## Four inferences this service refuses to make

```text
recognition_status_from_name_or_state
federal_eligibility_from_state_recognition
operating_state_from_mailing_address
applicant_class_from_tenant_kind
```

They are recorded on every profile as `inference_prohibited`, and an invariant
fails any profile where one has been dropped from the record — a refusal that
stops being visible stops being a refusal.

**Recognition is never inferred.** Not from the tenant's name, not from its
state. Federal recognition, state recognition, historic affiliation and
unrecognised are legally distinct, and a wrong guess reaches a real government's
eligibility. A `verified` recognition status without a named source is downgraded
to `needs_human_review`.

**Federal eligibility is never inferred from state recognition.** South Carolina
recognising a Tribe says nothing about federal programme eligibility, and the
inverse is equally false.

**Operating state is not mailing address.** A tenant may operate, serve and be
eligible in a state it is not headquartered in. Supplying a mailing state without
operating states is flagged, not used.

## SC priority is tenant-specific

`sc_priority` is derived from the tenant's own `operating_states`. A tenant that
does not operate in South Carolina does not get SC prioritisation, and an
invariant fails any profile claiming it without SC in its states.

South Carolina is the beta's immediate priority because *these four tenants*
operate there — it is not a property of NativeForge.

## A profile is not coverage

```text
source_monitoring_live   false
live_source_coverage     false
collectors_active        0
eligibility_determined   false
```

A tenant with a fully configured watchlist and no collectors is exactly the state
this repository is in, and the profile says so.

## The four demo tenants

Generic identities: `nf-demo-tenant-01` … `-04`, "Demo Tenant One" … "Four".

**No real Tribe is named.** Not Catawba, not any state-recognised entity in the
SC registry rows, not a lightly-disguised variant. `REAL_TRIBE_NAME_TOKENS` lists
seventeen tokens that must never appear, an invariant scans every generated name
and service area for them, and a test scans the committed artifact.

Putting a real government's name on a fabricated eligibility profile is a harm to
that government whatever the disclaimer says.

```text
facts verified       0
facts demo_fixture  10
facts unknown       14
```

Recognition status, applicant classes and service area are `unknown` for **every**
demo tenant, deliberately. The demo profiles are incomplete and the incompleteness
is the point: a demo showing `recognition_status: unknown` is showing how the
product behaves when it does not know, which is most of the time.

Two tenants operate in SC, one in NC, one has no state — so the demo can show SC
prioritisation working *and* show a tenant that does not get it.

`build_supplied_tenant_profile` is a separate function from
`build_demo_tenant_profile`, so nobody reaches the fabricating path by passing a
flag.
