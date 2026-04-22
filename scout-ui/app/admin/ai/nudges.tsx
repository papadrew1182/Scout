/**
 * Sprint 05 Phase 2 + Phase 4 - /admin/ai/nudges
 *
 * Admin surface for managing family-wide proactive-nudge quiet hours
 * (Phase 2) and custom nudge rules (Phase 4). The page shell is gated
 * by `quiet_hours.manage || nudges.configure`, and each tab has its
 * own per-tab permission gate so that rescoping one permission does
 * not silently surface a 403-throwing tab.
 *
 * Quiet hours tab: gated by `quiet_hours.manage`. Reads via
 *   GET /api/admin/family-config/quiet-hours and writes via PUT on
 *   the same path. Per-member overrides are not in scope for Phase 2.
 * Rules tab: gated by `nudges.configure`. Lists/creates/patches/deletes
 *   rows in /api/admin/nudges/rules and can preview match counts via
 *   the /preview-count subresource (Phase 4).
 */

import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import {
  createNudgeRule,
  deleteNudgeRule,
  getFamilyQuietHours,
  listNudgeRules,
  patchNudgeRule,
  previewRuleCount,
  putFamilyQuietHours,
  type NudgeRule,
  type QuietHoursConfig,
  type RuleSeverity,
} from "../../../lib/nudges";
import { useHasPermission } from "../../../lib/permissions";
import { colors, fonts, shared } from "../../../lib/styles";

function minuteToHHMM(m: number): string {
  const hh = Math.floor(m / 60).toString().padStart(2, "0");
  const mm = (m % 60).toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function hhmmToMinute(s: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!match) return null;
  const h = parseInt(match[1], 10);
  const m = parseInt(match[2], 10);
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return h * 60 + m;
}

const TABS = ["quiet_hours", "rules"] as const;
type Tab = (typeof TABS)[number];

export default function AdminNudges() {
  const router = useRouter();
  const canManageQuietHours = useHasPermission("quiet_hours.manage");
  const canConfigureRules = useHasPermission("nudges.configure");
  const canAccessPage = canManageQuietHours || canConfigureRules;
  const [tab, setTab] = useState<Tab>("quiet_hours");

  // If the currently-selected tab is one the user lacks permission for,
  // default-select the one they do have. Runs when the permission hooks
  // resolve (they start false and flip true once /me returns).
  useEffect(() => {
    if (tab === "quiet_hours" && !canManageQuietHours && canConfigureRules) {
      setTab("rules");
    } else if (tab === "rules" && !canConfigureRules && canManageQuietHours) {
      setTab("quiet_hours");
    }
  }, [tab, canManageQuietHours, canConfigureRules]);

  if (!canAccessPage) {
    return (
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.h1}>Not available</Text>
        <Text style={styles.blurb}>
          Nudges admin requires the
          <Text style={styles.code}> quiet_hours.manage</Text> or
          <Text style={styles.code}> nudges.configure</Text> permission.
        </Text>
      </ScrollView>
    );
  }

  const showQuietHoursBody = tab === "quiet_hours" && canManageQuietHours;
  const showRulesBody = tab === "rules" && canConfigureRules;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.backLink}>&larr; Admin</Text>
        </Pressable>
        <Text style={styles.h1}>Nudges</Text>
      </View>

      <View style={styles.tabBar}>
        {canManageQuietHours && (
          <Pressable
            style={[styles.tabBtn, tab === "quiet_hours" && styles.tabBtnActive]}
            onPress={() => setTab("quiet_hours")}
            accessibilityRole="button"
          >
            <Text
              style={[
                styles.tabBtnText,
                tab === "quiet_hours" && styles.tabBtnTextActive,
              ]}
            >
              Quiet hours
            </Text>
          </Pressable>
        )}
        {canConfigureRules && (
          <Pressable
            style={[styles.tabBtn, tab === "rules" && styles.tabBtnActive]}
            onPress={() => setTab("rules")}
            accessibilityRole="button"
          >
            <Text
              style={[
                styles.tabBtnText,
                tab === "rules" && styles.tabBtnTextActive,
              ]}
            >
              Rules
            </Text>
          </Pressable>
        )}
      </View>

      {showQuietHoursBody && <QuietHoursSection />}
      {showRulesBody && <RulesSection />}
      {!showQuietHoursBody && !showRulesBody && (
        <Text style={styles.blurb}>This tab is not available for your role.</Text>
      )}
    </ScrollView>
  );
}

function QuietHoursSection() {
  const [config, setConfig] = useState<QuietHoursConfig | null>(null);
  const [startStr, setStartStr] = useState("22:00");
  const [endStr, setEndStr] = useState("07:00");
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getFamilyQuietHours()
      .then((c) => {
        setConfig(c);
        setStartStr(minuteToHHMM(c.start_local_minute));
        setEndStr(minuteToHHMM(c.end_local_minute));
      })
      .catch(() => setError("Failed to load quiet hours."));
  }, []);

  const handleSave = async () => {
    setError(null);
    const start = hhmmToMinute(startStr);
    const end = hhmmToMinute(endStr);
    if (start === null || end === null) {
      setError("Use HH:MM format (00:00 to 23:59).");
      return;
    }
    if (start === end) {
      setError("Start and end must differ.");
      return;
    }
    setSaving(true);
    try {
      const updated = await putFamilyQuietHours(start, end);
      setConfig(updated);
      setSavedAt(new Date());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Quiet hours</Text>
      <Text style={styles.blurb}>
        During quiet hours, low-severity nudges are suppressed and
        normal-severity nudges are held until the window ends.
        High-severity nudges are delivered anyway. Per-family window;
        per-member overrides ship in a later phase.
      </Text>

      {config === null && !error && (
        <ActivityIndicator color={colors.muted} style={{ marginTop: 8 }} />
      )}

      {config !== null && (
        <>
          <View style={styles.row}>
            <View style={styles.col}>
              <Text style={styles.label}>Start (local time)</Text>
              <TextInput
                style={styles.input}
                value={startStr}
                onChangeText={setStartStr}
                placeholder="22:00"
                accessibilityLabel="Quiet hours start (HH:MM)"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.label}>End (local time)</Text>
              <TextInput
                style={styles.input}
                value={endStr}
                onChangeText={setEndStr}
                placeholder="07:00"
                accessibilityLabel="Quiet hours end (HH:MM)"
              />
            </View>
          </View>

          {error && <Text style={styles.errorText}>{error}</Text>}

          <Pressable
            style={[styles.saveBtn, saving && styles.saveBtnBusy]}
            onPress={handleSave}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel="Save quiet hours"
          >
            <Text style={styles.saveBtnText}>
              {saving ? "Saving..." : "Save"}
            </Text>
          </Pressable>

          {savedAt !== null && !error && (
            <Text style={styles.savedText}>
              Saved at {savedAt.toLocaleTimeString()}
            </Text>
          )}

          {config.is_default && (
            <Text style={styles.helperText}>
              Currently using the default 22:00 - 07:00 window. Your next
              save will persist a custom window for your family.
            </Text>
          )}
        </>
      )}
    </View>
  );
}

function RulesSection() {
  const [rules, setRules] = useState<NudgeRule[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    template_sql: "",
    severity: "normal" as RuleSeverity,
    default_lead_time_minutes: 0,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [previewByRule, setPreviewByRule] = useState<Record<string, string>>(
    {},
  );

  const load = async () => {
    try {
      setRules(await listNudgeRules());
      setLoadError(null);
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setFormError(null);
    try {
      await createNudgeRule({
        name: form.name,
        template_sql: form.template_sql,
        severity: form.severity,
        default_lead_time_minutes: form.default_lead_time_minutes,
      });
      setForm({
        name: "",
        template_sql: "",
        severity: "normal",
        default_lead_time_minutes: 0,
      });
      setFormOpen(false);
      await load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async (rule: NudgeRule) => {
    try {
      const res = await previewRuleCount(rule.id);
      setPreviewByRule({
        ...previewByRule,
        [rule.id]: res.error
          ? `Error: ${res.error}`
          : `Matches: ${res.count}${res.capped ? " (capped)" : ""}`,
      });
    } catch (e: unknown) {
      setPreviewByRule({
        ...previewByRule,
        [rule.id]: e instanceof Error ? e.message : "Preview failed",
      });
    }
  };

  const handleToggleActive = async (rule: NudgeRule) => {
    await patchNudgeRule(rule.id, { is_active: !rule.is_active });
    await load();
  };

  const handleDelete = async (rule: NudgeRule) => {
    // Use window.confirm on web; fall through if unavailable.
    if (
      typeof window !== "undefined" &&
      typeof window.confirm === "function"
    ) {
      if (!window.confirm(`Delete rule "${rule.name}"?`)) return;
    }
    await deleteNudgeRule(rule.id);
    await load();
  };

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Custom nudge rules</Text>
      <Text style={styles.blurb}>
        Scout will run each active rule on every scheduler tick and create
        nudges for any rows it returns. SQL must SELECT the four columns
        member_id, entity_id, entity_kind, scheduled_for. Only SELECTs
        from approved tables are accepted. See docs.
      </Text>

      <Pressable
        style={styles.addBtn}
        onPress={() => setFormOpen((v) => !v)}
        accessibilityRole="button"
      >
        <Text style={styles.addBtnText}>
          {formOpen ? "Cancel" : "Add rule"}
        </Text>
      </Pressable>

      {formOpen && (
        <View style={styles.form}>
          <Text style={styles.label}>Name</Text>
          <TextInput
            style={styles.input}
            value={form.name}
            onChangeText={(v) => setForm({ ...form, name: v })}
          />

          <Text style={styles.label}>SQL template</Text>
          <TextInput
            style={[styles.input, styles.textarea]}
            multiline
            numberOfLines={6}
            value={form.template_sql}
            onChangeText={(v) => setForm({ ...form, template_sql: v })}
            placeholder={
              "SELECT assigned_to AS member_id, id AS entity_id, 'personal_task' AS entity_kind, due_at AS scheduled_for FROM personal_tasks WHERE status = 'pending' LIMIT 100"
            }
          />
          <Text style={styles.helperText}>
            SQL must SELECT the four columns member_id, entity_id,
            entity_kind, scheduled_for. Only SELECTs from approved tables
            are accepted.
          </Text>

          <Text style={styles.label}>Severity</Text>
          <View style={styles.row}>
            {(["low", "normal", "high"] as RuleSeverity[]).map((s) => (
              <Pressable
                key={s}
                style={[styles.chip, form.severity === s && styles.chipActive]}
                onPress={() => setForm({ ...form, severity: s })}
              >
                <Text
                  style={[
                    styles.chipText,
                    form.severity === s && styles.chipTextActive,
                  ]}
                >
                  {s}
                </Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.label}>Default lead time (minutes)</Text>
          <TextInput
            style={styles.input}
            value={String(form.default_lead_time_minutes)}
            onChangeText={(v) =>
              setForm({ ...form, default_lead_time_minutes: Number(v) || 0 })
            }
            keyboardType="numeric"
          />

          {formError && <Text style={styles.errorText}>{formError}</Text>}

          <Pressable
            style={[styles.saveBtn, saving && styles.saveBtnBusy]}
            onPress={handleSave}
            disabled={saving}
            accessibilityRole="button"
          >
            <Text style={styles.saveBtnText}>
              {saving ? "Saving..." : "Save rule"}
            </Text>
          </Pressable>
        </View>
      )}

      {rules === null && !loadError && (
        <ActivityIndicator color={colors.muted} style={{ marginTop: 10 }} />
      )}
      {loadError && <Text style={styles.errorText}>{loadError}</Text>}

      {rules !== null && rules.length === 0 && (
        <Text style={styles.blurb}>No rules yet.</Text>
      )}

      {rules !== null &&
        rules.map((rule) => (
          <View key={rule.id} style={styles.ruleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.ruleName}>{rule.name}</Text>
              <Text style={styles.ruleMeta}>
                severity: {rule.severity}  ·  lead:{" "}
                {rule.default_lead_time_minutes}m  ·{" "}
                {rule.is_active ? "active" : "paused"}
              </Text>
              {previewByRule[rule.id] && (
                <Text style={styles.rulePreview}>
                  {previewByRule[rule.id]}
                </Text>
              )}
            </View>
            <View style={styles.rowBtns}>
              <Pressable
                style={styles.smallBtn}
                onPress={() => handlePreview(rule)}
                accessibilityRole="button"
              >
                <Text style={styles.smallBtnText}>Preview</Text>
              </Pressable>
              <Pressable
                style={styles.smallBtn}
                onPress={() => handleToggleActive(rule)}
                accessibilityRole="button"
              >
                <Text style={styles.smallBtnText}>
                  {rule.is_active ? "Pause" : "Resume"}
                </Text>
              </Pressable>
              <Pressable
                style={[styles.smallBtn, styles.smallBtnDanger]}
                onPress={() => handleDelete(rule)}
                accessibilityRole="button"
              >
                <Text style={[styles.smallBtnText, styles.smallBtnTextDanger]}>
                  Delete
                </Text>
              </Pressable>
            </View>
          </View>
        ))}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  headerRow: { gap: 6 },
  backLink: { color: colors.muted, fontSize: 14, fontFamily: fonts.body },
  h1: {
    fontSize: 22,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  blurb: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: fonts.body,
  },
  code: {
    fontFamily: "monospace",
    color: colors.text,
  },
  row: { flexDirection: "row", gap: 12, marginTop: 8 },
  col: { flex: 1 },
  label: {
    color: colors.muted,
    fontSize: 12,
    marginBottom: 4,
    marginTop: 8,
    fontFamily: fonts.body,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 8,
    fontSize: 14,
    color: colors.text,
    fontFamily: fonts.body,
  },
  textarea: {
    minHeight: 120,
    textAlignVertical: "top",
    fontFamily: "monospace",
  },
  errorText: {
    color: "#dc2626",
    fontSize: 13,
    marginTop: 8,
    fontFamily: fonts.body,
  },
  saveBtn: {
    marginTop: 14,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#1f2937",
    alignSelf: "flex-start",
  },
  saveBtnBusy: { opacity: 0.6 },
  saveBtnText: {
    color: "#ffffff",
    fontSize: 14,
    fontFamily: fonts.body,
  },
  savedText: {
    color: "#16a34a",
    fontSize: 13,
    marginTop: 10,
    fontFamily: fonts.body,
  },
  helperText: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 6,
    fontFamily: fonts.body,
    fontStyle: "italic",
  },
  // Tab bar
  tabBar: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 4,
  },
  tabBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "transparent",
  },
  tabBtnActive: {
    backgroundColor: "#1f2937",
    borderColor: "#1f2937",
  },
  tabBtnText: {
    color: colors.text,
    fontSize: 13,
    fontFamily: fonts.body,
  },
  tabBtnTextActive: {
    color: "#ffffff",
  },
  // Rules section
  addBtn: {
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    alignSelf: "flex-start",
  },
  addBtnText: {
    color: colors.text,
    fontSize: 13,
    fontFamily: fonts.body,
  },
  form: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "transparent",
  },
  chipActive: {
    backgroundColor: "#1f2937",
    borderColor: "#1f2937",
  },
  chipText: {
    color: colors.text,
    fontSize: 13,
    fontFamily: fonts.body,
  },
  chipTextActive: {
    color: "#ffffff",
  },
  ruleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  ruleName: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
  ruleMeta: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 2,
    fontFamily: fonts.body,
  },
  rulePreview: {
    color: colors.text,
    fontSize: 12,
    marginTop: 4,
    fontFamily: fonts.body,
  },
  rowBtns: {
    flexDirection: "row",
    gap: 6,
    flexWrap: "wrap",
  },
  smallBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.border,
  },
  smallBtnDanger: {
    borderColor: "#dc2626",
  },
  smallBtnText: {
    color: colors.text,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  smallBtnTextDanger: {
    color: "#dc2626",
  },
});
