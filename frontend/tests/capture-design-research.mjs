import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const frontendRoot = path.resolve(__dirname, "..");
const outDir = path.join(repoRoot, "docs", "design-research");

function loadPlaywright() {
  const requireFromHere = createRequire(import.meta.url);
  const candidates = [frontendRoot, repoRoot];
  const npxCache = path.join(process.env.LOCALAPPDATA || "", "npm-cache", "_npx");
  if (fs.existsSync(npxCache)) {
    for (const entry of fs.readdirSync(npxCache)) {
      const nm = path.join(npxCache, entry, "node_modules");
      if (fs.existsSync(path.join(nm, "playwright"))) {
        candidates.push(nm);
      }
    }
  }
  for (const base of candidates) {
    try {
      const resolved = requireFromHere.resolve("playwright", { paths: [base] });
      return requireFromHere(resolved);
    } catch {
      // continue
    }
  }
  throw new Error("Could not resolve 'playwright'");
}

const TARGETS = [
  {
    id: "01-canvas-lms",
    product: "Canvas LMS (Instructure)",
    category: "Exam/assessment delivery",
    url: "https://www.instructure.com/canvas",
  },
  {
    id: "02-inspera-assessment",
    product: "Inspera Assessment",
    category: "Exam/assessment delivery",
    url: "https://www.inspera.com/products/inspera-assessment/",
  },
  {
    id: "03-tao-testing",
    product: "TAO Testing (TAO Advance)",
    category: "Exam/assessment delivery",
    url: "https://www.taotesting.com/",
  },
  {
    id: "04-sat-bluebook",
    product: "College Board SAT Bluebook",
    category: "Standardised test practice UI",
    url: "https://bluebook.collegeboard.org/students",
  },
  {
    id: "05-gradescope",
    product: "Gradescope Assessment & Analytics",
    category: "Admin/analytics dashboard",
    url: "https://www.gradescope.com/",
  },
  {
    id: "06-stripe-dashboard-docs",
    product: "Stripe Dashboard Documentation",
    category: "Admin/analytics dashboard",
    url: "https://docs.stripe.com/dashboard/basics",
  },
  {
    id: "07-linear-interface",
    product: "Linear Product Interface",
    category: "Admin/analytics dashboard",
    url: "https://linear.app/features",
  },
  {
    id: "08-khan-academy",
    product: "Khan Academy Digital Practice",
    category: "Standardised test practice UI",
    url: "https://www.khanacademy.org/",
  },
];

async function main() {
  fs.mkdirSync(outDir, { recursive: true });
  const staleMoodle = path.join(outDir, "01-moodle-quiz-docs.png");
  if (fs.existsSync(staleMoodle)) {
    fs.unlinkSync(staleMoodle);
  }
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  });
  const results = [];

  try {
    for (const t of TARGETS) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      const fileName = `${t.id}.png`;
      const filePath = path.join(outDir, fileName);
      try {
        const res = await page.goto(t.url, { waitUntil: "domcontentloaded", timeout: 20000 });
        await page.waitForTimeout(1500);
        const title = await page.title();
        await page.screenshot({ path: filePath, fullPage: false });
        results.push({
          ...t,
          status: res ? res.status() : 0,
          pageTitle: title,
          screenshot: `docs/design-research/${fileName}`,
          capturedAt: new Date().toISOString(),
          ok: true,
        });
        console.log(`Captured ${t.id} (${res?.status()}): ${title}`);
      } catch (err) {
        results.push({
          ...t,
          ok: false,
          error: String(err),
          capturedAt: new Date().toISOString(),
        });
        console.warn(`Failed ${t.id}: ${err}`);
      } finally {
        await context.close();
      }
    }

    const mockupsDir = path.join(outDir, "mockups");
    for (const htmlFile of [
      "attempt-option-a.html",
      "attempt-option-b.html",
      "result-option-a.html",
      "result-option-b.html",
    ]) {
      const htmlPath = path.join(mockupsDir, htmlFile);
      if (fs.existsSync(htmlPath)) {
        const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
        const page = await context.newPage();
        await page.goto(new URL(`file:///${htmlPath.replace(/\\/g, "/")}`).href, {
          waitUntil: "domcontentloaded",
        });
        await page.waitForTimeout(200);
        const pngPath = htmlPath.replace(/\.html$/, ".png");
        await page.screenshot({ path: pngPath, fullPage: true });
        console.log(`Rendered mockup screenshot: ${path.basename(pngPath)}`);
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(outDir, "sources.json"), JSON.stringify(results, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
