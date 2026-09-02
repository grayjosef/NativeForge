# 717 — Gate 136: second account invite execution

Not theoretical. Every command below exists and has been run end to end.

```text
organization  bbbbbbbb-cccc-dddd-eeee-ffffffffffff   the demo org, only
login URL     https://nf-dev.mayhem-nc.dev/api/auth/login
provider      Google
environment   dev/demo. NF_APP_ENV=local on this host.
```

---

## Step 0 — add the second account as a Google OAuth test user

**Do this first.** The app is **External / Testing** with one test user. Google
refuses an account that is not on that list *before NativeForge sees the
request*, so the second person gets Google's own "Access blocked" screen and no
NativeForge log line explains it.

```text
console.cloud.google.com
  -> APIs & Services
  -> OAuth consent screen
  -> Audience  (older console: "Test users")
  -> ADD USERS
  -> the second account's Google address
  -> SAVE
```

Nothing in this repository can do this. It is the one step that is not a
command.

Up to 100 test users are allowed, so this does not need the app verified or
published. **Do not publish the app** to get around it — that exposes a dev
consent screen to anybody with the URL, and it is not needed.

---

## Step 1 — the second account signs in once

In a **clean browser profile**, so the owner's Google session is not reused:

```text
Chrome    ⌘/Ctrl+Shift+N          new Incognito window
Firefox   ⌘/Ctrl+Shift+P          new Private window
or        a second Chrome profile entirely
```

Then open:

```text
https://nf-dev.mayhem-nc.dev/api/auth/login
```

Cloudflare Access is in front, so there is an Access challenge before Google.
Complete both.

**Expect: no session.** The callback writes an `nf_identities` row for the
verified subject and stops there — it issues a cookie only when the identity
already resolves to an organization through a membership row, and the second
account has no membership yet. The response will say the organization binding
is missing.

That is correct. It is step 3 that creates the membership. Do not treat this as
a failure and do not retry it differently.

Confirm the identity landed:

```bash
cd /home/josefgray/projects/nativeforge && .venv/bin/python -c "import sqlalchemy as sa,sys; sys.path.insert(0,'src'); from nativeforge.db.session import engine; c=engine.connect(); print('identities:', c.execute(sa.text('SELECT COUNT(*) FROM nf_identities')).scalar_one())"
```

It should read `2`. If it still reads `1`, the login did not complete — most
likely Step 0 was skipped.

---

## Step 2 — the owner issues the invite

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/nativeforge_demo_invite_issue.py --email THE_SECOND_ACCOUNT_ADDRESS
```

Substitute the real address. It is read at runtime and is **not printed, not
stored, and not written to any artifact** — the row keeps the domain half and a
fingerprint, and nothing else.

Expect:

```text
issued                       True
invite_id                    nf-invite-xxxxxxxxxxxx
organization_id              bbbbbbbb-cccc-dddd-eeee-ffffffffffff
invited_email_recorded       False
email_sent                   False
```

**Copy the `invite_id`.** No email is sent — nothing in NativeForge can send
one, and the table has no column for an address to send to. Telling the second
person is a message you send yourself, and they do not need the id.

The issuer is read from the organization's active `org_owner` membership row,
not supplied. That is deliberate: letting the operator name who issued an
invite would let the operator forge who authorized a membership.

Defaults: role `grant_lead`, expiry 14 days. Override with `--role` and
`--ttl-days` if you want something else.

---

## Step 3 — accept it for them

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/nativeforge_demo_invite_accept.py --invite-id INVITE_ID_FROM_STEP_2 --email THE_SECOND_ACCOUNT_ADDRESS
```

Expect:

```text
membership_activated         True
invite_accepted              True
accepter_matched_the_invite  True
membership_rows_written      1
provenance                   completed_invite
invite_binding_passed        True
```

`invite_binding_passed True` on this line is the blocker clearing.

The address must be the **same one** as step 2. The identity is resolved from
`nf_identities` by that address, and the acceptance then requires it to match
the invite's own fingerprint — so running this with a different address does
not redirect the membership, it refuses.

Both writes are one transaction. If the membership fails after the acceptance,
both roll back, because an invite marked accepted with nobody behind it reads
as consumed and its id cannot be reused.

---

## Step 4 — the second account signs in again

Same clean browser profile:

```text
https://nf-dev.mayhem-nc.dev/api/auth/login
```

**Now expect a session.** There is a membership, so the callback resolves an
organization and sets the cookie.

---

## Step 5 — verify

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/verify_nativeforge_customer_auth_live.sh
```

### Ready looks like this

```text
check=login_live status=PASS true
check=dev_header_consumers_zero status=PASS n=0
count=invite_rows n=1
count=accepted_invite_rows n=1
count=memberships_from_a_completed_invite n=1
check=invite_binding_passed status=PASS true
check=owner_activation_decision status=PASS approves_customer_auth_live

RESULT=PASS
customer_auth_live=true
scope=controlled_dev_demo_org_only
production_rollout=false
controlled_customer_pilot=false
```

Exit code 0. That is the gate.

### Blocked looks like this

```text
RESULT=BLOCKED
customer_auth_live=false
blocker=invite_binding_passed
next=docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md
```

Exit code 1, and the blocker is always named. Which count is zero says which
step has not happened:

```text
invite_rows 0                            step 2 has not run
accepted_invite_rows 0                   step 3 has not run, or it refused
memberships_from_a_completed_invite 0    the membership does not name its
                                         invite — see below
```

### One output that means stop

```text
blocker=gate_says_live_while_measurements_say:...
```

The gate claims customer auth is live and the rows disagree. One of the two is
wrong. The verifier will not pick which, and neither should you — this is worse
news than a blocker.

---

## Refusals you may hit, and what each means

```text
no_identity_has_signed_in_with_that_address
    step 1 has not happened for this address. There is no flag that accepts on
    behalf of somebody who has not authenticated — that is the faked user this
    whole gate exists to avoid. Do step 1.

accepting_identity_is_not_the_invited_identity
    the address in step 3 is not the one in step 2, or the invite named nobody.
    Re-issue with the right address.

invite_already_accepted
    it worked. Check the verifier rather than re-running step 3.

invite_expired
    past --ttl-days. Issue a new one with a new id.

invite_requested_approved_and_accepted_by_one_identity
    the owner is trying to accept their own invite. It authorizes nothing, and
    it is refused in the repository on every dialect and by a CHECK on
    PostgreSQL.

seat_cap_reached
    the demo org's seat cap is 5 and it is full. Nothing here raises it.

organization_is_the_explicitly_refused_real_org
    aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee. Exits 2, writes nothing.

several_identities_share_that_address
    two provider identities hold one address. Choosing one would be choosing
    who gets the membership, so it refuses. Ask which account they used.
```

---

## What not to do

```text
do not publish the Google OAuth app to skip step 0
     add the test user instead. Up to 100 are allowed.

do not run step 3 before step 1
     it refuses, and correctly. The identity has to come from real OAuth.

do not INSERT rows by hand to make the verifier pass
     a membership that does not name an accepted invite does not count. The
     verifier reports that near-miss separately, as
     memberships_matching_an_accepter_by_identity_only — which is exactly the
     state migration 0039 exists to stop passing as evidence.

do not use the owner's browser profile for step 1
     Google will reuse the owner's session and you will bind the owner again,
     which the self-dealing refusal then blocks.

do not point either script at the real organization
     --organization exists so the refusals are reachable. It cannot widen the
     scope.

do not put the second account's address into a commit, a doc, or an artifact
     the scripts never print it. Keep it that way.
```

---

## What this does NOT make true

```text
production_rollout             false
controlled_customer_pilot      false
verified_operational_binding   false   Gate 113 refuses one on a demo org
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

`customer_auth_live` true means **controlled dev customer auth on one demo
organization, with two real Google identities**. It is not a customer pilot and
it is not production. Those are separate decisions and neither is authorized.
