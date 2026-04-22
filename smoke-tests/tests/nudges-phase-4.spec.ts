/**
 * Smoke test: Sprint 05 Phase 4 - admin rule engine.
 *
 * Exercises:
 * - POST /api/admin/nudges/rules creates a rule; GET lists it; preview-count
 *   returns a number; PATCH updates name; DELETE removes it
 * - /admin/ai/nudges renders both tabs (Quiet hours + Rules)
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

const BASIC_RULE_SQL =
  "SELECT assigned_to AS member_id, id AS entity_id, " +
  "'personal_task' AS entity_kind, due_at AS scheduled_for " +
  "FROM personal_tasks WHERE status = 'pending' LIMIT 100";

test.describe("Sprint 05 Phase 4 - admin rule engine", () => {
  test("rule CRUD round-trip + preview-count", async ({ page }) => {
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

    const unique = `smoke rule ${Date.now()}`;

    // Create
    const createRes = await page.request.post(
      `${API_URL}/api/admin/nudges/rules`,
      {
        headers,
        data: {
          name: unique,
          template_sql: BASIC_RULE_SQL,
          severity: "normal",
          default_lead_time_minutes: 5,
        },
      },
    );
    expect(createRes.status()).toBe(200);
    const created = await createRes.json();
    expect(created.name).toBe(unique);
    expect(created.canonical_sql).toBeTruthy();

    try {
      // List
      const listRes = await page.request.get(
        `${API_URL}/api/admin/nudges/rules`,
        { headers },
      );
      const rules = await listRes.json();
      expect(Array.isArray(rules)).toBe(true);
      expect(rules.some((r: { id: string }) => r.id === created.id)).toBe(true);

      // Preview count
      const prevRes = await page.request.post(
        `${API_URL}/api/admin/nudges/rules/${created.id}/preview-count`,
        { headers, data: {} },
      );
      expect(prevRes.status()).toBe(200);
      const prev = await prevRes.json();
      expect(typeof prev.count).toBe("number");
      expect(prev).toHaveProperty("capped");
      expect(prev).toHaveProperty("error");

      // Patch
      const patchRes = await page.request.patch(
        `${API_URL}/api/admin/nudges/rules/${created.id}`,
        { headers, data: { name: `${unique} edited` } },
      );
      expect(patchRes.status()).toBe(200);
      const patched = await patchRes.json();
      expect(patched.name).toBe(`${unique} edited`);
    } finally {
      // Always clean up
      await page.request.delete(
        `${API_URL}/api/admin/nudges/rules/${created.id}`,
        { headers },
      );
    }
  });

  test("bad SQL is rejected with 422 and tagged error", async ({ page }) => {
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
    const r = await page.request.post(
      `${API_URL}/api/admin/nudges/rules`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          name: `bad ${Date.now()}`,
          template_sql: "DROP TABLE personal_tasks",
          severity: "normal",
        },
      },
    );
    expect(r.status()).toBe(422);
    const body = await r.json();
    expect(typeof body.detail).toBe("string");
    expect(body.detail).toMatch(/^\[/); // tag like [not-select]
  });

  test("/admin/ai/nudges renders both tabs", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/ai/nudges");
    await expect(page.locator("text=Quiet hours").first()).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=Rules").first()).toBeVisible();
    // Click the Rules tab and assert the card header renders
    await page.getByText("Rules").first().click();
    await expect(page.locator("text=Custom nudge rules")).toBeVisible({
      timeout: 5000,
    });
    await expect(page.locator("text=Add rule")).toBeVisible();
  });
});
