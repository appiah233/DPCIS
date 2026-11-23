import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch {
  const cache = path.join(process.env.LOCALAPPDATA, "npm-cache/_npx");
  for (const folder of fs.readdirSync(cache)) {
    const candidate = path.join(cache, folder, "node_modules/playwright");
    if (fs.existsSync(candidate)) { playwright = require(candidate); break; }
  }
}
assert(playwright, "Existing Playwright required");
const session = await fetch("http://127.0.0.1:8000/__test_session").then((r) => r.json());
assert(session.test_session, "Isolated backend required");
const response = await fetch("http://127.0.0.1:8000/api/admin/exams", {
  method: "POST",
  headers: { Authorization: `Bearer ${session.token}`, "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Crop retry regression", duration_minutes: 30 }),
});
assert(response.ok);
const exam = await response.json();
let browser;
for (const options of [{ headless: true }, { headless: true, channel: "chrome" }, { headless: true, channel: "msedge" }]) {
  try { browser = await playwright.chromium.launch(options); break; } catch { /* next installed browser */ }
}
assert(browser, "Installed Chromium browser required");
try {
  for (const width of [320, 360, 375, 390, 412, 768, 1024, 1280, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    const page = await context.newPage();
    page.on("pageerror", (error) => console.error(error.message));
    try {
      await page.goto(`http://127.0.0.1:5173/admin/exams/${exam.id}`);
      await page.getByRole("tab", { name: "Questions (0)", exact: true }).click();
      await page.locator('input[type="file"]').first().setInputFiles(
        path.resolve("../backend/tests/fixtures/graphics_boundaries.pdf"),
      );
      await page.getByRole("tab", { name: "Answer key", exact: true }).click();
      await page.getByLabel("Answers used for marking").fill("AAA");
      await page.getByRole("button", { name: "Preview Questions", exact: true }).click();
      await page.getByRole("button", { name: "Edit on full page", exact: true }).first().click();
      const dialog = page.getByRole("dialog");
      const region = dialog.getByRole("region", { name: "Selected crop region. Use arrow keys to nudge position.", exact: true });
      await region.focus();
      await page.keyboard.press("ArrowDown");
      const selection = await region.getAttribute("style");
      // Send invalid coordinates to the real backend once; no fabricated API response.
      let rejectNext = true;
      await page.route("**/questions/*/crops", async (route) => {
        if (!rejectNext) return route.continue();
        rejectNext = false;
        const body = route.request().postDataJSON();
        body.regions[0].bbox = [0, 0, 595, 10];
        await route.continue({ postData: JSON.stringify(body) });
      });
      await dialog.getByRole("button", { name: "Apply crop", exact: true }).click();
      await dialog.getByRole("alert").waitFor();
      assert.equal(await region.getAttribute("style"), selection, "Failed save must retain selection");
      await dialog.getByRole("button", { name: "Apply crop", exact: true }).click();
      await dialog.waitFor({ state: "hidden" });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      console.log(`${width}: real 422 retained selection, retry succeeded, no horizontal overflow`);
    } catch (error) {
      console.error((await page.locator("body").innerText()).slice(0, 1500));
      throw error;
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
