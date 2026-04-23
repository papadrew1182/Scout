import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

// Viewport-agnostic login: does NOT rely on desktop NavBar text (the
// "Personal" link is only rendered on desktop — on mobile the NavBar
// collapses into a hamburger menu and that text isn't visible).
async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  // Wait for the email input to disappear — this is the auth-complete
  // signal and is viewport-independent.
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({ timeout: 15000 });
}

const SURFACES = [
  { path: "/", ready: "Good evening" },
  // Anchored on an unconditionally-rendered card title rather than
  // the first-name-dependent "${first_name}'s Dashboard" heading,
  // so the test passes regardless of which account is logged in.
  { path: "/personal", ready: "Top 5 tasks" },
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
    // The store cards come from admin config (`grocery.stores`), which is
    // fetched async after mount. Give the config fetch a chance to resolve
    // before we assert on specific stores.
    await page.waitForTimeout(3000);

    // Check whichever default-seeded stores render. If config hasn't loaded
    // or was edited by an admin, skip missing ones — the primary overflow
    // assertion lives in the parameterized test above.
    const candidateStoreNames = ["Costco", "Tom Thumb", "Grocery"];
    let checkedAny = false;
    for (const name of candidateStoreNames) {
      const card = page.locator(`text=${name}`).first();
      const visible = await card.isVisible().catch(() => false);
      if (!visible) continue;
      const box = await card.boundingBox();
      if (!box) continue;
      checkedAny = true;
      expect(
        box.x + box.width,
        `${name} card right edge > viewport`,
      ).toBeLessThanOrEqual(390 + 1);
    }
    expect(checkedAny, "expected at least one store card to render").toBe(true);
  });
});
