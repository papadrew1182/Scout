import { useRef, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../../lib/styles";
import { createChoreTemplate, uploadAttachment } from "../../../lib/api";
import { useHasPermission } from "../../../lib/permissions";

// Convert a multi-line textarea into a trimmed string[]; empty lines
// are dropped. Used for the scope-contract list fields (included,
// not_included, supplies) which are stored as string[] on the model.
function linesToList(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

const CADENCE_OPTIONS = ["daily", "weekly", "monthly", "odd-even"];

export default function NewChoreTemplate() {
  const canManage = useHasPermission("chores.manage_config");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cadence, setCadence] = useState("daily");
  const [dueTime, setDueTime] = useState("");
  // Scope-contract fields. Stored as raw textarea strings here;
  // converted to string[] via linesToList on submit so the UX is
  // one-item-per-line and matches the model's list<text> shape.
  const [includedRaw, setIncludedRaw] = useState("");
  const [notIncludedRaw, setNotIncludedRaw] = useState("");
  const [doneMeansDone, setDoneMeansDone] = useState("");
  const [suppliesRaw, setSuppliesRaw] = useState("");
  const [estimatedMin, setEstimatedMin] = useState("");
  const [consequenceOnMiss, setConsequenceOnMiss] = useState("");
  // Photo example: upload via uploadAttachment on selection. Store
  // the returned storage PATH on the template row (signed URLs
  // expire in 1h, so persisting one breaks within the hour).
  // Preview uses the fresh signed URL from the upload response
  // since it's still well within the 1h window at form-fill time.
  // Render-side consumers resolve path -> fresh signed URL via
  // fetchSignedUrl (see scout-ui/lib/api.ts).
  const [photoPath, setPhotoPath] = useState<string | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const handlePhotoSelected = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(null);
    setPhotoUploading(true);
    try {
      const result = await uploadAttachment(file, file.name);
      // Persist the stable path; use the short-lived signed URL only
      // for the in-form preview below.
      setPhotoPath(result.path);
      setPhotoPreviewUrl(result.signed_url);
    } catch (err: any) {
      setMsg({
        kind: "err",
        text: err?.message ?? "Photo upload failed",
      });
    } finally {
      setPhotoUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const submit = async () => {
    if (!name.trim()) {
      setMsg({ kind: "err", text: "Name is required" });
      return;
    }
    const durationParsed = estimatedMin.trim()
      ? Number.parseInt(estimatedMin.trim(), 10)
      : null;
    if (estimatedMin.trim() && (Number.isNaN(durationParsed) || (durationParsed ?? 0) < 0)) {
      setMsg({ kind: "err", text: "Estimated duration must be a non-negative number of minutes" });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      await createChoreTemplate({
        name: name.trim(),
        description: description.trim() || undefined,
        recurrence: cadence,
        // chore_templates.due_time is NOT NULL in the DB. Default to
        // end-of-day when the (optional) field is left blank so the
        // template still creates cleanly.
        due_time: dueTime.trim() || "23:59",
        // Backend CHECK constraint only allows fixed/rotating_daily/rotating_weekly.
        // Default to fixed with empty rule; an assignee picker can be
        // added later to populate assignment_rule.assigned_to.
        assignment_type: "fixed",
        assignment_rule: {},
        // Phase 3 scope-contract fields, surfaced through the API in
        // Batch 2 PR 1b. All optional; backend defaults lists to [].
        included: linesToList(includedRaw),
        not_included: linesToList(notIncludedRaw),
        done_means_done: doneMeansDone.trim() || undefined,
        supplies: linesToList(suppliesRaw),
        photo_example_url: photoPath ?? undefined,
        estimated_duration_minutes:
          durationParsed !== null && !Number.isNaN(durationParsed)
            ? durationParsed
            : undefined,
        consequence_on_miss: consequenceOnMiss.trim() || undefined,
      });
      setMsg({ kind: "ok", text: "Template created" });
      setName("");
      setDescription("");
      setCadence("daily");
      setDueTime("");
      setIncludedRaw("");
      setNotIncludedRaw("");
      setDoneMeansDone("");
      setSuppliesRaw("");
      setEstimatedMin("");
      setConsequenceOnMiss("");
      setPhotoPath(null);
      setPhotoPreviewUrl(null);
    } catch (e: any) {
      setMsg({ kind: "err", text: e?.message ?? "Failed to create" });
    } finally {
      setSaving(false);
    }
  };

  if (!canManage) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
        <Text style={styles.h1}>New Chore Template</Text>
        <Text style={styles.muted}>You do not have permission to create chore templates.</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>New Chore Template</Text>

      <View style={shared.card}>
        <Text style={styles.label}>Name</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="e.g. Clean bedroom"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Chore name"
        />

        <Text style={styles.label}>Description (optional)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={description}
          onChangeText={setDescription}
          placeholder="What does this chore involve?"
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Chore description"
        />

        <Text style={styles.label}>Cadence</Text>
        <View style={styles.chipRow}>
          {CADENCE_OPTIONS.map((opt) => (
            <Pressable
              key={opt}
              style={[styles.chip, cadence === opt && styles.chipActive]}
              onPress={() => setCadence(opt)}
              accessibilityRole="button"
              accessibilityLabel={`Cadence: ${opt}`}
            >
              <Text style={[styles.chipText, cadence === opt && styles.chipTextActive]}>
                {opt}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>Due time (optional)</Text>
        <TextInput
          style={styles.input}
          value={dueTime}
          onChangeText={setDueTime}
          placeholder="HH:MM (24h)"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Due time"
        />

        <Text style={styles.sectionHeader}>Scope contract</Text>
        <Text style={styles.sectionBlurb}>
          Spell out what the chore does and does not cover so the
          child knows where the line is. One item per line.
        </Text>

        <Text style={styles.label}>Included (one per line)</Text>
        <TextInput
          style={[styles.input, { minHeight: 80, textAlignVertical: "top" }]}
          value={includedRaw}
          onChangeText={setIncludedRaw}
          placeholder={"Make bed\nVacuum floor\nEmpty trash"}
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Included items"
        />

        <Text style={styles.label}>Not included (one per line)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={notIncludedRaw}
          onChangeText={setNotIncludedRaw}
          placeholder={"Wash windows (parents)\nDust baseboards (parents)"}
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Not included items"
        />

        <Text style={styles.label}>Done means done (optional)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={doneMeansDone}
          onChangeText={setDoneMeansDone}
          placeholder="What the finished result should look like."
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Done-means-done description"
        />

        <Text style={styles.sectionHeader}>Supporting detail</Text>

        <Text style={styles.label}>Supplies needed (one per line, optional)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={suppliesRaw}
          onChangeText={setSuppliesRaw}
          placeholder={"Vacuum\nTrash bag\nPaper towels"}
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Supplies needed"
        />

        <Text style={styles.label}>Photo example (optional)</Text>
        {Platform.OS === "web" && (
          // eslint-disable-next-line @typescript-eslint/ban-ts-comment
          // @ts-ignore — lowercase `input` is HTML-only; Platform guard keeps it web-only
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            ref={fileInputRef as any}
            onChange={handlePhotoSelected as any}
          />
        )}
        {photoPath && photoPreviewUrl ? (
          <View style={styles.photoPreview}>
            <Image
              source={{ uri: photoPreviewUrl }}
              style={styles.photoImage}
              resizeMode="cover"
              accessibilityLabel="Photo example preview"
            />
            <Pressable
              style={[styles.chip, styles.chipDanger]}
              onPress={() => {
                setPhotoPath(null);
                setPhotoPreviewUrl(null);
              }}
              disabled={saving}
              accessibilityRole="button"
            >
              <Text style={[styles.chipText, styles.chipTextDanger]}>Remove</Text>
            </Pressable>
          </View>
        ) : (
          <Pressable
            style={[styles.chip, styles.chipUpload, (photoUploading || Platform.OS !== "web") && styles.chipDisabled]}
            onPress={() => {
              if (Platform.OS !== "web") return;
              (fileInputRef.current as any)?.click();
            }}
            disabled={photoUploading || saving || Platform.OS !== "web"}
            accessibilityRole="button"
            accessibilityLabel="Upload photo example"
          >
            <Text style={styles.chipText}>
              {photoUploading
                ? "Uploading..."
                : Platform.OS === "web"
                  ? "Upload photo"
                  : "Photo upload is web-only for now"}
            </Text>
          </Pressable>
        )}

        <Text style={styles.label}>Estimated duration (minutes, optional)</Text>
        <TextInput
          style={styles.input}
          value={estimatedMin}
          onChangeText={setEstimatedMin}
          placeholder="e.g. 15"
          placeholderTextColor={colors.muted}
          editable={!saving}
          keyboardType="number-pad"
          accessibilityLabel="Estimated duration in minutes"
        />

        <Text style={styles.label}>Consequence on miss (optional)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={consequenceOnMiss}
          onChangeText={setConsequenceOnMiss}
          placeholder="What happens when the chore is skipped."
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Consequence on miss"
        />

        {msg && (
          <Text style={[styles.msg, msg.kind === "err" && styles.msgErr]}>{msg.text}</Text>
        )}

        <Pressable
          style={[styles.btn, saving && styles.btnDisabled]}
          onPress={submit}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Create template"
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.btnText}>Create template</Text>
          )}
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  muted: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  label: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fonts.body,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 14,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  chipText: { fontSize: 12, color: colors.text, fontWeight: "600", fontFamily: fonts.body },
  chipTextActive: { color: "#FFFFFF" },
  chipUpload: { alignSelf: "flex-start", marginTop: 2 },
  chipDanger: { borderColor: colors.red, alignSelf: "flex-start", marginLeft: 12 },
  chipTextDanger: { color: colors.red },
  chipDisabled: { opacity: 0.6 },
  sectionHeader: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.text,
    fontFamily: fonts.body,
    marginTop: 20,
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  sectionBlurb: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 18,
    marginBottom: 4,
  },
  photoPreview: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
  },
  photoImage: {
    width: 120,
    height: 120,
    borderRadius: 8,
    backgroundColor: colors.surfaceMuted,
  },
  msg: { fontSize: 12, color: colors.green, fontFamily: fonts.body, marginTop: 10 },
  msgErr: { color: colors.red },
  btn: {
    backgroundColor: colors.purple,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 18,
  },
  btnDisabled: { backgroundColor: colors.border },
  btnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});
