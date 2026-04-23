/**
 * Smoke test: core write paths.
 *
 * Converts the previously read-path-only smoke suite into a real
 * regression net for the highest-value write flows. Every test here
 * depends on seed_smoke.py having been run.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
const CHILD_PASSWORD = process.env.SMOKE_CHILD_PASSWORD || "testpass123";
const API_URL = process.env.SCOUT_API_URL || "http://localhost:8000";

async function login(page: Page, email: string, password: string) {
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

// Pull the authenticated member's own id out of localStorage so tests can
// navigate directly to routes like /child/[memberId] without relying on a
// particular default-landing behavior. The real storage key is
// "scout_session_token" (see scout-ui/lib/auth.tsx:TOKEN_KEY) — an earlier
// version of this helper read "scout_token" and silently got null, which
// sent an unauthenticated /api/auth/me request and tripped the 401 path.
async function currentMemberId(page: Page): Promise<string> {
  const headers = await page.evaluate(() => {
    const token = localStorage.getItem("scout_session_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  });
  const res = await page.request.get(`${API_URL}/api/auth/me`, { headers });
  if (!res.ok()) throw new Error(`/api/auth/me returned ${res.status()}`);
  const body = await res.json();
  const memberId = body?.member?.member_id ?? body?.member_id;
  if (!memberId) throw new Error("/api/auth/me did not return a member id");
  return memberId;
}

test.describe("Write paths — parent", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("parent approves a pending grocery item", async ({ page }) => {
    // Navigate directly instead of clicking the NavBar link to avoid the
    // same race the /parent test hit under CI's React Native Web build.
    await page.goto("/grocery");
    await expect(page.locator("text=Needs Review")).toBeVisible({ timeout: 10000 });

    const reviewSection = page.locator("text=Needs Review").locator("..").locator("..");
    const gummy = reviewSection.locator("text=Gummy bears").first();
    await expect(gummy).toBeVisible({ timeout: 8000 });

    // Frontend routes this through updateGroceryItem(id, {approval_status})
    // which PATCHes /families/{fid}/groceries/items/{id} (PLURAL
    // "groceries" + "/items/" segment). The earlier matcher used
    // "/grocery/" (singular, no "/items/") and never fired — the
    // approve click still landed, but waitForResponse just timed out.
    const approvePromise = page.waitForResponse(
      (r) =>
        r.url().includes("/groceries/items/") &&
        r.request().method() === "PATCH",
      { timeout: 15000 },
    );
    // Approve button inside the Gummy bears card
    const card = page.locator('text="Gummy bears"').first().locator("xpath=ancestor::*[self::div][position()<=4]").first();
    await card.getByText("Approve", { exact: true }).first().click();
    const approveResp = await approvePromise;
    expect(approveResp.status()).toBeLessThan(400);

    // Gummy bears should no longer appear under "Needs Review"
    await page.waitForTimeout(1200);
    await expect(
      page
        .locator("text=Needs Review")
        .locator("..")
        .locator("..")
        .locator("text=Gummy bears"),
    ).toHaveCount(0);
  });

  test("parent approves the draft weekly meal plan", async ({ page }) => {
    // Seed now creates the current-week plan in 'draft' status and
    // normalizes it back to draft on re-run, so /meals/this-week
    // always surfaces a draft with an "Approve Plan" button for the
    // adult. The test approves, asserts the success toast, and asserts
    // the button disappears (status → 'approved').
    await page.goto("/meals/this-week");
    await expect(page.locator("text=This Week").first()).toBeVisible({ timeout: 10000 });

    const approveBtn = page.getByRole("button", { name: "Approve Plan" }).first();
    await expect(approveBtn).toBeVisible({ timeout: 8000 });

    const approvePromise = page.waitForResponse(
      (r) => r.url().includes("/meals/weekly/") && r.url().includes("/approve"),
      { timeout: 15000 },
    );
    await approveBtn.click();
    const resp = await approvePromise;
    expect(resp.status()).toBeLessThan(400);
    await expect(page.locator("text=Plan approved")).toBeVisible({ timeout: 5000 });

    // Post-approve: the button must no longer be visible (plan is now approved)
    await expect(approveBtn).not.toBeVisible({ timeout: 5000 });
  });

  test("parent runs weekly payout", async ({ page }) => {
    // Navigate directly to /parent instead of clicking the NavBar link. The
    // NavBar renders "Parent" as a Pressable that router.push()es to /parent,
    // but under CI's React Native Web build the text-based click is racy
    // with navigation; page.goto is unambiguous.
    await page.goto("/parent");
    await page.waitForSelector("text=Run Weekly Payout", { timeout: 15000 });

    const payoutBtn = page.getByRole("button", { name: "Run Weekly Payout" });
    // If the button is disabled because payout was already run, the test is
    // still useful — it asserts the disabled-state message is present.
    const disabled = await payoutBtn.isDisabled().catch(() => false);
    if (disabled) {
      await expect(page.locator("text=Payout already run for this week")).toBeVisible();
      return;
    }

    const payoutPromise = page.waitForResponse(
      (r) => r.url().includes("/allowance/") || r.url().includes("/payout"),
      { timeout: 15000 },
    );
    await payoutBtn.click();
    const resp = await payoutPromise.catch(() => null);
    // 2xx = payout created; 409 = payout already exists for this week
    // (also a valid idempotent response). Anything >= 500 is a real
    // regression the test should catch.
    if (resp) expect(resp.status()).toBeLessThan(500);
    // Post-state: the button transitions to the disabled "Payout already
    // run for this week" label. Both the action-message Text AND the
    // button Text render that string, which trips strict-mode when the
    // locator resolves to 2 elements. Scope to the first match.
    await expect(
      page
        .locator("text=payout created")
        .or(page.locator("text=already exists for this week"))
        .or(page.locator("text=Payout already run for this week"))
        .first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test("parent converts a pending purchase request to a grocery item", async ({ page }) => {
    await page.goto("/grocery");
    await expect(page.locator("text=Purchase Requests")).toBeVisible({ timeout: 10000 });

    const card = page
      .locator('text="New soccer ball"')
      .first()
      .locator("xpath=ancestor::*[self::div][position()<=4]")
      .first();
    await expect(card).toBeVisible({ timeout: 8000 });

    const convertPromise = page.waitForResponse(
      (r) =>
        r.url().includes("/purchase-requests/") ||
        r.url().includes("/grocery"),
      { timeout: 15000 },
    );
    // Prefer "Add to List" (convert); fall back to "Approve".
    const addBtn = card.getByText("Add to List", { exact: true }).first();
    const fallback = card.getByText("Approve", { exact: true }).first();
    if (await addBtn.isVisible().catch(() => false)) {
      await addBtn.click();
    } else {
      await fallback.click();
    }
    const resp = await convertPromise;
    expect(resp.status()).toBeLessThan(400);

    // Card should disappear from the Purchase Requests section.
    await page.waitForTimeout(1200);
    await expect(
      page
        .locator("text=Purchase Requests")
        .locator("..")
        .locator("..")
        .locator('text="New soccer ball"'),
    ).toHaveCount(0);
  });
});

test.describe("Write paths — child", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, CHILD_EMAIL, CHILD_PASSWORD);
  });

  test("child marks seeded chore task instance complete", async ({ page }) => {
    // Chore task instances render inside the per-child detail screen
    // (scout-ui/app/child/[memberId].tsx), not on the default post-login
    // landing page. Resolve this child's own member id and navigate there
    // explicitly so the test isn't coupled to default-landing behavior.
    const memberId = await currentMemberId(page);
    await page.goto(`/child/${memberId}`);

    await expect(
      page.locator("text=Feed the dog").first(),
    ).toBeVisible({ timeout: 10000 });

    const checkbox = page.locator('[data-testid="task-checkbox-feed-the-dog"]').first();
    await expect(checkbox).toBeVisible({ timeout: 8000 });

    const completePromise = page.waitForResponse(
      (r) => r.url().includes("/task-instances/") && r.request().method() === "POST",
      { timeout: 15000 },
    );
    await checkbox.click();
    const resp = await completePromise;
    expect(resp.status()).toBeLessThan(400);
  });

  test("child submits a meal review", async ({ page }) => {
    // Go straight to the Reviews subpage — the meals layout's sub-tab click
    // was inconsistent under CI's React Native Web build.
    await page.goto("/meals/reviews");

    await page.waitForSelector('input[placeholder="Meal title"]', { timeout: 10000 });
    await page.fill('input[placeholder="Meal title"]', "Smoke Test Lasagna");
    // Default rating is 4, decision is "Repeat", leftovers optional.
    // Actual endpoint is POST /families/{fid}/meals/reviews — match on
    // the "meals/reviews" suffix. The earlier matcher "/meal-reviews"
    // (with a hyphen) never matched and always timed out.
    const savePromise = page.waitForResponse(
      (r) => r.url().includes("/meals/reviews") && r.request().method() === "POST",
      { timeout: 15000 },
    );
    await page.getByRole("button", { name: "Save Review" }).first().click();
    const resp = await savePromise;
    expect(resp.status()).toBeLessThan(400);
    await expect(page.locator("text=Review saved")).toBeVisible({ timeout: 5000 });
  });
});
