#!/usr/bin/env python3
"""Audit HTML/CSS motion quality for html-ppt-maker outputs."""

from __future__ import annotations

import re
import sys
from pathlib import Path


FATAL_RULES = [
    ("transition-all", re.compile(r"transition\s*:\s*all\b", re.I), "avoid transition: all; list transform/opacity explicitly"),
    ("scale-zero", re.compile(r"\bscale\(\s*0(?:\.0+)?\s*\)", re.I), "avoid scale(0); use scale(.94-.98) plus opacity"),
    ("ease-in", re.compile(r"(?<![-\w])ease-in(?![-\w])", re.I), "avoid ease-in for UI motion; use ease-out or a custom curve"),
]

WARN_RULES = [
    ("missing-reduced-motion", None, "add @media (prefers-reduced-motion: reduce)"),
    ("layout-transition", re.compile(r"transition[^;{}]*(width|height|top|left|right|bottom|margin|padding)", re.I | re.S), "avoid layout-property transitions; prefer transform/opacity"),
    ("ungated-hover", re.compile(r":hover", re.I), "gate hover motion with @media (hover: hover) and (pointer: fine)"),
]


def line_no(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    warnings: list[str] = []

    for name, pattern, message in FATAL_RULES:
        for match in pattern.finditer(text):
            failures.append(f"{path}:{line_no(text, match.start())}: {name}: {message}")

    for name, pattern, message in WARN_RULES:
        if name == "missing-reduced-motion":
            if "prefers-reduced-motion" not in text:
                warnings.append(f"{path}: {name}: {message}")
            continue

        assert pattern is not None
        for match in pattern.finditer(text):
            if name == "ungated-hover" and "@media (hover: hover)" in text:
                continue
            warnings.append(f"{path}:{line_no(text, match.start())}: {name}: {message}")

    if "cubic-bezier(0.23, 1, 0.32, 1)" not in text and "--ease-out" not in text:
        warnings.append(f"{path}: missing-motion-token: define --ease-out for consistent deck motion")

    if "data-reveal" not in text and "data-step" not in text:
        warnings.append(f"{path}: missing-reveal-contract: use data-reveal or data-step for predictable slide reveals")

    return failures, warnings


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: audit_motion_quality.py <index.html> [more.html ...]", file=sys.stderr)
        return 2

    all_failures: list[str] = []
    all_warnings: list[str] = []

    for raw in sys.argv[1:]:
        path = Path(raw)
        if not path.exists():
            all_failures.append(f"{path}: file does not exist")
            continue
        failures, warnings = scan(path)
        all_failures.extend(failures)
        all_warnings.extend(warnings)

    for warning in all_warnings:
        print(f"[WARN] {warning}")
    for failure in all_failures:
        print(f"[FAIL] {failure}")

    if all_failures:
        return 1

    print(f"[OK] motion audit passed for {len(sys.argv) - 1} file(s); warnings={len(all_warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
