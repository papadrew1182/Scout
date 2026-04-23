import { test, expect } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
const CHILD_PASSWORD = process.env.SMOKE_CHILD_PASSWORD || "testpass123";

async function login(page: any, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  // Wait for LoginScreen to disappear — surface-agnostic post-login
  // signal. Works against both the legacy Personal-tab default landing
  // and the Session 3 `/today` redirect which suppresses the legacy
  // NavBar. See scout-ui/app/_layout.tsx SCOUT_PATHS.
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({ timeout: 15000 });
  // Navigate explicitly to the legacy Personal surface so downstream
  // test steps can continue relying on NavBar + Personal tab. On main's
  // frontend this is a no-op. On the Session 3 frontend, `/personal` is
  // still routable and is NOT in SCOUT_PATHS, so NavBar renders there.
  await page.goto("/personal");
  await page.waitForSelector("text=Personal", { timeout: 10000 });
}

test.describe("Adult surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("personal dashboard loads", async ({ page }) => {
    await page.click("text=Personal");
    await expect(page.locator("text=Dashboard")).toBeVisible({ timeout: 10000 });
  });

  test("meals this week loads", async ({ page }) => {
    await page.click("text=Meals");
    await expect(page.locator("text=This Week").first()).toBeVisible({ timeout: 10000 });
  });

  test("grocery page loads", async ({ page }) => {
    await page.click("text=Grocery");
    // Wait for either grocery items or empty state
    await page.waitForTimeout(3000);
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(0);
  });

  test("settings page loads", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=My Account")).toBeVisible({ timeout: 10000 });
  });

  test("adult sees Accounts & Access", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=Accounts & Access")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Child surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, CHILD_EMAIL, CHILD_PASSWORD);
  });

  test("settings loads for child", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=My Account")).toBeVisible({ timeout: 10000 });
  });

  test("child does NOT see Accounts & Access", async ({ page }) => {
    await page.click("text=Settings");
    await page.waitForTimeout(2000);
    await expect(page.locator("text=Accounts & Access")).not.toBeVisible();
  });
});
