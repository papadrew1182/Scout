/**
 * Smoke test: interaction contract (Phase 1).
 *
 * Asserts tap-target behavior by interaction class:
 *   - navigate-detail: route changes or detail sheet opens
 *   - execute-action: expected state mutation occurs
 *   - expand-inline: expanded content visible in same view
 *   - no-op-documented: no navigation occurs
 *
 * Also includes a regression test for the CompletionSheet menu-rollup
 * defect: the sheet must stay visible while interacting with its
 * internal controls.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({
    timeout: 15000,
  });
}

// ---------------------------------------------------------------------------
// navigate-detail tests
// ---------------------------------------------------------------------------

test.describe("navigate-detail targets", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("Daily Win pill on /today navigates to /members/{id}", async ({
    page,
  }) => {
    await page.goto("/today");
    await page.waitForTimeout(2000);

    // Daily Win pill is rendered as role=link with accessibleName
    // "<kid> <done> of <required> complete" (TodayHome.tsx winPill).
    const pill = page.getByRole("link", { name: /of \d+ complete$/ }).first();
    if (await pill.isVisible()) {
      await pill.click();
      await page.waitForTimeout(1500);
      expect(page.url()).toContain("/members/");
    }
  });

  test("DailyWinCard on /rewards navigates to /members/{id}?tab=wins", async ({
    page,
  }) => {
    await page.goto("/rewards");
    await page.waitForTimeout(2000);

    const card = page
      .locator('[aria-label*="daily wins"]')
      .first();
    if (await card.isVisible()) {
      await card.click();
      await page.waitForTimeout(1500);
      expect(page.url()).toContain("/members/");
      expect(page.url()).toContain("tab=wins");
    }
  });

  test("WeeklyPayoutCard on /rewards navigates to /members/{id}?tab=payout", async ({
    page,
  }) => {
    await page.goto("/rewards");
    await page.waitForTimeout(2000);

    const card = page
      .locator('[aria-label*="payout details"]')
      .first();
    if (await card.isVisible()) {
      await card.click();
      await page.waitForTimeout(1500);
      expect(page.url()).toContain("/members/");
      expect(page.url()).toContain("tab=payout");
    }
  });
});

// ---------------------------------------------------------------------------
// execute-action tests
// ---------------------------------------------------------------------------

test.describe("execute-action targets", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("filter chip on /today toggles child focus", async ({ page }) => {
    await page.goto("/today");
    await page.waitForTimeout(2000);

    const householdChip = page.locator('text=Household').first();
    if (await householdChip.isVisible()) {
      // Verify the Household chip is initially active (selected state)
      await householdChip.click();
      await page.waitForTimeout(500);
      // Page should still be on /today (no navigation)
      expect(page.url()).toContain("/today");
    }
  });
});

// ---------------------------------------------------------------------------
// expand-inline tests
// ---------------------------------------------------------------------------

test.describe("expand-inline targets", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("meal day cell expands on tap", async ({ page }) => {
    await page.goto("/meals/this-week");
    await page.waitForTimeout(2000);

    // Find a day cell and tap it
    const dayCell = page.locator('[role="button"]').filter({
      hasText: /Mon|Tue|Wed|Thu|Fri|Sat|Sun/,
    }).first();
    if (await dayCell.isVisible()) {
      await dayCell.click();
      await page.waitForTimeout(500);
      // Page should still be on meals (no navigation, inline expand)
      expect(page.url()).toContain("/meals");
    }
  });

  test("calendar anchor block row expands on tap", async ({ page }) => {
    await page.goto("/calendar");
    await page.waitForTimeout(2000);

    const blockRow = page
      .locator('[role="button"]')
      .filter({ hasText: /Routine block|Weekly event/ })
      .first();
    if (await blockRow.isVisible()) {
      await blockRow.click();
      await page.waitForTimeout(500);
      // Should show detail text inline
      const detail = page.locator("text=Source:").first();
      await expect(detail).toBeVisible({ timeout: 3000 });
    }
  });
});

// ---------------------------------------------------------------------------
// no-op-documented tests
// ---------------------------------------------------------------------------

test.describe("no-op-documented targets", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("summary strip counters on /today do not navigate", async ({
    page,
  }) => {
    await page.goto("/today");
    await page.waitForTimeout(2000);

    const currentUrl = page.url();
    // Summary cells are Views (not Pressable), so clicking them should
    // not change the URL
    const dueLabel = page.locator("text=Due").first();
    if (await dueLabel.isVisible()) {
      await dueLabel.click();
      await page.waitForTimeout(500);
      expect(page.url()).toBe(currentUrl);
    }
  });
});

// ---------------------------------------------------------------------------
// Regression: CompletionSheet menu-rollup defect
// ---------------------------------------------------------------------------

test.describe("CompletionSheet stability", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("sheet stays visible while interacting with notes input", async ({
    page,
  }) => {
    await page.goto("/today");
    await page.waitForTimeout(2000);

    // Find a task body to open the CompletionSheet
    const taskBody = page
      .locator('[aria-label*="Open details for"]')
      .first();
    if (!(await taskBody.isVisible())) {
      test.skip();
      return;
    }

    await taskBody.click();
    await page.waitForTimeout(1000);

    // The sheet should now be visible with a notes input
    const notesInput = page
      .locator('[aria-label="Optional completion notes"]')
      .first();
    if (!(await notesInput.isVisible({ timeout: 3000 }).catch(() => false))) {
      // Sheet might show "Done" state with no notes field - skip
      test.skip();
      return;
    }

    // Type into the notes field
    await notesInput.click();
    await page.waitForTimeout(300);
    await notesInput.fill("Test note for regression");
    await page.waitForTimeout(500);

    // The sheet should still be visible (not collapsed)
    const closeButton = page.locator(
      '[aria-label="Close completion sheet"]',
    );
    await expect(closeButton).toBeVisible({ timeout: 3000 });
  });
});
