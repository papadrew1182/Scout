import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Slot } from "expo-router";

import { AuthProvider, useAuth } from "../lib/auth";
import { setApiToken, setApiFamilyId } from "../lib/api";
import { LoginScreen } from "../components/LoginScreen";
import { NavBar } from "../components/NavBar";
import { ScoutPanel } from "../components/ScoutLauncher";
import { colors } from "../lib/styles";

function AppShell() {
  const { token, member, loading } = useAuth();
  const [scoutOpen, setScoutOpen] = useState(false);

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

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <NavBar onScoutPress={() => setScoutOpen(true)} />
      <Slot />
      <ScoutPanel visible={scoutOpen} onClose={() => setScoutOpen(false)} />
    </View>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
