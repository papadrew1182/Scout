/**
 * Scout design system — derived from Rex OS visual language.
 *
 * Tokens renamed from --rex-* to scout namespace.
 * Light theme: clean backgrounds, white cards, soft shadows.
 * Typography: Syne for headings, DM Sans for body (loaded via Expo fonts
 * when available — falls back to system fonts).
 */
import { StyleSheet } from "react-native";

// ---- Color tokens (Rex OS → Scout) ----
export const colors = {
  // Backgrounds
  bg: "#F8F5FC",
  card: "#FFFFFF",
  cardBorder: "#E8E0F0",
  divider: "#E8E0F0",
  surfaceElevated: "#FFFFFF",
  surfaceMuted: "#F0EBF5",

  // Text
  textPrimary: "#1A1135",
  textSecondary: "#5C5478",
  textMuted: "#8B83A0",
  textPlaceholder: "#B0A8C0",

  // Brand / accent
  accent: "#6C5CE7",
  accentLight: "#A29BFE",
  accentBg: "#EDE9FE",

  // Status
  positive: "#00B894",
  positiveBg: "#E6F9F3",
  warning: "#F39C12",
  warningBg: "#FEF5E7",
  negative: "#E74C3C",
  negativeBg: "#FDEDEB",
  info: "#0984E3",
  infoBg: "#E8F4FD",

  // Buttons
  buttonPrimary: "#6C5CE7",
  buttonPrimaryText: "#FFFFFF",
  buttonMuted: "#F0EBF5",
  buttonMutedText: "#5C5478",
  buttonDisabledBg: "#E8E0F0",
  buttonDisabledText: "#B0A8C0",

  // Messages
  msgSuccess: "#E6F9F3",
  msgSuccessBorder: "#00B894",
  msgSuccessText: "#00866B",
  msgError: "#FDEDEB",
  msgErrorBorder: "#E74C3C",
  msgErrorText: "#C0392B",
} as const;

// ---- Shadows ----
const cardShadow = {
  shadowColor: "#1A1135",
  shadowOffset: { width: 0, height: 1 },
  shadowOpacity: 0.06,
  shadowRadius: 4,
  elevation: 2,
};

// ---- Shared styles ----
export const shared = StyleSheet.create({
  // Page
  pageContainer: { flex: 1, backgroundColor: colors.bg },
  pageContent: { padding: 20, paddingBottom: 48 },
  pageCenter: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: "center",
    alignItems: "center",
  },

  // Header
  headerBlock: { marginBottom: 24 },
  headerEyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "700",
    marginTop: 4,
    letterSpacing: -0.5,
    // fontFamily: "Syne" when loaded
  },
  headerSubtitle: { color: colors.textMuted, fontSize: 13, marginTop: 6 },

  // Section header
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1.5,
    marginTop: 28,
    marginBottom: 12,
  },

  // Card
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 18,
    marginBottom: 12,
    ...cardShadow,
  },
  cardRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  // Text
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: -0.2,
  },
  cardSubtle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  emptyText: { color: colors.textPlaceholder, fontSize: 14 },
  errorText: { color: colors.negative, fontSize: 13 },
  errorLarge: { color: colors.negative, fontSize: 16 },

  // Items (used in lists inside cards)
  itemList: { gap: 10 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  itemMain: { flex: 1, paddingRight: 10 },
  itemTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "500" },
  itemMeta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  itemBadge: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },

  // Meal type label
  mealType: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    width: 80,
  },

  // Loading
  spinner: { marginTop: 8, alignSelf: "flex-start" },

  // Status message (left-accent bar pattern from Rex)
  msgBox: {
    backgroundColor: colors.msgSuccess,
    borderLeftWidth: 3,
    borderLeftColor: colors.msgSuccessBorder,
    borderRadius: 8,
    padding: 14,
    marginBottom: 16,
  },
  msgBoxError: {
    backgroundColor: colors.msgError,
    borderLeftColor: colors.msgErrorBorder,
  },
  msgText: { color: colors.msgSuccessText, fontSize: 13, lineHeight: 18 },
  msgTextError: { color: colors.msgErrorText },

  // Buttons
  button: {
    backgroundColor: colors.buttonPrimary,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 16,
    marginBottom: 8,
  },
  buttonText: {
    color: colors.buttonPrimaryText,
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  buttonDisabled: { backgroundColor: colors.buttonDisabledBg },
  buttonTextDisabled: { color: colors.buttonDisabledText },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  buttonSmall: {
    flex: 1,
    backgroundColor: colors.buttonMuted,
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: "center",
  },
  buttonSmallText: {
    color: colors.buttonMutedText,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 0.3,
  },

  // Stat typography
  statBig: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "700",
    fontVariant: ["tabular-nums"] as any,
  },
  statBigMuted: {
    color: colors.textPlaceholder,
    fontSize: 18,
    fontWeight: "500",
  },
});
