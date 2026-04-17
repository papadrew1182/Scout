/**
 * Grocery helpers for Scout.
 *
 * Types and defaults for the three family-level grocery config keys:
 *   grocery.stores          — GroceryStoreConfig
 *   grocery.categories      — GroceryCategoryConfig
 *   grocery.approval_rules  — GroceryApprovalRules
 *
 * These are consumed by:
 *   - app/admin/grocery/index.tsx  (admin configuration UI)
 *   - app/grocery/index.tsx        (de-hardcoded grocery list page)
 */

// ---------------------------------------------------------------------------
// grocery.stores
// ---------------------------------------------------------------------------

export type StoreKind = "bulk" | "local" | "online" | "other";

export interface GroceryStore {
  id: string;
  name: string;
  kind: StoreKind;
}

export interface GroceryStoreConfig {
  stores: GroceryStore[];
}

export const DEFAULT_STORE_CONFIG: GroceryStoreConfig = {
  stores: [],
};

// ---------------------------------------------------------------------------
// grocery.categories
// ---------------------------------------------------------------------------

export interface GroceryCategoryConfig {
  categories: string[];
}

export const DEFAULT_CATEGORY_CONFIG: GroceryCategoryConfig = {
  categories: ["Produce", "Protein", "Pantry", "Dairy", "Requested"],
};

// ---------------------------------------------------------------------------
// grocery.approval_rules
// ---------------------------------------------------------------------------

export interface GroceryApprovalRules {
  require_approval_for_children: boolean;
  require_approval_for_teens: boolean;
  auto_approve_under_cents: number;
}

export const DEFAULT_APPROVAL_RULES: GroceryApprovalRules = {
  require_approval_for_children: true,
  require_approval_for_teens: false,
  auto_approve_under_cents: 500,
};
