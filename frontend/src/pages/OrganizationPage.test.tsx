import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OrganizationPage } from "./OrganizationPage";

describe("OrganizationPage", () => {
  it("lists members and pending invites without implying email was stored", () => {
    render(
      <OrganizationPage
        profile={null}
        identityVerified
        busy={false}
        error={null}
        onEditProfile={vi.fn()}
        onRefresh={vi.fn()}
        people={{
          members: [
            {
              membership_id: "m1",
              role: "org_owner",
              state: "active",
              is_viewer: true,
            },
          ],
          invites: [
            {
              invite_id: "nf-invite-abc123",
              requested_role: "grant_lead",
              invited_email_domain: "example.com",
              invite_state: "approved",
              accepted: false,
              revoked: false,
            },
          ],
        }}
        onIssueInvite={vi.fn(async () => undefined)}
      />,
    );
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("nf-invite-abc123")).toBeInTheDocument();
    expect(screen.getByText(/example.com/)).toBeInTheDocument();
    expect(screen.getByText(/does not send the invitation/i)).toBeInTheDocument();
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
  });
});
