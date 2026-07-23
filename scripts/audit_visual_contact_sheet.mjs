#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { launchChromium, loadModule } from "./lib/node-runtime.mjs";

let chromium;
let sharp;

function parseArgs(argv) {
  const args = { outDir: "visual-audit", chrome: process.env.CHROME_PATH || "", htmlFiles: [] };
  for (let i = 2; i < argv.length; i += 1) {
    const value = argv[i];
    if (value === "--out") {
      args.outDir = argv[++i];
    } else if (value === "--chrome") {
      args.chrome = argv[++i];
    } else if (value === "--help" || value === "-h") {
      args.help = true;
    } else {
      args.htmlFiles.push(value);
    }
  }
  return args;
}

function usage() {
  console.log("Usage: node audit_visual_contact_sheet.mjs [--out visual-audit] [--chrome /path/to/chrome] <index.html> [...]");
}

function slugFor(file) {
  const parent = path.basename(path.dirname(file));
  return parent && parent !== "." ? parent : path.basename(file, path.extname(file));
}

function similarity(a, b) {
  if (!a || !b) return 0;
  const aSet = new Set(a.split("|").filter(Boolean));
  const bSet = new Set(b.split("|").filter(Boolean));
  if (!aSet.size || !bSet.size) return 0;
  let shared = 0;
  for (const item of aSet) {
    if (bSet.has(item)) shared += 1;
  }
  return shared / Math.max(aSet.size, bSet.size);
}

async function collectSlideMeta(page, index) {
  return page.evaluate((activeIndex) => {
    const slides = Array.from(document.querySelectorAll(".slide"));
    const slide = slides[activeIndex];
    const text = (slide?.innerText || "").replace(/\s+/g, " ").trim();
    const rects = Array.from(slide?.querySelectorAll("h1,h2,h3,blockquote,p,li,.card,.panel,.metric,.quote,.chart,.visual,.frame,.row,.column,[data-role='main-structure']") || [])
      .map((node) => {
        const rect = node.getBoundingClientRect();
        const cls = Array.from(node.classList || []).slice(0, 3).join(".");
        return `${node.tagName.toLowerCase()}.${cls}:${Math.round(rect.left / 40)}:${Math.round(rect.top / 40)}:${Math.round(rect.width / 80)}:${Math.round(rect.height / 60)}`;
      })
      .filter(Boolean)
      .slice(0, 80)
      .join("|");
    const mainTitle = (slide?.querySelector("h1,h2,blockquote")?.textContent || "").replace(/\s+/g, " ").trim();
    return {
      index: activeIndex + 1,
      title: mainTitle,
      textLength: text.length,
      signature: rects,
    };
  }, index);
}

function auditMeta(slides) {
  const warnings = [];
  let similarRun = 1;
  for (let i = 1; i < slides.length; i += 1) {
    if (similarity(slides[i - 1].signature, slides[i].signature) >= 0.72) {
      similarRun += 1;
    } else {
      similarRun = 1;
    }
    if (similarRun >= 4) {
      warnings.push({
        type: "repeated-silhouette",
        slide: slides[i].index,
        message: "4+ consecutive slides have highly similar layout silhouettes; vary the layout family or merge content.",
      });
      break;
    }
  }
  for (const slide of slides) {
    if (slide.textLength < 18) {
      warnings.push({
        type: "thin-slide",
        slide: slide.index,
        message: "Slide has very little readable text; verify it is an intentional visual anchor, not an unfinished placeholder.",
      });
    }
    if (!slide.title) {
      warnings.push({
        type: "missing-title",
        slide: slide.index,
        message: "Slide has no detectable h1/h2 title; verify hierarchy in the contact sheet.",
      });
    }
  }
  return warnings;
}

async function renderDeck(browser, htmlFile, outDir) {
  const absoluteHtml = path.resolve(htmlFile);
  const name = slugFor(absoluteHtml);
  const deckDir = path.join(outDir, name);
  await mkdir(deckDir, { recursive: true });

  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(absoluteHtml).href, { waitUntil: "load" });
  await page.waitForSelector(".slide", { timeout: 10000 });
  const count = await page.locator(".slide").count();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  const images = [];
  const slides = [];

  for (let i = 0; i < count; i += 1) {
    await page.evaluate((activeIndex) => {
      const slides = Array.from(document.querySelectorAll(".slide"));
      slides.forEach((slide, idx) => {
        slide.classList.toggle("active", idx === activeIndex);
        slide.querySelectorAll("[data-reveal], [data-step]").forEach((node) => {
          node.classList.toggle("revealed", idx === activeIndex);
        });
      });
      slides[activeIndex]?.querySelectorAll("[data-count-to]").forEach((node) => {
        const target = Number.parseFloat(node.dataset.countTo || "0");
        const decimals = Number.parseInt(node.dataset.decimals || "0", 10);
        if (Number.isFinite(target)) node.textContent = target.toFixed(Number.isFinite(decimals) ? decimals : 0);
      });
    }, i);
    await page.waitForTimeout(100);
    slides.push(await collectSlideMeta(page, i));
    const file = path.join(deckDir, `slide-${String(i + 1).padStart(2, "0")}.png`);
    await page.screenshot({ path: file, fullPage: false });
    images.push(file);
  }
  await page.close();

  const thumbW = 320;
  const thumbH = 180;
  const gap = 16;
  const cols = Math.min(5, Math.max(1, Math.ceil(Math.sqrt(count))));
  const rows = Math.ceil(count / cols);
  const width = cols * (thumbW + gap) - gap;
  const composites = [];

  const title = Buffer.from(
    `<svg width="${width}" height="36"><rect width="100%" height="100%" fill="#f4f4f4"/><text x="10" y="25" font-size="22" font-family="Arial" fill="#111">${name} / ${count} slides</text></svg>`
  );
  composites.push({ input: title, left: 0, top: 0 });

  for (let i = 0; i < images.length; i += 1) {
    const left = (i % cols) * (thumbW + gap);
    const top = Math.floor(i / cols) * (thumbH + gap) + 48;
    const buf = await sharp(images[i]).resize(thumbW, thumbH).png().toBuffer();
    const label = Buffer.from(
      `<svg width="${thumbW}" height="32"><rect width="100%" height="100%" fill="#111"/><text x="10" y="22" font-size="18" font-family="Arial" fill="#fff">${String(i + 1).padStart(2, "0")}</text></svg>`
    );
    composites.push({ input: label, left, top });
    composites.push({ input: buf, left, top: top + 32 });
  }

  const contactSheet = path.join(outDir, `${name}-contact-sheet.png`);
  await sharp({
    create: {
      width,
      height: rows * (thumbH + gap) + 88,
      channels: 4,
      background: "#efefef",
    },
  }).composite(composites).png().toFile(contactSheet);

  const warnings = auditMeta(slides);
  const report = { deck: name, html: absoluteHtml, slideCount: count, contactSheet, warnings, slides };
  await writeFile(path.join(outDir, `${name}-visual-audit.json`), JSON.stringify(report, null, 2), "utf8");
  console.log(`[OK] ${name}: ${count} slides -> ${contactSheet}; warnings=${warnings.length}`);
  for (const warning of warnings) {
    console.log(`[WARN] slide ${warning.slide}: ${warning.type}: ${warning.message}`);
  }
  return report;
}

const args = parseArgs(process.argv);
if (args.help || args.htmlFiles.length === 0) {
  usage();
  process.exit(args.help ? 0 : 2);
}

await mkdir(args.outDir, { recursive: true });

let browser;
try {
  ({ chromium } = loadModule("playwright"));
  sharp = loadModule("sharp");
  browser = await launchChromium(chromium, args.chrome);
} catch (error) {
  const firstLine = String(error && error.message ? error.message : error).split("\n")[0];
  console.log(`[INFO] Playwright unavailable (${firstLine}); run the visual contact sheet audit manually:`);
  console.log("  1. Install both `playwright` and `sharp`, install Chromium, or pass a local Chrome path with `--chrome <path>`.");
  console.log("  2. Open the deck in a browser and capture every final-reveal 16:9 slide screenshot.");
  console.log("  3. Assemble a contact sheet and inspect: title readability, cover specificity, repeated outlines, placeholder feel, and visual-anchor strength.");
  process.exit(3);
}

const reports = [];
try {
  for (const htmlFile of args.htmlFiles) {
    reports.push(await renderDeck(browser, htmlFile, path.resolve(args.outDir)));
  }
} finally {
  await browser.close();
}

const totalWarnings = reports.reduce((sum, report) => sum + report.warnings.length, 0);
console.log(`[OK] visual contact sheet audit finished: ${reports.length} deck(s), warnings=${totalWarnings}`);
