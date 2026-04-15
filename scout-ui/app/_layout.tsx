import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Slot, usePathname } from "expo-router";

import { AuthProvider, useAuth } from "../lib/auth";
import { setApiToken, setApiFamilyId } from "../lib/api";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { LoginScreen } from "../components/LoginScreen";
import { NavBar } from "../components/NavBar";
import { ScoutPanel } from "../components/ScoutLauncher";
import { colors } from "../lib/styles";

// Routes that belong to the Session 3 operating surface. They render
// inside their own ScoutShell (header + bottom-tab nav) and must not
// be wrapped in the legacy NavBar.
const SCOUT_PATHS = ["/today", "/rewards", "/calendar", "/control-plane", "/assist"];

function isScoutPath(pathname: string): boolean {
  return SCOUT_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function AppShell() {
  const { token, member, loading } = useAuth();
  const [scoutOpen, setScoutOpen] = useState(false);
  const pathname = usePathname();

  // Sync auth token + family to API module
  useEffect(() => {
    setApiToken(token);
    setApiFamilyId(member?.family_id ?? null);
  }, [token, member]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (!token || !member) {
    return <LoginScreen />;
  }

  // Inside the Session 3 group the Shell brings its own chrome.
  // Legacy routes still get the desktop NavBar + ScoutPanel modal.
  const inScoutShell = isScoutPath(pathname);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {!inScoutShell && <NavBar onScoutPress={() => setScoutOpen(true)} />}
      <Slot />
      {!inScoutShell && (
        <ScoutPanel visible={scoutOpen} onClose={() => setScoutOpen(false)} />
      )}
    </View>
  );
}

export default function RootLayout() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </ErrorBoundary>
  );
}
