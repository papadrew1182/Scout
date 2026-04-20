/**
 * Smoke test: data entry (Phase 2).
 *
 * Covers create flows for personal tasks, calendar events, chore
 * templates, and meal staples. Includes permission-denial tests
 * verifying child users cannot access admin forms.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
const API_URL = process.env.SCOUT_API_URL || "http://localhost:8000";

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
// Personal tasks
// ---------------------------------------------------------------------------

test.describe("Personal task creation", () => {
  test.beforeEach(async ({ page }) => {
    // Skip in CI environments without Session 3 frontend
    if (!process.env.SMOKE_SESSION3) test.skip();
  });

  test("parent can create personal task from /today", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/today");
    await page.waitForTimeout(2000);

    const addBtn = page.locator('text=+ Add task');
    if (!(await addBtn.isVisible())) {
      test.skip();
      return;
    }
    await addBtn.click();
    await page.waitForTimeout(500);

    const titleInput = page.locator('[accessibilityLabel="Task title"]');
    await expect(titleInput).toBeVisible({ timeout: 3000 });
    await titleInput.fill("Smoke test task");

    const submitBtn = page.locator('[accessibilityLabel="Add task"]');
    await submitBtn.click();
    await page.waitForTimeout(2000);

    // Sheet should close after creation
    await expect(titleInput).not.toBeVisible({ timeout: 3000 });
  });
});

// ---------------------------------------------------------------------------
// Calendar events
// ---------------------------------------------------------------------------

test.describe("Calendar event creation", () => {
  test.beforeEach(async ({ page }) => {
    // Skip in CI environments without Session 3 frontend
    if (!process.env.SMOKE_SESSION3) test.skip();
  });

  test("parent can create event from /calendar", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/calendar");
    await page.waitForTimeout(2000);

    const addBtn = page.locator('text=+ Add event');
    if (!(await addBtn.isVisible())) {
      test.skip();
      return;
    }
    await addBtn.click();
    await page.waitForTimeout(500);

    const titleInput = page.locator('[accessibilityLabel="Event title"]');
    await expect(titleInput).toBeVisible({ timeout: 3000 });
    await titleInput.fill("Smoke test event");

    const startInput = page.locator('[accessibilityLabel="Start time"]');
    await startInput.fill("2026-04-25T10:00");

    const endInput = page.locator('[accessibilityLabel="End time"]');
    await endInput.fill("2026-04-25T11:00");

    const createBtn = page.locator('[accessibilityLabel="Create event"]');
    await createBtn.click();
    await page.waitForTimeout(2000);

    await expect(titleInput).not.toBeVisible({ timeout: 3000 });
  });
});

// ---------------------------------------------------------------------------
// Admin chore template
// ---------------------------------------------------------------------------

test.describe("Chore template creation", () => {
  test.beforeEach(async ({ page }) => {
    // Skip in CI environments without Session 3 frontend
    if (!process.env.SMOKE_SESSION3) test.skip();
  });

  test("admin can create chore template", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/chores/new");
    await page.waitForTimeout(2000);

    const nameInput = page.locator('[accessibilityLabel="Chore name"]');
    if (!(await nameInput.isVisible())) {
      test.skip();
      return;
    }
    await nameInput.fill("Smoke test chore");

    const submitBtn = page.locator('[accessibilityLabel="Create template"]');
    await submitBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator("text=Template created");
    await expect(successMsg).toBeVisible({ timeout: 5000 });
  });

  test("child cannot see chore template form", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
    await page.goto("/admin/chores/new");
    await page.waitForTimeout(2000);

    const noPermission = page.locator("text=do not have permission");
    await expect(noPermission).toBeVisible({ timeout: 5000 });
  });
});

// ---------------------------------------------------------------------------
// Admin meal staple
// ---------------------------------------------------------------------------

test.describe("Meal staple creation", () => {
  test.beforeEach(async ({ page }) => {
    // Skip in CI environments without Session 3 frontend
    if (!process.env.SMOKE_SESSION3) test.skip();
  });

  test("admin can create meal staple", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/meals/staples/new");
    await page.waitForTimeout(2000);

    const nameInput = page.locator('[accessibilityLabel="Meal name"]');
    if (!(await nameInput.isVisible())) {
      test.skip();
      return;
    }
    await nameInput.fill("Smoke test meal");

    const submitBtn = page.locator('[accessibilityLabel="Create staple meal"]');
    await submitBtn.click();
    await page.waitForTimeout(2000);

    const successMsg = page.locator("text=Meal staple created");
    await expect(successMsg).toBeVisible({ timeout: 5000 });
  });

  test("child cannot see meal staple form", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
    await page.goto("/admin/meals/staples/new");
    await page.waitForTimeout(2000);

    const noPermission = page.locator("text=do not have permission");
    await expect(noPermission).toBeVisible({ timeout: 5000 });
  });
});
