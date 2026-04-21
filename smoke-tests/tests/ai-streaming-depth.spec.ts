/**
 * Smoke test: AI chat streaming depth.
 *
 * Opens the streaming endpoint directly (POST /api/ai/chat/stream)
 * and asserts the SSE response contains multiple text_delta events
 * before the terminal done event. Catches regressions where the
 * backend silently collapses streaming into a single chunk or where
 * the stream terminates before any text is produced.
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

async function probeAiAvailable(page: Page): Promise<boolean> {
  try {
    const ready = await page.request.get(`${API_URL}/ready`);
    const data = await ready.json();
    return data.ai_available === true;
  } catch {
    return true;
  }
}

async function currentToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem("scout_session_token"));
}

/**
 * Parse an SSE body (the full buffered string) into a list of decoded
 * event objects. SSE frames are separated by a blank line; each data
 * line after "data: " is a JSON blob emitted by ai_chat_stream.
 */
function parseSse(body: string): Array<Record<string, unknown>> {
  const frames = body.split(/\n\n/);
  const events: Array<Record<string, unknown>> = [];
  for (const frame of frames) {
    for (const line of frame.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (!payload) continue;
      try {
        events.push(JSON.parse(payload));
      } catch {
        // Skip malformed frames; an assertion below will fail loudly
        // if there aren't enough good ones.
      }
    }
  }
  return events;
}

test.describe("Scout AI streaming depth", () => {
  test("SSE stream yields multiple text deltas before done", async ({ page }) => {
    const aiAvailable = await probeAiAvailable(page);
    if (!aiAvailable) {
      test.skip(true, "AI disabled on backend (ai_available=false)");
      return;
    }

    await login(page, ADULT_EMAIL, PASSWORD);
    const token = await currentToken(page);
    if (!token) {
      test.skip(true, "no session token available");
      return;
    }

    // Ask for something that requires a multi-sentence reply so we can
    // reliably expect more than one text chunk from Anthropic's SDK.
    const res = await page.request.post(`${API_URL}/api/ai/chat/stream`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      data: {
        message:
          "In exactly three short sentences, describe how Scout helps families stay organized.",
        surface: "personal",
      },
      timeout: 60_000,
    });

    expect(res.status(), await res.text().then((t) => t.slice(0, 200))).toBe(200);
    const body = await res.text();
    const events = parseSse(body);

    const textEvents = events.filter((e) => e.type === "text");
    const doneEvents = events.filter((e) => e.type === "done");
    const errorEvents = events.filter((e) => e.type === "error");

    // Guardrail: no errors during the stream
    expect(
      errorEvents,
      `stream emitted error events: ${JSON.stringify(errorEvents)}`,
    ).toHaveLength(0);

    // Depth: at least two text deltas arrived (regression trap — a
    // single-chunk response would mean streaming is broken).
    expect(
      textEvents.length,
      `expected > 1 text delta, got ${textEvents.length}`,
    ).toBeGreaterThan(1);

    // Ordering: a terminal done event exists and is the last event.
    expect(doneEvents.length).toBeGreaterThanOrEqual(1);
    const lastEvent = events[events.length - 1];
    expect(lastEvent?.type).toBe("done");

    // Content: concatenated deltas form a non-trivial response.
    const fullText = textEvents
      .map((e) => (typeof e.text === "string" ? e.text : ""))
      .join("");
    expect(fullText.length).toBeGreaterThan(20);
  });
});
