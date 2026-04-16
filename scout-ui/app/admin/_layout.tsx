import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Slot, Redirect } from "expo-router";

import { useHasPermission, usePermissionsReady } from "../../lib/permissions";
import { colors } from "../../lib/styles";

export default function AdminLayout() {
  // Defer until permissions load, then check admin-tier membership
  // (holder of any admin.* permission).
  const ready = usePermissionsReady();
  const canViewConfig = useHasPermission("admin.view_config");
  const canViewPermissions = useHasPermission("admin.view_permissions");
  const canManageMembers = useHasPermission("family.manage_members");

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color={colors.purple} />
      </View>
    );
  }

  const hasAnyAdminAccess = canViewConfig || canViewPermissions || canManageMembers;
  if (!hasAnyAdminAccess) {
    return <Redirect href="/" />;
  }

  return <Slot />;
}
