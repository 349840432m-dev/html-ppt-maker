#!/usr/bin/env node
import { createRequire } from "node:module";
import { access, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const EXTRA_MODULE_DIRS = [
  process.env.CODEX_NODE_MODULES,
  "/Users/linhan12312/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
].filter(Boolean);
const LAYOUT_ALIASES = new Map([
  ["journey-blueprint", "journey"],
  ["section-impact", "section"],
  ["quote-principle", "quote"],
  ["process-map", "process"],
  ["case-walkthrough", "case"],
]);

function loadModule(name) {
  try {
    return require(name);
  } catch (firstError) {
    for (const dir of EXTRA_MODULE_DIRS) {
      try {
        return require(path.join(dir, name));
      } catch {
        // Try the next configured runtime.
      }
    }
    throw new Error(`Cannot load ${name}. Install it or set CODEX_NODE_MODULES. ${firstError.message}`);
  }
}

function normalizeLayout(value) {
  const key = String(value || "").trim().toLowerCase();
  return LAYOUT_ALIASES.get(key) || key;
}

function parseArgs(argv) {
  const args = { html: "", plan: "", out: "", chrome: process.env.CHROME_PATH || "" };
  const positional = [];
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--out") args.out = argv[++i];
    else if (argv[i] === "--chrome") args.chrome = argv[++i];
    else if (argv[i] === "--help" || argv[i] === "-h") args.help = true;
    else positional.push(argv[i]);
  }
  [args.html, args.plan] = positional;
  return args;
}

async function launch(chromium, chrome) {
  const candidates = [chrome, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].filter(Boolean);
  for (const executablePath of candidates) {
    try {
      await access(executablePath);
      return await chromium.launch({ headless: true, executablePath });
    } catch {
      // Try the next browser candidate.
    }
  }
  return chromium.launch({ headless: true });
}

function nonEmptyList(value) {
  if (Array.isArray(value)) return value.filter((item) => String(item || "").trim());
  return String(value || "").trim() ? [value] : [];
}

const args = parseArgs(process.argv);
if (args.help || !args.html || !args.plan) {
  console.log("Usage: node audit_layout_contract.mjs <index.html> <deck-plan.json> [--out report.json] [--chrome path]");
  process.exit(args.help ? 0 : 2);
}

try {
  const htmlPath = path.resolve(args.html);
  const planPath = path.resolve(args.plan);
  const plan = JSON.parse(await readFile(planPath, "utf8"));
  const specs = Array.isArray(plan.slides) ? plan.slides : [];
  if (!specs.length) throw new Error("deck plan has no slides");

  const { chromium } = loadModule("playwright");
  const browser = await launch(chromium, args.chrome);
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.waitForSelector(".slide", { timeout: 10000 });
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.textContent = "*,*::before,*::after{animation:none!important;transition:none!important}";
    document.head.appendChild(style);
    document.querySelectorAll(".slide").forEach((slide) => {
      slide.classList.add("active");
      slide.querySelectorAll("[data-reveal],[data-step]").forEach((node) => node.classList.add("revealed"));
    });
  });
  await page.waitForTimeout(80);
  const actual = await page.evaluate(() => {
    const visible = (node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && Number.parseFloat(style.opacity || "1") > 0.04 && rect.width > 1 && rect.height > 1;
    };
    return Array.from(document.querySelectorAll(".slide")).map((slide) => {
      const rect = slide.getBoundingClientRect();
      const role = (name) => Array.from(slide.querySelectorAll(`[data-role~="${name}"]`)).filter(visible).map((node) => {
        const box = node.getBoundingClientRect();
        return { tag: node.tagName.toLowerCase(), text: (node.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80), area_ratio: (box.width * box.height) / Math.max(1, rect.width * rect.height) };
      });
      const layoutClass = Array.from(slide.classList).find((name) => name.startsWith("layout-")) || "";
      return {
        id: slide.dataset.slideId || "",
        layout: layoutClass.replace(/^layout-/, ""),
        anchor: Array.from(slide.querySelectorAll("[data-primary-anchor]")).filter(visible).length,
        main: role("main-structure"),
        support: role("support"),
        rhythm: role("rhythm"),
      };
    });
  });
  await browser.close();

  const failures = [];
  const warnings = [];
  if (actual.length !== specs.length) failures.push(`slide count mismatch: plan=${specs.length}, html=${actual.length}`);
  for (let index = 0; index < Math.min(actual.length, specs.length); index += 1) {
    const dom = actual[index];
    const spec = specs[index];
    const sid = String(spec.id || `slide#${index + 1}`);
    if (dom.id !== sid) failures.push(`${sid}: HTML data-slide-id is '${dom.id || "missing"}'`);
    const expectedLayout = normalizeLayout(spec.layout_family || spec.type);
    const actualLayout = normalizeLayout(dom.layout);
    if (expectedLayout !== actualLayout) failures.push(`${sid}: layout mismatch plan=${expectedLayout}, html=${actualLayout || "missing"}`);
    if (dom.anchor < 1) failures.push(`${sid}: missing visible [data-primary-anchor]`);
    if (dom.main.length !== 1) failures.push(`${sid}: expected exactly 1 visible [data-role=main-structure], found ${dom.main.length}`);
    const budget = spec.element_budget || {};
    if (nonEmptyList(budget.supporting_elements).length && dom.support.length < 1) failures.push(`${sid}: supporting elements declared but no visible [data-role=support] exists`);
    if (nonEmptyList(budget.rhythm_element).length && dom.rhythm.length < 1) failures.push(`${sid}: rhythm element declared but no visible [data-role=rhythm] exists`);
    if (dom.main.length === 1 && dom.main[0].area_ratio < 0.08) warnings.push(`${sid}: main structure occupies only ${(dom.main[0].area_ratio * 100).toFixed(1)}% of the slide`);
  }

  const report = { html: htmlPath, plan: planPath, slide_count: actual.length, failures, warnings, slides: actual };
  if (args.out) await writeFile(path.resolve(args.out), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  warnings.forEach((warning) => console.log(`[WARN] ${warning}`));
  failures.forEach((failure) => console.error(`[FAIL] ${failure}`));
  if (failures.length) {
    console.error(`[FAIL] layout contract audit failed: ${failures.length} error(s), ${warnings.length} warning(s)`);
    process.exit(1);
  }
  console.log(`[OK] layout contract audit passed: ${actual.length} slides, warnings=${warnings.length}`);
} catch (error) {
  console.error(`[FAIL] ${error.message || error}`);
  process.exit(1);
}
