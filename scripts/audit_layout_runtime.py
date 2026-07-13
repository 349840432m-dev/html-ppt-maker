#!/usr/bin/env python3
"""Run the runtime layout probe (layout_probe.js) against a deck.

Preferred path: if Playwright is installed, opens the deck headlessly and
executes the probe automatically.

Fallback (no Playwright): prints the probe path and instructions. Agents with
browser tools should serve the deck locally, open it, and execute the probe
via CDP Runtime.evaluate (awaitPromise: true), then fix every violation.

Usage:
    python3 audit_layout_runtime.py path/to/index.html [--chrome /path/to/chrome]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent / "layout_probe.js"


def report(result: dict) -> int:
    for warning in result.get("warnings", []):
        print(f"[WARN] slide {warning['slide']} ({warning['layout']}) {warning['type']}: "
              f"{warning['text']} -- {warning['detail']}")
    for violation in result.get("violations", []):
        print(f"[FAIL] slide {violation['slide']} ({violation['layout']}) {violation['type']}: "
              f"{violation['text']} -- {violation['detail']}")
    if result.get("pass"):
        print(f"[OK] runtime layout probe passed: {result.get('checked_slides')} slides, "
              f"0 violations, {len(result.get('warnings', []))} warning(s)")
        return 0
    print(f"[FAIL] {len(result.get('violations', []))} layout violation(s); fix and rerun")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html")
    parser.add_argument("--chrome", default="")
    args = parser.parse_args()
    deck = Path(args.html).resolve()
    if not deck.exists():
        print(f"[FAIL] not found: {deck}", file=sys.stderr)
        return 1

    probe_src = PROBE.read_text(encoding="utf-8")

    def manual_fallback(reason: str) -> int:
        print(f"[INFO] {reason}; run the probe manually:")
        print(f"  1. 本地起服务并在浏览器打开 {deck.name}")
        print(f"  2. 通过 CDP Runtime.evaluate 执行 {PROBE}（awaitPromise: true, returnByValue: true）")
        print("  3. violations 非空即未通过；逐条修复后重跑")
        return 3

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return manual_fallback("Playwright not installed")

    try:
        with sync_playwright() as pw:
            local_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            executable = args.chrome or (str(local_chrome) if local_chrome.exists() else None)
            browser = pw.chromium.launch(executable_path=executable) if executable else pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(deck.as_uri())
            page.wait_for_timeout(500)
            result = page.evaluate(probe_src)
            browser.close()
    except Exception as exc:  # 浏览器二进制缺失等环境问题，降级为手动执行
        return manual_fallback(f"Playwright unavailable ({type(exc).__name__}: {str(exc).splitlines()[0][:100]})")

    if isinstance(result, str):
        result = json.loads(result)
    return report(result)


if __name__ == "__main__":
    raise SystemExit(main())
