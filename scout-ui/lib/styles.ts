/**
 * Scout design system v2 — purple-forward, DM Sans / DM Mono.
 * Source of truth: scout_mockups.html.
 */
import { StyleSheet } from "react-native";

export const colors = {
  // Brand
  purple: "#6C63FF",
  purpleLight: "#EEEDFE",
  purpleMid: "#AFA9EC",
  purpleDeep: "#534AB7",

  // Surfaces
  bg: "#F4F3FC",
  card: "#FFFFFF",
  sidebar: "#1A1830",
  border: "#E8E6F4",

  // Text
  text: "#1A1830",
  muted: "#8B89A8",

  // Status
  green: "#22C55E",
  greenBg: "#DCFCE7",
  greenText: "#166534",
  amber: "#F59E0B",
  amberBg: "#FEF3C7",
  amberText: "#92400E",
  red: "#EF4444",
  redBg: "#FEE2E2",
  redText: "#991B1B",
  teal: "#14B8A6",
  tealBg: "#CCFBF1",
  tealText: "#115E59",

  // Avatar tints (kid color slots from mockup)
  avPurpleBg: "#EEEDFE",
  avPurpleText: "#534AB7",
  avTealBg: "#E1F5EE",
  avTealText: "#0F6E56",
  avAmberBg: "#FAEEDA",
  avAmberText: "#854F0B",
  avCoralBg: "#FAECE7",
  avCoralText: "#993C1D",

  // ---- Compatibility shims for any leftover legacy imports ----
  // These point to the closest new-system equivalent so pages that
  // haven't been rewritten yet still compile. Remove once every
  // page is on the new design system.
  //
  // NOTE: Most shim values duplicate a new-system token, but these
  // five hex values are LEGACY-ONLY (no new-system equivalent):
  //   #5C5478  textSecondary, buttonMutedText
  //   #F0EBF5  surfaceMuted, buttonMuted
  //   #B0A8C0  textPlaceholder, buttonDisabledText
  //   #0984E3  info
  //   #E8F4FD  infoBg
  // Later page rewrites should decide replacements consciously, not
  // pick one of these by default.
  accent: "#6C63FF",
  accentBg: "#EEEDFE",
  accentLight: "#AFA9EC",
  textPrimary: "#1A1830",
  textSecondary: "#5C5478",
  textMuted: "#8B89A8",
  textPlaceholder: "#B0A8C0",
  cardBorder: "#E8E6F4",
  divider: "#E8E6F4",
  surfaceElevated: "#FFFFFF",
  surfaceMuted: "#F0EBF5",
  positive: "#22C55E",
  positiveBg: "#DCFCE7",
  warning: "#F59E0B",
  warningBg: "#FEF3C7",
  negative: "#EF4444",
  negativeBg: "#FEE2E2",
  info: "#0984E3",
  infoBg: "#E8F4FD",
  buttonPrimary: "#6C63FF",
  buttonPrimaryText: "#FFFFFF",
  buttonMuted: "#F0EBF5",
  buttonMutedText: "#5C5478",
  buttonDisabledBg: "#E8E6F4",
  buttonDisabledText: "#B0A8C0",
  msgSuccess: "#DCFCE7",
  msgSuccessBorder: "#22C55E",
  msgSuccessText: "#166534",
  msgError: "#FEE2E2",
  msgErrorBorder: "#EF4444",
  msgErrorText: "#991B1B",
} as const;

export const fonts = {
  body: "DMSans_400Regular",
  bodyMedium: "DMSans_500Medium",
  bodySemi: "DMSans_600SemiBold",
  mono: "DMMono_400Regular",
  monoMedium: "DMMono_500Medium",
} as const;

export const radii = { sm: 6, md: 8, lg: 10, xl: 14, pill: 999 } as const;
export const space = { xs: 4, sm: 6, md: 8, lg: 10, xl: 14, xxl: 18, xxxl: 24 } as const;

const cardShadow = {
  shadowColor: "#1A1830",
  shadowOffset: { width: 0, height: 1 },
  shadowOpacity: 0.06,
  shadowRadius: 4,
  elevation: 2,
};

export const shared = StyleSheet.create({
  pageContainer: { flex: 1, backgroundColor: colors.bg },
  pageContent: { padding: 20, paddingBottom: 48, gap: 14 },
  pageCenter: { flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" },

  card: {
    backgroundColor: colors.card,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    ...cardShadow,
  },
  cardTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  cardAction: { fontSize: 11, color: colors.purple, fontWeight: "500" },

  sectionHead: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    paddingTop: 6,
    paddingBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    marginBottom: 4,
  },

  pageH1: { fontSize: 20, fontWeight: "600", color: colors.text },
  pageEyebrow: { fontSize: 11, color: colors.muted },

  rowDivider: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  rowLast: { borderBottomWidth: 0 },

  // Compat (used by un-rewritten pages until they're updated)
  pageHeader: { padding: 20, paddingBottom: 0 },
  headerBlock: { marginBottom: 24 },
  headerEyebrow: { color: colors.purple, fontSize: 11, fontWeight: "700", letterSpacing: 1.5, textTransform: "uppercase" },
  headerTitle: { color: colors.text, fontSize: 28, fontWeight: "700", marginTop: 4, letterSpacing: -0.5 },
  headerSubtitle: { color: colors.muted, fontSize: 13, marginTop: 6 },
  sectionTitle: { color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 1.5, marginTop: 28, marginBottom: 12 },
  cardRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardSubtle: { color: colors.muted, fontSize: 13, marginTop: 4 },
  emptyText: { color: colors.muted, fontSize: 14 },
  errorText: { color: colors.red, fontSize: 13 },
  errorLarge: { color: colors.red, fontSize: 16 },
  itemList: { gap: 10 },
  itemRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  itemMain: { flex: 1, paddingRight: 10 },
  itemTitle: { color: colors.text, fontSize: 14, fontWeight: "500" },
  itemMeta: { color: colors.muted, fontSize: 12, marginTop: 2 },
  itemBadge: { color: colors.muted, fontSize: 10, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5 },
  mealType: { color: colors.purple, fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, width: 80 },
  spinner: { marginTop: 8, alignSelf: "flex-start" },
  msgBox: { backgroundColor: colors.greenBg, borderLeftWidth: 3, borderLeftColor: colors.green, borderRadius: 8, padding: 14, marginBottom: 16 },
  msgBoxError: { backgroundColor: colors.redBg, borderLeftColor: colors.red },
  msgText: { color: colors.greenText, fontSize: 13, lineHeight: 18 },
  msgTextError: { color: colors.redText },
  button: { backgroundColor: colors.purple, borderRadius: 10, paddingVertical: 14, alignItems: "center", marginTop: 16, marginBottom: 8 },
  buttonText: { color: "#FFFFFF", fontSize: 15, fontWeight: "700", letterSpacing: 0.3 },
  buttonDisabled: { backgroundColor: colors.border },
  buttonTextDisabled: { color: colors.muted },
  buttonRow: { flexDirection: "row", gap: 8, marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.border },
  buttonSmall: { flex: 1, backgroundColor: colors.purpleLight, borderRadius: 8, paddingVertical: 9, alignItems: "center" },
  buttonSmallText: { color: colors.purpleDeep, fontSize: 12, fontWeight: "600", letterSpacing: 0.3 },
  statBig: { color: colors.text, fontSize: 22, fontWeight: "700", fontVariant: ["tabular-nums"] as const },
  statBigMuted: { color: colors.muted, fontSize: 18, fontWeight: "500" },
});
