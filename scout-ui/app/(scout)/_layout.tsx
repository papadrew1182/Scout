/**
 * Session 3 route group.
 *
 * Wraps every /today, /rewards, /calendar, /control-plane, /assist
 * route in the AppProvider + Shell. Routes outside this group keep
 * the legacy NavBar + per-screen state.
 */

import { AppProvider } from "../../features/app/AppContext";
import { ScoutShell } from "../../features/app/Shell";

export default function ScoutGroupLayout() {
  return (
    <AppProvider>
      <ScoutShell />
    </AppProvider>
  );
}
