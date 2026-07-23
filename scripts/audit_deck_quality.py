#!/usr/bin/env python3
"""Audit deck plan quality for high-end HTML/PPT generation."""

import json
import sys
from collections import Counter
from pathlib import Path

VISUAL_TYPES = {"cover", "section", "closing"}
LAYOUT_FIELD = "layout_family"
MIN_LAYOUTS_LONG_DECK = 6
ADVANCED_LAYOUTS = {
    "decision-tree",
    "funnel",
    "causal-chain",
    "matrix",
    "journey",
    "before-after",
    "cycle",
    "radial",
    "pyramid",
    "hierarchy",
    "diagnostic-axis",
    "system-map",
    "spectrum",
}
LAYOUT_ALIASES = {"journey-blueprint": "journey"}


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: audit_deck_quality.py <deck-plan.json>")

    path = Path(sys.argv[1])
    if not path.exists():
        fail(f"file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        fail("'slides' must be a non-empty list")

    layout_values = [LAYOUT_ALIASES.get(str(slide.get(LAYOUT_FIELD, "")).strip(), str(slide.get(LAYOUT_FIELD, "")).strip()) for slide in slides]
    missing_layouts = [slide.get("id", f"#{i+1}") for i, slide in enumerate(slides) if not str(slide.get(LAYOUT_FIELD, "")).strip()]
    if missing_layouts:
        warn(f"{len(missing_layouts)} slides missing '{LAYOUT_FIELD}': {', '.join(map(str, missing_layouts[:8]))}")

    used_layouts = {value for value in layout_values if value}
    if len(slides) >= 20 and len(used_layouts) < MIN_LAYOUTS_LONG_DECK:
        fail(f"long deck needs at least {MIN_LAYOUTS_LONG_DECK} layout families; found {len(used_layouts)}")

    advanced_used = used_layouts & ADVANCED_LAYOUTS
    scenario_text = " ".join(str(data.get(field, "")) for field in ["scenario", "goal", "visual_style"])
    is_course = any(key in scenario_text for key in ["公开课", "培训", "课程", "NotebookLM", "信息图"])
    if is_course and len(slides) >= 20 and len(advanced_used) < 3:
        fail(
            "course/NotebookLM decks need at least 3 advanced infographic layouts; "
            f"found {len(advanced_used)} ({', '.join(sorted(advanced_used)) or 'none'})"
        )

    repeated = []
    current = None
    streak = 0
    for slide, layout in zip(slides, layout_values):
        key = layout or slide.get("type", "")
        if key == current:
            streak += 1
        else:
            current = key
            streak = 1
        if streak >= 4:
            repeated.append(str(slide.get("id", "?")))
    if repeated:
        fail(f"layout/type repeats for 4+ consecutive slides near: {', '.join(repeated[:8])}")

    visual_slides = [slide for slide in slides if slide.get("type") in VISUAL_TYPES]
    if len(slides) >= 12 and len(visual_slides) < 3:
        fail("formal decks need at least 3 visual anchor slides: cover, section, closing, or equivalent")

    # 锚点页有两种合法策略：生图（image_prompt）或排版/图形锚点（visual 字段有实质描述）。两者都缺才算弱。
    def has_image_strategy(slide: dict) -> bool:
        prompt = str(slide.get("image_prompt", "")).strip()
        return bool(prompt) and "不需要生图" not in prompt

    def has_typographic_strategy(slide: dict) -> bool:
        return len(str(slide.get("visual", "")).strip()) >= 8

    weak_visuals = [
        str(slide.get("id", "?"))
        for slide in visual_slides
        if not has_image_strategy(slide) and not has_typographic_strategy(slide)
    ]
    if weak_visuals:
        warn(f"visual anchor slides without active visual/image strategy: {', '.join(weak_visuals)}")

    animations = Counter(str(slide.get("animation", "")).strip() for slide in slides)
    if len(animations) <= 3 and len(slides) >= 15:
        warn("animation variety is low; consider reveal, path, contrast, highlight, and section transitions")

    workshop_like = [slide for slide in slides if slide.get("type") in {"case", "workshop"} or "练习" in str(slide.get("title", ""))]
    if len(slides) >= 20 and not workshop_like:
        warn("long educational deck has no case/workshop/practice slide")

    print(
        f"[OK] {path}: {len(slides)} slides, {len(used_layouts)} layout families, "
        f"{len(visual_slides)} visual anchors, {len(advanced_used)} advanced layouts"
    )


if __name__ == "__main__":
    main()
