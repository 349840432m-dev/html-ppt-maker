#!/usr/bin/env python3
"""Audit visual concept and asset strength for high-end HTML/PPT decks.

Usage:
    python3 audit_visual_strength.py visual-concepts.json [deck-plan.json]

With a deck plan, this checks the visual-asset minimums against deck length,
sections, and teaching/course intent instead of only checking the asset file
shape.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

REQUIRED_ROLES = {"cover", "section", "concept"}
VALID_STATUS = {"generated", "prompt_ready", "editable_graphic", "placeholder", "not_needed"}
WEAK_STATUS = {"placeholder", "not_needed"}
TEACHING_HINTS = ("公开课", "培训", "课程", "教学", "workshop", "练习", "方法论")


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path}: invalid JSON: {exc}")


def asset_slides(asset: dict) -> list[str]:
    value = asset.get("slides", [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def audit_asset_shape(data: dict) -> tuple[list[dict], Counter, int, list[str]]:
    selected = str(data.get("selected_concept", "")).strip()
    if not selected:
        fail("missing selected_concept")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        fail("assets must be a non-empty list")

    concepts = data.get("concepts") or data.get("directions") or data.get("visual_concepts")
    if isinstance(concepts, list) and len(concepts) < 3:
        warn("formal visual concept proposals should compare 3 directions")

    roles = Counter()
    generated_like = 0
    weak = []
    seen_ids: set[str] = set()
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            fail(f"asset #{index} must be an object")
        asset_id = str(asset.get("asset_id", "")).strip()
        role = str(asset.get("role", "")).strip()
        status = str(asset.get("status", "")).strip()
        prompt = str(asset.get("prompt", "")).strip()
        fallback = str(asset.get("fallback", "")).strip()
        safe_area = str(asset.get("safe_area", "")).strip()
        risk = str(asset.get("risk", "")).strip()

        if not asset_id:
            fail(f"asset #{index} missing asset_id")
        if asset_id in seen_ids:
            fail(f"duplicate asset_id: {asset_id}")
        seen_ids.add(asset_id)
        if not role:
            fail(f"{asset_id}: missing role")
        if status not in VALID_STATUS:
            fail(f"{asset_id}: invalid status '{status}'")
        if status != "not_needed" and not prompt:
            fail(f"{asset_id}: prompt or implementation note is required")
        if status in {"prompt_ready", "placeholder"} and not fallback:
            fail(f"{asset_id}: fallback is required when asset is not generated")
        if role in {"cover", "section", "concept"} and not safe_area:
            fail(f"{asset_id}: safe_area is required for visual anchor assets")
        if role in {"cover", "section", "concept", "case"} and not risk:
            warn(f"{asset_id}: risk field should name copyright/privacy/authenticity/readability risks")

        roles[role] += 1
        if status in {"generated", "editable_graphic"}:
            generated_like += 1
        if status in WEAK_STATUS and role in REQUIRED_ROLES:
            weak.append(asset_id)

    missing = REQUIRED_ROLES - set(roles)
    if missing:
        fail(f"missing required visual asset roles: {', '.join(sorted(missing))}")

    if roles["section"] < 2:
        warn("formal decks usually need at least 2 section visual anchors")
    if generated_like == 0:
        warn("no generated/editable visual assets; deck may still look text-heavy")
    if weak:
        warn(f"visual anchors are weak or not needed: {', '.join(weak)}")

    return assets, roles, generated_like, weak


def audit_against_plan(assets: list[dict], roles: Counter, plan_path: Path) -> None:
    plan = load_json(plan_path)
    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        fail(f"{plan_path}: slides must be a non-empty list")

    slide_count = len(slides)
    section_slides = [s for s in slides if str(s.get("type", "")).strip() == "section" or str(s.get("layout_family", "")).strip() in {"section", "section-impact"}]
    scenario = " ".join(str(plan.get(field, "")) for field in ("scenario", "goal", "audience", "visual_style", "design_read"))
    title_blob = " ".join(str(s.get("title", "")) for s in slides)
    is_teaching = any(hint in scenario or hint in title_blob for hint in TEACHING_HINTS)

    non_card_roles = roles["cover"] + roles["section"] + roles["concept"] + roles["case"]
    min_section_assets = max(1, len(section_slides))
    min_non_card = max(1, math.ceil(slide_count / 10))
    min_concept = 2 if slide_count >= 8 else 1

    if roles["cover"] < 1:
        fail("deck plan requires at least 1 cover visual asset")
    if roles["section"] < min_section_assets:
        fail(f"deck has {len(section_slides)} section slide(s); need at least {min_section_assets} section visual asset(s), found {roles['section']}")
    if non_card_roles < min_non_card:
        fail(f"deck has {slide_count} slides; need at least {min_non_card} non-card visual anchor asset(s), found {non_card_roles}")
    if roles["concept"] < min_concept:
        fail(f"deck needs at least {min_concept} concept/framework visual asset(s), found {roles['concept']}")
    if is_teaching and roles["case"] < 2:
        fail("teaching/course decks need at least 2 case/error-remake/practice visual assets")

    slide_ids = {str(s.get("id", "")).strip() for s in slides if str(s.get("id", "")).strip()}
    unknown_refs = []
    for asset in assets:
        for sid in asset_slides(asset):
            if sid and slide_ids and sid not in slide_ids:
                unknown_refs.append(f"{asset.get('asset_id')}->{sid}")
    if unknown_refs:
        warn(f"asset slide references not found in deck plan: {', '.join(unknown_refs[:8])}")


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        fail("usage: audit_visual_strength.py <visual-concepts.json> [deck-plan.json]")

    path = Path(sys.argv[1])
    if not path.exists():
        fail(f"file not found: {path}")

    data = load_json(path)
    assets, roles, generated_like, _weak = audit_asset_shape(data)

    if len(sys.argv) == 3:
        plan_path = Path(sys.argv[2])
        if not plan_path.exists():
            fail(f"file not found: {plan_path}")
        audit_against_plan(assets, roles, plan_path)

    print(f"[OK] {path}: {len(assets)} assets, concept='{data.get('selected_concept')}', roles={dict(roles)}, generated_like={generated_like}")


if __name__ == "__main__":
    main()
