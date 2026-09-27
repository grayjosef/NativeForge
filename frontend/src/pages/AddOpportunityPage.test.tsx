import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddOpportunityPage } from "./AddOpportunityPage";
import type { UrlReadResult } from "../lib/opportunityIntake";

/**
 * Pasting a link, and what the customer is told about it.
 *
 * The three endings are the point. "NativeForge did not open that" and
 * "NativeForge opened it and found nothing in it" are different facts, and a
 * page that renders them the same way - or renders the second one as an
 * opportunity with no contacts - is lying quietly.
 */

const READ: UrlReadResult = {
  fetched: true,
  readable: true,
  message: "",
  finalUrl: "https://www.hud.gov/notice-final",
  noticeText: "Program Contact\n\nJane Doe, Program Officer\njane.doe@hud.gov\n",
  deadline: "2027-01-15",
};

/** A document has no address, so the reading carries no final URL. */
const READ_FILE: UrlReadResult = { ...READ, finalUrl: "" };

function renderPage(
  onReadUrl: (url: string) => Promise<UrlReadResult | null>,
  onReadDocument: (file: File) => Promise<UrlReadResult | null> = vi.fn(async () => null),
) {
  return render(
    <AddOpportunityPage
      tracked={[]}
      busy={false}
      error={null}
      onCreate={vi.fn(async () => "id-1")}
      onReadUrl={onReadUrl}
      onReadDocument={onReadDocument}
      onOpenExisting={vi.fn()}
      onCancel={vi.fn()}
    />,
  );
}

function documentField() {
  return screen.getByLabelText("Or upload the notice") as HTMLInputElement;
}

function pick(name = "notice.pdf", type = "application/pdf") {
  const file = new File(["%PDF-1.4"], name, { type });
  fireEvent.change(documentField(), { target: { files: [file] } });
  return file;
}

function urlField() {
  return screen.getByLabelText("Link to the opportunity");
}

function readButton() {
  return screen.getByRole("button", { name: /read the page/i });
}

function noticeField() {
  return screen.getByLabelText("Paste the notice") as HTMLTextAreaElement;
}

describe("reading a customer-supplied link", () => {
  it("cannot be asked for before there is a link to read", async () => {
    const read = vi.fn(async () => READ);
    renderPage(read);
    expect(readButton()).toBeDisabled();

    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    expect(readButton()).toBeEnabled();
  });

  it("fills the notice and the deadline when the page is read", async () => {
    renderPage(vi.fn(async () => READ));
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(noticeField().value).toContain("jane.doe@hud.gov"));
    expect(screen.getByLabelText("Application deadline")).toHaveValue("2027-01-15");
    // The address that was actually read, after redirects, is the one kept.
    expect(urlField()).toHaveValue("https://www.hud.gov/notice-final");
  });

  it("never overwrites what the customer already typed", async () => {
    renderPage(vi.fn(async () => READ));
    fireEvent.change(noticeField(), { target: { value: "The notice they already had." } });
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(screen.getByText(/notice read from the link/i)).toBeTruthy());
    expect(noticeField().value).toBe("The notice they already had.");
  });

  it("says why an address was refused, in a sentence", async () => {
    const refusal: UrlReadResult = {
      fetched: false,
      readable: false,
      message: "That address is not a public web page, so NativeForge will not open it.",
      finalUrl: "",
      noticeText: "",
      deadline: "",
    };
    renderPage(vi.fn(async () => refusal));
    fireEvent.change(urlField(), { target: { value: "https://internal.example/notice" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(screen.getByText(refusal.message)).toBeTruthy());
    expect(screen.getByText(/did not open that link/i)).toBeTruthy();
    expect(noticeField().value).toBe("");
  });

  it("distinguishes a document it could not read from a link it would not open", async () => {
    const unreadable: UrlReadResult = {
      fetched: true,
      readable: false,
      message: "That page has no readable text. Paste the notice text instead.",
      finalUrl: "https://www.hud.gov/scan.pdf",
      noticeText: "",
      deadline: "",
    };
    renderPage(vi.fn(async () => unreadable));
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/scan.pdf" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(screen.getByText(/opened, but not readable/i)).toBeTruthy());
    expect(screen.queryByText(/did not open that link/i)).toBeNull();
    // And the path that always works is still right there.
    expect(noticeField()).toBeTruthy();
  });

  it("keeps a partial reading's caveat attached to the success", async () => {
    const partial: UrlReadResult = {
      ...READ,
      message: "This looks like a scanned document, so NativeForge could only read part of it.",
    };
    renderPage(vi.fn(async () => partial));
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(screen.getByText(partial.message)).toBeTruthy());
    expect(noticeField().value).toContain("jane.doe@hud.gov");
  });

  it("survives the request failing outright", async () => {
    renderPage(vi.fn(async () => null));
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    fireEvent.click(readButton());

    await waitFor(() => expect(readButton()).toBeEnabled());
    expect(noticeField().value).toBe("");
  });

  it("clears a stale outcome when the link is edited", async () => {
    renderPage(vi.fn(async () => READ));
    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice" } });
    fireEvent.click(readButton());
    await waitFor(() => expect(screen.getByText(/notice read from the link/i)).toBeTruthy());

    fireEvent.change(urlField(), { target: { value: "https://www.hud.gov/notice-2" } });
    expect(screen.queryByText(/notice read from the link/i)).toBeNull();
  });

  it("does not claim NativeForge refuses to open links", async () => {
    /** The old copy, which the capability has outlived. */
    renderPage(vi.fn(async () => READ));
    expect(screen.queryByText(/does not open links you supply/i)).toBeNull();
  });
});

describe("reading a notice the customer uploads", () => {
  it("fills the notice from a file, without a link", async () => {
    const read = vi.fn(async () => READ_FILE);
    renderPage(vi.fn(async () => null), read);
    pick();

    await waitFor(() => expect(noticeField().value).toContain("jane.doe@hud.gov"));
    expect(read).toHaveBeenCalledTimes(1);
    // A document has no address, so nothing is written into the link field.
    expect(urlField()).toHaveValue("");
  });

  it("does not tell someone their scanned PDF was rejected", async () => {
    /**
     * The route says `read: false` for two different endings, and only one of
     * them means the file was not accepted.
     */
    const scanned: UrlReadResult = {
      fetched: true,
      readable: false,
      message: "This looks like a scanned document.",
      finalUrl: "",
      noticeText: "",
      deadline: "",
    };
    renderPage(vi.fn(async () => null), vi.fn(async () => scanned));
    pick("scan.pdf");

    await waitFor(() => expect(screen.getByText(/opened, but not readable/i)).toBeTruthy());
    expect(screen.queryByText(/cannot read that file/i)).toBeNull();
  });

  it("says plainly when the format is one it cannot read", async () => {
    const refused: UrlReadResult = {
      fetched: false,
      readable: false,
      message: "NativeForge cannot read that kind of file.",
      finalUrl: "",
      noticeText: "",
      deadline: "",
    };
    renderPage(vi.fn(async () => null), vi.fn(async () => refused));
    pick("budget.xlsx", "application/vnd.ms-excel");

    await waitFor(() => expect(screen.getByText(/cannot read that file/i)).toBeTruthy());
    expect(noticeField().value).toBe("");
  });

  it("never overwrites a notice the customer already pasted", async () => {
    renderPage(vi.fn(async () => null), vi.fn(async () => READ_FILE));
    fireEvent.change(noticeField(), { target: { value: "Already theirs." } });
    pick();

    await waitFor(() => expect(screen.getByText(/notice read from the file/i)).toBeTruthy());
    expect(noticeField().value).toBe("Already theirs.");
  });

  it("survives the upload failing outright", async () => {
    renderPage(vi.fn(async () => null), vi.fn(async () => null));
    pick();
    await waitFor(() => expect(documentField()).toBeEnabled());
    expect(noticeField().value).toBe("");
  });
});
