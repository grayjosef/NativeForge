# 765 — Gate 146: the next human action

## Where it stands

```text
customer_auth_live          false
blocker                     invite_binding_passed
stage                       second_identity_signed_in
next action owner           the second person
owner_activation_decision   already approves customer_auth_live
```

Nothing is waiting on code. Nothing is waiting on an approval. The next thing
that has to happen is a person signing in.

## The steps, in order

### 0 — enrol the second Google account as an OAuth test user

**Do this first.** The app is External/Testing. Google refuses an unenrolled
account *before NativeForge sees the request*, so the second person gets
Google's own "Access blocked" screen and nothing in our logs explains it.

```text
console.cloud.google.com
  -> APIs & Services
  -> OAuth consent screen
  -> Audience   (older console: "Test users")
  -> ADD USERS
  -> the second account's Google address
  -> SAVE
```

Up to 100 test users are allowed. **Do not publish the app** to get around
this: it exposes a dev consent screen to anybody with the URL and is not needed.

Nothing in this repository can do this step, and nothing in this repository can
tell whether it has been done. It is reported `UNKNOWN`.

### 1 — the second account signs in once

In a clean browser profile, so the owner's Google session is not reused
(Incognito, a private window, or a second Chrome profile):

```text
https://nf-dev.mayhem-nc.dev/api/auth/login
```

Cloudflare Access sits in front, so there is an Access challenge before Google.
Complete both.

**Expect no session.** The callback writes an `nf_identities` row for the
verified subject and stops: it issues a cookie only once the identity resolves
to an organization through a membership, and the membership is step 3. The
response will say the organization binding is missing.

That is correct. Do not treat it as a failure and do not retry it differently.

Check the stage moved:

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/verify_nativeforge_customer_auth_second_person_event.sh
```

`stage=invite_issued` means step 1 worked.

### 2 — the owner issues the invite

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/nativeforge_demo_invite_issue.py --email THE_SECOND_ACCOUNT_ADDRESS
```

The address is read at runtime and is **not printed, not stored, and not
written to any artifact** — the row keeps the domain half and two fingerprints.

**Copy the invite id it prints.** No email is sent; nothing in NativeForge can
send one, and the table has no column for an address to send to. Telling the
second person is a message you send yourself, and they do not need the id.

Defaults: role `grant_lead`, expiry 14 days.

### 3 — accept it for them

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/nativeforge_demo_invite_accept.py --invite-id INVITE_ID_FROM_STEP_2 --email THE_SECOND_ACCOUNT_ADDRESS
```

The address must be the **same one** as step 2. If step 1 has not happened this
refuses with `no_identity_has_signed_in_with_that_address`, which is the honest
answer and not an error to work around.

`invite_binding_passed True` on the output is the blocker clearing.

### 4 — the second account signs in again

Same clean profile, same login URL. **Now expect a session**: there is a
membership, so the callback resolves an organization and sets the cookie.

### 5 — verify

```bash
cd /home/josefgray/projects/nativeforge && ./scripts/verify_nativeforge_customer_auth_live.sh
```

Ready looks like:

```text
count=invite_rows n=1
count=accepted_invite_rows n=1
count=memberships_from_a_completed_invite n=1
check=invite_binding_passed status=PASS true

RESULT=PASS
customer_auth_live=true
scope=controlled_dev_demo_org_only
```

## Who owns which step

```text
0   Mayhem, in the Google console        not a command
1   the second person                    not a command
2   the operator                         a command
3   the operator                         a command
4   the second person                    not a command
5   the operator                         a command
```

Three of the six are not commands. That is the actual shape of this blocker and
the reason it has stayed false through ten gates.

## Which count being zero says which step has not run

```text
identity_rows 1                          step 1 has not run
invite_rows 0                            step 2 has not run
accepted_invite_rows 0                   step 3 has not run, or it refused
memberships_from_a_completed_invite 0    the membership does not name its
                                         invite
```

## What must not be printed at any point

```text
the invited address        report the domain half and a fingerprint
the provider subject       report a fingerprint
the session cookie         report whether a session was issued
the OAuth state and PKCE   report nothing; no readout needs them
```

The invite id is safe to print, and is printed on purpose.

## What stays false until Gate 150 re-decides

```text
verified_operational_binding   false
controlled_customer_pilot      false
production_rollout             false
```

`customer_auth_live` becoming true clears one of the four approvals the
controlled customer beta needs. The other three — verified operational binding,
a documented consent and data boundary, and the scope approval itself — do not
move with it. Gates 147, 148 and 150 are where those are taken up.
