#!/usr/bin/env python3
"""Validate the minimal plan contract required to export an existing HTML deck."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read plan: {exc}"]

    if not isinstance(data, dict):
        return ["plan root must be an object"]
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        return ["plan.slides must be a non-empty array"]

    seen: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slides[{index}] must be an object")
            continue
        slide_id = slide.get("id")
        if not isinstance(slide_id, str) or not slide_id.strip():
            errors.append(f"slides[{index}].id must be a non-empty string")
            continue
        normalized = slide_id.strip()
        if normalized in seen:
            errors.append(f"slides[{index}].id is duplicated: {normalized}")
        seen.add(normalized)
        notes = slide.get("speaker_notes")
        if notes is not None and not isinstance(notes, str):
            errors.append(f"slides[{index}].speaker_notes must be a string when present")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the legacy-friendly minimum plan contract for HTML-matched export."
    )
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    errors = validate(args.plan.resolve())
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    if errors:
        print(f"[FAIL] export plan validation failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"[OK] export plan contract valid: {args.plan.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
