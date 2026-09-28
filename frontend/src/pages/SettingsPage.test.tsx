import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./SettingsPage";

function renderSettings(locked: boolean) {
  render(
    <SettingsPage
      environment="demo"
      onEnvironmentChange={vi.fn()}
      organizationId="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
      onOrganizationIdChange={vi.fn()}
      organizationIdValid
      organizationLocked={locked}
      onOpen={vi.fn()}
    />,
  );
}

describe("SettingsPage organization context", () => {
  it("stops the identifier being edited once a session owns it", () => {
    renderSettings(true);
    expect(screen.getByLabelText(/organization identifier/i)).toBeDisabled();
    expect(
      screen.getByText(/comes from your sign-in session/i),
    ).toBeInTheDocument();
  });

  it("leaves the identifier editable when nobody is signed in", () => {
    renderSettings(false);
    expect(screen.getByLabelText(/organization identifier/i)).not.toBeDisabled();
  });
});
