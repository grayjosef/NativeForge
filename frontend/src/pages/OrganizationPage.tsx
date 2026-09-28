import { useState } from "react";

import { EmptyState, StateView } from "../components/StateView";
import type { CustomerState } from "../customerState";
import { PageHeader, Section, StatusBadge } from "../components/ui/primitives";
import { VerificationTiers, buildTiers } from "../components/VerificationTiers";
import { humanEntity } from "../lib/entityTypes";

/**
 * The organization: what NativeForge holds, and how much of it is confirmed.
 *
 * ## Unanswered is shown as unanswered
 *
 * Fields left blank during onboarding render as "Not provided", not as an
 * empty cell. An empty cell reads as *nothing to say*; a customer looking at
 * a half-filled profile should be able to see which half is missing, because
 * the missing half is what NativeForge will have to report as unknown when a
 * funder asks.
 *
 * ## People are listed without mailboxes
 *
 * Members and pending invites come from the membership tables. NativeForge
 * never shows the invited address, never stores it, and never sends it.
 * An invitation is a fingerprint plus an invite id you hand to the person
 * yourself. They bind when they sign in with that address.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface OrganizationPeople {
  members: Record<string, unknown>[];
  invites: Record<string, unknown>[];
  member_count?: number;
  invite_count?: number;
}

export interface OrganizationPageProps {
  profile: Record<string, unknown> | null;
  identityVerified: boolean;
  busy: boolean;
  error: CustomerState | null;
  onEditProfile: () => void;
  onRefresh: () => void;
  people?: OrganizationPeople | null;
  peopleBusy?: boolean;
  lastIssuedInviteId?: string | null;
  onIssueInvite?: (email: string, role: string) => Promise<void>;
}

function roleLabel(role: string): string {
  return role.replace(/_/g, " ");
}

export function OrganizationPage(props: OrganizationPageProps) {
  const {
    profile,
    identityVerified,
    busy,
    error,
    onEditProfile,
    onRefresh,
    people = null,
    peopleBusy = false,
    lastIssuedInviteId = null,
    onIssueInvite,
  } = props;

  const address = (profile?.physical_address ?? null) as Record<string, unknown> | null;
  const rep = (profile?.authorized_representative ?? null) as Record<string, unknown> | null;
  const gm = (profile?.grants_manager ?? null) as Record<string, unknown> | null;
  const narratives = (profile?.standard_narratives ?? null) as Record<string, unknown> | null;
  const interests = Array.isArray(narratives?.funding_interests)
    ? (narratives?.funding_interests as string[])
    : [];

  const rows: Array<[string, string]> = profile
    ? [
        ["Legal name", str(profile.legal_name)],
        ["Classification", str(profile.entity_type) ? humanEntity(str(profile.entity_type)) : ""],
        ["UEI", str(profile.uei)],
        ["EIN", str(profile.ein)],
        ["SAM.gov registration", str(profile.sam_registration_status)],
        [
          "Location",
          address ? [str(address.city), str(address.state)].filter(Boolean).join(", ") : "",
        ],
        ["Service area", str(profile.service_area_description)],
        [
          "Authorized representative",
          rep ? [str(rep.name), str(rep.title), str(rep.email)].filter(Boolean).join(" · ") : "",
        ],
        ["Grants manager", gm ? [str(gm.name), str(gm.email)].filter(Boolean).join(" · ") : ""],
        ["Funding interests", interests.join(", ")],
      ]
    : [];

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Govern"
        title="Organization"
        lead="What NativeForge holds about your organization, and how confident it is in each part."
        actions={
          <>
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onRefresh}
              disabled={busy}
            >
              Refresh
            </button>
            <button
              type="button"
              className="nf-btn nf-btn-primary nf-btn-sm"
              onClick={onEditProfile}
              disabled={busy}
            >
              {profile ? "Edit profile" : "Set up organization"}
            </button>
          </>
        }
      />

      {error ? <StateView state={error} /> : null}

      <Section
        title="Verification"
        lead="Three separate questions, which fail independently."
      >
        <VerificationTiers
          tiers={buildTiers({ identityVerified, hasProfile: profile !== null })}
        />
      </Section>

      <Section
        title="Profile"
        lead="Stated by your organization. NativeForge records it as a claim."
        aside={profile ? <StatusBadge tone="info">Self-declared</StatusBadge> : null}
      >
        {!profile ? (
          <EmptyState
            title="No organization profile yet."
            body="NativeForge needs your legal name and classification before it can evaluate an opportunity against you."
            actionLabel="Set up organization"
            onAction={onEditProfile}
          />
        ) : (
          <dl className="nf-review">
            {rows.map(([label, value]) => (
              <div key={label} className="nf-review-row">
                <dt>{label}</dt>
                <dd>
                  <span data-empty={value.trim() ? undefined : "true"}>
                    {value.trim() || "Not provided"}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </Section>

      <Section
        title="People"
        lead="Who can act in this workspace. Addresses are never shown."
      >
        {!people ? (
          <p className="nf-note">
            Member list loads for a signed-in organization session. NativeForge
            will not invent a roster.
          </p>
        ) : (
          <>
            {people.members.length === 0 ? (
              <EmptyState
                title="No members recorded."
                body="The first person to sign in becomes the owner. Until that happens, this list stays empty."
                inline
              />
            ) : (
              <ul className="nf-source-list">
                {people.members.map((member) => {
                  const id = str(member.membership_id);
                  const role = str(member.role);
                  const state = str(member.state);
                  return (
                    <li key={id || role} className="nf-source">
                      <p className="nf-source-name">
                        {member.is_viewer ? "You" : roleLabel(role) || "Member"}
                      </p>
                      <p className="nf-note">
                        {roleLabel(role)}
                        {state ? ` · ${state}` : ""}
                        {member.invite_id ? " · joined by invitation" : ""}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}

            {people.invites.filter((row) => !row.accepted && !row.revoked).length > 0 ? (
              <div className="nf-stack" style={{ marginTop: "1rem" }}>
                <p className="nf-note">Pending invitations — domain only, never the mailbox.</p>
                <ul className="nf-source-list">
                  {people.invites
                    .filter((row) => !row.accepted && !row.revoked)
                    .map((invite) => (
                      <li key={str(invite.invite_id)} className="nf-source">
                        <p className="nf-source-name">{str(invite.invite_id)}</p>
                        <p className="nf-note">
                          {roleLabel(str(invite.requested_role))}
                          {invite.invited_email_domain
                            ? ` · ${str(invite.invited_email_domain)}`
                            : ""}
                          {invite.invite_state ? ` · ${str(invite.invite_state)}` : ""}
                        </p>
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}

            {onIssueInvite ? (
              <IssueInviteForm
                busy={busy || peopleBusy}
                lastIssuedInviteId={lastIssuedInviteId}
                onIssueInvite={onIssueInvite}
              />
            ) : (
              <p className="nf-note">
                Issuing an invitation requires an owner or admin session.
                NativeForge does not email the person.
              </p>
            )}
          </>
        )}
      </Section>
    </div>
  );
}

function IssueInviteForm(props: {
  busy: boolean;
  lastIssuedInviteId: string | null;
  onIssueInvite: (email: string, role: string) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("grant_lead");
  const [localError, setLocalError] = useState<string | null>(null);

  return (
    <form
      className="nf-stack"
      style={{ marginTop: "1.25rem" }}
      onSubmit={(event) => {
        event.preventDefault();
        setLocalError(null);
        const address = email.trim();
        if (!address.includes("@")) {
          setLocalError("Enter the address you will tell them out of band.");
          return;
        }
        void props.onIssueInvite(address, role).then(() => setEmail(""));
      }}
    >
      <p className="nf-note">
        NativeForge does not send the invitation. You tell the person the invite
        id. They sign in with this address; the mailbox itself is never stored.
      </p>
      <label className="nf-field">
        <span>Colleague address</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={props.busy}
          autoComplete="off"
        />
      </label>
      <label className="nf-field">
        <span>Role</span>
        <select
          value={role}
          onChange={(event) => setRole(event.target.value)}
          disabled={props.busy}
        >
          <option value="grant_lead">Grant lead</option>
          <option value="reviewer">Reviewer</option>
          <option value="viewer">Viewer</option>
          <option value="org_admin">Admin</option>
          <option value="authorized_representative">Authorized representative</option>
        </select>
      </label>
      {localError ? <p className="nf-note">{localError}</p> : null}
      {props.lastIssuedInviteId ? (
        <p className="nf-note">
          Invitation issued. Give them this id: <strong>{props.lastIssuedInviteId}</strong>
        </p>
      ) : null}
      <button type="submit" className="nf-btn nf-btn-primary nf-btn-sm" disabled={props.busy}>
        {props.busy ? "Working…" : "Issue invitation"}
      </button>
    </form>
  );
}
