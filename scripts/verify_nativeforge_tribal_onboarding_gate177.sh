#!/usr/bin/env bash
# Gate 177 — can a real Native organisation safely establish and run its own
# NativeForge tenant?
#
# RESULT=PASS only when identity, affiliation and authority are three
# independent answers rather than one boolean; when a mailbox at the right
# domain proves control of a mailbox and nothing more; when an authority
# nobody signed for cannot be stored; when a customer administrator cannot
# reach controlling-company powers by any route; when a real administrator of
# one Tribe cannot touch another; and when one person reordering their own
# dashboard leaves everybody else's exactly where it was.
#
# THIS SCRIPT MAKES NO NETWORK CALL. The phase replaces `socket.socket` with
# one that raises and counts attempts, and the count is asserted to be zero.
#
# THE MEASUREMENT THIS GATE TURNS ON:
#
#   real_organization_has_an_authorized_admin=false
#
# The real organisation has zero active members and zero authority grants.
# "Organisation has no authorised administrator" is adversarial case 11 in the
# corpus AND the current state of the real tenant. Asserted false on purpose:
# if it flips to true, somebody has been granted authority over a real Tribal
# government's tenant, and that is a decision a human must have made
# deliberately.
#
# What is structural and what is INFO:
#
#   asserted   the three dimensions and their independence, evidence typing
#              and its refusals, manual verification, revocation semantics,
#              tenant creation, roles and the controlling-company boundary,
#              tenancy, invitations, the phrase rule, branding safety, org
#              defaults, personal overrides, self-health specificity, 176
#              semantics, zero network
#   INFO       corpus counts, local database revision, evidence type count
#
# The corpus result is INFO. Fifteen cases we thought of are not a claim about
# whether any particular person may speak for any particular government.
#
# No secrets, tokens, credentials, request URLs or customer data.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1

FAILED=""
pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

require_true() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_false() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "False" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_zero() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_empty_list() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_value() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "$3" ]; then pass "${4:-$2}" "value=$v"; else fail "${4:-$2}" "expected=$3 got=$v"; fi
}

run_phase() {
  local out
  out="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  printf '%s' "$out" | grep -q '^{' || return 1
  printf '%s' "$out"
}

echo "=== Gate 177: Tribal authority, onboarding and tenant administration ==="

PROOF="$(run_phase scripts/_g177_phase_proof.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=proof_phase_did_not_report"; exit 0; }

# ---------------- 177B: three questions, three answers -------------------
require_true "$PROOF" identity_affiliation_authority_separated

# ---------------- 177C: evidence -----------------------------------------
require_true "$PROOF" authority_evidence_ready
info evidence_type_count "value=$(jget "$PROOF" evidence_type_count)"

# ---------------- 177D: the first-four-customer path ---------------------
require_true "$PROOF" manual_authority_verification_ready

# ---------------- 177J: revocation ---------------------------------------
require_true "$PROOF" authority_revocation_ready

# ---------------- 177E/F: tenant, profile, roles -------------------------
require_true "$PROOF" tenant_creation_authorized
require_true "$PROOF" organization_profile_ready
require_true "$PROOF" organization_roles_ready
# The rule the block called critical: a real human phrase is never silently
# mapped to no entity classes.
require_true "$PROOF" phrase_recognition_distinguishes_four_outcomes

# ---------------- tenancy and the boundary -------------------------------
require_true "$PROOF" cross_tenant_admin_blocked
require_true "$PROOF" controlling_company_boundary_ready

# ---------------- 177G: invitations --------------------------------------
require_true "$PROOF" organization_invitations_ready

# ---------------- 177H/I: branding, defaults, overrides ------------------
require_true "$PROOF" organization_branding_ready
require_true "$PROOF" organization_dashboard_defaults_ready
require_true "$PROOF" individual_dashboard_overrides_ready

# ---------------- 177L: self health --------------------------------------
require_true "$PROOF" authority_self_health_ready
require_value "$PROOF" self_health_detector_count 9 self_health_detector_count

# ---------------- 177K: the corpus ---------------------------------------
require_value "$PROOF" corpus_case_count 15 corpus_case_count
require_value "$PROOF" corpus_passed_count 15 corpus_passed_count
require_empty_list "$PROOF" corpus_failed_cases
# A corpus claiming to be world truth would be this gate's worst failure.
require_false "$PROOF" corpus_is_world_truth
require_false "$PROOF" real_tribe_onboarded
info corpus_clock_is_pinned "value=$(jget "$PROOF" corpus_clock_is_pinned)"

# ---------------- the real world -----------------------------------------
# Asserted FALSE on purpose. See the header.
require_false "$PROOF" real_organization_has_an_authorized_admin
info real_organization_active_members "value=$(jget "$PROOF" real_organization_active_members)"
info real_organization_authority_grants "value=$(jget "$PROOF" real_organization_authority_grants)"
info local_database_revision "value=$(jget "$PROOF" local_database_revision)"
info authority_tables_applied_locally "value=$(jget "$PROOF" authority_tables_applied_locally)"

# ---------------- what came before must still hold -----------------------
require_true "$PROOF" gate176_semantics_preserved

# ---------------- the boundaries -----------------------------------------
require_zero "$PROOF" network_requests
require_zero "$PROOF" fixture_residue

require_true "$PROOF" gate177_ready

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "identity_affiliation_authority_separated=true"
echo "authority_evidence_ready=true"
echo "manual_authority_verification_ready=true"
echo "authority_revocation_ready=true"
echo "tenant_creation_authorized=true"
echo "organization_profile_ready=true"
echo "organization_roles_ready=true"
echo "cross_tenant_admin_blocked=true"
echo "organization_invitations_ready=true"
echo "organization_branding_ready=true"
echo "organization_dashboard_defaults_ready=true"
echo "individual_dashboard_overrides_ready=true"
echo "controlling_company_boundary_ready=true"
echo "authority_self_health_ready=true"
echo "real_organization_has_an_authorized_admin=false"
echo "gate176_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate177_ready=true"
