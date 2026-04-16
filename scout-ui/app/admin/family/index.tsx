/**
 * /admin/family — Family members admin screen
 *
 * Section 1: FamilyMembersSection (full member CRUD — reuses existing component)
 * Section 2: Tier assignments (role_tier_id per member via PATCH /admin/permissions/members/{id})
 *
 * Permission: family.manage_members
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { shared, colors, fonts, radii } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { fetchMembers } from "../../../lib/api";
import { FamilyMembersSection } from "../../../components/FamilyMembersSection";
import { useAuth } from "../../../lib/auth";
import { API_BASE_URL } from "../../../lib/config";

// ---------------------------------------------------------------------------
// Tier types + options
// ---------------------------------------------------------------------------

type TierKey = "admin" | "parent_peer" | "teen" | "child" | "kid";

const TIER_OPTIONS: Array<{ value: TierKey; label: string }> = [
  { value: "admin",       label: "Admin" },
  { value: "parent_peer", label: "Parent peer" },
  { value: "teen",        label: "Teen" },
  { value: "child",       label: "Child" },
  { value: "kid",         label: "Kid" },
];

// ---------------------------------------------------------------------------
// Tier assignments section
// ---------------------------------------------------------------------------

interface MemberTierState {
  memberId: string;
  firstName: string;
  currentTier: TierKey | null;
  draft: TierKey | null;
  saving: boolean;
  saved: boolean;
  error: string | null;
}

function TierRow({
  state,
  onChange,
}: {
  state: MemberTierState;
  onChange: (tier: TierKey) => void;
}) {
  return (
    <View style={tierStyles.row}>
      <View style={tierStyles.nameCol}>
        <View style={tierStyles.avatar}>
          <Text style={tierStyles.avatarText}>
            {state.firstName.slice(0, 2).toUpperCase()}
          </Text>
        </View>
        <Text style={tierStyles.name}>{state.firstName}</Text>
      </View>
      <View style={tierStyles.pillsCol}>
        {TIER_OPTIONS.map((opt) => {
          const active = state.draft === opt.value;
          return (
            <Pressable
              key={opt.value}
              style={[tierStyles.chip, active && tierStyles.chipActive]}
              onPress={() => onChange(opt.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected: active }}
            >
              <Text style={[tierStyles.chipText, active && tierStyles.chipTextActive]}>
                {opt.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <View style={tierStyles.statusCol}>
        {state.saving && <ActivityIndicator size="small" color={colors.purple} />}
        {!state.saving && state.saved && (
          <Text style={tierStyles.savedText}>Saved</Text>
        )}
        {!state.saving && state.error && (
          <Text style={tierStyles.errorText}>{state.error}</Text>
        )}
      </View>
    </View>
  );
}

function TierAssignmentsSection({ token }: { token: string | null }) {
  const [rows, setRows] = useState<MemberTierState[]>([]);
  const [loading, setLoading] = useState(true);

  const makeHeaders = useCallback(
    (): Record<string, string> =>
      token ? { Authorization: `Bearer ${token}` } : {},
    [token],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const members = await fetchMembers();
      const active = members.filter((m) => m.is_active);

      // Fetch tiers in parallel — treat 404/error as null tier
      const tierResults = await Promise.allSettled(
        active.map(async (m) => {
          const res = await fetch(
            `${API_BASE_URL}/admin/permissions/members/${m.id}`,
            { headers: makeHeaders() },
          );
          if (!res.ok) return null;
          const data = await res.json().catch(() => null);
          return (data?.role_tier_id as TierKey) ?? null;
        }),
      );

      setRows(
        active.map((m, idx) => {
          const tier =
            tierResults[idx].status === "fulfilled"
              ? (tierResults[idx] as PromiseFulfilledResult<TierKey | null>).value
              : null;
          return {
            memberId: m.id,
            firstName: m.first_name,
            currentTier: tier,
            draft: tier,
            saving: false,
            saved: false,
            error: null,
          };
        }),
      );
    } catch {
      // leave rows empty on load failure
    } finally {
      setLoading(false);
    }
  }, [makeHeaders]);

  useEffect(() => {
    load();
  }, [load]);

  const handleChange = useCallback(
    (memberId: string, tier: TierKey) => {
      setRows((prev) =>
        prev.map((r) =>
          r.memberId === memberId
            ? { ...r, draft: tier, saving: true, saved: false, error: null }
            : r,
        ),
      );

      fetch(`${API_BASE_URL}/admin/permissions/members/${memberId}`, {
        method: "PATCH",
        headers: { ...makeHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ role_tier_id: tier }),
      })
        .then(async (res) => {
          if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error((body as any)?.detail ?? `HTTP ${res.status}`);
          }
          setRows((prev) =>
            prev.map((r) =>
              r.memberId === memberId
                ? { ...r, currentTier: tier, saving: false, saved: true, error: null }
                : r,
            ),
          );
          setTimeout(() => {
            setRows((prev) =>
              prev.map((r) =>
                r.memberId === memberId ? { ...r, saved: false } : r,
              ),
            );
          }, 2000);
        })
        .catch((e: any) => {
          setRows((prev) =>
            prev.map((r) =>
              r.memberId === memberId
                ? {
                    ...r,
                    draft: r.currentTier,
                    saving: false,
                    error: e?.message ?? "Save failed",
                  }
                : r,
            ),
          );
        });
    },
    [makeHeaders],
  );

  return (
    <View style={shared.card}>
      <View style={shared.cardTitleRow}>
        <Text style={shared.cardTitle}>Tier assignments</Text>
      </View>
      <Text style={styles.sectionSubtitle}>
        Assign each member a permission tier. Tiers control what Scout surfaces
        and which actions are allowed.
      </Text>

      {loading ? (
        <ActivityIndicator size="small" color={colors.purple} style={{ marginTop: 12 }} />
      ) : rows.length === 0 ? (
        <Text style={styles.empty}>No active members found.</Text>
      ) : (
        rows.map((row) => (
          <TierRow
            key={row.memberId}
            state={row}
            onChange={(tier) => handleChange(row.memberId, tier)}
          />
        ))
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function FamilyAdmin() {
  const canManage = useHasPermission("family.manage_members");
  const { token } = useAuth();

  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Family Members</Text>
      <Text style={styles.subtitle}>
        Manage family members, sign-in accounts, and permission tiers.
      </Text>

      {/* Section 1: Full member CRUD (reuses existing component) */}
      <FamilyMembersSection />

      {/* Section 2: Tier assignments */}
      <TierAssignmentsSection token={token} />
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 48, gap: 14 },
  h1: {
    fontSize: 20,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  subtitle: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
    marginTop: -4,
  },
  sectionSubtitle: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 17,
    marginBottom: 8,
  },
  empty: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
  },
});

const tierStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  nameCol: {
    width: 80,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.purpleLight,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.purpleDeep,
    fontFamily: fonts.body,
  },
  name: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    flex: 1,
  },
  pillsCol: {
    flex: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  chip: {
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  chipActive: {
    backgroundColor: colors.purpleLight,
    borderColor: colors.purple,
  },
  chipText: {
    fontSize: 11,
    color: colors.muted,
    fontFamily: fonts.body,
  },
  chipTextActive: {
    color: colors.purpleDeep,
    fontWeight: "600",
  },
  statusCol: {
    width: 50,
    alignItems: "flex-end",
    paddingTop: 4,
  },
  savedText: {
    fontSize: 11,
    color: colors.greenText,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
  errorText: {
    fontSize: 10,
    color: colors.redText,
    fontFamily: fonts.body,
  },
});
