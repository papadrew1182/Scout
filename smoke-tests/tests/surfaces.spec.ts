import { test, expect } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: any, email: string, password: string) {
  await page.goto("/");
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await page.waitForSelector("text=Scout", { timeout: 15000 });
}

test.describe("Adult surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("personal dashboard loads", async ({ page }) => {
    await page.click("text=Personal");
    await expect(page.locator("text=Dashboard")).toBeVisible({ timeout: 5000 });
  });

  test("meals this week loads", async ({ page }) => {
    await page.click("text=Meals");
    await expect(page.locator("text=This Week")).toBeVisible({ timeout: 5000 });
  });

  test("grocery page loads", async ({ page }) => {
    await page.click("text=Grocery");
    await page.waitForTimeout(2000);
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("settings page loads", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=My Account")).toBeVisible({ timeout: 5000 });
  });

  test("adult sees Accounts & Access", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=Accounts & Access")).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Child surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
  });

  test("settings loads for child", async ({ page }) => {
    await page.click("text=Settings");
    await expect(page.locator("text=My Account")).toBeVisible({ timeout: 5000 });
  });

  test("child does NOT see Accounts & Access", async ({ page }) => {
    await page.click("text=Settings");
    await page.waitForTimeout(1500);
    await expect(page.locator("text=Accounts & Access")).not.toBeVisible();
  });
});
