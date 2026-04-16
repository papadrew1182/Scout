import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect } from "expo-router";

import { useAuth } from "../../lib/auth";
import { fetchMembers } from "../../lib/api";
import { colors } from "../../lib/styles";
import type { FamilyMember } from "../../lib/types";

export default function ChildIndex() {
  const { member } = useAuth();
  const [target, setTarget] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    // If the current user is a child, redirect to their own /child/:id.
    if (member?.role === "child") {
      setTarget(`/child/${member.member_id}`);
      return;
    }
    // If the current user is an adult, redirect to the first kid.
    fetchMembers()
      .then((all) => {
        const firstKid = all.find((m) => m.role === "child" && m.is_active);
        if (firstKid) {
          setTarget(`/child/${firstKid.id}`);
        } else {
          setError(true);
        }
      })
      .catch(() => setError(true));
  }, [member]);

  if (target) return <Redirect href={target as any} />;
  if (error) return <Redirect href="/" />; // fallback: no kids in family
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
      <ActivityIndicator size="large" color={colors.purple} />
    </View>
  );
}
