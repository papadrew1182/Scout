import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";

import { useAuth } from "../lib/auth";
import { useFamilyMembers } from "../lib/hooks";
import { colors } from "../lib/styles";

interface NavBarProps {
  onScoutPress?: () => void;
}

export function NavBar({ onScoutPress }: NavBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { member, logout } = useAuth();
  const [childOpen, setChildOpen] = useState(false);
  const { children, loading } = useFamilyMembers();

  const isActive = (path: string) =>
    pathname === path || pathname.startsWith(path + "/");

  return (
    <View style={styles.bar}>
      <View style={styles.brandRow}>
        <Pressable onPress={() => router.push("/")}>
          <Text style={styles.brand}>Scout</Text>
        </Pressable>
        {member && (
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{member.first_name}</Text>
            <Pressable onPress={logout}>
              <Text style={styles.logoutLink}>Sign out</Text>
            </Pressable>
          </View>
        )}
      </View>

      <View style={styles.links}>
        {onScoutPress && (
          <Pressable style={styles.scoutBtn} onPress={onScoutPress}>
            <Text style={styles.scoutBtnText}>Scout AI</Text>
          </Pressable>
        )}

        <Pressable
          style={[styles.link, isActive("/personal") && styles.linkActive]}
          onPress={() => router.push("/personal")}
        >
          <Text style={[styles.linkText, isActive("/personal") && styles.linkTextActive]}>
            Personal
          </Text>
        </Pressable>

        <Pressable
          style={[styles.link, isActive("/parent") && styles.linkActive]}
          onPress={() => router.push("/parent")}
        >
          <Text style={[styles.linkText, isActive("/parent") && styles.linkTextActive]}>
            Parent
          </Text>
        </Pressable>

        <Pressable
          style={[styles.link, isActive("/meals") && styles.linkActive]}
          onPress={() => router.push("/meals")}
        >
          <Text style={[styles.linkText, isActive("/meals") && styles.linkTextActive]}>
            Meals
          </Text>
        </Pressable>

        <Pressable
          style={[styles.link, isActive("/grocery") && styles.linkActive]}
          onPress={() => router.push("/grocery")}
        >
          <Text style={[styles.linkText, isActive("/grocery") && styles.linkTextActive]}>
            Grocery
          </Text>
        </Pressable>

        <Pressable
          style={[styles.link, isActive("/child") && styles.linkActive]}
          onPress={() => setChildOpen(!childOpen)}
        >
          <Text style={[styles.linkText, isActive("/child") && styles.linkTextActive]}>
            Child {childOpen ? "▴" : "▾"}
          </Text>
        </Pressable>

        <Pressable
          style={[styles.link, isActive("/settings") && styles.linkActive]}
          onPress={() => router.push("/settings")}
        >
          <Text style={[styles.linkText, isActive("/settings") && styles.linkTextActive]}>
            Settings
          </Text>
        </Pressable>
      </View>

      {childOpen && (
        <View style={styles.childMenu}>
          {loading && <ActivityIndicator size="small" color={colors.accent} />}
          {!loading && children.length === 0 && (
            <Text style={styles.childEmpty}>No children found</Text>
          )}
          {!loading &&
            children.map((c) => (
              <Pressable
                key={c.id}
                style={[
                  styles.childItem,
                  isActive(`/child/${c.id}`) && styles.childItemActive,
                ]}
                onPress={() => {
                  setChildOpen(false);
                  router.push(`/child/${c.id}`);
                }}
              >
                <Text
                  style={[
                    styles.childItemText,
                    isActive(`/child/${c.id}`) && styles.childItemTextActive,
                  ]}
                >
                  {c.first_name}
                </Text>
              </Pressable>
            ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.surfaceElevated,
    borderBottomWidth: 1,
    borderBottomColor: colors.cardBorder,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 12,
  },
  brandRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  userInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  userName: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "600",
  },
  logoutLink: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
  },
  brand: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  links: {
    flexDirection: "row",
    gap: 4,
  },
  link: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
  },
  linkActive: {
    backgroundColor: colors.accentBg,
  },
  linkText: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: "600",
  },
  linkTextActive: {
    color: colors.accent,
  },
  childMenu: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  childItem: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 6,
  },
  childItemActive: {
    backgroundColor: colors.accent,
  },
  childItemText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: "500",
  },
  childItemTextActive: {
    color: colors.buttonPrimaryText,
  },
  childEmpty: {
    color: colors.textPlaceholder,
    fontSize: 12,
  },
  scoutBtn: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 14,
    marginRight: 8,
  },
  scoutBtnText: {
    color: colors.buttonPrimaryText,
    fontSize: 13,
    fontWeight: "700",
  },
});
