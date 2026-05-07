import { describe, expect, it } from "vitest";
import {
  buildEvidencePackPath,
  collectEvidenceLinkRows,
  looksLikeUuid,
  type EvidenceKind,
} from "./evidenceUrls";

describe("looksLikeUuid", () => {
  it("accepts canonical UUID strings", () => {
    expect(looksLikeUuid("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
  });

  it("rejects script and data URLs so they never drive evidence navigation", () => {
    expect(looksLikeUuid("javascript:alert(1)")).toBe(false);
    expect(looksLikeUuid("data:text/html,<svg/onload=alert(1)>")).toBe(false);
    expect(looksLikeUuid("vbscript:msgbox(1)")).toBe(false);
  });
});

describe("buildEvidencePackPath", () => {
  it("only emits same-origin discovery evidence routes for fixed kinds", () => {
    const org = "550e8400-e29b-41d4-a716-446655440001";
    const id = "550e8400-e29b-41d4-a716-446655440002";
    const kinds: EvidenceKind[] = [
      "sources",
      "review-items",
      "operator-actions",
      "grant-sparks",
      "intake-candidates",
      "source-check-runs",
      "intake-runs",
    ];
    for (const k of kinds) {
      const p = buildEvidencePackPath("demo", org, k, id);
      expect(p).toContain("/discovery/evidence-pack/");
      expect(p).not.toMatch(/^javascript:/i);
      expect(p).not.toMatch(/^data:/i);
    }
  });
});

describe("collectEvidenceLinkRows", () => {
  it("ignores non-UUID refs so user-shaped strings cannot become link ids", () => {
    const rows = collectEvidenceLinkRows({
      decisionPack: {
        decision_items: [
          {
            title: "t",
            refs: {
              source_registry_id: "javascript:void(0)",
              grant_spark_id: "550e8400-e29b-41d4-a716-446655440099",
            },
          },
        ],
      },
      ledgerList: null,
      reviewItems: null,
      overdueSources: null,
      coverageIntel: null,
      sourceRecs: null,
    });
    expect(rows.some((r) => r.id.includes("javascript"))).toBe(false);
    expect(rows.some((r) => r.kind === "grant-sparks")).toBe(true);
  });
});
