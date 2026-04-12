import { useState } from "react";
import { View } from "react-native";
import { Slot } from "expo-router";

import { NavBar } from "../components/NavBar";
import { ScoutPanel } from "../components/ScoutLauncher";
import { colors } from "../lib/styles";

export default function RootLayout() {
  const [scoutOpen, setScoutOpen] = useState(false);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <NavBar onScoutPress={() => setScoutOpen(true)} />
      <Slot />
      <ScoutPanel visible={scoutOpen} onClose={() => setScoutOpen(false)} />
    </View>
  );
}
