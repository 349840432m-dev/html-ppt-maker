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
REQUIRED_LAYOUTS = {"cover", "section", "statement", "data", "process", "close"}


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
    layouts = set(manifest.get("layouts", []))
    if style_ids != REQUIRED_STYLES:
        fail(f"style ids mismatch: {sorted(style_ids)}")
    if layouts != REQUIRED_LAYOUTS:
        fail(f"layout ids mismatch: {sorted(layouts)}")

    html = gallery_path.read_text(encoding="utf-8")
    for style_id in sorted(REQUIRED_STYLES):
        section_match = re.search(
            rf'<section class="style-band" data-style="{re.escape(style_id)}">([\s\S]*?)</section>',
            html,
        )
        if not section_match:
            fail(f"gallery missing style section: {style_id}")
        section = section_match.group(1)
        for layout in sorted(REQUIRED_LAYOUTS):
            if section.count(f'data-layout="{layout}"') != 1:
                fail(f"{style_id} missing layout: {layout}")
        if section.count('class="slide-template') != len(REQUIRED_LAYOUTS):
            fail(f"{style_id} must contain exactly 6 template slides")

    if html.count('class="slide-template') < len(REQUIRED_STYLES) * len(REQUIRED_LAYOUTS):
        fail("gallery has fewer than 42 template slides")

    print("[PASS] 7 styles, 6 layouts each, 42 template slides")


if __name__ == "__main__":
    main()
