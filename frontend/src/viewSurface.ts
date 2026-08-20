/** URL/query helpers for Workspace vs Workbench vs Activation vs demos. */

export type AppSurface =
  | "workspace"
  | "workbench"
  | "activation"
  | "nm_wa_operator_demo"
  | "sc_customer_demo";

export function readSurface(): AppSurface {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    if (q === "workbench") return "workbench";
    if (q === "activation") return "activation";
    if (q === "nm_wa_operator_demo") return "nm_wa_operator_demo";
    if (q === "sc_customer_demo") return "sc_customer_demo";
    return "workspace";
  } catch {
    return "workspace";
  }
}
