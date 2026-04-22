/**
 * Smoke test: Sprint 05 Phase 5 - AI-driven nudge discovery regression guard.
 *
 * Phase 5 ships NO new routes, NO admin UI, and NO migration. The entire
 * surface is the scheduler tick (nudge_ai_discovery_tick) emitting
 * trigger_kind='ai_suggested' NudgeProposals that ride the existing
 * P1/P2/P3 dispatch pipeline (quiet hours, batching, dedupe, held-copy
 * composer). Smoke coverage is therefore non-regression of the shared
 * pipeline when ai_suggested items are present.
 *
 * Assertions:
 * - GET /api/nudges/me still returns 200 with the expected array shape
 *   and item-level trigger_kind field; if any item has
 *   trigger_kind='ai_suggested', its body is a non-empty string.
 * - The inbox surface (/personal) renders with no console errors even
 *   when ai_suggested dispatches are present in the feed.
 *
 * Skips cleanly if AI is disabled (e.g. no ANTHROPIC_API_KEY on the
 * target environment), matching the Phase 4 skip pattern.
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

test.describe("Sprint 05 Phase 5 - AI-driven nudge discovery", () => {
  test("GET /api/nudges/me accepts ai_suggested trigger_kind in item shape", async ({
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

    const r = await page.request.get(`${API_URL}/api/nudges/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(r.status()).toBe(200);
    const dispatches = await r.json();
    expect(Array.isArray(dispatches)).toBe(true);

    // Phase 5's ai_suggested items must not break the pipeline. If the
    // discovery tick has fired in the test window, validate the shape;
    // otherwise the empty / non-ai case is also valid.
    for (const dispatch of dispatches) {
      expect(dispatch).toHaveProperty("items");
      expect(Array.isArray(dispatch.items)).toBe(true);
      for (const item of dispatch.items) {
        expect(typeof item.trigger_kind).toBe("string");
        if (item.trigger_kind === "ai_suggested") {
          // Phase 3 composer guarantees body; Phase 5 rides that pipeline.
          expect(typeof dispatch.body).toBe("string");
          expect((dispatch.body || "").length).toBeGreaterThan(0);
        }
      }
    }
  });

  test("inbox /personal renders without console errors when ai_suggested items are present", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled");
      return;
    }

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/personal");
    await page.waitForSelector("text=Personal", { timeout: 10000 });

    // Allow the feed to hydrate.
    await page.waitForTimeout(1000);

    // Filter out benign noise (favicon 404s, dev HMR) and keep genuine errors.
    const real = consoleErrors.filter(
      (e) => !/favicon|ServiceWorker|Manifest/i.test(e),
    );
    expect(real, `unexpected console errors: ${real.join(" | ")}`).toHaveLength(
      0,
    );
  });

  // Readme
  //
  // Phase 5 ships NO new REST routes, NO admin UI, and NO migration.
  // All behavior is backend-only: a scheduler tick that emits
  // trigger_kind='ai_suggested' NudgeProposals which ride the shared
  // P1/P2/P3 pipeline (quiet hours, batching, dedupe, composer). This
  // smoke file's purpose is regression coverage only; the primary
  // Phase 5 verification lives in backend unit tests
  // (test_ai_discovery.py, test_ai_discovery_service.py, and the
  // P1-P5 dedupe-boundary cases in test_nudges.py).
});
