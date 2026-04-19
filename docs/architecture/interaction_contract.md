# Interaction Contract

**Status:** Enforced via `scripts/architecture-check.js` Check 5
**Introduced:** Operability Sprint Phase 1 (2026-04-19)

---

## Rule

Every interactive element in `scout-ui/` (`Pressable`, `TouchableOpacity`,
any component with an `onPress` prop) MUST belong to exactly one of the
five interaction classes listed below. No interactive element may exist
without a defined target.

## Interaction Classes

### 1. `navigate-detail`

The tap changes the route or opens a detail sheet on a new screen.

**Implementation:** `router.push("/path")` or equivalent expo-router
navigation call inside `onPress`.

**Assertion:** After tap, the route changes or a detail sheet becomes
visible.

### 2. `open-panel`

The tap opens a panel, modal, or overlay within the current screen.

**Implementation:** State setter that toggles a panel's visibility
(e.g., `setShowPanel(true)`, `sheet.open(id)`).

**Assertion:** After tap, the expected panel or modal is visible.

### 3. `execute-action`

The tap performs a state mutation: toggling a filter, marking an item
complete, submitting a form, approving a request.

**Implementation:** A function call that changes local or remote state.

**Assertion:** After tap, the expected state change has occurred (filter
toggled, item checked, API call made).

### 4. `expand-inline`

The tap reveals additional content within the same view without
navigation or panel. Accordions, collapsible sections, detail
expansions.

**Implementation:** State setter that toggles an expanded ID or
boolean.

**Assertion:** After tap, the expanded content is visible in the same
view.

### 5. `no-op-documented`

The element is deliberately non-interactive. A code comment MUST exist
on the handler or the element explaining why.

**Required comment format:** `// no-op: {reason}`

**Examples:**
- `// no-op: summary counts, not interactive`
- `// no-op: status indicator, display only`
- `// no-op: informational disclosure text`

**Assertion:** After tap, no navigation occurs AND the source code has
an explicit `// no-op: {reason}` comment.

## Escape Hatches

### Indirect handlers

When a handler is passed as a prop from a parent, extracted to an
external hook, or imported from a `lib/` module, the architecture check
cannot statically verify it. These are presumed valid.

To suppress a false-positive WARN from Check 5, add the following
comment on the line immediately before the prop assignment:

```tsx
// arch-check: indirect-handler
onPress={externalCallback}
```

## Enforcement

`scripts/architecture-check.js` Check 5 enforces this contract:

- **WARN** on `onPress={() => {}}`, `onPress={undefined}`,
  `onPress={null}`, or handlers whose body is only a comment or a bare
  `return`.
- **WARN** on dashboard card components (from a curated allowlist) that
  have no `onPress` prop at all.
- **Exit non-zero** when any WARN-level dead-tap finding exists.

## Dashboard Tap-Target Map

The authoritative mapping of what each card/row/chip does on tap is
maintained in the operability sprint spec
(`SCOUT_OPERABILITY_SPRINT.md` section 7, Appendix A). That map is the
source of truth for Phase 1 wiring and all subsequent phases.
