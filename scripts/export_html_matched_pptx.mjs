#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { copyFile, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const EXTRA_MODULE_DIRS = [
  process.env.CODEX_NODE_MODULES,
  "/Users/linhan12312/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
].filter(Boolean);

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

function parseArgs(argv) {
  const args = {
    html: "",
    output: "",
    plan: "",
    storyboardPlan: "",
    slidesDir: "",
    chrome: process.env.CHROME_PATH || "",
    python: process.env.PYTHON || "python3",
    noTransitions: false,
  };
  const positional = [];
  for (let i = 2; i < argv.length; i += 1) {
    const value = argv[i];
    if (value === "--plan") args.plan = argv[++i];
    else if (value === "--storyboard-plan") args.storyboardPlan = argv[++i];
    else if (value === "--slides-dir") args.slidesDir = argv[++i];
    else if (value === "--chrome") args.chrome = argv[++i];
    else if (value === "--python") args.python = argv[++i];
    else if (value === "--no-transitions") args.noTransitions = true;
    else if (value === "--help" || value === "-h") args.help = true;
    else positional.push(value);
  }
  [args.html, args.output] = positional;
  return args;
}

function usage() {
  console.log("Usage: node export_html_matched_pptx.mjs <index.html> <output.pptx> [--plan deck-plan.json] [--storyboard-plan storyboard-plan.json] [--slides-dir dir] [--chrome path]");
}

function loadJson(file) {
  return JSON.parse(require("node:fs").readFileSync(file, "utf8"));
}

async function launchChromium(chromium, explicitPath) {
  const candidates = [
    explicitPath,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ].filter((value, index, values) => value && values.indexOf(value) === index && existsSync(value));

  const errors = [];
  for (const executablePath of candidates) {
    try {
      return await chromium.launch({ headless: true, executablePath });
    } catch (error) {
      errors.push(`${executablePath}: ${String(error.message || error).split("\n")[0]}`);
    }
  }
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    errors.push(`bundled Chromium: ${String(error.message || error).split("\n")[0]}`);
  }
  throw new Error(`Unable to launch Chromium. ${errors.join(" | ")}`);
}

async function prepareSlide(page, slideIndex, visibleSteps) {
  await page.evaluate(({ index, steps }) => {
    let style = document.getElementById("pptx-capture-static");
    if (!style) {
      style = document.createElement("style");
      style.id = "pptx-capture-static";
      style.textContent = "*,*::before,*::after{animation:none!important;transition:none!important}";
      document.head.appendChild(style);
    }
    const slides = Array.from(document.querySelectorAll(".slide"));
    slides.forEach((slide, idx) => slide.classList.toggle("active", idx === index));
    const slide = slides[index];
    if (!slide) throw new Error(`slide index ${index} not found`);

    slide.querySelectorAll("[data-reveal]").forEach((node) => node.classList.add("revealed"));
    const allowed = steps === null ? null : new Set(steps.map(String));
    slide.querySelectorAll("[data-step]").forEach((node) => {
      const reveal = allowed === null || allowed.has(String(node.dataset.step));
      node.classList.toggle("revealed", reveal);
    });
    slide.querySelectorAll("[data-count-to]").forEach((node) => {
      const target = Number.parseFloat(node.dataset.countTo || "0");
      const decimals = Number.parseInt(node.dataset.decimals || "0", 10);
      if (Number.isFinite(target)) node.textContent = target.toFixed(Number.isFinite(decimals) ? decimals : 0);
    });
  }, { index: slideIndex, steps: visibleSteps });
  await page.waitForTimeout(80);
}

function buildStates(htmlCount, plan, storyboardPlan) {
  if (!storyboardPlan) {
    return Array.from({ length: htmlCount }, (_, index) => ({
      id: plan?.slides?.[index]?.id || `slide-${index + 1}`,
      source_slide_id: plan?.slides?.[index]?.id || `slide-${index + 1}`,
      slideIndex: index,
      visible_steps: null,
      speaker_notes: plan?.slides?.[index]?.speaker_notes || "",
    }));
  }
  if (!plan?.slides?.length) throw new Error("--storyboard-plan requires --plan so source slide ids can be mapped to HTML order");
  const sourceIndex = new Map(plan.slides.map((slide, index) => [String(slide.id), index]));
  return storyboardPlan.slides.map((state) => {
    const sourceId = String(state.source_slide_id || state.id || "");
    if (!sourceIndex.has(sourceId)) throw new Error(`storyboard source slide not found in plan: ${sourceId}`);
    return {
      ...state,
      source_slide_id: sourceId,
      slideIndex: sourceIndex.get(sourceId),
      visible_steps: Array.isArray(state.visible_steps) ? state.visible_steps : null,
    };
  });
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help || !args.html || !args.output) {
    usage();
    process.exit(args.help ? 0 : 2);
  }

  const htmlPath = path.resolve(args.html);
  const outputPath = path.resolve(args.output);
  if (!existsSync(htmlPath)) throw new Error(`HTML not found: ${htmlPath}`);
  const plan = args.plan ? loadJson(path.resolve(args.plan)) : null;
  const storyboardPlan = args.storyboardPlan ? loadJson(path.resolve(args.storyboardPlan)) : null;

  const { chromium } = loadModule("playwright");
  const PptxGenJS = loadModule("pptxgenjs");
  const browser = await launchChromium(chromium, args.chrome);
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.waitForSelector(".slide", { timeout: 10000 });
  const htmlCount = await page.locator(".slide").count();
  const states = buildStates(htmlCount, plan, storyboardPlan);

  const slidesDir = path.resolve(args.slidesDir || path.join(path.dirname(outputPath), "assets", "pptx-rendered-slides"));
  await mkdir(slidesDir, { recursive: true });
  const captures = [];
  try {
    for (let i = 0; i < states.length; i += 1) {
      const state = states[i];
      await prepareSlide(page, state.slideIndex, state.visible_steps);
      const file = path.join(slidesDir, `slide-${String(i + 1).padStart(2, "0")}.png`);
      await page.screenshot({ path: file, fullPage: false });
      captures.push({
        index: i + 1,
        id: state.id,
        source_slide_id: state.source_slide_id,
        visible_steps: state.visible_steps,
        file,
      });
    }
  } finally {
    await page.close();
    await browser.close();
  }

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "html-ppt-maker";
  pptx.subject = plan?.title || path.basename(htmlPath);
  pptx.title = plan?.title || path.basename(htmlPath, path.extname(htmlPath));
  pptx.company = "OpenAI Codex";
  pptx.lang = "zh-CN";
  for (let i = 0; i < captures.length; i += 1) {
    const slide = pptx.addSlide();
    slide.background = { color: "FFFFFF" };
    slide.addImage({ path: captures[i].file, x: 0, y: 0, w: 13.333, h: 7.5 });
    const notes = states[i].speaker_notes || states[i].speaker_note || "";
    if (notes) slide.addNotes(notes);
  }

  const tempDir = await mkdtemp(path.join(tmpdir(), "html-ppt-maker-"));
  const basePptx = path.join(tempDir, "base.pptx");
  await pptx.writeFile({ fileName: basePptx });

  let transitionStatus = "not-applied";
  if (args.noTransitions) {
    await copyFile(basePptx, outputPath);
  } else {
    const transitionScript = path.join(path.dirname(fileURLToPath(import.meta.url)), "apply_ppt_transitions.py");
    const transitionPlan = args.storyboardPlan || args.plan;
    const command = [transitionScript, basePptx, "--output", outputPath];
    if (transitionPlan) command.push("--plan", path.resolve(transitionPlan));
    const result = spawnSync(args.python, command, { encoding: "utf8" });
    if (result.status === 0) {
      transitionStatus = "applied";
    } else {
      await copyFile(basePptx, outputPath);
      transitionStatus = "degraded-no-transitions";
      console.warn(`[WARN] transition injection failed; preserved valid PPTX without transitions: ${(result.stderr || result.stdout || "unknown error").trim()}`);
    }
  }

  const manifest = {
    html: htmlPath,
    output: outputPath,
    html_slide_count: htmlCount,
    exported_slide_count: captures.length,
    storyboard: Boolean(storyboardPlan),
    transitions: transitionStatus,
    captures,
  };
  const manifestPath = outputPath.replace(/\.pptx$/i, "-export.json");
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  await rm(tempDir, { recursive: true, force: true });
  console.log(`[OK] wrote HTML-matched PPTX: ${outputPath} (${captures.length} slides, transitions=${transitionStatus})`);
  console.log(`[OK] screenshots: ${slidesDir}`);
  console.log(`[OK] export manifest: ${manifestPath}`);
}

main().catch((error) => {
  console.error(`[FAIL] ${error.message || error}`);
  process.exit(1);
});
