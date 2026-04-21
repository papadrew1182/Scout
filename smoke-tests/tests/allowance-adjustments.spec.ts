/**
 * Smoke test: parent bonus / penalty adjustments.
 *
 * Admin goes to /admin/allowance, uses the Bonus/Penalty card to apply
 * one of each to the first kid, and asserts the resulting ledger rows
 * land with the right sign and entry_type via the API.
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

async function currentFamilyId(page: Page): Promise<string | null> {
  const token = await currentToken(page);
  const res = await page.request.get(`${API_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token ?? ""}` },
  });
  if (!res.ok()) return null;
  const body = await res.json();
  return body?.family_id ?? null;
}

interface LedgerRow {
  id: string;
  family_member_id: string;
  entry_type: string;
  amount_cents: number;
  note: string | null;
  created_at: string;
}

async function listLedger(
  page: Page,
  familyId: string,
  memberId: string,
): Promise<LedgerRow[]> {
  const token = await currentToken(page);
  const res = await page.request.get(
    `${API_URL}/families/${familyId}/allowance/ledger?member_id=${memberId}`,
    { headers: { Authorization: `Bearer ${token ?? ""}` } },
  );
  expect(res.status()).toBe(200);
  return (await res.json()) as LedgerRow[];
}

test.describe("Allowance adjustments", () => {
  test("admin can apply one bonus and one penalty via /admin/allowance", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    const familyId = await currentFamilyId(page);
    expect(familyId).toBeTruthy();

    await page.goto("/admin/allowance");
    await expect(page.getByText("Bonus / penalty", { exact: true })).toBeVisible({
      timeout: 10000,
    });

    // The card auto-selects the first kid. We read the selected chip by
    // its "Select <name>" accessibleName so the test doesn't hardcode a
    // specific kid order across environments.
    const kidChips = page.getByRole("button", { name: /^Select / });
    await expect(kidChips.first()).toBeVisible({ timeout: 5000 });

    // Apply a $2.00 bonus.
    const bonusPut = page.waitForResponse(
      (r) => r.url().includes("/allowance/adjustments") && r.request().method() === "POST",
      { timeout: 10000 },
    );
    await page.getByLabel("Adjustment amount").fill("2");
    await page.getByLabel("Adjustment reason").fill("Smoke bonus");
    await page.getByRole("button", { name: "Apply bonus" }).click();
    const bonusResp = await bonusPut;
    expect(bonusResp.status()).toBe(201);
    const bonusBody = await bonusResp.json();
    expect(bonusBody.amount_cents).toBe(200);
    expect(bonusBody.entry_type).toBe("adjustment");
    expect(String(bonusBody.note)).toMatch(/^\[bonus\]/);

    await expect(page.getByText("Bonus applied", { exact: true })).toBeVisible({
      timeout: 5000,
    });

    // Apply a $1.50 penalty.
    const penaltyPut = page.waitForResponse(
      (r) => r.url().includes("/allowance/adjustments") && r.request().method() === "POST",
      { timeout: 10000 },
    );
    await page.getByLabel("Adjustment amount").fill("1.5");
    await page.getByLabel("Adjustment reason").fill("Smoke penalty");
    await page.getByRole("button", { name: "Apply penalty" }).click();
    const penaltyResp = await penaltyPut;
    expect(penaltyResp.status()).toBe(201);
    const penaltyBody = await penaltyResp.json();
    expect(penaltyBody.amount_cents).toBe(-150);
    expect(penaltyBody.entry_type).toBe("adjustment");
    expect(String(penaltyBody.note)).toMatch(/^\[penalty\]/);

    await expect(page.getByText("Penalty applied", { exact: true })).toBeVisible({
      timeout: 5000,
    });

    // Sanity: both rows appear in the ledger for that member.
    const memberId = bonusBody.family_member_id;
    const ledger = await listLedger(page, familyId!, memberId);
    expect(ledger.some((r) => r.id === bonusBody.id && r.amount_cents === 200)).toBe(true);
    expect(ledger.some((r) => r.id === penaltyBody.id && r.amount_cents === -150)).toBe(true);
  });
});
