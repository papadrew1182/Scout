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

const SURFACES = [
  { path: "/", ready: "Good evening" },
  { path: "/personal", ready: "Andrew's Dashboard" },
  { path: "/parent", ready: "Parent Dashboard" },
  { path: "/meals/this-week", ready: "Week of" },
  { path: "/grocery", ready: "Grocery List" },
  { path: "/child/townes", ready: "Hey Townes" },
  { path: "/settings", ready: "Settings" },
];

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "iPhone-portrait", width: 390, height: 844 },
  { name: "iPhone-landscape", width: 844, height: 390 },
];

test.describe("Responsive layout — no horizontal overflow", () => {
  for (const vp of VIEWPORTS) {
    for (const surface of SURFACES) {
      test(`${vp.name} · ${surface.path} has no horizontal overflow`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await login(page, ADULT_EMAIL, PASSWORD);
        await page.goto(surface.path);
        await page.waitForSelector(`text=${surface.ready}`, { timeout: 10000 });
        // Allow a render settling frame
        await page.waitForTimeout(300);

        const overflow = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
        }));
        // Tolerate 1px rounding
        expect(overflow.scrollWidth, `scrollWidth ${overflow.scrollWidth} > innerWidth ${overflow.innerWidth}`).toBeLessThanOrEqual(
          overflow.innerWidth + 1,
        );
      });
    }
  }
});

test.describe("Grocery store cards fit viewport on iPhone portrait", () => {
  test("all rendered cards fit within viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/grocery");
    await page.waitForSelector("text=Grocery List", { timeout: 10000 });
    await page.waitForTimeout(500); // let layout settle

    // The store cards each have title text "Costco" or "Tom Thumb" somewhere
    const storeNames = ["Costco", "Tom Thumb"];
    for (const name of storeNames) {
      const card = page.locator(`text=${name}`).first();
      const box = await card.boundingBox();
      if (!box) throw new Error(`Card ${name} not found or not visible`);
      expect(box.x + box.width, `${name} card right edge > viewport`).toBeLessThanOrEqual(390 + 1);
    }
  });
});
