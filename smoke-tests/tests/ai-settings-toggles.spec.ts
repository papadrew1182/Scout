/**
 * Smoke test: Scout AI capability toggles.
 *
 * Admin flips allow_general_chat and allow_homework_help from
 * /admin/scout-ai, asserts each PUT /admin/config/family/scout_ai.toggles
 * round-trips with the new value, and confirms the saved value persists
 * on reload.
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
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({ timeout: 15000 });
}

async function currentToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem("scout_session_token"));
}

async function readToggles(
  page: Page,
): Promise<{ allow_general_chat: boolean; allow_homework_help: boolean }> {
  const token = await currentToken(page);
  const res = await page.request.get(`${API_URL}/admin/config/family`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(res.status()).toBe(200);
  const rows = (await res.json()) as Array<{ key: string; value: Record<string, unknown> }>;
  const row = rows.find((r) => r.key === "scout_ai.toggles");
  const val = (row?.value ?? {}) as Record<string, unknown>;
  return {
    allow_general_chat: Boolean(val.allow_general_chat ?? true),
    allow_homework_help: Boolean(val.allow_homework_help ?? true),
  };
}

test.describe("Scout AI capability toggles", () => {
  test("admin can flip allow_general_chat and allow_homework_help", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);

    const original = await readToggles(page);

    // Wait for one PUT per flip so we can assert on the request bodies.
    const firstPut = page.waitForRequest(
      (r) =>
        r.method() === "PUT" &&
        r.url().includes("/admin/config/family/scout_ai.toggles"),
      { timeout: 10000 },
    );

    await page.goto("/admin/scout-ai");
    await expect(page.getByText("Capability toggles", { exact: true })).toBeVisible({
      timeout: 10000,
    });

    // Flip "Allow general chat" — the switch renders with
    // accessibilityLabel="Allow general chat" which web shows as
    // aria-label, matching getByRole("switch", {name: "..."}).
    const generalSwitch = page.getByRole("switch", { name: "Allow general chat" });
    await expect(generalSwitch).toBeVisible({ timeout: 5000 });
    await generalSwitch.click();

    const req1 = await firstPut;
    const body1 = JSON.parse(req1.postData() || "{}");
    expect(body1?.value?.allow_general_chat).toBe(!original.allow_general_chat);

    // Flip "Homework help (kids)" while we're here to cover both toggles.
    const secondPut = page.waitForRequest(
      (r) =>
        r.method() === "PUT" &&
        r.url().includes("/admin/config/family/scout_ai.toggles"),
      { timeout: 10000 },
    );
    const homeworkSwitch = page.getByRole("switch", { name: "Homework help (kids)" });
    await homeworkSwitch.click();
    const req2 = await secondPut;
    const body2 = JSON.parse(req2.postData() || "{}");
    expect(body2?.value?.allow_homework_help).toBe(!original.allow_homework_help);

    // Confirm persistence by re-reading the config directly.
    await page.waitForTimeout(500);
    const after = await readToggles(page);
    expect(after.allow_general_chat).toBe(!original.allow_general_chat);
    expect(after.allow_homework_help).toBe(!original.allow_homework_help);

    // Clean up — flip both back so the seed is idempotent across runs.
    await generalSwitch.click();
    await homeworkSwitch.click();
    await page.waitForTimeout(500);
    const restored = await readToggles(page);
    expect(restored.allow_general_chat).toBe(original.allow_general_chat);
    expect(restored.allow_homework_help).toBe(original.allow_homework_help);
  });
});
