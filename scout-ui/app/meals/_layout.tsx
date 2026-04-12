import { Pressable, StyleSheet, Text, View } from "react-native";
import { Slot, usePathname, useRouter } from "expo-router";

import { colors } from "../../lib/styles";

const TABS = [
  { href: "/meals/this-week", label: "This Week" },
  { href: "/meals/prep", label: "Prep Plan" },
  { href: "/meals/groceries", label: "Groceries" },
  { href: "/meals/reviews", label: "Reviews" },
];

export default function MealsLayout() {
  const router = useRouter();
  const pathname = usePathname();

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.tabs}>
        {TABS.map((t) => (
          <Pressable
            key={t.href}
            style={[styles.tab, isActive(t.href) && styles.tabActive]}
            onPress={() => router.push(t.href as any)}
          >
            <Text style={[styles.tabText, isActive(t.href) && styles.tabTextActive]}>
              {t.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <Slot />
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: {
    flexDirection: "row",
    gap: 4,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 6,
    backgroundColor: colors.bg,
  },
  tab: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: colors.surfaceMuted,
  },
  tabActive: {
    backgroundColor: colors.accent,
  },
  tabText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  tabTextActive: {
    color: colors.buttonPrimaryText,
  },
});
