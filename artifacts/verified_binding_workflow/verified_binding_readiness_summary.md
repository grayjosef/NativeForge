# Verified binding workflow readiness (Gate 120)

## The sentence to refuse

> "The binding repository exists, so tenants can be bound."

A repository is somewhere to put a verified binding. A verified binding
names the identity that verified it, and `verified_by_identity_id`
references `nf_identities` — a verified OIDC subject. No OIDC subject
can be verified while 11 of 16 activation gates are
unsatisfied, so no verifier identity exists to name.

A production verified binding is not merely unauthorized today. It is
unconstructible.

## What moved

```text
binding repository            none          six operations, DB-backed
verified binding workflow     none          authorization -> contract
                                            -> repository, in that order
write_allowed                 unconsumed    acted on
identity_binding lane repo    false         true
identity_binding write path   false         true
revocation                    a dict        an UPDATE that keeps the row
```

## What did not move

```text
verified_operational_binding                false
customer_auth_live                          false
login_live                                  false
customer_persistence_live                   false
beta_onboarding_ready                       false
production_rollout_ready                    false
source_monitoring_live                      false
source_coverage_claimed                     false
production_verified_bindings_created        0
real_customer_rows_written                  0
rows_in_the_application_database            0
```

## The unsatisfied gates

```text
provider_configured
secret_present
issuer_configured
issuer_jwks_validated
audience_configured
callback_session_validated
invite_binding_passed
org_binding_passed
role_mapping_passed
dev_header_disabled_for_production
session_signing_key_ready
```

## The fixture set

```text
cases                          8
authorized                     7
repository writes performed    4
operational bindings produced  0
production verified bindings   0
real customer rows written     0
```

Four of eight cases write a row. Every one of those rows is a demo
fixture in an in-memory database that is discarded when the case
ends, and none of them is an operational binding.

## Why no API route

```text
1  a read route needs a session to scope by, and /current-user
   401s for everybody, so the permitted branch is unreachable
2  the table is empty, so the route's only behaviour is refusal
3  a route is a surface, and the first thing to exercise it would
   be a real browser with a real cookie
```

Recorded in doc 652 as a decision rather than left as an omission.

## What the next gate needs

```text
1. customer auth activation   11 of 16 gates. Everything below
                              waits on this and nothing else does.

2. a verifier identity        an nf_identities row from a verified
                              OIDC subject

3. a database with 0029       store_writable is false: the
                              migration is defined and no runtime
                              database has applied it

4. the remaining six lanes    each needs a repository of its own
```
