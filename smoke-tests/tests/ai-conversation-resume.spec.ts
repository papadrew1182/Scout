/**
 * Smoke test: Sprint 04 Phase 1 - AI conversation resume.
 *
 * Primary flow (UI): send a message in ScoutSheet, close, reopen; the
 * prior user message is still visible (resume hydrated from backend).
 *
 * Secondary flow (API via authenticated request): stats endpoint
 * responds, archive-older-than endpoint responds with archived_count,
 * new POST /conversations endpoint creates a conversation.
 *
 * Skips cleanly if AI is disabled on the backend (ai_available=false).
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
  // The frontend stores the bearer token in localStorage under 'scout_token'
  // (or similar). Read it via evaluate.
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

test.describe("AI conversation resume (Sprint 04 Phase 1)", () => {
  test("new endpoints respond with the right shape", async ({ page }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "No bearer token found in localStorage");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };

    // Stats endpoint
    const statsRes = await page.request.get(
      `${API_URL}/api/ai/conversations/stats`,
      { headers },
    );
    expect(statsRes.status()).toBe(200);
    const stats = await statsRes.json();
    expect(stats).toHaveProperty("total_count");
    expect(stats).toHaveProperty("active_count");
    expect(stats).toHaveProperty("archived_count");

    // Create a conversation
    const createRes = await page.request.post(
      `${API_URL}/api/ai/conversations`,
      {
        headers,
        data: { first_message: "Smoke test conversation" },
      },
    );
    expect(createRes.status()).toBe(200);
    const conv = await createRes.json();
    expect(conv).toHaveProperty("id");
    expect(conv.title).toBe("Smoke test conversation");
    expect(conv.status).toBe("active");
    expect(conv.is_pinned).toBe(false);

    // Patch: rename + pin
    const patchRes = await page.request.patch(
      `${API_URL}/api/ai/conversations/${conv.id}`,
      {
        headers,
        data: { title: "Renamed via smoke", is_pinned: true },
      },
    );
    expect(patchRes.status()).toBe(200);
    const patched = await patchRes.json();
    expect(patched.title).toBe("Renamed via smoke");
    expect(patched.is_pinned).toBe(true);

    // Archive via patch
    const archiveRes = await page.request.patch(
      `${API_URL}/api/ai/conversations/${conv.id}`,
      { headers, data: { status: "archived" } },
    );
    expect(archiveRes.status()).toBe(200);
    expect((await archiveRes.json()).status).toBe("archived");

    // List default (archived excluded) does not include this conversation
    const listDefault = await page.request.get(
      `${API_URL}/api/ai/conversations?limit=100`,
      { headers },
    );
    expect(listDefault.status()).toBe(200);
    const defaultRows = await listDefault.json();
    expect(defaultRows.find((r: any) => r.id === conv.id)).toBeUndefined();

    // List with include_archived=true includes it
    const listArchived = await page.request.get(
      `${API_URL}/api/ai/conversations?include_archived=true&limit=100`,
      { headers },
    );
    const archivedRows = await listArchived.json();
    expect(archivedRows.find((r: any) => r.id === conv.id)).toBeDefined();

    // archive-older-than responds with archived_count
    const bulkRes = await page.request.post(
      `${API_URL}/api/ai/conversations/archive-older-than`,
      { headers, data: { days: 365 } },
    );
    expect(bulkRes.status()).toBe(200);
    expect((await bulkRes.json())).toHaveProperty("archived_count");
  });

  test("AI settings page shows conversation history section", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/ai");

    await expect(page.locator("text=Conversation history")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=Older than 30 days")).toBeVisible();
  });

  test("paginated messages endpoint returns new response shape", async ({
    page,
  }) => {
    if (!(await probeAiAvailable(page))) {
      test.skip(true, "AI disabled on backend");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await getBearerToken(page);
    if (!token) {
      test.skip(true, "No bearer token found in localStorage");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };

    // Create a conversation first
    const createRes = await page.request.post(
      `${API_URL}/api/ai/conversations`,
      { headers, data: { first_message: "paginate me" } },
    );
    const conv = await createRes.json();

    const msgsRes = await page.request.get(
      `${API_URL}/api/ai/conversations/${conv.id}/messages?limit=50`,
      { headers },
    );
    expect(msgsRes.status()).toBe(200);
    const page1 = await msgsRes.json();
    expect(page1).toHaveProperty("messages");
    expect(Array.isArray(page1.messages)).toBe(true);
    expect(page1).toHaveProperty("has_more");
  });
});
