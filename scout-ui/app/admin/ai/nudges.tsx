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
import {
  deleteMemberConfig,
  fetchAllMemberConfigForKey,
  fetchMembers,
  putMemberConfig,
  type MemberConfigRow,
} from "../../../lib/api";
import type { FamilyMember } from "../../../lib/types";
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

// Pre-filled example snippets for the rule SQL template field.
// Every snippet exercises a whitelisted table and returns the four
// required columns (member_id, entity_id, entity_kind, scheduled_for).
// Operators start from one and edit the specifics rather than writing
// from scratch against a blank text area. If you add snippets here,
// keep them under 200 chars and do not reference tables outside the
// Phase 4 validator allowlist (backend/app/services/nudge_rule_validator.py).
const RULE_SQL_SNIPPETS: Array<{ name: string; sql: string }> = [
  {
    name: "Overdue personal tasks",
    sql:
      "SELECT assigned_to AS member_id, id AS entity_id, " +
      "'personal_task' AS entity_kind, due_at AS scheduled_for " +
      "FROM personal_tasks WHERE status = 'pending' " +
      "AND due_at < now() - interval '1 day' LIMIT 100",
  },
  {
    name: "Bills due in 3 days",
    sql:
      "SELECT owner_member_id AS member_id, id AS entity_id, " +
      "'bill' AS entity_kind, due_date AS scheduled_for FROM bills " +
      "WHERE status != 'paid' AND due_date BETWEEN current_date " +
      "AND current_date + interval '3 days' LIMIT 100",
  },
  {
    name: "Events starting in 30 min",
    sql:
      "SELECT ea.family_member_id AS member_id, e.id AS entity_id, " +
      "'event' AS entity_kind, e.starts_at AS scheduled_for " +
      "FROM events e JOIN event_attendees ea ON ea.event_id = e.id " +
      "WHERE e.starts_at BETWEEN now() AND now() + interval '30 minutes' " +
      "LIMIT 100",
  },
  {
    name: "Missed routine instances today",
    sql:
      "SELECT family_member_id AS member_id, id AS entity_id, " +
      "'task_instance' AS entity_kind, due_at AS scheduled_for " +
      "FROM task_instances WHERE is_completed = false " +
      "AND due_at < now() AND due_at > now() - interval '24 hours' LIMIT 100",
  },
];

export default function AdminNudges() {
  const router = useRouter();
  const canManageQuietHours = useHasPermission("quiet_hours.manage");
  const canConfigureRules = useHasPermission("nudges.configure");
  const canAccessPage = canManageQuietHours || canConfigureRules;
  const [tabRaw, setTab] = useState<Tab>("quiet_hours");

  // Derive the effective tab from the user's last selection AND their
  // current permissions. If they picked a tab they lack permission for
  // (or permissions resolved after mount with only one side granted),
  // fall back to the one they can actually see. Deriving here (instead
  // of useEffect + setState) avoids a one-render flash of the "not
  // available" fallback body during the state-flip tick.
  let tab: Tab = tabRaw;
  if (tabRaw === "quiet_hours" && !canManageQuietHours && canConfigureRules) {
    tab = "rules";
  } else if (tabRaw === "rules" && !canConfigureRules && canManageQuietHours) {
    tab = "quiet_hours";
  }

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
      {showQuietHoursBody && <MemberQuietHoursOverridesSection />}
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
      <Text style={shared.cardTitle}>Quiet hours (family default)</Text>
      <Text style={styles.blurb}>
        During quiet hours, low-severity nudges are suppressed and
        normal-severity nudges are held until the window ends.
        High-severity nudges are delivered anyway. This window is the
        family default; per-member overrides are managed in the card
        below.
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

// Per-member quiet-hours override editor.
//
// Reads member_config rows with key='nudges.quiet_hours'. Backend
// resolution in nudges_service.py:_resolve_quiet_hours_window lets
// any member override win over the family default; absence of a row
// means the member inherits the family default.
const QUIET_HOURS_KEY = "nudges.quiet_hours";

interface OverrideValue {
  start_local_minute: number;
  end_local_minute: number;
}

function parseOverride(raw: unknown): OverrideValue | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const s = typeof o.start_local_minute === "number" ? o.start_local_minute : null;
  const e = typeof o.end_local_minute === "number" ? o.end_local_minute : null;
  if (s === null || e === null) return null;
  return { start_local_minute: s, end_local_minute: e };
}

function MemberQuietHoursOverridesSection() {
  const [members, setMembers] = useState<FamilyMember[] | null>(null);
  const [overrides, setOverrides] = useState<Record<string, OverrideValue>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftStart, setDraftStart] = useState("22:00");
  const [draftEnd, setDraftEnd] = useState("07:00");
  const [rowError, setRowError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [mems, rows] = await Promise.all([
        fetchMembers(),
        fetchAllMemberConfigForKey(QUIET_HOURS_KEY),
      ]);
      setMembers(mems.filter((m) => m.is_active));
      const map: Record<string, OverrideValue> = {};
      rows.forEach((r: MemberConfigRow) => {
        const parsed = parseOverride(r.value);
        if (parsed) map[r.member_id] = parsed;
      });
      setOverrides(map);
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Failed to load overrides.");
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const startEdit = (memberId: string) => {
    setRowError(null);
    const existing = overrides[memberId];
    if (existing) {
      setDraftStart(minuteToHHMM(existing.start_local_minute));
      setDraftEnd(minuteToHHMM(existing.end_local_minute));
    } else {
      setDraftStart("22:00");
      setDraftEnd("07:00");
    }
    setEditingId(memberId);
  };

  const handleSave = async (memberId: string) => {
    setRowError(null);
    const start = hhmmToMinute(draftStart);
    const end = hhmmToMinute(draftEnd);
    if (start === null || end === null) {
      setRowError("Use HH:MM format (00:00 to 23:59).");
      return;
    }
    if (start === end) {
      setRowError("Start and end must differ.");
      return;
    }
    setSavingId(memberId);
    try {
      await putMemberConfig(memberId, QUIET_HOURS_KEY, {
        start_local_minute: start,
        end_local_minute: end,
      });
      await refresh();
      setEditingId(null);
    } catch (e: unknown) {
      setRowError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSavingId(null);
    }
  };

  const handleRemove = async (memberId: string) => {
    setRowError(null);
    setSavingId(memberId);
    try {
      await deleteMemberConfig(memberId, QUIET_HOURS_KEY);
      await refresh();
      setEditingId(null);
    } catch (e: unknown) {
      setRowError(e instanceof Error ? e.message : "Remove failed.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Per-member overrides</Text>
      <Text style={styles.blurb}>
        Override the family quiet-hours window for a specific member.
        Absence of an override means the member inherits the family
        default above.
      </Text>

      {loadError && <Text style={styles.errorText}>{loadError}</Text>}
      {members === null && !loadError && (
        <ActivityIndicator color={colors.muted} style={{ marginTop: 8 }} />
      )}

      {members !== null && members.length === 0 && (
        <Text style={styles.blurb}>No active family members.</Text>
      )}

      {members !== null &&
        members.map((m) => {
          const override = overrides[m.id];
          const isEditing = editingId === m.id;
          const isSaving = savingId === m.id;
          return (
            <View key={m.id} style={styles.overrideRow}>
              <View style={styles.overrideRowHeader}>
                <Text style={styles.overrideName}>
                  {m.first_name} {m.last_name ?? ""}
                </Text>
                <Text style={styles.overrideSummary}>
                  {override
                    ? `${minuteToHHMM(override.start_local_minute)} - ${minuteToHHMM(
                        override.end_local_minute,
                      )}`
                    : "Inherits family default"}
                </Text>
              </View>

              {!isEditing && (
                <View style={styles.row}>
                  <Pressable
                    style={styles.chip}
                    onPress={() => startEdit(m.id)}
                    accessibilityRole="button"
                  >
                    <Text style={styles.chipText}>
                      {override ? "Edit" : "Add override"}
                    </Text>
                  </Pressable>
                  {override && (
                    <Pressable
                      style={styles.chip}
                      onPress={() => handleRemove(m.id)}
                      accessibilityRole="button"
                      disabled={isSaving}
                    >
                      <Text style={styles.chipText}>Remove</Text>
                    </Pressable>
                  )}
                </View>
              )}

              {isEditing && (
                <View>
                  <View style={styles.row}>
                    <View style={styles.col}>
                      <Text style={styles.label}>Start</Text>
                      <TextInput
                        style={styles.input}
                        value={draftStart}
                        onChangeText={setDraftStart}
                        placeholder="22:00"
                        autoCapitalize="none"
                      />
                    </View>
                    <View style={styles.col}>
                      <Text style={styles.label}>End</Text>
                      <TextInput
                        style={styles.input}
                        value={draftEnd}
                        onChangeText={setDraftEnd}
                        placeholder="07:00"
                        autoCapitalize="none"
                      />
                    </View>
                  </View>
                  <View style={styles.row}>
                    <Pressable
                      style={[styles.chip, styles.chipActive]}
                      onPress={() => handleSave(m.id)}
                      accessibilityRole="button"
                      disabled={isSaving}
                    >
                      <Text style={[styles.chipText, styles.chipTextActive]}>
                        {isSaving ? "Saving..." : "Save"}
                      </Text>
                    </Pressable>
                    <Pressable
                      style={styles.chip}
                      onPress={() => setEditingId(null)}
                      accessibilityRole="button"
                      disabled={isSaving}
                    >
                      <Text style={styles.chipText}>Cancel</Text>
                    </Pressable>
                  </View>
                  {rowError && editingId === m.id && (
                    <Text style={styles.errorText}>{rowError}</Text>
                  )}
                </View>
              )}
            </View>
          );
        })}
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

          <Text style={styles.label}>Start from an example</Text>
          <View style={[styles.row, { flexWrap: "wrap", gap: 6 }]}>
            {RULE_SQL_SNIPPETS.map((snip) => (
              <Pressable
                key={snip.name}
                style={styles.snippetChip}
                onPress={() => setForm({ ...form, template_sql: snip.sql })}
                accessibilityRole="button"
                accessibilityLabel={`Load snippet: ${snip.name}`}
              >
                <Text style={styles.snippetChipText}>{snip.name}</Text>
              </Pressable>
            ))}
          </View>
          <Text style={styles.helperText}>
            Loading a snippet overwrites the SQL template field. Edit
            the bound values (member names, thresholds, tables) before
            saving.
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
  snippetChip: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "#f3f4f6",
  },
  snippetChipText: {
    color: colors.text,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  overrideRow: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  overrideRowHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  overrideName: {
    fontSize: 14,
    color: colors.text,
    fontFamily: fonts.body,
    fontWeight: "500",
  },
  overrideSummary: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
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
