#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, mkdtemp, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchChromium, loadModule } from "./lib/node-runtime.mjs";

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
  return JSON.parse(readFileSync(file, "utf8"));
}

function manifestFor(outputPath) {
  const parsed = path.parse(outputPath);
  return path.join(parsed.dir, `${parsed.name}-export.json`);
}

function assertSafeOutputs(outputPath, inputs) {
  if (path.extname(outputPath).toLowerCase() !== ".pptx") {
    throw new Error(`output must end in .pptx: ${outputPath}`);
  }
  const manifestPath = manifestFor(outputPath);
  for (const [label, inputPath] of inputs) {
    if (inputPath && outputPath === inputPath) {
      throw new Error(`output must not overwrite ${label}: ${outputPath}`);
    }
    if (inputPath && manifestPath === inputPath) {
      throw new Error(`export manifest must not overwrite ${label}: ${manifestPath}`);
    }
  }
  return manifestPath;
}

async function sha256File(file) {
  return createHash("sha256").update(await readFile(file)).digest("hex");
}

async function atomicCopy(source, target) {
  await mkdir(path.dirname(target), { recursive: true });
  const staged = path.join(path.dirname(target), `.${path.basename(target)}.${process.pid}.tmp`);
  try {
    await copyFile(source, staged);
    await rename(staged, target);
  } finally {
    await rm(staged, { force: true });
  }
}

async function atomicWrite(target, content) {
  await mkdir(path.dirname(target), { recursive: true });
  const staged = path.join(path.dirname(target), `.${path.basename(target)}.${process.pid}.tmp`);
  try {
    await writeFile(staged, content, "utf8");
    await rename(staged, target);
  } finally {
    await rm(staged, { force: true });
  }
}

async function waitForDocumentAssets(page) {
  await page.evaluate(async () => {
    const loadAssets = async () => {
      if (document.fonts?.ready) await document.fonts.ready;
      const images = Array.from(document.images);
      await Promise.all(images.map(async (image) => {
        if (image.complete && image.naturalWidth > 0) return;
        if (typeof image.decode === "function") await image.decode();
        else {
          await new Promise((resolve, reject) => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", () => reject(new Error(`image failed: ${image.currentSrc || image.src}`)), { once: true });
          });
        }
        if (image.naturalWidth <= 0) throw new Error(`image has no decoded pixels: ${image.currentSrc || image.src}`);
      }));
    };
    await Promise.race([
      loadAssets(),
      new Promise((_, reject) => setTimeout(() => reject(new Error("font/image readiness timed out after 10s")), 10000)),
    ]);
  });
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
  const planPath = args.plan ? path.resolve(args.plan) : "";
  const storyboardPlanPath = args.storyboardPlan ? path.resolve(args.storyboardPlan) : "";
  if (!existsSync(htmlPath)) throw new Error(`HTML not found: ${htmlPath}`);
  const manifestPath = assertSafeOutputs(
    outputPath,
    [["HTML input", htmlPath], ["deck plan", planPath], ["storyboard plan", storyboardPlanPath]],
  );
  if (storyboardPlanPath && !planPath) throw new Error("--storyboard-plan requires --plan");
  const plan = planPath ? loadJson(planPath) : null;
  const storyboardPlan = storyboardPlanPath ? loadJson(storyboardPlanPath) : null;

  const { chromium } = loadModule("playwright");
  const PptxGenJS = loadModule("pptxgenjs");
  const slidesDir = path.resolve(args.slidesDir || path.join(path.dirname(outputPath), "assets", "pptx-rendered-slides"));
  if (slidesDir === outputPath || slidesDir === manifestPath) {
    throw new Error(`--slides-dir must be a directory distinct from output files: ${slidesDir}`);
  }
  await mkdir(slidesDir, { recursive: true });
  const browser = await launchChromium(chromium, args.chrome);
  const captures = [];
  let htmlCount = 0;
  let states = [];
  let page;
  try {
    page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    await page.waitForSelector(".slide", { timeout: 10000 });
    await waitForDocumentAssets(page);
    htmlCount = await page.locator(".slide").count();
    if (plan?.slides?.length && plan.slides.length !== htmlCount) {
      throw new Error(`slide count mismatch: plan=${plan.slides.length}, html=${htmlCount}`);
    }
    states = buildStates(htmlCount, plan, storyboardPlan);
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
        width: 1280,
        height: 720,
        sha256: await sha256File(file),
      });
    }
  } finally {
    if (page) await page.close();
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
  const stagedPptx = path.join(tempDir, "final.pptx");
  let transitionStatus = "not-applied";
  try {
    await pptx.writeFile({ fileName: basePptx });
    if (args.noTransitions) {
      await copyFile(basePptx, stagedPptx);
    } else {
      const transitionScript = path.join(path.dirname(fileURLToPath(import.meta.url)), "apply_ppt_transitions.py");
      const transitionPlan = storyboardPlanPath || planPath;
      const command = [transitionScript, basePptx, "--output", stagedPptx];
      if (transitionPlan) command.push("--plan", transitionPlan);
      const result = spawnSync(args.python, command, { encoding: "utf8" });
      if (result.status === 0) {
        transitionStatus = "applied";
      } else {
        await copyFile(basePptx, stagedPptx);
        transitionStatus = "degraded-no-transitions";
        console.warn(`[WARN] transition injection failed; preserved valid PPTX without transitions: ${(result.stderr || result.stdout || "unknown error").trim()}`);
      }
    }
    const stagedStats = await stat(stagedPptx);
    if (!stagedStats.isFile() || stagedStats.size === 0) throw new Error("staged PPTX is empty");

    const manifest = {
      version: 2,
      html: htmlPath,
      plan: planPath || null,
      storyboard_plan: storyboardPlanPath || null,
      output: outputPath,
      html_slide_count: htmlCount,
      plan_slide_count: plan?.slides?.length ?? null,
      storyboard_slide_count: storyboardPlan?.slides?.length ?? null,
      exported_slide_count: captures.length,
      storyboard: Boolean(storyboardPlan),
      transitions: transitionStatus,
      captures,
    };
    await atomicCopy(stagedPptx, outputPath);
    await atomicWrite(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    console.log(`[OK] export manifest: ${manifestPath}`);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
  console.log(`[OK] wrote HTML-matched PPTX: ${outputPath} (${captures.length} slides, transitions=${transitionStatus})`);
  console.log(`[OK] screenshots: ${slidesDir}`);
}

main().catch((error) => {
  console.error(`[FAIL] ${error.message || error}`);
  process.exit(1);
});
