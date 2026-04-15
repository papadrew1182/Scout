import { test, expect } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: any, email: string, password: string) {
  await page.goto("/");
  // Wait for login screen
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

test.describe("Login", () => {
  test("adult can sign in", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await expect(page.locator("text=Sign out")).toBeVisible();
  });

  test("child can sign in", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
    await expect(page.locator("text=Personal")).toBeVisible();
  });

  test("bad password shows error", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
    await page.fill('input[placeholder="Email"]', ADULT_EMAIL);
    await page.fill('input[placeholder="Password"]', "wrongpassword");
    await page.click("text=Sign In");
    await expect(page.locator("text=Invalid email or password")).toBeVisible({ timeout: 5000 });
  });

  test("sign out returns to login", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Sign out");
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 10000 });
  });

  test("invalid token clears to login", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.setItem("scout_session_token", "invalid-xxx"));
    await page.reload();
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 10000 });
  });
});
