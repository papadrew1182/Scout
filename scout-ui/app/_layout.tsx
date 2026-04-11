import { View } from "react-native";
import { Slot } from "expo-router";

import { NavBar } from "../components/NavBar";
import { colors } from "../lib/styles";

export default function RootLayout() {
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <NavBar />
      <Slot />
    </View>
  );
}
