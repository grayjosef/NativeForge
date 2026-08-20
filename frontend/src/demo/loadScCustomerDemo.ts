/** Load SC Monday customer demo bridge payload (static JSON import). */

import demoJson from "./sc_customer_demo.json";
import type { ScCustomerDemoPayload } from "./scCustomerDemoTypes";

export function loadScCustomerDemoPayload(): ScCustomerDemoPayload {
  return demoJson as ScCustomerDemoPayload;
}
