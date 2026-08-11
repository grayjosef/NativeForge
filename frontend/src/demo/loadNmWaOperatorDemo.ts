/** Load NM/WA operator demo bridge payload (static JSON import). */

import demoJson from "./nm_wa_operator_demo.json";
import type { NmWaOperatorDemoPayload } from "./nmWaOperatorDemoTypes";

export function loadNmWaOperatorDemoPayload(): NmWaOperatorDemoPayload {
  return demoJson as NmWaOperatorDemoPayload;
}
