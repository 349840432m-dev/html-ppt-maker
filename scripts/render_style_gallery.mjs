#!/usr/bin/env node
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { launchChromium, loadModule } from "./lib/node-runtime.mjs";

function usage() {
  console.log("Usage: node render_style_gallery.mjs [--chrome /path/to/chrome] [--full-matrix] <style-library/index.html> <output.png>");
}

const args = process.argv.slice(2);
let chrome = process.env.CHROME_PATH || "";
let fullMatrix = false;
if (args[0] === "--chrome") {
  chrome = args[1] || "";
  args.splice(0, 2);
}
const matrixIndex = args.indexOf("--full-matrix");
if (matrixIndex !== -1) {
  fullMatrix = true;
  args.splice(matrixIndex, 1);
}
if (args.length !== 2 || args.includes("--help") || args.includes("-h")) {
  usage();
  process.exit(args.length === 2 ? 0 : 2);
}

const [input, output] = args.map((value) => path.resolve(value));
const manifest = JSON.parse(await readFile(path.join(path.dirname(input), "manifest.json"), "utf8"));
const expected = manifest.layouts.length;
const { chromium } = loadModule("playwright");
const browser = await launchChromium(chromium, chrome);
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(input).href, { waitUntil: "networkidle" });
  await page.evaluate(async () => document.fonts?.ready);
  const slides = await page.locator(".slide-template").count();
  if (slides !== expected) throw new Error(`Expected ${expected} canonical templates, found ${slides}`);
  const baseline = await page.evaluate(() => {
    window.__atlasArticles = Array.from(document.querySelectorAll(".slide-template"));
    return window.__atlasArticles.map((node) => ({
      id: node.dataset.templateId,
      layout: node.dataset.layout,
      text: node.textContent.replace(/\s+/g, " ").trim(),
      className: node.className,
      width: node.getBoundingClientRect().width,
      height: node.getBoundingClientRect().height,
    }));
  });
  for (const layout of manifest.layouts) {
    await page.locator(`[data-layout-filter="${layout}"]`).click();
    const visible = await page.locator(`.slide-template[data-layout="${layout}"]:visible`).count();
    if (visible !== 1) throw new Error(`${layout} filter expected 1 template, found ${visible}`);
  }
  await page.locator('[data-layout-filter="all"]').click();
  const visualSignatures = new Set();
  for (const style of manifest.styles) {
    await page.locator(`[data-theme-filter="${style.id}"]`).click();
    await page.waitForTimeout(220);
    const visible = await page.locator(".slide-template:visible").count();
    if (visible !== manifest.layouts.length) throw new Error(`${style.id} expected ${manifest.layouts.length} templates, found ${visible}`);
    const state = await page.evaluate((expectedTheme) => {
      const current = Array.from(document.querySelectorAll(".slide-template"));
      const pressed = Array.from(document.querySelectorAll("[data-theme-filter][aria-pressed=true]"));
      return {
        theme: document.documentElement.dataset.theme,
        count: current.length,
        sameNodes: current.length === window.__atlasArticles.length
          && current.every((node, index) => node === window.__atlasArticles[index]),
        pressed: pressed.map((button) => button.dataset.themeFilter),
        snapshot: current.map((node) => ({
          id: node.dataset.templateId,
          layout: node.dataset.layout,
          text: node.textContent.replace(/\s+/g, " ").trim(),
          className: node.className,
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
        })),
        overflow: current
          .filter((node) => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1)
          .map((node) => ({
            layout: node.dataset.layout,
            client: `${node.clientWidth}×${node.clientHeight}`,
            scroll: `${node.scrollWidth}×${node.scrollHeight}`,
          })),
        visual: (() => {
          const computed = getComputedStyle(current[0]);
          return [
            computed.backgroundColor,
            computed.color,
            computed.fontFamily,
            computed.borderTopWidth,
            computed.borderRadius,
          ].join("|");
        })(),
        expectedTheme,
      };
    }, style.id);
    if (state.theme !== style.id) throw new Error(`Theme switch did not set root theme to ${style.id}`);
    if (!state.sameNodes || state.count !== expected) throw new Error(`${style.id} changed canonical DOM identity`);
    if (JSON.stringify(state.snapshot) !== JSON.stringify(baseline)) throw new Error(`${style.id} changed canonical content or classes`);
    if (state.pressed.length !== 1 || state.pressed[0] !== style.id) throw new Error(`${style.id} must be the only pressed theme`);
    if (state.overflow.length) {
      throw new Error(`${style.id} overflows layouts: ${state.overflow.map((item) => `${item.layout}(${item.client}→${item.scroll})`).join(", ")}`);
    }
    visualSignatures.add(state.visual);
  }
  if (visualSignatures.size !== manifest.styles.length) {
    throw new Error(`Expected ${manifest.styles.length} distinct theme visual signatures, found ${visualSignatures.size}`);
  }
  await page.locator('[data-theme-filter="swiss-editorial"]').click();
  await page.locator('[data-layout-filter="system-map"]').click();
  const combinedVisible = await page.locator(".slide-template:visible").count();
  if (combinedVisible !== 1) throw new Error(`Combined filters expected 1 template, found ${combinedVisible}`);
  await page.locator('.slide-template[data-layout="system-map"]').click();
  const preview = await page.evaluate(() => ({
    total: document.querySelectorAll(".slide-template").length,
    preview: document.querySelectorAll(".slide-template.is-preview").length,
    theme: document.documentElement.dataset.theme,
    sameNodes: Array.from(document.querySelectorAll(".slide-template"))
      .every((node, index) => node === window.__atlasArticles[index]),
  }));
  if (preview.total !== expected || preview.preview !== 1 || !preview.sameNodes || preview.theme !== "swiss-editorial") {
    throw new Error("Preview must preserve the canonical DOM and active theme");
  }
  await page.keyboard.press("Escape");
  if (fullMatrix) {
    for (const style of manifest.styles) {
      await page.locator(`[data-theme-filter="${style.id}"]`).click();
      for (const layout of manifest.layouts) {
        await page.locator(`[data-layout-filter="${layout}"]`).click();
        const visible = await page.locator(".slide-template:visible").count();
        if (visible !== 1) throw new Error(`${style.id} × ${layout} expected 1 visible template, found ${visible}`);
      }
    }
  }
  await page.locator('[data-layout-filter="all"]').click();
  await page.locator(`[data-theme-filter="${manifest.gallery.default_theme}"]`).click();
  await mkdir(path.dirname(output), { recursive: true });
  await page.screenshot({ path: output, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll(".filters button"));
    const slides = Array.from(document.querySelectorAll(".slide-template"));
    return {
      documentOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      shortTargets: buttons
        .filter((button) => button.getBoundingClientRect().height < 44)
        .map((button) => button.textContent.trim()),
      slideOverflow: slides
        .filter((node) => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1)
        .map((node) => node.dataset.layout),
    };
  });
  if (mobile.documentOverflow) throw new Error("Mobile viewport has document-level horizontal overflow");
  if (mobile.shortTargets.length) throw new Error(`Mobile touch targets below 44px: ${mobile.shortTargets.join(", ")}`);
  if (mobile.slideOverflow.length) throw new Error(`Mobile layouts overflow: ${mobile.slideOverflow.join(", ")}`);
  const scope = fullMatrix ? `${manifest.styles.length * manifest.layouts.length} optional matrix states` : `${manifest.styles.length} theme smoke checks`;
  console.log(`[PASS] rendered ${slides} canonical templates with ${scope} to ${output}`);
} finally {
  await browser.close();
}
