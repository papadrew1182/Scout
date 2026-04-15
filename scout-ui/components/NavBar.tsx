import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";

import { colors, fonts } from "../lib/styles";
import { useIsDesktop } from "../lib/breakpoint";

const LINKS = [
  { href: "/",         label: "Dashboard" },
  { href: "/personal", label: "Personal" },
  { href: "/parent",   label: "Parent" },
  { href: "/meals",    label: "Meals" },
  { href: "/grocery",  label: "Grocery" },
  { href: "/child",    label: "Child" },
  { href: "/settings", label: "Settings" },
] as const;

interface NavBarProps {
  onScoutPress?: () => void;
  onMenuPress?: () => void;
  /** Override pill label (e.g. "Hey Townes!" on child surface). */
  pillLabel?: string;
}

export function NavBar({ onScoutPress, onMenuPress, pillLabel = "Scout AI" }: NavBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const isDesktop = useIsDesktop();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href === "/child") return pathname.startsWith("/child");
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <View style={styles.bar}>
      <Pressable onPress={() => router.push("/")} style={styles.logoBtn}>
        <Text style={styles.logo}>
          SC<Text style={styles.logoO}>O</Text>UT
        </Text>
      </Pressable>

      {isDesktop ? (
        <View style={styles.links}>
          {LINKS.map((l) => {
            const active = isActive(l.href);
            return (
              <Pressable key={l.href} style={[styles.link, active && styles.linkActive]} onPress={() => router.push(l.href as any)}>
                <Text style={[styles.linkText, active && styles.linkTextActive]}>{l.label}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : (
        <Pressable style={styles.menuBtn} onPress={onMenuPress}>
          <Text style={styles.menuIcon}>☰</Text>
        </Pressable>
      )}

      <Pressable style={styles.pill} onPress={onScoutPress}>
        <View style={styles.pillDot} />
        <Text style={styles.pillText}>{pillLabel}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.sidebar,
    height: 44,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    gap: 0,
  },
  logoBtn: { marginRight: 18, flexShrink: 0 },
  logo: {
    fontFamily: fonts.mono,
    fontSize: 13,
    letterSpacing: 1.5,
    color: "#FFFFFF",
    fontWeight: "500",
  },
  logoO: { color: colors.purple },

  links: { flexDirection: "row", alignItems: "center", gap: 2, flex: 1 },
  link: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 5 },
  linkActive: { backgroundColor: "rgba(108,99,255,0.25)" },
  linkText: { fontSize: 12, color: "rgba(255,255,255,0.55)", fontFamily: fonts.body },
  linkTextActive: { color: "#FFFFFF" },

  menuBtn: { flex: 1, alignItems: "flex-start", paddingLeft: 4 },
  menuIcon: { color: "#FFFFFF", fontSize: 18 },

  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 4,
    marginLeft: "auto",
  },
  pillDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.green,
  },
  pillText: { fontSize: 11, color: "rgba(255,255,255,0.75)", fontFamily: fonts.body },
});
