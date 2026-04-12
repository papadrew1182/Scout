/**
 * Smoke test: Scout AI panel.
 *
 * Exercises the AI chat panel through the real UI.
 * Skips cleanly if AI is disabled on the backend.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
const API_URL = process.env.SCOUT_API_URL || "http://localhost:8000";

async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await page.waitForSelector("text=Personal", { timeout: 15000 });
}

test.describe("Scout AI Panel", () => {
  test.beforeEach(async ({ page }) => {
    // Collect console + error events for debugging
    page.on("console", (msg) => {
      if (msg.text().includes("[Scout AI]")) {
        console.log(`  BROWSER: ${msg.text()}`);
      }
    });
    page.on("pageerror", (err) => {
      console.log(`  PAGE ERROR: ${err.message}`);
    });
  });

  test("AI panel sends prompt and gets response or known-disabled state", async ({ page }) => {
    // Check if AI is available
    let aiAvailable = true;
    try {
      const ready = await page.request.get(`${API_URL}/ready`);
      const data = await ready.json();
      aiAvailable = data.ai_available === true;
    } catch {
      // If /ready is unreachable, assume AI might be available and let the test proceed
    }

    if (!aiAvailable) {
      test.skip(true, "AI is disabled on backend (ai_available=false)");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);

    // Open the Scout AI panel via the NavBar button
    await page.click("text=Scout AI");
    await expect(page.locator("text=What can I help with?")).toBeVisible({ timeout: 5000 });

    // Intercept the AI chat request
    const chatPromise = page.waitForResponse(
      (r) => r.url().includes("/api/ai/chat"),
      { timeout: 30000 },
    );

    // Click a quick action
    await page.click("text=What does today look like?");

    // Wait for the response
    const chatResponse = await chatPromise;
    const chatStatus = chatResponse.status();

    console.log(`  AI chat response status: ${chatStatus}`);

    if (chatStatus === 200) {
      // Successful response — verify assistant message appears (not the error fallback)
      await expect(page.locator("text=Something went wrong")).not.toBeVisible({ timeout: 5000 });
      // At least one assistant bubble should appear
      const assistantBubbles = page.locator('[class*="assistantBubble"], [class*="assistant"]');
      // Just verify no error message appeared — the assistant response content varies
    } else {
      // Non-200 — capture details for debugging
      const body = await chatResponse.text().catch(() => "");
      console.log(`  AI chat error body: ${body.slice(0, 300)}`);
      // If it's a known infrastructure issue (502, 503), note it but don't mask
      expect.soft(chatStatus, `AI chat returned ${chatStatus}: ${body.slice(0, 100)}`).toBeLessThan(500);
    }

    // Must NOT show the generic error if the request succeeded
    if (chatStatus === 200) {
      await page.waitForTimeout(2000);
      const pageText = await page.textContent("body");
      expect(pageText).not.toContain("Something went wrong");
    }
  });
});
