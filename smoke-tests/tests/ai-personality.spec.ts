/**
 * Smoke test: Sprint 04 Phase 2 - per-member AI personality.
 *
 * Exercises:
 * - GET /personality/me returns {stored, resolved, preamble} even when
 *   the member has no member_config row
 * - PATCH /personality/me persists and updates the resolved view
 * - Invalid enum returns 422
 * - /settings/ai renders the Personality section after Phase 2 ships
 *
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
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({
    timeout: 15000,
  });
  await page.goto("/personal");
  await page.waitForSelector("text=Personal", { timeout: 10000 });
}

async function probeAiAvailable(page: Page): Promise<boolean> {
  try {
    const ready = await page.request.get(`${API_URL}/ready`);
    const data = await ready.json();
    return data.ai_available === true;
  } catch {
    return true;
  }
}

async function getBearerToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => {
    try {
      return (
        window.localStorage.getItem("scout_token") ||
        window.localStorage.getItem("token") ||
        null
      );
    } catch {
      return null;
    }
  });
}

test.describe("AI personality (Sprint 04 Phase 2)", () => {
  test("GET /personality/me returns merged shape with preamble", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "No bearer token found");
      return;
    }

    const res = await page.request.get(
      `${API_URL}/api/ai/personality/me`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("resolved");
    expect(body).toHaveProperty("preamble");
    expect(body.resolved).toHaveProperty("tone");
    expect(body.resolved).toHaveProperty("vocabulary_level");
    expect(body.resolved).toHaveProperty("verbosity");
    expect(body.preamble).toContain("Voice profile");
  });

  test("PATCH /personality/me persists a tone change", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "No bearer token found");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };

    const patchRes = await page.request.patch(
      `${API_URL}/api/ai/personality/me`,
      { headers, data: { tone: "playful" } },
    );
    expect(patchRes.status()).toBe(200);
    const body = await patchRes.json();
    expect(body.resolved.tone).toBe("playful");

    // Read-back confirms persistence
    const readRes = await page.request.get(
      `${API_URL}/api/ai/personality/me`,
      { headers },
    );
    expect((await readRes.json()).stored.tone).toBe("playful");
  });

  test("PATCH rejects invalid enum with 422", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "No bearer token found");
      return;
    }
    const res = await page.request.patch(
      `${API_URL}/api/ai/personality/me`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { tone: "sarcastic" },
      },
    );
    expect(res.status()).toBe(422);
  });

  test("/settings/ai shows Personality section", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/ai");

    await expect(page.locator("text=Personality")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=Preview preamble")).toBeVisible();
  });
});
