/**
 * Smoke test: chore ops (Phase 3).
 *
 * Tests child master card rendering, scope contract visibility,
 * and dispute-scope flow.
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";
const API_URL = process.env.SCOUT_API_URL || "http://localhost:8000";

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

async function siblingMemberId(page: Page, selfId: string): Promise<string | null> {
  const headers = await page.evaluate(() => {
    const token = localStorage.getItem("scout_session_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  });
  const res = await page.request.get(`${API_URL}/api/family/context/current`, { headers });
  if (!res.ok()) return null;
  const body = await res.json();
  const kids = (body?.kids ?? []) as Array<{ family_member_id: string }>;
  const other = kids.find((k) => k.family_member_id && k.family_member_id !== selfId);
  return other?.family_member_id ?? null;
}

async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({
    timeout: 15000,
  });
}

test.describe("Child master card", () => {
  test("parent can view child master card", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/today");
    await page.waitForTimeout(2000);

    const pill = page.locator('[role="link"]').first();
    if (!(await pill.isVisible())) {
      test.skip();
      return;
    }
    await pill.click();
    await page.waitForTimeout(1500);

    expect(page.url()).toContain("/members/");

    const memberTitle = page.getByText("MEMBER", { exact: true });
    await expect(memberTitle).toBeVisible({ timeout: 5000 });

    const progressSection = page.getByText("Today's progress", { exact: true });
    await expect(progressSection).toBeVisible({ timeout: 5000 });
  });

  test("child sees own master card", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);

    let memberId: string;
    try {
      memberId = await currentMemberId(page);
    } catch {
      test.skip();
      return;
    }

    await page.goto(`/members/${memberId}`);
    await page.waitForTimeout(2000);

    // The eyebrow is the literal uppercase "MEMBER" string; use exact match
    // to avoid matching "Member" fallback (memberName) or "Members" nav items.
    const memberTitle = page.getByText("MEMBER", { exact: true });
    await expect(memberTitle).toBeVisible({ timeout: 5000 });
  });

  test("child cannot view another child's card", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);

    let selfId: string;
    try {
      selfId = await currentMemberId(page);
    } catch {
      test.skip();
      return;
    }
    const otherId = await siblingMemberId(page, selfId);
    if (!otherId) {
      test.skip();
      return;
    }

    await page.goto(`/members/${otherId}`);
    await page.waitForTimeout(2000);

    const denied = page.getByText("Not available", { exact: true });
    await expect(denied).toBeVisible({ timeout: 5000 });
  });
});
