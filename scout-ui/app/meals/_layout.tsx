import { Pressable, StyleSheet, Text, View } from "react-native";
import { Slot, usePathname, useRouter } from "expo-router";

import { colors, fonts } from "../../lib/styles";

const TABS = [
  { href: "/meals",          label: "This week" },
  { href: "/meals/prep",     label: "Prep plan" },
  { href: "/meals/groceries",label: "Groceries" },
  { href: "/meals/reviews",  label: "Reviews" },
];

export default function MealsLayout() {
  const router = useRouter();
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/meals" ? pathname === "/meals" || pathname === "/meals/this-week" : pathname.startsWith(href);

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.headerRow}>
        <Text style={styles.h1}>Meals</Text>
        <View style={styles.tabs}>
          {TABS.map((t) => {
            const active = isActive(t.href);
            return (
              <Pressable key={t.href} style={[styles.tab, active && styles.tabActive]} onPress={() => router.push(t.href as any)} accessibilityRole="link" accessibilityState={{ selected: active }}>
                <Text style={[styles.tabText, active && styles.tabTextActive]}>{t.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Slot />
    </View>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 6,
    backgroundColor: colors.bg,
    flexWrap: "wrap",
    rowGap: 8,
  },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  tabs: { flexDirection: "row", gap: 4, flexWrap: "wrap" },
  tab: { paddingVertical: 6, paddingHorizontal: 14, borderRadius: 8 },
  tabActive: { backgroundColor: colors.purple },
  tabText: { fontSize: 11, color: colors.muted, fontFamily: fonts.body, fontWeight: "600" },
  tabTextActive: { color: "#FFFFFF" },
});
