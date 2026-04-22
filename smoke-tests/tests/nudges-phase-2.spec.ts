/**
 * Smoke test: Sprint 05 Phase 2 - nudges APIs + UI surface.
 *
 * Exercises:
 * - GET /api/nudges/me returns the shape expected by the UI
 * - Admin GET /api/admin/family-config/quiet-hours returns the default
 *   when unset
 * - Admin PUT /api/admin/family-config/quiet-hours upserts and read-back
 *   confirms the value
 * - /settings/ai renders the Recent nudges section
 * - /admin/ai/nudges renders the Quiet hours control for admins
 *
 * Skips cleanly if AI is disabled.
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

test.describe("Sprint 05 Phase 2 - nudges APIs + UI", () => {
  test("GET /api/nudges/me returns array shape", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "no bearer token");
      return;
    }

    const r = await page.request.get(`${API_URL}/api/nudges/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(Array.isArray(body)).toBe(true);
    // If any dispatches exist, spot-check the shape
    if (body.length > 0) {
      const first = body[0];
      expect(first).toHaveProperty("status");
      expect(first).toHaveProperty("severity");
      expect(first).toHaveProperty("source_count");
      expect(first).toHaveProperty("items");
      expect(Array.isArray(first.items)).toBe(true);
    }
  });

  test("admin quiet-hours GET returns default then PUT round-trips", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "no bearer token");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };

    const getRes = await page.request.get(
      `${API_URL}/api/admin/family-config/quiet-hours`,
      { headers },
    );
    expect(getRes.status()).toBe(200);
    const before = await getRes.json();
    expect(before).toHaveProperty("start_local_minute");
    expect(before).toHaveProperty("end_local_minute");
    expect(before).toHaveProperty("is_default");

    const newStart = 23 * 60;
    const newEnd = 6 * 60 + 30;
    const putRes = await page.request.put(
      `${API_URL}/api/admin/family-config/quiet-hours`,
      {
        headers,
        data: { start_local_minute: newStart, end_local_minute: newEnd },
      },
    );
    expect(putRes.status()).toBe(200);
    const afterPut = await putRes.json();
    expect(afterPut.start_local_minute).toBe(newStart);
    expect(afterPut.end_local_minute).toBe(newEnd);
    expect(afterPut.is_default).toBe(false);

    const readBack = await page.request.get(
      `${API_URL}/api/admin/family-config/quiet-hours`,
      { headers },
    );
    const final = await readBack.json();
    expect(final.start_local_minute).toBe(newStart);
    expect(final.end_local_minute).toBe(newEnd);
    expect(final.is_default).toBe(false);

    // Restore (best-effort) so repeat runs don't leave state
    await page.request.put(
      `${API_URL}/api/admin/family-config/quiet-hours`,
      {
        headers,
        data: {
          start_local_minute: before.start_local_minute,
          end_local_minute: before.end_local_minute,
        },
      },
    );
  });

  test("/settings/ai renders Recent nudges section", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/ai");
    await expect(page.locator("text=Recent nudges")).toBeVisible({
      timeout: 10000,
    });
  });

  test("/admin/ai/nudges renders Quiet hours control for admins", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/ai/nudges");
    await expect(page.locator("text=Quiet hours")).toBeVisible({
      timeout: 10000,
    });
    // Start input placeholder is 22:00
    await expect(page.getByPlaceholder("22:00")).toBeVisible();
    await expect(page.getByPlaceholder("07:00")).toBeVisible();
  });
});
