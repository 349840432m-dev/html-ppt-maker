#!/usr/bin/env python3
"""Apply or check simple PowerPoint slide transition tags in a .pptx file."""

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
ET.register_namespace("p", NS["p"])

TRANSITION_TAG = f"{{{NS['p']}}}transition"
CSLD_TAG = f"{{{NS['p']}}}cSld"

ALLOWED = {"fade", "push", "wipe"}
DEFAULT_BY_TYPE = {
    "cover": "fade",
    "agenda": "push",
    "section": "push",
    "content": "fade",
    "data": "fade",
    "case": "wipe",
    "process": "push",
    "comparison": "fade",
    "summary": "fade",
    "closing": "fade",
}


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def transition_for(slide: dict) -> str:
    requested = str(slide.get("transition") or "").strip().lower()
    if requested in ALLOWED:
        return requested
    slide_type = str(slide.get("type") or "").strip().lower()
    return DEFAULT_BY_TYPE.get(slide_type, "fade")


def slide_paths(zf: zipfile.ZipFile) -> list[str]:
    paths = [name for name in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
    return sorted(paths, key=lambda item: int(re.search(r"slide(\d+)\.xml", item).group(1)))


def transition_element(kind: str) -> ET.Element:
    root = ET.Element(TRANSITION_TAG, {"spd": "med"})
    ET.SubElement(root, f"{{{NS['p']}}}{kind}")
    return root


def apply_transition(xml_bytes: bytes, kind: str) -> bytes:
    root = ET.fromstring(xml_bytes)
    existing = root.find("p:transition", NS)
    if existing is not None:
        root.remove(existing)
    c_sld = root.find("p:cSld", NS)
    insert_index = list(root).index(c_sld) + 1 if c_sld is not None else 0
    root.insert(insert_index, transition_element(kind))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def check(path: Path, allow_partial: bool = False) -> None:
    if not path.exists():
        fail(f"file not found: {path}")
    with zipfile.ZipFile(path) as zf:
        paths = slide_paths(zf)
        if not paths:
            fail("no slide XML files found")
        transition_count = 0
        for slide_path in paths:
            root = ET.fromstring(zf.read(slide_path))
            if root.find("p:transition", NS) is not None:
                transition_count += 1
    if transition_count != len(paths) and not allow_partial:
        fail(f"{path}: expected {len(paths)} transition tags, found {transition_count}")
    label = "OK" if transition_count == len(paths) else "WARN"
    print(f"[{label}] {path}: {len(paths)} slides, {transition_count} transition tags")


def apply(input_path: Path, output_path: Path, plan_path: Path | None) -> None:
    if not input_path.exists():
        fail(f"file not found: {input_path}")

    plan_slides = []
    if plan_path:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan_slides = plan.get("slides", [])
        if not isinstance(plan_slides, list):
            fail("plan field 'slides' must be a list")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_output = Path(tmp_dir) / "out.pptx"
        with zipfile.ZipFile(input_path, "r") as src, zipfile.ZipFile(tmp_output, "w", zipfile.ZIP_DEFLATED) as dst:
            paths = slide_paths(src)
            if not paths:
                fail("no slide XML files found")
            if plan_path and len(plan_slides) != len(paths):
                fail(f"plan/PPT slide count mismatch: plan={len(plan_slides)}, pptx={len(paths)}")
            for name in src.namelist():
                content = src.read(name)
                if name in paths:
                    index = paths.index(name)
                    slide = plan_slides[index] if index < len(plan_slides) and isinstance(plan_slides[index], dict) else {}
                    content = apply_transition(content, transition_for(slide))
                dst.writestr(name, content)
        shutil.copyfile(tmp_output, output_path)
    print(f"[OK] wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", nargs="?", help="input .pptx")
    parser.add_argument("--plan", help="deck-plan.json")
    parser.add_argument("--output", help="output .pptx")
    parser.add_argument("--check", action="store_true", help="only check transition tags")
    parser.add_argument("--allow-partial", action="store_true", help="do not fail when some slides lack transitions")
    args = parser.parse_args()

    if not args.pptx:
        fail("usage: apply_ppt_transitions.py [--check] <deck.pptx> [--plan deck-plan.json --output out.pptx]")

    pptx = Path(args.pptx)
    if args.check:
        check(pptx, allow_partial=args.allow_partial)
        return

    output = Path(args.output) if args.output else pptx.with_name(f"{pptx.stem}-transitions.pptx")
    plan = Path(args.plan) if args.plan else None
    apply(pptx, output, plan)


if __name__ == "__main__":
    main()
