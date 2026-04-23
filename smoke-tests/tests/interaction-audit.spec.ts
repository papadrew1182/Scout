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
  await page.goto("/personal");
  await page.waitForSelector("text=Personal", { timeout: 10000 });
}

test.describe("NavBar — all 7 desktop nav links navigate", () => {
  // Desktop viewport so the horizontal nav link list renders (not the hamburger).
  test.use({ viewport: { width: 1280, height: 800 } });

  const NAV_ITEMS = [
    { label: "Home", path: "/", readyText: "Good evening" },
    // Anchored on an unconditionally-rendered card title rather than
    // the first-name-dependent "${first_name}'s Dashboard" heading,
    // so the test passes regardless of which account is logged in.
    { label: "Personal", path: "/personal", readyText: "Top 5 tasks" },
    { label: "Parent", path: "/parent", readyText: "Parent Dashboard" },
    { label: "Meals", path: "/meals", readyText: "Week of" },
    { label: "Grocery", path: "/grocery", readyText: "Grocery List" },
    { label: "Child", path: "/child", readyText: "Hey" }, // redirects to /child/:id
    { label: "Settings", path: "/settings", readyText: "Settings" },
  ];

  for (const item of NAV_ITEMS) {
    test(`clicking "${item.label}" navigates to ${item.path}`, async ({ page }) => {
      await login(page, ADULT_EMAIL, PASSWORD);
      // Click the nav link by its label. Use .first() since "Settings" and other labels may appear elsewhere on a page.
      await page.getByRole("link", { name: item.label, exact: true }).first().click();
      await page.waitForLoadState("load");
      await page.waitForTimeout(300);
      await expect(page.locator(`text=${item.readyText}`).first()).toBeVisible({ timeout: 8000 });
    });
  }
});

test.describe("Dashboard cardAction CTAs are wired to real routes", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test('clicking "Manage chores" navigates to /parent', async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/");
    await page.waitForSelector("text=Good evening", { timeout: 10000 });
    await page.click("text=Manage chores");
    await expect(page.locator("text=Parent Dashboard")).toBeVisible({ timeout: 8000 });
  });

  test('clicking "Full plan" navigates to meals', async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/");
    await page.waitForSelector("text=Good evening", { timeout: 10000 });
    await page.click("text=Full plan");
    await expect(page.locator("text=Week of")).toBeVisible({ timeout: 8000 });
  });

  test('clicking "Full list" navigates to grocery', async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/");
    await page.waitForSelector("text=Good evening", { timeout: 10000 });
    await page.click("text=Full list");
    await expect(page.locator("text=Grocery List")).toBeVisible({ timeout: 8000 });
  });

  test('clicking "View all" navigates to parent', async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/");
    await page.waitForSelector("text=Good evening", { timeout: 10000 });
    await page.click("text=View all");
    await expect(page.locator("text=Parent Dashboard")).toBeVisible({ timeout: 8000 });
  });
});

test.describe("NavBar Sign out returns to login", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("clicking Sign out in NavBar returns to login", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    // Sign out button is in the desktop NavBar
    await page.click("text=Sign out");
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 10000 });
  });
});
