/**
 * Smoke test: AI tool round-trip + confirmation round-trip through the
 * real browser UI. Skips cleanly if the backend reports
 * ai_available=false, since there is no point running against a
 * disabled AI.
 *
 * These tests exercise the full ScoutPanel path end-to-end and are
 * nondeterministic by nature (they depend on Claude's tool selection).
 * They assert the *plumbing* works: a /api/ai/chat response renders
 * non-empty content, and if the model returns a handoff or a
 * pending_confirmation, the UI reflects it correctly. Tests skip the
 * "no handoff / no confirmation" branches rather than failing, because
 * those outcomes are valid AI behavior.
 */

import { test, expect, type Page, type Response } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
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
    return false;
  }
}

async function openScoutPanel(page: Page) {
  await page.click("text=Scout AI");
  await expect(page.locator("text=What can I help with?")).toBeVisible({ timeout: 10000 });
}

async function readChatBody(resp: Response): Promise<any> {
  try {
    return await resp.json();
  } catch {
    return {};
  }
}

test.describe("Scout AI round-trip", () => {
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

  test("AI add-to-grocery quick-action round-trip", async ({ page }) => {
    const ok = await probeAiAvailable(page);
    if (!ok) {
      test.skip(true, "AI is disabled on backend (ai_available=false)");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    await openScoutPanel(page);

    const chatPromise = page.waitForResponse(
      (r) => r.url().includes("/api/ai/chat"),
      { timeout: 45000 },
    );
    // "Add to grocery list" is the most deterministic write quick action —
    // add_grocery_item is the cheapest tool for Claude to pick up and
    // is NOT in the confirmation-required set.
    await page.click("text=Add to grocery list");
    const resp = await chatPromise;
    const status = resp.status();
    console.log(`  round-trip chat status: ${status}`);

    if (status !== 200) {
      const body = await resp.text().catch(() => "");
      console.log(`  error body: ${body.slice(0, 300)}`);
      expect.soft(status, `AI chat returned ${status}`).toBeLessThan(500);
      return;
    }

    const body = await readChatBody(resp);
    expect(body.response, "response field must be non-empty").toBeTruthy();
    expect(String(body.response).length).toBeGreaterThan(3);

    // If Claude asked for clarification (no tool call) the test still
    // proves the panel round-trip is healthy. If Claude DID call
    // add_grocery_item, we should see a handoff payload.
    if (body.handoff) {
      expect(body.handoff.entity_type).toBe("grocery_item");
      expect(body.handoff.route_hint).toContain("/grocery");
      // Tap the handoff card and assert we landed on /grocery
      const handoffBtn = page.locator("text=" + body.handoff.summary).first();
      if (await handoffBtn.isVisible().catch(() => false)) {
        await handoffBtn.click();
        await page.waitForURL(/\/grocery/, { timeout: 10000 });
      }
    } else {
      console.log("  note: no handoff on this turn (Claude asked to clarify or chose not to call a tool)");
    }
  });

  test("AI create_event confirmation round-trip", async ({ page }) => {
    const ok = await probeAiAvailable(page);
    if (!ok) {
      test.skip(true, "AI is disabled on backend (ai_available=false)");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    await openScoutPanel(page);

    // Prompt Claude to create an event. create_event is in
    // CONFIRMATION_REQUIRED — if the model calls it, the backend
    // surfaces pending_confirmation and the panel renders a confirm card.
    const chatPromise = page.waitForResponse(
      (r) => r.url().includes("/api/ai/chat"),
      { timeout: 45000 },
    );
    await page.fill(
      'input[placeholder="Ask Scout anything..."]',
      "Please add a calendar event called 'Smoke Test Meeting' tomorrow at 2pm for 1 hour",
    );
    await page.keyboard.press("Enter");
    const resp = await chatPromise;
    const status = resp.status();
    console.log(`  first chat status: ${status}`);

    if (status !== 200) {
      const body = await resp.text().catch(() => "");
      console.log(`  error body: ${body.slice(0, 300)}`);
      expect.soft(status, `AI chat returned ${status}`).toBeLessThan(500);
      return;
    }

    const body = await readChatBody(resp);
    expect(body.response).toBeTruthy();

    // If Claude chose to call create_event, pending_confirmation must
    // be set. If not, skip the round-trip assertions with a note —
    // the plumbing is still exercised by the first request.
    if (!body.pending_confirmation) {
      console.log("  note: Claude did not call create_event on this turn (may have clarified instead)");
      return;
    }

    expect(body.pending_confirmation.tool_name).toBe("create_event");
    // Panel must render the confirm card
    await expect(page.locator("text=Confirm this action")).toBeVisible({ timeout: 5000 });
    await expect(page.locator("text=create_event")).toBeVisible();

    // Tap Confirm and expect a second chat call with confirm_tool
    const confirmPromise = page.waitForResponse(
      (r) =>
        r.url().includes("/api/ai/chat") &&
        r.request().method() === "POST",
      { timeout: 30000 },
    );
    await page.locator("text=Confirm").first().click();
    const confirmResp = await confirmPromise;
    expect(confirmResp.status()).toBeLessThan(400);

    const confirmBody = await readChatBody(confirmResp);
    // confirm_tool direct-execution path tags the response
    expect(confirmBody.model).toBe("confirmation-direct");
    // pending_confirmation should NOT be set on the result
    expect(confirmBody.pending_confirmation ?? null).toBeNull();
  });
});
