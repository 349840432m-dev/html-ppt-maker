#!/usr/bin/env python3
"""Audit per-slide layout intent, visual translation, and element budget."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ANCHOR_LAYOUTS = {"cover", "hero", "section", "quote", "end", "metaphor"}
LAYOUT_ALIASES = {"journey-blueprint": "journey", "section-impact": "section", "quote-principle": "quote"}
STRUCTURE_OBJECTS = {
    "matrix",
    "decision-tree",
    "flow",
    "process",
    "timeline",
    "journey",
    "funnel",
    "waterfall",
    "bars",
    "stack",
    "blueprint",
    "before-after",
    "causal-chain",
    "diagnostic-gate",
    "coordinate",
    "map",
    "architecture",
    "comparison",
    "cycle",
    "radial",
    "pyramid",
    "hierarchy",
    "diagnostic-axis",
    "system-map",
    "spectrum",
}
SUPPORT_ELEMENTS = {
    "annotation",
    "arrow",
    "label",
    "legend",
    "source-line",
    "side-note",
    "numbering",
    "callout",
    "axis",
    "connector",
}
RHYTHM_ELEMENTS = {
    "big-number",
    "quote",
    "contrast-band",
    "dark-break",
    "crop-image",
    "code-snippet",
    "terminal-snippet",
    "texture",
    "spotlight",
    "oversized-type",
}
DESIGN_CONTRACT_FIELDS = (
    "hierarchy",
    "whitespace_intent",
    "alignment_contract",
    "color_emphasis",
    "single_claim",
)


def as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def norm(value) -> str:
    normalized = str(value or "").strip().lower()
    return LAYOUT_ALIASES.get(normalized, normalized)


def fail(errors: list[str], sid: str, message: str) -> None:
    errors.append(f"{sid}: {message}")


def audit_slide(slide: dict, index: int, errors: list[str], warnings: list[str]) -> None:
    sid = str(slide.get("id") or f"slide#{index}")
    layout = norm(slide.get("layout_family") or slide.get("type"))
    slide_type = norm(slide.get("type"))
    is_anchor = layout in ANCHOR_LAYOUTS or slide_type in ANCHOR_LAYOUTS

    for field in ("layout_intent", "first_visual_anchor", "aesthetic_risk", "pass_criteria"):
        if not has_text(slide.get(field)):
            fail(errors, sid, f"missing {field}; every slide needs explicit layout judgment")

    design_contract = slide.get("design_contract")
    if not isinstance(design_contract, dict):
        fail(errors, sid, "missing design_contract object")
    else:
        for field in DESIGN_CONTRACT_FIELDS:
            if not has_text(design_contract.get(field)):
                fail(errors, sid, f"design_contract.{field} must be a concrete, non-empty statement")

    translation = slide.get("visual_translation")
    if not isinstance(translation, dict):
        fail(errors, sid, "missing visual_translation object; translate text into a drawable visual object")
        translation = {}

    object_name = norm(translation.get("object"))
    if not object_name:
        fail(errors, sid, "visual_translation.object is required")
    elif object_name not in STRUCTURE_OBJECTS and not is_anchor:
        warnings.append(
            f"{sid}: visual_translation.object '{object_name}' is custom; verify it is a real structure, not decoration"
        )

    components = as_list(translation.get("components"))
    if len([c for c in components if has_text(c)]) < (1 if is_anchor else 3):
        fail(errors, sid, "visual_translation.components needs at least 3 concrete parts on content slides")

    if not has_text(translation.get("layout")):
        fail(errors, sid, "visual_translation.layout is required; name the composition before writing HTML")

    budget = slide.get("element_budget")
    if not isinstance(budget, dict):
        fail(errors, sid, "missing element_budget object")
        budget = {}

    main = as_list(budget.get("main_structure"))
    support = as_list(budget.get("supporting_elements"))
    rhythm = as_list(budget.get("rhythm_element"))
    decorative = as_list(budget.get("decorative_elements"))

    if len([x for x in main if has_text(x)]) != 1:
        fail(errors, sid, "element_budget.main_structure must contain exactly 1 primary visual structure")
    elif object_name and norm(main[0]) != object_name:
        fail(errors, sid, "element_budget.main_structure must match visual_translation.object")
    if not is_anchor and len([x for x in support if has_text(x)]) < 1:
        fail(errors, sid, "content slides need at least 1 supporting explanatory element")
    if not is_anchor and len([x for x in rhythm if has_text(x)]) < 1:
        fail(errors, sid, "content slides need at least 1 rhythm element to avoid plain text-card pages")
    if len([x for x in support if has_text(x)]) > 3:
        fail(errors, sid, "too many supporting elements; cap at 3 to preserve clarity")
    if len([x for x in decorative if has_text(x)]) > 1:
        fail(errors, sid, "too many decorative elements; decoration must not carry the page")

    known_support = {norm(x) for x in support}
    known_rhythm = {norm(x) for x in rhythm}
    unknown_support = sorted(x for x in known_support if x and x not in SUPPORT_ELEMENTS)
    unknown_rhythm = sorted(x for x in known_rhythm if x and x not in RHYTHM_ELEMENTS)
    if unknown_support:
        warnings.append(f"{sid}: custom supporting_elements {unknown_support}; verify they explain relationships")
    if unknown_rhythm:
        warnings.append(f"{sid}: custom rhythm_element {unknown_rhythm}; verify it creates real pacing")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: audit_layout_aesthetics.py <deck-plan.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[FAIL] file not found: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] invalid JSON: {exc}", file=sys.stderr)
        return 1

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        print("[FAIL] slides must be a non-empty list", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slide#{index}: slide must be an object")
            continue
        audit_slide(slide, index, errors, warnings)

    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)

    if errors:
        print(f"[FAIL] layout aesthetics audit failed: {len(errors)} error(s), warnings={len(warnings)}", file=sys.stderr)
        return 1

    print(f"[OK] layout aesthetics audit passed: {len(slides)} slides, warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
