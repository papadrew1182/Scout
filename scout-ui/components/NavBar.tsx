import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { useState } from "react";

import { colors, fonts } from "../lib/styles";
import { useIsDesktop } from "../lib/breakpoint";
import { useAuth } from "../lib/auth";
import { useHasPermission } from "../lib/permissions";

const BASE_LINKS = [
  { href: "/",         label: "Home" },
  { href: "/personal", label: "Personal" },
  { href: "/parent",   label: "Parent" },
  { href: "/meals",    label: "Meals" },
  { href: "/grocery",  label: "Grocery" },
  { href: "/child",    label: "Child" },
  { href: "/settings", label: "Settings" },
] as const;

const ADMIN_LINK = { href: "/admin", label: "Admin" } as const;

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
  const { logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  // Check for admin access
  const canViewConfig = useHasPermission("admin.view_config");
  const canViewPermissions = useHasPermission("admin.view_permissions");
  const canManageMembers = useHasPermission("family.manage_members");
  const hasAdminAccess = canViewConfig || canViewPermissions || canManageMembers;

  // Build the links array dynamically
  const LINKS = hasAdminAccess ? [...BASE_LINKS, ADMIN_LINK] : BASE_LINKS;

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href === "/child") return pathname === "/child" || pathname.startsWith("/child/");
    if (href === "/admin") return pathname === "/admin" || pathname.startsWith("/admin/");
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <View style={styles.bar}>
      <Pressable onPress={() => router.push("/")} style={styles.logoBtn} accessibilityRole="link" accessibilityLabel="Scout home">
        <Text style={styles.logo}>
          SC<Text style={styles.logoO}>O</Text>UT
        </Text>
      </Pressable>

      {isDesktop ? (
        <View style={styles.links}>
          {LINKS.map((l) => {
            const active = isActive(l.href);
            return (
              <Pressable key={l.href} style={[styles.link, active && styles.linkActive]} onPress={() => router.push(l.href as any)} accessibilityRole="link" accessibilityState={{ selected: active }}>
                <Text style={[styles.linkText, active && styles.linkTextActive]}>{l.label}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : (
        <Pressable style={styles.menuBtn} onPress={() => { setMenuOpen(true); onMenuPress?.(); }} accessibilityRole="button" accessibilityLabel="Open menu">
          <Text style={styles.menuIcon}>☰</Text>
        </Pressable>
      )}

      {isDesktop && (
        <Pressable
          style={styles.signOut}
          onPress={logout}
          accessibilityRole="button"
          accessibilityLabel="Sign out"
        >
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      )}

      <Pressable style={styles.pill} onPress={onScoutPress} accessibilityRole="button" accessibilityLabel={pillLabel}>
        <View style={styles.pillDot} />
        <Text style={styles.pillText}>{pillLabel}</Text>
      </Pressable>

      {!isDesktop && (
        <Modal visible={menuOpen} transparent animationType="fade" onRequestClose={() => setMenuOpen(false)}>
          <Pressable
            style={styles.menuBackdrop}
            onPress={() => setMenuOpen(false)}
            accessibilityLabel="Close menu"
            accessibilityRole="button"
          >
            <View style={styles.menuSheet} onStartShouldSetResponder={() => true}>
              {LINKS.map((l) => {
                const active = isActive(l.href);
                return (
                  <Pressable
                    key={l.href}
                    style={[styles.menuItem, active && styles.menuItemActive]}
                    onPress={() => { setMenuOpen(false); router.push(l.href as any); }}
                    accessibilityRole="link"
                    accessibilityState={{ selected: active }}
                  >
                    <Text style={[styles.menuItemText, active && styles.menuItemTextActive]}>{l.label}</Text>
                  </Pressable>
                );
              })}
              <View style={styles.menuDivider} />
              <Pressable
                style={styles.menuItem}
                onPress={() => { setMenuOpen(false); logout(); }}
                accessibilityRole="button"
                accessibilityLabel="Sign out"
              >
                <Text style={[styles.menuItemText, { color: colors.red }]}>Sign out</Text>
              </Pressable>
            </View>
          </Pressable>
        </Modal>
      )}
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

  signOut: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginRight: 8,
  },
  signOutText: {
    fontSize: 11,
    color: "rgba(255,255,255,0.55)",
    fontFamily: fonts.body,
  },

  menuBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.35)",
    justifyContent: "flex-start",
  },
  menuSheet: {
    backgroundColor: colors.sidebar,
    paddingVertical: 8,
    paddingHorizontal: 0,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.08)",
  },
  menuItem: {
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  menuItemActive: {
    backgroundColor: "rgba(108,99,255,0.25)",
  },
  menuItemText: {
    fontSize: 14,
    color: "rgba(255,255,255,0.85)",
    fontFamily: fonts.body,
    fontWeight: "500",
  },
  menuItemTextActive: {
    color: "#FFFFFF",
    fontWeight: "600",
  },
  menuDivider: {
    height: 1,
    backgroundColor: "rgba(255,255,255,0.1)",
    marginVertical: 6,
    marginHorizontal: 20,
  },
});
