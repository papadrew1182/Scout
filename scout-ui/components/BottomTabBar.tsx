import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";

import { colors, fonts } from "../lib/styles";

const TABS = [
  { href: "/",        label: "Home",    icon: "⌂" },
  { href: "/parent",  label: "Chores",  icon: "✓" },
  { href: "__scout",  label: "Scout",   icon: "✦" },
  { href: "/meals",   label: "Meals",   icon: "♨" },
  { href: "/grocery", label: "Grocery", icon: "🛒" },
] as const;

interface Props {
  onScoutPress: () => void;
}

export function BottomTabBar({ onScoutPress }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");

  return (
    <View style={styles.bar}>
      {TABS.map((t) => {
        if (t.href === "__scout") {
          return (
            <Pressable key={t.href} style={styles.fabWrap} onPress={onScoutPress} accessibilityRole="button" accessibilityLabel="Open Scout">
              <View style={styles.fab}>
                <Text style={styles.fabIcon}>{t.icon}</Text>
              </View>
              <Text style={[styles.label, { color: colors.purple }]}>{t.label}</Text>
            </Pressable>
          );
        }
        const active = isActive(t.href);
        return (
          <Pressable key={t.href} style={styles.tab} onPress={() => router.push(t.href as any)} accessibilityRole="link" accessibilityState={{ selected: active }}>
            <Text style={[styles.icon, active && { color: colors.purple }]}>{t.icon}</Text>
            <Text style={[styles.label, active && { color: colors.purple }]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    height: 64,
    paddingBottom: 6,
    paddingTop: 4,
    alignItems: "flex-end",
  },
  tab: { flex: 1, alignItems: "center", justifyContent: "flex-end", gap: 2 },
  icon: { fontSize: 18, color: colors.muted },
  label: { fontSize: 10, color: colors.muted, fontFamily: fonts.body, fontWeight: "500" },

  fabWrap: { flex: 1, alignItems: "center", justifyContent: "flex-end", gap: 2 },
  fab: {
    position: "absolute",
    top: -22,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.purple,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.purple,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  fabIcon: { color: "#FFFFFF", fontSize: 24, fontWeight: "700" },
});
