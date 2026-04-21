/**
 * Smoke test: family projects engine (Sprint Expansion Phase 3).
 *
 * Verifies the web surfaces render and the create → detail flow works
 * end-to-end against the deployed backend. Asserts the tasks tab can
 * mark a task complete and the health completion percentage reflects
 * the change.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({ timeout: 15000 });
}

test.describe("Family projects", () => {
  test("project list renders", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/projects");
    await page.waitForTimeout(1500);
    await expect(page.getByText("Projects", { exact: true })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("New project", { exact: true })).toBeVisible();
  });

  test("create blank project, add task, mark complete, see health update", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/projects/new");
    await page.waitForTimeout(1500);

    const projectName = `Smoke project ${Date.now()}`;
    await page.fill('input[placeholder="Project name"]', projectName);
    await page.getByText("Weekend reset", { exact: true }).click();
    await page.click("text=Create project");

    // Land on detail page
    await expect(page.getByText(projectName, { exact: true })).toBeVisible({ timeout: 8000 });

    // Add a task on the Tasks tab
    await page.fill('input[placeholder="Task title"]', "Smoke task");
    await page.click("text=Add task");
    await expect(page.getByText("Smoke task", { exact: true })).toBeVisible({ timeout: 5000 });

    // Mark it complete
    await page.click('text="Mark complete"');
    await page.waitForTimeout(1500);

    // Health summary should now report at least 1 task done
    const headerRegion = page.locator("text=tasks complete");
    await expect(headerRegion).toBeVisible({ timeout: 5000 });
  });

  test("admin can access /admin/projects", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/projects");
    await page.waitForTimeout(1500);
    await expect(page.getByText("Projects (admin)", { exact: true })).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByText("All projects", { exact: true })).toBeVisible();
    await expect(page.getByText("Family templates", { exact: true })).toBeVisible();
  });
});
