#!/usr/bin/env python3
"""Expand deck-plan slides into storyboard states for PPT export."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")


def normalize_state(slide_id: str, index: int, state: dict) -> dict:
    if not isinstance(state, dict):
        fail(f"{slide_id}: storyboard state #{index} must be an object")
    suffix = str(state.get("suffix", chr(ord("a") + index - 1))).strip()
    if not suffix:
        fail(f"{slide_id}: storyboard state #{index} missing suffix")
    include_steps = state.get("include_steps", [])
    if not isinstance(include_steps, list) or any(not isinstance(item, int) or item < 0 for item in include_steps):
        fail(f"{slide_id}: storyboard state #{index} include_steps must be non-negative integers")
    return {
        "suffix": suffix,
        "label": str(state.get("label", f"state {index}")).strip(),
        "include_steps": include_steps,
        "speaker_note": str(state.get("speaker_note", "")).strip(),
    }


def expand(data: dict) -> dict:
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        fail("deck plan must contain non-empty slides list")

    expanded = deepcopy(data)
    expanded_slides = []
    seen_ids: set[str] = set()

    for slide in slides:
        if not isinstance(slide, dict):
            fail("each slide must be an object")
        slide_id = str(slide.get("id", "")).strip()
        if not slide_id:
            fail("slide missing id")

        states = slide.get("storyboard_states")
        if states is None:
            clone = deepcopy(slide)
            clone["source_slide_id"] = slide_id
            clone["storyboard_state"] = "final"
            if clone["id"] in seen_ids:
                fail(f"duplicate output slide id: {clone['id']}")
            seen_ids.add(clone["id"])
            expanded_slides.append(clone)
            continue

        if not isinstance(states, list) or not states:
            fail(f"{slide_id}: storyboard_states must be a non-empty list when provided")
        if len(states) > 5:
            fail(f"{slide_id}: storyboard_states has {len(states)} states; split the source slide instead")

        for index, raw_state in enumerate(states, start=1):
            state = normalize_state(slide_id, index, raw_state)
            clone = deepcopy(slide)
            clone.pop("storyboard_states", None)
            clone["id"] = f"{slide_id}{state['suffix']}"
            clone["source_slide_id"] = slide_id
            clone["storyboard_state"] = state["label"]
            clone["visible_steps"] = state["include_steps"]
            if state["speaker_note"]:
                base_note = str(clone.get("speaker_notes", "")).strip()
                clone["speaker_notes"] = f"{base_note}\n\n分镜：{state['speaker_note']}".strip()
            clone["animation"] = f"{clone.get('animation', '').strip()} | PPT分镜显示步骤: {state['include_steps']}"
            clone["transition"] = str(clone.get("transition", "fade")).strip() or "fade"
            if clone["id"] in seen_ids:
                fail(f"duplicate output slide id: {clone['id']}")
            seen_ids.add(clone["id"])
            expanded_slides.append(clone)

    expanded["slides"] = expanded_slides
    expanded["storyboard_export"] = {
        "source_slide_count": len(slides),
        "expanded_slide_count": len(expanded_slides),
        "mode": "static-state-pages",
    }
    return expanded


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: expand_storyboard_plan.py <deck-plan.json> <storyboard-plan.json>")

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    if not source.exists():
        fail(f"file not found: {source}")

    expanded = expand(load_json(source))
    output.write_text(json.dumps(expanded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] wrote {output}: {expanded['storyboard_export']['expanded_slide_count']} slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
