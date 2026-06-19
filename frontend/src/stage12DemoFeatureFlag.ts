/** Stage 12 guided demo feature flag — requires workbench flag too. */

const LS_KEY = "nf-stage12-demo-enabled";

export function readStage12DemoFlag(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get("nf_stage12_demo");
    if (q === "1" || q === "true") {
      return true;
    }
    if (q === "0" || q === "false") {
      return false;
    }
    return localStorage.getItem(LS_KEY) === "1";
  } catch {
    return false;
  }
}

export function stage12DemoQueryParam(): string {
  return readStage12DemoFlag() ? "true" : "false";
}
