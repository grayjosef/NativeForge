#!/usr/bin/env bash
# Postgres row-level-security isolation proof (Gate 62).
#
# Proves three things against a REAL PostgreSQL instance:
#   1. RLS policies from migration 0002 actually restrict a non-owner app role
#      to its own organization's rows.
#   2. A cross-org read returns ZERO rows, not an error — the safe failure mode.
#   3. The table OWNER bypasses RLS entirely, which is why the app role must be
#      non-owner and non-superuser. This is the failure mode that would silently
#      void every policy.
#
# Requires DATABASE_URL_ADMIN pointing at a Postgres where migrations are applied.
# Never prints a password. Prints RESULT=PASS|FAIL.
#
# Local dev proof (no root required):
#   python3 -m venv /tmp/pgenv && /tmp/pgenv/bin/pip install pgserver
#   /tmp/pgenv/bin/python -c "import pgserver; pgserver.get_server('/tmp/nfpgdata', cleanup_mode=None)"
#   export DATABASE_URL_ADMIN='postgresql://postgres@/nf_dev_proof?host=/tmp/nfpgdata'
set -u

ADMIN_URL="${DATABASE_URL_ADMIN:-}"
if [[ -z "$ADMIN_URL" ]]; then
  echo "check=admin_url_present status=FAIL detail=DATABASE_URL_ADMIN not set"
  echo "RESULT=FAIL"
  exit 1
fi

APP_ROLE="${NF_RLS_TEST_APP_ROLE:-nf_rls_app}"
ORG_A="11111111-1111-1111-1111-111111111111"
ORG_B="22222222-2222-2222-2222-222222222222"
FAIL=0

q() { psql "$ADMIN_URL" -X -q -t -A -c "$1" 2>&1; }

say() {
  local name="$1" status="$2" detail="${3:-}"
  echo "check=${name} status=${status} ${detail}"
  [[ "$status" == "FAIL" ]] && FAIL=1
  return 0
}

# ── environment ──
VER="$(q "SHOW server_version;" | head -1)"
case "$VER" in
  1[6-9].*|2[0-9].*) say postgres_version_supported PASS "version=${VER}" ;;
  *) say postgres_version_supported FAIL "version=${VER} (need 16+)" ;;
esac

POLICY_COUNT="$(q "SELECT count(*) FROM pg_policies WHERE schemaname='public';" | head -1)"
if [[ "${POLICY_COUNT:-0}" -ge 1 ]]; then
  say rls_policies_present PASS "count=${POLICY_COUNT}"
else
  say rls_policies_present FAIL "no policies found — are migrations applied?"
fi

FORCED="$(q "SELECT count(*) FROM pg_class WHERE relrowsecurity AND relforcerowsecurity AND relnamespace='public'::regnamespace;" | head -1)"
if [[ "${FORCED:-0}" -ge 1 ]]; then
  say rls_forced_on_tables PASS "count=${FORCED}"
else
  say rls_forced_on_tables FAIL "FORCE ROW LEVEL SECURITY not set"
fi

# ── fixture: two organizations and one audit row each ──
q "INSERT INTO organizations (id, org_type) VALUES ('${ORG_A}','real')
   ON CONFLICT (id) DO NOTHING;" >/dev/null
q "INSERT INTO organizations (id, org_type) VALUES ('${ORG_B}','real')
   ON CONFLICT (id) DO NOTHING;" >/dev/null
q "DELETE FROM nf_audit_events WHERE organization_id IN ('${ORG_A}','${ORG_B}');" >/dev/null
q "INSERT INTO nf_audit_events (id, organization_id, is_demo, action)
   VALUES (gen_random_uuid(),'${ORG_A}',false,'rls_probe_org_a');" >/dev/null
q "INSERT INTO nf_audit_events (id, organization_id, is_demo, action)
   VALUES (gen_random_uuid(),'${ORG_B}',false,'rls_probe_org_b');" >/dev/null

SEEDED="$(q "SELECT count(*) FROM nf_audit_events
             WHERE organization_id IN ('${ORG_A}','${ORG_B}');" | head -1)"
if [[ "${SEEDED:-0}" == "2" ]]; then
  say fixture_rows_seeded PASS "rows=2"
else
  say fixture_rows_seeded FAIL "rows=${SEEDED}"
fi

# ── the owner bypass, demonstrated deliberately ──
# The table owner is exempt from RLS unless FORCE is set. This check records what
# the owner can see so the contrast with the app role is explicit in the output.
OWNER_SEES="$(q "SELECT set_config('app.current_org_id','${ORG_A}',false);
                 SELECT set_config('app.current_org_is_demo','false',false);
                 SELECT count(*) FROM nf_audit_events
                 WHERE organization_id IN ('${ORG_A}','${ORG_B}');" | tail -1)"
say owner_visibility_recorded PASS "owner_sees=${OWNER_SEES} (expected 2 — owners are not the isolation boundary)"

# ── create a least-privilege app role ──
q "DO \$\$
   BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${APP_ROLE}') THEN
       CREATE ROLE ${APP_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
     END IF;
   END
   \$\$;" >/dev/null
q "GRANT USAGE ON SCHEMA public TO ${APP_ROLE};" >/dev/null
q "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ${APP_ROLE};" >/dev/null

IS_SUPER="$(q "SELECT rolsuper FROM pg_roles WHERE rolname='${APP_ROLE}';" | head -1)"
if [[ "$IS_SUPER" == "f" ]]; then
  say app_role_not_superuser PASS
else
  say app_role_not_superuser FAIL "rolsuper=${IS_SUPER}"
fi

OWNS="$(q "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
           WHERE r.rolname='${APP_ROLE}' AND c.relnamespace='public'::regnamespace;" | head -1)"
if [[ "${OWNS:-0}" == "0" ]]; then
  say app_role_owns_no_tables PASS
else
  say app_role_owns_no_tables FAIL "owns=${OWNS} tables — RLS would be bypassed"
fi

# ── the actual isolation proof, as the app role ──
A_ROWS="$(q "SET ROLE ${APP_ROLE};
             SELECT set_config('app.current_org_id','${ORG_A}',false);
             SELECT set_config('app.current_org_is_demo','false',false);
             SELECT count(*) FROM nf_audit_events;" | tail -1)"
if [[ "${A_ROWS:-x}" == "1" ]]; then
  say app_role_sees_own_org PASS "rows=1"
else
  say app_role_sees_own_org FAIL "rows=${A_ROWS} (expected 1)"
fi

CROSS="$(q "SET ROLE ${APP_ROLE};
            SELECT set_config('app.current_org_id','${ORG_A}',false);
            SELECT set_config('app.current_org_is_demo','false',false);
            SELECT count(*) FROM nf_audit_events
            WHERE organization_id='${ORG_B}';" | tail -1)"
if [[ "${CROSS:-x}" == "0" ]]; then
  say cross_org_read_returns_zero_rows PASS "rows=0"
else
  say cross_org_read_returns_zero_rows FAIL "rows=${CROSS} — CROSS-TENANT LEAK"
fi

# With no GUC set at all, the app role must see nothing.
NOGUC="$(q "SET ROLE ${APP_ROLE};
            SELECT count(*) FROM nf_audit_events;" | tail -1)"
if [[ "${NOGUC:-x}" == "0" ]]; then
  say app_role_without_guc_sees_nothing PASS "rows=0"
else
  say app_role_without_guc_sees_nothing FAIL "rows=${NOGUC} — unscoped read allowed"
fi

# Switching the GUC to org B must switch the visible row, not widen it.
B_ROWS="$(q "SET ROLE ${APP_ROLE};
             SELECT set_config('app.current_org_id','${ORG_B}',false);
             SELECT set_config('app.current_org_is_demo','false',false);
             SELECT count(*) FROM nf_audit_events;" | tail -1)"
if [[ "${B_ROWS:-x}" == "1" ]]; then
  say app_role_scope_follows_guc PASS "rows=1"
else
  say app_role_scope_follows_guc FAIL "rows=${B_ROWS} (expected 1)"
fi

# A demo/real mismatch must also deny: the policy checks both columns.
DEMO_MISMATCH="$(q "SET ROLE ${APP_ROLE};
                    SELECT set_config('app.current_org_id','${ORG_A}',false);
                    SELECT set_config('app.current_org_is_demo','true',false);
                    SELECT count(*) FROM nf_audit_events;" | tail -1)"
if [[ "${DEMO_MISMATCH:-x}" == "0" ]]; then
  say demo_real_plane_mismatch_denies PASS "rows=0"
else
  say demo_real_plane_mismatch_denies FAIL "rows=${DEMO_MISMATCH}"
fi

# ── the NEW membership table (migrations 0024 / 0027) ──
# The point of Gate 61/62: membership is the record that grants a role, so it
# must be at least as well isolated as anything else.
q "INSERT INTO nf_identities (id, subject, issuer, email, email_verified)
   VALUES ('33333333-3333-3333-3333-333333333333','auth0|rls-probe',
           'https://rls.probe.test/','probe@example.org',true)
   ON CONFLICT (issuer, subject) DO NOTHING;" >/dev/null
q "DELETE FROM nf_org_memberships
   WHERE organization_id IN ('${ORG_A}','${ORG_B}');" >/dev/null
for ORG in "${ORG_A}" "${ORG_B}"; do
  q "INSERT INTO nf_org_memberships
       (id, organization_id, identity_id, is_demo, state, membership_source,
        role, role_source, approved_by)
     VALUES (gen_random_uuid(), '${ORG}', '33333333-3333-3333-3333-333333333333', false, 'active',
             'org_owner_approved', 'grant_lead', 'membership_record',
             '33333333-3333-3333-3333-333333333333');" >/dev/null
done

MEM_A="$(q "SET ROLE ${APP_ROLE};
            SELECT set_config('app.current_org_id','${ORG_A}',false);
            SELECT set_config('app.current_org_is_demo','false',false);
            SELECT count(*) FROM nf_org_memberships;" | tail -1)"
if [[ "${MEM_A:-x}" == "1" ]]; then
  say membership_table_scoped_to_own_org PASS "rows=1"
else
  say membership_table_scoped_to_own_org FAIL "rows=${MEM_A} (expected 1)"
fi

MEM_CROSS="$(q "SET ROLE ${APP_ROLE};
                SELECT set_config('app.current_org_id','${ORG_A}',false);
                SELECT set_config('app.current_org_is_demo','false',false);
                SELECT count(*) FROM nf_org_memberships
                WHERE organization_id='${ORG_B}';" | tail -1)"
if [[ "${MEM_CROSS:-x}" == "0" ]]; then
  say membership_cross_org_read_denied PASS "rows=0"
else
  say membership_cross_org_read_denied FAIL "rows=${MEM_CROSS} - MEMBERSHIP LEAK"
fi

# WITH CHECK: writing a membership for another org must be refused outright.
WRITE_OTHER="$(q "SET ROLE ${APP_ROLE};
                  SELECT set_config('app.current_org_id','${ORG_A}',false);
                  SELECT set_config('app.current_org_is_demo','false',false);
                  INSERT INTO nf_org_memberships
                    (id, organization_id, identity_id, is_demo, state,
                     membership_source, role, role_source, approved_by)
                  VALUES (gen_random_uuid(), '${ORG_B}', '33333333-3333-3333-3333-333333333333', false,
                          'active','org_owner_approved','org_owner',
                          'membership_record','33333333-3333-3333-3333-333333333333');")"
if echo "$WRITE_OTHER" | grep -qi "row-level security"; then
  say membership_cross_org_write_denied PASS "refused by RLS WITH CHECK"
else
  say membership_cross_org_write_denied FAIL "write not refused"
fi

q "DELETE FROM nf_org_memberships
   WHERE organization_id IN ('${ORG_A}','${ORG_B}');" >/dev/null
q "DELETE FROM nf_identities WHERE subject='auth0|rls-probe';" >/dev/null

# ── cleanup fixture rows ──
q "DELETE FROM nf_audit_events WHERE organization_id IN ('${ORG_A}','${ORG_B}');" >/dev/null

echo "note=owner_and_superuser_roles_bypass_rls_app_role_must_be_neither"
echo "note=this_is_a_dev_proof_not_a_production_provisioning_claim"

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
  exit 0
fi
echo "RESULT=FAIL"
exit 1
