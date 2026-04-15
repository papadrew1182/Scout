/**
 * Default landing route.
 *
 * Session 3 makes Today the canonical entry point. The previous
 * Family Overview that lived here is preserved at /legacy-overview
 * for anyone who still wants the per-child progress widget.
 */

import { Redirect } from "expo-router";

export default function Index() {
  return <Redirect href="/today" />;
}
