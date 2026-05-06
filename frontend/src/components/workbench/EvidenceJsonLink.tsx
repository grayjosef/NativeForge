import type { ReactNode } from "react";
import type { Plane } from "../../m0Flow";
import {
  buildEvidencePackPath,
  type EvidenceKind,
  openEvidenceJsonTab,
} from "./evidenceUrls";

export interface EvidenceJsonLinkProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  kind: EvidenceKind;
  id: string;
  children: ReactNode;
}

export function EvidenceJsonLink({
  baseUrl,
  plane,
  orgId,
  kind,
  id,
  children,
}: EvidenceJsonLinkProps) {
  const path = buildEvidencePackPath(plane, orgId, kind, id);
  return (
    <button
      type="button"
      className="nf-btn nf-btn-secondary nf-btn-inline"
      onClick={() => openEvidenceJsonTab(baseUrl, path)}
    >
      {children}
    </button>
  );
}
