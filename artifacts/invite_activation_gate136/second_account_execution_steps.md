# Gate 136 — the second account, in order

Full version with the console screens in `docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md`.

## Before anything

The Google OAuth app is **External / Testing** with one test user. Google
refuses an account that is not on that list *before NativeForge sees the
request*, so this is first and nothing in the repository can do it:

```text
Google Cloud console -> APIs & Services -> OAuth consent screen
  -> Audience / Test users -> ADD USERS -> the second account
```

## Then, four steps

```text
1  the second account signs in once
     https://nf-dev.mayhem-nc.dev/api/auth/login
   an nf_identities row is written. NO session yet - the callback needs a
   membership before it sets a cookie, and that is what step 3 creates.
   This is correct and is not an error.

2  the owner issues the invite
     ./scripts/nativeforge_demo_invite_issue.py --email <that account's address>
   prints an invite id. The address is not printed and is not stored.

3  accept it for them
     ./scripts/nativeforge_demo_invite_accept.py \
         --invite-id <the id from step 2> --email <the same address>
   the invite is accepted and a membership is written, naming the invite,
   in one transaction.

4  the second account signs in again
     https://nf-dev.mayhem-nc.dev/api/auth/login
   now there is a membership, so now there is a session.
```

## Then verify

```text
./scripts/verify_nativeforge_customer_auth_live.sh
```

```text
RESULT=PASS      customer_auth_live=true. Done.
RESULT=BLOCKED   the blocker is named on the next line.
```

## What not to do

```text
do not accept an invite for somebody who has not signed in
     it refuses: no_identity_has_signed_in_with_that_address
     there is no flag that overrides this, deliberately

do not run step 3 with a different address to redirect the membership
     it refuses: accepting_identity_is_not_the_invited_identity

do not issue an invite against aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
     it refuses by name and exits 2

do not add rows by hand to make the verifier pass
     a membership that does not name an accepted invite does not count, and
     the verifier reports the near-miss separately
```
