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
 * ## Members and invitations are absent on purpose
 *
 * There is a membership table and a bootstrap path, and no invite flow a
 * customer can drive. Drawing a member list with a disabled "Invite" button
 * would imply the feature exists and is switched off. The section says what
 * is true instead: one member, created at first sign-in, and invitations are
 * not built.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface OrganizationPageProps {
  profile: Record<string, unknown> | null;
  identityVerified: boolean;
  busy: boolean;
  error: CustomerState | null;
  onEditProfile: () => void;
  onRefresh: () => void;
}

export function OrganizationPage(props: OrganizationPageProps) {
  const { profile, identityVerified, busy, error, onEditProfile, onRefresh } = props;

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

      <Section title="People" lead="Who can act in this workspace.">
        <p className="nf-note">
          This workspace has one member: the account that first signed in and bootstrapped the
          organization. Inviting colleagues is not built yet — when it is, an invitation will have
          to be approved by an existing member rather than accepted by anybody holding the link.
        </p>
      </Section>
    </div>
  );
}
