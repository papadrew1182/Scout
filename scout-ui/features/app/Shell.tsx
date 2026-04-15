/**
 * Mobile-first Session 3 shell.
 *
 * Visual model:
 *   ┌──────────────────────┐
 *   │   header (brand)     │   ← thin, with optional sign-out
 *   ├──────────────────────┤
 *   │                      │
 *   │      <Slot/>         │   ← active tab content
 *   │                      │
 *   ├──────────────────────┤
 *   │  bottom tab bar      │   ← Today / Rewards / Calendar / Plane / Assist
 *   └──────────────────────┘
 *
 * The bottom tab bar is the canonical Session 3 navigation. It does
 * NOT replace the legacy desktop NavBar that ships with /personal,
 * /parent, etc. — those routes still exist for now and are reachable
 * via the "More" entry. Once Session 2 surfaces the same data through
 * the published contracts, the legacy routes can be retired.
 */

import { ReactNode } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Slot, useRouter, usePathname } from "expo-router";

import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/styles";

interface TabDef {
  key: string;
  href:
    | "/today"
    | "/rewards"
    | "/calendar"
    | "/control-plane"
    | "/assist";
  label: string;
  icon: string; // unicode glyph; replace with vector icon set later
}

const TABS: TabDef[] = [
  { key: "today", href: "/today", label: "Today", icon: "◉" },
  { key: "rewards", href: "/rewards", label: "Rewards", icon: "★" },
  { key: "calendar", href: "/calendar", label: "Calendar", icon: "▦" },
  { key: "control-plane", href: "/control-plane", label: "Plane", icon: "◇" },
  { key: "assist", href: "/assist", label: "Assist", icon: "✦" },
];

export function ScoutShell({ children }: { children?: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { member, logout } = useAuth();

  const activeKey =
    TABS.find((t) => pathname === t.href || pathname.startsWith(`${t.href}/`))?.key ?? "today";

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.brand}>SCOUT</Text>
        <View style={styles.headerRight}>
          {member && <Text style={styles.headerName}>{member.first_name}</Text>}
          <Pressable onPress={() => router.push("/personal")} accessibilityRole="link">
            <Text style={styles.headerLink}>More</Text>
          </Pressable>
          {member && (
            <Pressable onPress={logout} accessibilityRole="button">
              <Text style={styles.headerLink}>Sign out</Text>
            </Pressable>
          )}
        </View>
      </View>

      <ScrollView
        style={styles.body}
        contentContainerStyle={styles.bodyContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.column}>
          {children ?? <Slot />}
        </View>
      </ScrollView>

      <View style={styles.tabBar}>
        {TABS.map((tab) => {
          const active = tab.key === activeKey;
          return (
            <Pressable
              key={tab.key}
              style={styles.tab}
              onPress={() => router.push(tab.href)}
              accessibilityRole="button"
              accessibilityLabel={`${tab.label} tab`}
            >
              <Text style={[styles.tabIcon, active && styles.tabIconActive]}>
                {tab.icon}
              </Text>
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>
                {tab.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    backgroundColor: colors.surfaceElevated,
    borderBottomWidth: 1,
    borderBottomColor: colors.cardBorder,
    paddingHorizontal: 18,
    paddingTop: 14,
    paddingBottom: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  brand: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 2.4,
  },
  headerRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  headerName: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "600",
  },
  headerLink: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  body: {
    flex: 1,
  },
  bodyContent: {
    paddingHorizontal: 14,
    paddingTop: 14,
    paddingBottom: 28,
    alignItems: "center",
  },
  column: {
    width: "100%",
    maxWidth: 560,
  },
  tabBar: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    backgroundColor: colors.surfaceElevated,
    paddingTop: 8,
    paddingBottom: 12,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 4,
  },
  tabIcon: {
    color: colors.textMuted,
    fontSize: 18,
    marginBottom: 2,
  },
  tabIconActive: {
    color: colors.accent,
  },
  tabLabel: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  tabLabelActive: {
    color: colors.accent,
  },
});
