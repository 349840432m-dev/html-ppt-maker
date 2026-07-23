#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


REQUIRED_STYLES = {
    "swiss-editorial",
    "magazine-editorial",
    "bauhaus-geometric",
    "dieter-rams",
    "kenya-hara",
    "brutalist-developer",
    "field-motion",
}
REQUIRED_FOUNDATION_LAYOUTS = {
    "cover", "agenda", "section", "statement", "image-text", "data",
    "comparison", "timeline", "matrix", "case", "process", "close",
}
REQUIRED_EXPRESSION_LAYOUTS = {
    "decision-tree", "funnel", "causal-chain", "journey", "cycle", "radial",
    "pyramid", "hierarchy", "bars", "waterfall", "gantt", "checklist",
    "before-after", "stack", "blueprint", "diagnostic-axis", "system-map", "spectrum",
}
REQUIRED_LAYOUTS = REQUIRED_FOUNDATION_LAYOUTS | REQUIRED_EXPRESSION_LAYOUTS


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    manifest_path = root / "assets" / "style-library" / "manifest.json"
    gallery_path = root / "assets" / "style-library" / "index.html"
    if not manifest_path.is_file() or not gallery_path.is_file():
        fail("style library manifest or gallery is missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    style_ids = {item.get("id") for item in manifest.get("styles", [])}
    layout_list = manifest.get("layouts", [])
    layouts = set(layout_list)
    if style_ids != REQUIRED_STYLES:
        fail(f"style ids mismatch: {sorted(style_ids)}")
    if layouts != REQUIRED_LAYOUTS:
        fail(f"layout ids mismatch: {sorted(layouts)}")
    if len(layout_list) != len(layouts):
        fail("layouts must not contain duplicate ids")
    catalog = manifest.get("layout_catalog")
    if not isinstance(catalog, list):
        fail("layout_catalog must be a list")
    catalog_id_list = [item.get("id") for item in catalog if isinstance(item, dict)]
    catalog_ids = set(catalog_id_list)
    if catalog_ids != REQUIRED_LAYOUTS:
        fail(f"layout_catalog ids mismatch: {sorted(catalog_ids)}")
    if len(catalog_id_list) != len(catalog_ids):
        fail("layout_catalog must not contain duplicate ids")
    for item in catalog:
        if not isinstance(item, dict) or any(not str(item.get(key, "")).strip() for key in ("id", "logic", "use_for", "grid")):
            fail("every layout_catalog item needs id, logic, use_for, and grid")

    html = gallery_path.read_text(encoding="utf-8")
    gallery = manifest.get("gallery")
    if not isinstance(gallery, dict):
        fail("manifest.gallery must be an object")
    if gallery.get("mode") != "single-layout-set":
        fail("gallery.mode must be single-layout-set")
    if gallery.get("example_count") != len(REQUIRED_LAYOUTS):
        fail("gallery.example_count must match the layout count")
    if gallery.get("theme_count") != len(REQUIRED_STYLES):
        fail("gallery.theme_count must match the style count")
    default_theme = gallery.get("default_theme")
    if default_theme not in REQUIRED_STYLES:
        fail("gallery.default_theme must be a registered style id")
    if gallery.get("theme_switch") != "runtime-data-theme":
        fail("gallery.theme_switch must be runtime-data-theme")
    regression = gallery.get("regression")
    if not isinstance(regression, dict):
        fail("gallery.regression must be an object")
    if regression.get("default") != "changed-scope":
        fail("default gallery regression must be changed-scope")
    if regression.get("full_matrix") != "optional-release":
        fail("full matrix regression must be optional-release")
    if regression.get("full_matrix_combinations") != len(REQUIRED_LAYOUTS) * len(REQUIRED_STYLES):
        fail("full matrix combination count must equal layouts × styles")

    root_match = re.search(r'<html\b[^>]*\bdata-theme="([^"]+)"', html)
    if not root_match or root_match.group(1) != default_theme:
        fail("gallery root data-theme must match gallery.default_theme")
    if html.count('data-example-set="canonical"') != 1:
        fail("gallery needs exactly one canonical example set")
    for layout in sorted(REQUIRED_LAYOUTS):
        if html.count(f'data-layout-filter="{layout}"') != 1:
            fail(f"gallery needs exactly one filter button for: {layout}")
    if html.count('data-layout-filter="all"') != 1:
        fail("gallery needs one all-layout filter")
    for style_id in sorted(REQUIRED_STYLES):
        if html.count(f'data-theme-filter="{style_id}"') != 1:
            fail(f"gallery needs exactly one theme button for: {style_id}")
        if f'[data-theme="{style_id}"]' not in html:
            fail(f"gallery CSS needs a theme rule for: {style_id}")
    if "data-style-filter" in html or 'class="style-band"' in html:
        fail("legacy duplicated style filters or style bands are not allowed")
    if "cloneNode(" in html or ".innerHTML" in html:
        fail("gallery must not clone or rebuild the canonical slide DOM")

    expected = len(REQUIRED_LAYOUTS)
    if html.count('class="slide-template') != expected:
        fail(f"gallery must contain exactly {expected} canonical template slides")
    for layout in sorted(REQUIRED_LAYOUTS):
        if html.count(f'data-layout="{layout}"') != 1:
            fail(f"{layout} must appear exactly once")
        if html.count(f'data-template-id="{layout}"') != 1:
            fail(f"{layout} needs a matching unique data-template-id")

    article_classes = re.findall(r'<article\b[^>]*class="([^"]*)"[^>]*\bdata-layout=', html)
    legacy_classes = {"swiss", "magazine", "bauhaus", "rams", "hara", "brutalist", "field"}
    for classes in article_classes:
        collision = set(classes.split()) & legacy_classes
        if collision:
            fail(f"canonical articles must not carry theme classes: {sorted(collision)}")

    print(f"[PASS] 1 canonical set, {expected} layouts, {len(REQUIRED_STYLES)} runtime themes")


if __name__ == "__main__":
    main()
