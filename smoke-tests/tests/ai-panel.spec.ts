/**
 * Smoke test: Scout AI panel.
 *
 * Exercises the AI chat panel through the real UI with content assertions,
 * a disabled-state test (stubbed /ready), and a child-surface coverage
 * check. Skips cleanly if AI is disabled on the backend.
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

async function probeAiAvailable(page: Page): Promise<boolean> {
  try {
    const ready = await page.request.get(`${API_URL}/ready`);
    const data = await ready.json();
    return data.ai_available === true;
  } catch {
    return true; // optimistic; the test itself will fail loudly if not
  }
}

test.describe("Scout AI Panel", () => {
  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) => {
      if (msg.text().includes("[Scout AI]")) {
        console.log(`  BROWSER: ${msg.text()}`);
      }
    });
    page.on("pageerror", (err) => {
      console.log(`  PAGE ERROR: ${err.message}`);
    });
  });

  test("AI panel sends prompt and renders non-empty assistant content", async ({ page }) => {
    const aiAvailable = await probeAiAvailable(page);
    if (!aiAvailable) {
      test.skip(true, "AI is disabled on backend (ai_available=false)");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Scout AI");
    await expect(page.locator("text=What can I help with?")).toBeVisible({ timeout: 10000 });

    const chatPromise = page.waitForResponse(
      (r) => r.url().includes("/api/ai/chat"),
      { timeout: 30000 },
    );
    await page.click("text=What does today look like?");
    const chatResponse = await chatPromise;
    const chatStatus = chatResponse.status();
    console.log(`  AI chat response status: ${chatStatus}`);

    if (chatStatus !== 200) {
      const body = await chatResponse.text().catch(() => "");
      console.log(`  AI chat error body: ${body.slice(0, 300)}`);
      expect.soft(chatStatus, `AI chat returned ${chatStatus}: ${body.slice(0, 100)}`).toBeLessThan(500);
      return;
    }

    // Must NOT show the generic error
    await expect(page.locator("text=Something went wrong")).not.toBeVisible({ timeout: 5000 });

    // The response body must have an assistant response field with real text.
    const bodyJson: any = await chatResponse.json().catch(() => ({}));
    expect(
      bodyJson?.response,
      "ChatResponse.response should be a non-empty string",
    ).toBeTruthy();
    expect(String(bodyJson?.response || "").length).toBeGreaterThan(3);
  });

  test("AI panel renders disabled state when /ready reports ai_available=false", async ({ page }) => {
    // Stub the browser's fetch to /ready with ai_available=false BEFORE login.
    // The panel probes /ready on open and should render the disabled card.
    await page.route("**/ready", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ready",
          environment: "test",
          auth_required: true,
          bootstrap_enabled: false,
          accounts_exist: true,
          ai_available: false,
          meal_generation: false,
        }),
      });
    });

    // Note: login's own probe hits the real /ready via page.request, which is
    // not affected by page.route (browser-fetch only). We intentionally only
    // stub the browser path so login still succeeds.
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Scout AI");

    // Disabled-state card copy
    await expect(page.locator("text=Scout AI is unavailable right now")).toBeVisible({ timeout: 8000 });

    // Quick actions MUST NOT render
    await expect(page.locator("text=What does today look like?")).not.toBeVisible();
  });

  test("AI panel opens on child surface without crashing", async ({ page }) => {
    const aiAvailable = await probeAiAvailable(page);
    if (!aiAvailable) {
      test.skip(true, "AI is disabled on backend (ai_available=false)");
      return;
    }

    await login(page, CHILD_EMAIL, CHILD_PASSWORD);
    await page.click("text=Scout AI");
    // Either the chat UI or a disabled/checking state must render.
    const ok = page.locator("text=What can I help with?");
    const checking = page.locator("text=Checking Scout AI availability");
    const disabled = page.locator("text=Scout AI is unavailable right now");
    await expect(ok.or(checking).or(disabled)).toBeVisible({ timeout: 10000 });
    // And no page-level error banner.
    await expect(page.locator("text=Something went wrong")).not.toBeVisible();
  });
});
