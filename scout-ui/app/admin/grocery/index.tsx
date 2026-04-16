/**
 * /admin/grocery — Grocery admin screen
 *
 * Section 1: Stores          — editable list (add/remove/rename + kind)
 * Section 2: Categories      — editable string list
 * Section 3: Approval workflow — toggles + auto-approve threshold
 * Section 4: Analytics stub  — coming soon
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { shared, colors, fonts, radii } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { useFamilyConfig } from "../../../lib/config";
import type {
  GroceryStore,
  GroceryStoreConfig,
  GroceryCategoryConfig,
  GroceryApprovalRules,
  StoreKind,
} from "../../../lib/grocery";
import {
  DEFAULT_STORE_CONFIG,
  DEFAULT_CATEGORY_CONFIG,
  DEFAULT_APPROVAL_RULES,
} from "../../../lib/grocery";

// ---------------------------------------------------------------------------
// Store kind options
// ---------------------------------------------------------------------------

const KIND_OPTIONS: StoreKind[] = ["bulk", "local", "online", "other"];

// ---------------------------------------------------------------------------
// StoreRow — one editable store in the Stores card
// ---------------------------------------------------------------------------

interface StoreRowProps {
  store: GroceryStore;
  onUpdate: (updated: GroceryStore) => void;
  onRemove: () => void;
}

function StoreRow({ store, onUpdate, onRemove }: StoreRowProps) {
  return (
    <View style={storeStyles.row}>
      <View style={storeStyles.fields}>
        <TextInput
          style={storeStyles.nameInput as any}
          value={store.name}
          onChangeText={(v) => onUpdate({ ...store, name: v })}
          placeholder="Store name"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Store name"
        />
        <View style={storeStyles.kindRow}>
          {KIND_OPTIONS.map((k) => (
            <Pressable
              key={k}
              style={[storeStyles.kindChip, store.kind === k && storeStyles.kindChipActive]}
              onPress={() => onUpdate({ ...store, kind: k })}
              accessibilityRole="radio"
              accessibilityState={{ selected: store.kind === k }}
            >
              <Text
                style={[
                  storeStyles.kindChipText,
                  store.kind === k && storeStyles.kindChipTextActive,
                ]}
              >
                {k}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>
      <Pressable
        style={storeStyles.removeBtn}
        onPress={onRemove}
        accessibilityRole="button"
        accessibilityLabel={`Remove ${store.name}`}
      >
        <Text style={storeStyles.removeBtnText}>Remove</Text>
      </Pressable>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function GroceryAdmin() {
  const canManage = useHasPermission("grocery.manage_config");

  // -- Stores config ---------------------------------------------------------
  const {
    value: storeConfig,
    setValue: setStoreConfig,
    loading: storesLoading,
  } = useFamilyConfig<GroceryStoreConfig>("grocery.stores", DEFAULT_STORE_CONFIG);

  const [stores, setStores] = useState<GroceryStore[]>([]);
  const [storesSaving, setStoresSaving] = useState(false);
  const [storesSaved, setStoresSaved] = useState(false);
  const [storesError, setStoresError] = useState<string | null>(null);

  useEffect(() => {
    if (!storesLoading) {
      setStores(storeConfig.stores);
    }
  }, [storesLoading, storeConfig.stores]);

  const handleSaveStores = useCallback(async () => {
    setStoresSaving(true);
    setStoresError(null);
    try {
      await setStoreConfig({ stores });
      setStoresSaved(true);
      setTimeout(() => setStoresSaved(false), 2000);
    } catch {
      setStoresError("Save failed");
    } finally {
      setStoresSaving(false);
    }
  }, [setStoreConfig, stores]);

  const handleAddStore = useCallback(() => {
    const newId = `store_${Date.now()}`;
    setStores((prev) => [...prev, { id: newId, name: "", kind: "local" }]);
  }, []);

  const handleUpdateStore = useCallback((idx: number, updated: GroceryStore) => {
    setStores((prev) => prev.map((s, i) => (i === idx ? updated : s)));
  }, []);

  const handleRemoveStore = useCallback((idx: number) => {
    setStores((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // -- Categories config -----------------------------------------------------
  const {
    value: categoryConfig,
    setValue: setCategoryConfig,
    loading: categoriesLoading,
  } = useFamilyConfig<GroceryCategoryConfig>("grocery.categories", DEFAULT_CATEGORY_CONFIG);

  const [categories, setCategories] = useState<string[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [catSaving, setCatSaving] = useState(false);
  const [catSaved, setCatSaved] = useState(false);
  const [catError, setCatError] = useState<string | null>(null);

  useEffect(() => {
    if (!categoriesLoading) {
      setCategories(categoryConfig.categories);
    }
  }, [categoriesLoading, categoryConfig.categories]);

  const handleSaveCategories = useCallback(async () => {
    setCatSaving(true);
    setCatError(null);
    try {
      await setCategoryConfig({ categories });
      setCatSaved(true);
      setTimeout(() => setCatSaved(false), 2000);
    } catch {
      setCatError("Save failed");
    } finally {
      setCatSaving(false);
    }
  }, [setCategoryConfig, categories]);

  const handleAddCategory = useCallback(() => {
    const trimmed = newCategory.trim();
    if (!trimmed) return;
    setCategories((prev) => [...prev, trimmed]);
    setNewCategory("");
  }, [newCategory]);

  const handleRemoveCategory = useCallback((idx: number) => {
    setCategories((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // -- Approval rules config -------------------------------------------------
  const {
    value: approvalRules,
    setValue: setApprovalRules,
    loading: approvalLoading,
  } = useFamilyConfig<GroceryApprovalRules>("grocery.approval_rules", DEFAULT_APPROVAL_RULES);

  const [requireChildren, setRequireChildren] = useState(true);
  const [requireTeens, setRequireTeens] = useState(false);
  const [autoApproveDollars, setAutoApproveDollars] = useState("");
  const [approvalSaving, setApprovalSaving] = useState(false);
  const [approvalSaved, setApprovalSaved] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  useEffect(() => {
    if (!approvalLoading) {
      setRequireChildren(approvalRules.require_approval_for_children);
      setRequireTeens(approvalRules.require_approval_for_teens);
      setAutoApproveDollars(String(approvalRules.auto_approve_under_cents / 100));
    }
  }, [approvalLoading, approvalRules]);

  const handleSaveApproval = useCallback(async () => {
    setApprovalSaving(true);
    setApprovalError(null);
    try {
      await setApprovalRules({
        require_approval_for_children: requireChildren,
        require_approval_for_teens: requireTeens,
        auto_approve_under_cents: Math.round(
          parseFloat(autoApproveDollars || "0") * 100,
        ),
      });
      setApprovalSaved(true);
      setTimeout(() => setApprovalSaved(false), 2000);
    } catch {
      setApprovalError("Save failed");
    } finally {
      setApprovalSaving(false);
    }
  }, [setApprovalRules, requireChildren, requireTeens, autoApproveDollars]);

  // -- Guard -----------------------------------------------------------------
  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Grocery</Text>
      <Text style={styles.subtitle}>
        Configure stores, categories, and approval rules for your family grocery list.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Stores                                                   */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Stores</Text>
          <View style={styles.badgeRow}>
            {storesSaved && <Text style={styles.savedBadge}>Saved</Text>}
            {storesError && <Text style={styles.errorBadge}>{storesError}</Text>}
          </View>
        </View>

        {storesLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            {stores.length === 0 ? (
              <Text style={styles.empty}>No stores configured. Add one below.</Text>
            ) : (
              stores.map((store, idx) => (
                <View key={store.id}>
                  {idx > 0 && <View style={styles.divider} />}
                  <StoreRow
                    store={store}
                    onUpdate={(updated) => handleUpdateStore(idx, updated)}
                    onRemove={() => handleRemoveStore(idx)}
                  />
                </View>
              ))
            )}

            <View style={styles.addRow}>
              <Pressable
                style={styles.addBtn}
                onPress={handleAddStore}
                accessibilityRole="button"
                accessibilityLabel="Add store"
              >
                <Text style={styles.addBtnText}>+ Add Store</Text>
              </Pressable>

              <Pressable
                style={[styles.saveBtn, storesSaving && styles.saveBtnDisabled]}
                onPress={handleSaveStores}
                disabled={storesSaving}
                accessibilityRole="button"
                accessibilityLabel="Save stores"
              >
                <Text style={styles.saveBtnText}>
                  {storesSaving ? "Saving…" : "Save Stores"}
                </Text>
              </Pressable>
            </View>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Categories                                               */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Categories</Text>
          <View style={styles.badgeRow}>
            {catSaved && <Text style={styles.savedBadge}>Saved</Text>}
            {catError && <Text style={styles.errorBadge}>{catError}</Text>}
          </View>
        </View>

        {categoriesLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.chipWrap}>
              {categories.map((cat, idx) => (
                <View key={`${cat}-${idx}`} style={styles.catChip}>
                  <Text style={styles.catChipText}>{cat}</Text>
                  <Pressable
                    onPress={() => handleRemoveCategory(idx)}
                    accessibilityRole="button"
                    accessibilityLabel={`Remove ${cat}`}
                    hitSlop={8}
                  >
                    <Text style={styles.catChipRemove}>×</Text>
                  </Pressable>
                </View>
              ))}
            </View>

            <View style={styles.addCatRow}>
              <TextInput
                style={[styles.input, { flex: 1 }] as any}
                value={newCategory}
                onChangeText={setNewCategory}
                placeholder="New category"
                placeholderTextColor={colors.muted}
                onSubmitEditing={handleAddCategory}
                returnKeyType="done"
                accessibilityLabel="New category name"
              />
              <Pressable
                style={styles.addBtn}
                onPress={handleAddCategory}
                accessibilityRole="button"
                accessibilityLabel="Add category"
              >
                <Text style={styles.addBtnText}>Add</Text>
              </Pressable>
            </View>

            <Pressable
              style={[styles.saveBtn, catSaving && styles.saveBtnDisabled]}
              onPress={handleSaveCategories}
              disabled={catSaving}
              accessibilityRole="button"
              accessibilityLabel="Save categories"
            >
              <Text style={styles.saveBtnText}>
                {catSaving ? "Saving…" : "Save Categories"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3: Approval workflow                                        */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Approval workflow</Text>
          <View style={styles.badgeRow}>
            {approvalSaved && <Text style={styles.savedBadge}>Saved</Text>}
            {approvalError && <Text style={styles.errorBadge}>{approvalError}</Text>}
          </View>
        </View>

        {approvalLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Require approval for children</Text>
                <Text style={styles.fieldHint}>
                  Children's grocery requests need parent sign-off before appearing on the list.
                </Text>
              </View>
              <Switch
                value={requireChildren}
                onValueChange={setRequireChildren}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Require approval for teens</Text>
                <Text style={styles.fieldHint}>
                  Teen requests are auto-approved unless this is enabled.
                </Text>
              </View>
              <Switch
                value={requireTeens}
                onValueChange={setRequireTeens}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Auto-approve items under ($)</Text>
              <Text style={styles.fieldHint}>
                Items requested below this dollar threshold are approved automatically.
              </Text>
              <TextInput
                style={styles.input as any}
                value={autoApproveDollars}
                onChangeText={setAutoApproveDollars}
                keyboardType="decimal-pad"
                placeholder="5.00"
                placeholderTextColor={colors.muted}
                accessibilityLabel="Auto-approve threshold in dollars"
              />
            </View>

            <Pressable
              style={[styles.saveBtn, approvalSaving && styles.saveBtnDisabled]}
              onPress={handleSaveApproval}
              disabled={approvalSaving}
              accessibilityRole="button"
              accessibilityLabel="Save approval rules"
            >
              <Text style={styles.saveBtnText}>
                {approvalSaving ? "Saving…" : "Save Approval Rules"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 4: Analytics stub                                           */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Analytics</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — weekly spend by store, most-requested items, approval turnaround.
        </Text>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 48, gap: 14 },
  h1: { fontSize: 20, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  subtitle: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
    marginTop: -4,
  },

  sectionBody: { gap: 12 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 8 },
  empty: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },

  badgeRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  savedBadge: {
    fontSize: 11,
    color: colors.greenText,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
  errorBadge: { fontSize: 11, color: colors.redText, fontFamily: fonts.body },
  stubText: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, lineHeight: 19 },

  // Store add/save row
  addRow: { flexDirection: "row", gap: 10, marginTop: 4 },
  addBtn: {
    borderWidth: 1,
    borderColor: colors.purple,
    borderRadius: radii.md,
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  addBtnText: { color: colors.purple, fontSize: 12, fontWeight: "600", fontFamily: fonts.body },

  saveBtn: {
    flex: 1,
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 10,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },

  // Category chips
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  catChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.purpleLight,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  catChipText: {
    fontSize: 12,
    color: colors.purpleDeep,
    fontWeight: "500",
    fontFamily: fonts.body,
  },
  catChipRemove: { fontSize: 14, color: colors.purpleDeep, fontWeight: "700", lineHeight: 16 },

  addCatRow: { flexDirection: "row", gap: 8, alignItems: "center" },

  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,

  // Approval toggles
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  fieldLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    marginBottom: 2,
  },
  fieldHint: { fontSize: 11, color: colors.muted, fontFamily: fonts.body, lineHeight: 16 },
  fieldGroup: { gap: 4 },
});

// Store row styles
const storeStyles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  fields: { flex: 1, gap: 8 },
  nameInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,
  kindRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  kindChip: {
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  kindChipActive: {
    backgroundColor: colors.purpleLight,
    borderColor: colors.purple,
  },
  kindChipText: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },
  kindChipTextActive: { color: colors.purpleDeep, fontWeight: "600" },
  removeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  removeBtnText: { fontSize: 11, color: colors.redText, fontFamily: fonts.body, fontWeight: "600" },
});
