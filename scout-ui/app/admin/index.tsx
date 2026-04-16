import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { shared, colors, fonts } from "../../lib/styles";
import { useHasPermission } from "../../lib/permissions";

interface AdminLink {
  label: string;
  description: string;
  href: string;
  permission: string;
}

const ADMIN_SECTIONS: AdminLink[] = [
  { label: "Allowance", description: "Weekly targets, payout rules, workflow per kid", href: "/admin/allowance", permission: "allowance.manage_config" },
  { label: "Chores", description: "Routines, chore templates, point values, streak config", href: "/admin/chores", permission: "chores.manage_config" },
  { label: "Grocery", description: "Stores, categories, approval workflow", href: "/admin/grocery", permission: "grocery.manage_config" },
  { label: "Meals", description: "Plan rules, rating scale, batch cook templates", href: "/admin/meals", permission: "meals.manage_config" },
  { label: "Rewards", description: "Reward tiers, redemption rules, approval workflow", href: "/admin/rewards", permission: "rewards.manage_config" },
  { label: "Scout AI", description: "Capability toggles, moderation tiers, usage caps", href: "/admin/scout-ai", permission: "scout_ai.manage_toggles" },
  { label: "Family Members", description: "Add/remove/edit family members and their accounts", href: "/admin/family", permission: "family.manage_members" },
  { label: "Permissions", description: "Role tiers and per-member permission overrides", href: "/admin/permissions", permission: "admin.manage_permissions" },
];

export default function AdminHome() {
  const router = useRouter();

  // Unconditionally call useHasPermission for each permission (React rules of hooks)
  const perms = {
    "allowance.manage_config": useHasPermission("allowance.manage_config"),
    "chores.manage_config": useHasPermission("chores.manage_config"),
    "grocery.manage_config": useHasPermission("grocery.manage_config"),
    "meals.manage_config": useHasPermission("meals.manage_config"),
    "rewards.manage_config": useHasPermission("rewards.manage_config"),
    "scout_ai.manage_toggles": useHasPermission("scout_ai.manage_toggles"),
    "family.manage_members": useHasPermission("family.manage_members"),
    "admin.manage_permissions": useHasPermission("admin.manage_permissions"),
  };

  const visible = ADMIN_SECTIONS.filter((section) => perms[section.permission as keyof typeof perms]);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Admin</Text>
      <Text style={styles.intro}>Configure how Scout behaves for your family.</Text>
      <View style={{ gap: 10 }}>
        {visible.map((section) => (
          <Pressable
            key={section.href}
            style={[shared.card, styles.sectionCard]}
            onPress={() => router.push(section.href as any)}
            accessibilityRole="link"
            accessibilityLabel={`Open ${section.label} admin`}
          >
            <Text style={styles.sectionLabel}>{section.label}</Text>
            <Text style={styles.sectionDesc}>{section.description}</Text>
          </Pressable>
        ))}
      </View>
      {visible.length === 0 && (
        <View style={shared.card}>
          <Text style={styles.empty}>No admin sections available for your account.</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 20,
    paddingBottom: 48,
    gap: 14,
  },
  h1: {
    fontSize: 20,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  intro: {
    fontSize: 14,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 20,
  },
  sectionCard: {
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  sectionLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  sectionDesc: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 18,
    marginTop: 4,
  },
  empty: {
    fontSize: 14,
    color: colors.muted,
    fontFamily: fonts.body,
    textAlign: "center",
  },
});
