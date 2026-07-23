#!/usr/bin/env python3
"""Verify that an HTML-matched export manifest and PPTX agree byte-for-byte."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_DOC_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
R_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def slide_number(name: str) -> int:
    match = re.search(r"/slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    return struct.unpack(">II", header[16:24])


def require_int(data: dict, key: str, errors: list[str]) -> int | None:
    value = data.get(key)
    if not isinstance(value, int) or value < 0:
        errors.append(f"manifest.{key} must be a non-negative integer")
        return None
    return value


def verify(manifest_path: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"], warnings, {}

    if manifest.get("version") != 2:
        errors.append("manifest.version must be 2")
    html_count = require_int(manifest, "html_slide_count", errors)
    exported_count = require_int(manifest, "exported_slide_count", errors)
    plan_count = manifest.get("plan_slide_count")
    storyboard_count = manifest.get("storyboard_slide_count")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or not captures:
        errors.append("manifest.captures must be a non-empty list")
        captures = []
    if exported_count is not None and len(captures) != exported_count:
        errors.append(f"capture count mismatch: manifest={exported_count}, captures={len(captures)}")

    storyboard = manifest.get("storyboard") is True
    if not storyboard and isinstance(plan_count, int) and html_count is not None and exported_count is not None:
        if len({plan_count, html_count, exported_count}) != 1:
            errors.append(
                f"non-storyboard count mismatch: plan={plan_count}, html={html_count}, exported={exported_count}"
            )
    if storyboard and isinstance(storyboard_count, int) and exported_count is not None:
        if storyboard_count != exported_count:
            errors.append(f"storyboard count mismatch: plan={storyboard_count}, exported={exported_count}")

    capture_hashes: list[str] = []
    states_by_source: dict[str, list[str]] = defaultdict(list)
    for index, capture in enumerate(captures, start=1):
        if not isinstance(capture, dict):
            errors.append(f"capture #{index} must be an object")
            continue
        file = Path(str(capture.get("file", "")))
        if not file.is_file():
            errors.append(f"capture #{index} file missing: {file}")
            continue
        try:
            width, height = png_dimensions(file)
        except (OSError, ValueError) as exc:
            errors.append(f"capture #{index} invalid PNG: {exc}")
            continue
        if (width, height) != (1280, 720):
            errors.append(f"capture #{index} dimensions must be 1280x720, got {width}x{height}")
        recorded = str(capture.get("sha256", ""))
        actual = sha256_file(file)
        if recorded != actual:
            errors.append(f"capture #{index} sha256 mismatch")
        capture_hashes.append(actual)
        states_by_source[str(capture.get("source_slide_id", ""))].append(actual)

    if storyboard:
        for source_id, hashes in states_by_source.items():
            if len(hashes) > 1 and len(set(hashes)) == 1:
                errors.append(f"storyboard states for {source_id or '<missing>'} are visually identical")

    output = Path(str(manifest.get("output", "")))
    if output.suffix.lower() != ".pptx" or not output.is_file():
        errors.append(f"PPTX output missing or invalid: {output}")
        return errors, warnings, manifest

    try:
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            slide_names = sorted(
                (name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
                key=slide_number,
            )
            if exported_count is not None and len(slide_names) != exported_count:
                errors.append(f"PPTX slide count mismatch: pptx={len(slide_names)}, exported={exported_count}")

            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            size = presentation.find(f"{{{P_NS}}}sldSz")
            canvas_width = 0
            canvas_height = 0
            if size is None:
                errors.append("PPTX is missing p:sldSz")
            else:
                canvas_width = int(size.attrib.get("cx", "0"))
                canvas_height = int(size.attrib.get("cy", "0"))
                if canvas_height <= 0 or abs((canvas_width / canvas_height) - (16 / 9)) > 0.001:
                    errors.append(f"PPTX slide ratio is not 16:9: {canvas_width}x{canvas_height}")

            media = [name for name in names if name.startswith("ppt/media/") and name.lower().endswith(".png")]
            media_hashes = [sha256_bytes(archive.read(name)) for name in media]
            if Counter(media_hashes) != Counter(capture_hashes):
                errors.append(
                    "PPTX embedded PNG hashes do not match capture hashes "
                    f"(media={len(media_hashes)}, captures={len(capture_hashes)})"
                )

            transition_count = 0
            for slide_index, name in enumerate(slide_names):
                root = ET.fromstring(archive.read(name))
                if root.find(f"{{{P_NS}}}transition") is not None:
                    transition_count += 1
                pictures = root.findall(f".//{{{P_NS}}}pic")
                if len(pictures) != 1:
                    errors.append(f"{name} must contain exactly one full-page picture, found {len(pictures)}")
                    continue
                transform = pictures[0].find(f".//{{{A_NS}}}xfrm")
                offset = transform.find(f"{{{A_NS}}}off") if transform is not None else None
                extent = transform.find(f"{{{A_NS}}}ext") if transform is not None else None
                if offset is None or extent is None:
                    errors.append(f"{name} picture is missing placement geometry")
                    continue
                if transform.attrib.get("rot", "0") not in {"", "0"}:
                    errors.append(f"{name} picture must not be rotated")
                if transform.attrib.get("flipH", "0") not in {"", "0", "false", "False"}:
                    errors.append(f"{name} picture must not be flipped horizontally")
                if transform.attrib.get("flipV", "0") not in {"", "0", "false", "False"}:
                    errors.append(f"{name} picture must not be flipped vertically")
                crop = pictures[0].find(f".//{{{A_NS}}}srcRect")
                if crop is not None and any(value not in {"", "0"} for value in crop.attrib.values()):
                    errors.append(f"{name} picture must not be cropped")
                x = int(offset.attrib.get("x", "0"))
                y = int(offset.attrib.get("y", "0"))
                width = int(extent.attrib.get("cx", "0"))
                height = int(extent.attrib.get("cy", "0"))
                width_tolerance = max(2000, int(canvas_width * 0.001))
                height_tolerance = max(2000, int(canvas_height * 0.001))
                if abs(x) > 100 or abs(y) > 100:
                    errors.append(f"{name} picture must start at canvas origin, got x={x}, y={y}")
                if (
                    canvas_width <= 0
                    or canvas_height <= 0
                    or abs(width - canvas_width) > width_tolerance
                    or abs(height - canvas_height) > height_tolerance
                ):
                    errors.append(
                        f"{name} picture must cover the canvas: picture={width}x{height}, "
                        f"canvas={canvas_width}x{canvas_height}"
                    )
                blip = pictures[0].find(f".//{{{A_NS}}}blip")
                relationship_id = blip.attrib.get(f"{{{R_DOC_NS}}}embed") if blip is not None else None
                rels_name = posixpath.join(
                    posixpath.dirname(name),
                    "_rels",
                    f"{posixpath.basename(name)}.rels",
                )
                if not relationship_id or rels_name not in names:
                    errors.append(f"{name} picture relationship is missing")
                    continue
                relationships = ET.fromstring(archive.read(rels_name))
                relationship = next(
                    (
                        node
                        for node in relationships.findall(f"{{{R_PKG_NS}}}Relationship")
                        if node.attrib.get("Id") == relationship_id
                    ),
                    None,
                )
                target = relationship.attrib.get("Target") if relationship is not None else None
                media_name = (
                    posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                    if target
                    else ""
                )
                if not media_name or media_name not in names:
                    errors.append(f"{name} picture target is missing: {media_name or '<none>'}")
                elif slide_index >= len(capture_hashes):
                    errors.append(f"{name} has no matching capture entry")
                elif sha256_bytes(archive.read(media_name)) != capture_hashes[slide_index]:
                    errors.append(f"{name} picture does not match capture #{slide_index + 1}")
            transition_status = manifest.get("transitions")
            if transition_status == "applied" and transition_count != len(slide_names):
                errors.append(
                    f"transition status says applied, but found {transition_count}/{len(slide_names)} tags"
                )
            elif transition_status == "degraded-no-transitions":
                warnings.append("transition injection degraded; visual parity still verified")
            elif transition_status == "not-applied":
                warnings.append("transitions were intentionally not applied; visual parity still verified")
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError, ValueError) as exc:
        errors.append(f"cannot inspect PPTX: {exc}")

    report = {
        "manifest": str(manifest_path),
        "output": str(output),
        "errors": errors,
        "warnings": warnings,
        "capture_count": len(captures),
    }
    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    errors, warnings, report = verify(args.manifest.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    if errors:
        print(f"[FAIL] HTML-matched export verification failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"[OK] HTML-matched export verified: {report['capture_count']} slide(s), warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
