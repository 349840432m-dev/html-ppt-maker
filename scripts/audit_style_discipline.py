#!/usr/bin/env python3
"""Audit anti-slop style discipline for HTML-PPT artifacts."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


FATAL_TEXT_PATTERNS = [
    ("placeholder", re.compile(r"要素一|说明文字|看点一|方向一|阶段一|Stage 1|Step 1", re.I), "replace generic placeholder labels with real content"),
    # 中文合法破折号是成对的"——"，放行；只抓两侧带空格的装饰性分隔用法（AI tell）
    ("em-dash-separator", re.compile(r"[ \t][—–][ \t]"), "spaced em/en dash used as decorative separator; restructure the sentence"),
    ("ai-gradient", re.compile(r"purple|violet|#8b5cf6|#a855f7|#7c3aed|linear-gradient\([^)]*(?:purple|violet|#8b5cf6|#a855f7|#7c3aed)", re.I), "avoid default AI purple/blue gradient language"),
    ("numbered-kicker", re.compile(r">\s*0\d{1,2}\s*[/·]\s*[A-Za-z\u4e00-\u9fff]"), "numbered eyebrow labels (00 / INDEX style) are AI tells; name the topic instead"),
    ("unfinished-hand-track", re.compile(r"HAND-TRACK|在此手写本页内容"), "hand-track starter stub remains; finish the hand-designed slide and remove the marker"),
]

WARN_TEXT_PATTERNS = [
    ("hollow-verb", re.compile(r"赋能|助力打造|引领未来|全方位|一站式|新范式|极致体验"), "hollow marketing verbs; replace with concrete actions and objects"),
    ("generic-person", re.compile(r"张三|李四|John Doe|Jane Doe"), "generic placeholder names; use context-appropriate realistic names or anonymize"),
    ("middot-overuse", re.compile(r"·[^\n·]{0,40}·[^\n·]{0,40}·"), "3+ middle-dot separators in one line; use line breaks or columns"),
    # 孤立的单个 em/en dash（非中文成对"——"）多为文案 AI tell，提示复查
    ("lone-dash", re.compile(r"(?<!—)—(?!—)|–"), "lone em/en dash outside paired Chinese \u2014\u2014; verify it is intentional"),
]

WARN_HTML_PATTERNS = [
    # 只按透明度判重：大模糊半径 + 低透明度是合法的舞台悬浮投影（负例：stage 的 rgba(0,0,0,.18)）
    ("heavy-shadow", re.compile(r"box-shadow\s*:[^;]*rgba\(0,\s*0,\s*0,\s*\.(?:3|4|5|6|7|8|9)", re.I), "dark shadows (alpha >= .3) read as template UI"),
    ("large-radius", re.compile(r"border-radius\s*:\s*(?:2[4-9]|[3-9]\d)px", re.I), "large corner radius should be a deliberate system, not a default"),
    ("glassmorphism", re.compile(r"backdrop-filter|glassmorphism|frosted", re.I), "glass effects need explicit visual justification"),
    ("decorative-scroll", re.compile(r"scroll to|scroll↓|滚动探索|向下滚动", re.I), "scroll cues are decorative in slide decks"),
    ("emoji-icon", re.compile(r"[\U0001F300-\U0001FAFF\u2B00-\u2BFF\u2600-\u26FF]"), "emoji used as icons; use consistent line icons or symbol system instead"),
]

CSS_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|\b(?:red|blue|green|purple|violet|orange|yellow|pink|cyan|magenta)\b", re.I)
RADIUS_RE = re.compile(r"border-radius\s*:\s*([^;]+)", re.I)
# 不匹配 border-radius（负例：border-radius: 10px 曾被误计为边框宽）；捕获整条声明以便排除 CSS 三角形
BORDER_DECL_RE = re.compile(r"border(?:-(?:top|right|bottom|left))?(?:-width)?\s*:\s*([^;{}]+)", re.I)
PX_RE = re.compile(r"([0-9.]+px)\b")
TRANSITION_RE = re.compile(r"transition\s*:\s*([^;]+)", re.I)
DURATION_RE = re.compile(r"\b([0-9.]+(?:ms|s))\b")
CSS_RULE_RE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
CONNECTOR_SELECTOR_RE = re.compile(r"(?:timeline|track|road|flow|connector|relation|line|arrow|path|lane)", re.I)
PSEUDO_SELECTOR_RE = re.compile(r"::?(?:before|after)\b", re.I)
RED_RE = re.compile(r"#d8402c|#dc2626|#ef4444|#f43f5e|\bred\b|rgba?\(\s*(?:216|220|239|244)\s*,\s*(?:40|38|68|63)", re.I)
ALLOWED_NOTEBOOK_COLORS = {
    "#ffffff", "#fff", "#141414", "#33506b", "#d8402c", "#b9bdc2", "#000", "#000000",
    # 参考实现自带的中性色 token（bg-soft / ink-2 / ink-3）
    "#f2f3f4", "#3c3f43", "#85898e",
}


def normalize_css_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def scan_css_discipline(path: Path, text: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    lowered = text.lower()
    notebook_mode = "notebooklm" in lowered or "--red" in lowered and "--navy" in lowered

    # 承载关系语义的伪元素无法被 DOM 运行时探针可靠枚举，容易出现线穿字却审计通过。
    for match in CSS_RULE_RE.finditer(text):
        selector_raw = match.group("selector")
        if not CONNECTOR_SELECTOR_RE.search(selector_raw) or not PSEUDO_SELECTOR_RE.search(selector_raw):
            continue
        body = match.group("body")
        if re.search(r"position\s*:\s*absolute", body, re.I) and re.search(
            r"(?:background|border(?:-(?:top|right|bottom|left))?|width|height)\s*:", body, re.I
        ):
            selector = normalize_css_value(selector_raw)[:120]
            failures.append(
                f"{path}:{line_no(text, match.start())}: pseudo-connector: semantic line/node/arrow '{selector}' uses ::before/::after; use a real [data-connector] element so collision auditing can inspect it"
            )

    # 50% / 999px 是圆形与胶囊语义，不算圆角阶梯的一档
    radii = {normalize_css_value(v) for v in RADIUS_RE.findall(text)
             if "var(" not in v and normalize_css_value(v) not in {"50%", "999px", "9999px"}}
    if len(radii) > 2:
        warnings.append(f"{path}: radius-drift: multiple literal border-radius values {sorted(radii)[:8]}; prefer one tokenized radius system")

    # NotebookLM 参考实现是四阶边框系统（1px 发丝线 / 2px 卡片框 / 3px 强调线 / 4px 坐标轴），5 种以上才算漂移。
    # 排除含 transparent 的声明（CSS 三角形技法）——负例：甘特箭头 border: 22px solid transparent。
    border_widths: set[str] = set()
    for decl in BORDER_DECL_RE.findall(text):
        if "var(" in decl or "transparent" in decl.lower():
            continue
        border_widths.update(normalize_css_value(px) for px in PX_RE.findall(decl))
    if len(border_widths) > 4:
        warnings.append(f"{path}: border-width-drift: multiple literal border widths {sorted(border_widths)[:8]}; preserve one border rhythm")

    durations = Counter()
    for transition in TRANSITION_RE.findall(text):
        for duration in DURATION_RE.findall(transition):
            durations[normalize_css_value(duration)] += 1
    # 参考实现有 6 档语义时长（380 揭示 / 400 数值浮现 / 420 翻页 / 700-900 图表生长与描边），7 档以上才算漂移
    if len(durations) > 6:
        warnings.append(f"{path}: motion-duration-drift: many transition durations {sorted(durations)}; consolidate into motion tokens")

    if notebook_mode:
        root_match = re.search(r":root\s*\{(?P<body>.*?)\}", text, re.S)
        root_body = root_match.group("body") if root_match else ""
        colors = {normalize_css_value(c) for c in CSS_COLOR_RE.findall(root_body)}
        literal_colors = {c for c in colors if c.startswith("#")}
        extras = sorted(c for c in literal_colors if c not in ALLOWED_NOTEBOOK_COLORS)
        if extras:
            warnings.append(f"{path}: notebook-color-budget: token colors outside NotebookLM palette {extras[:8]}")

        for match in re.finditer(r'<section\b[^>]*class="[^"]*slide[^"]*"[^>]*>(?P<body>.*?)(?=\n\s*<section\b|\n\s*</main>)', text, re.S | re.I):
            body = match.group('body')
            red_hits = len(RED_RE.findall(body))
            if red_hits > 12:
                failures.append(f"{path}:{line_no(text, match.start())}: red-discipline: too many red tokens in one NotebookLM slide ({red_hits}); keep one red emphasis")
            elif red_hits > 8:
                warnings.append(f"{path}:{line_no(text, match.start())}: red-discipline: many red tokens in one NotebookLM slide ({red_hits}); verify there is only one semantic emphasis")

    return failures, warnings


def line_no(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_text(path: Path, text: str, html_mode: bool) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    template_mode = "html-deck-template" in str(path)
    for name, pattern, message in FATAL_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            item = f"{path}:{line_no(text, match.start())}: {name}: {message}"
            if template_mode:
                warnings.append(item)
            else:
                failures.append(item)
    for name, pattern, message in WARN_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            warnings.append(f"{path}:{line_no(text, match.start())}: {name}: {message}")
    if html_mode:
        for name, pattern, message in WARN_HTML_PATTERNS:
            for match in pattern.finditer(text):
                warnings.append(f"{path}:{line_no(text, match.start())}: {name}: {message}")
        css_failures, css_warnings = scan_css_discipline(path, text)
        failures.extend(css_failures)
        warnings.extend(css_warnings)
    return failures, warnings


def scan_deck_plan(path: Path, text: str) -> tuple[list[str], list[str]]:
    failures, warnings = scan_text(path, text, html_mode=False)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return failures, warnings

    if "design_read" not in data and "visual_system" not in data:
        warnings.append(f"{path}: missing-design-read: record design_read or visual_system before generating")

    system_blob = json.dumps(data.get("visual_system", data), ensure_ascii=False)
    for key in ["DESIGN_VARIANCE", "MOTION_INTENSITY", "VISUAL_DENSITY"]:
        if key not in system_blob:
            warnings.append(f"{path}: missing-dial: {key} should be recorded for taste discipline")

    slides = data.get("slides", [])
    card_like = 0
    for slide in slides if isinstance(slides, list) else []:
        layout = str(slide.get("layout_family", slide.get("type", "")))
        if layout in {"content", "cards", "data-card", "blueprint"}:
            card_like += 1
        else:
            card_like = 0
        if card_like >= 4:
            failures.append(f"{path}: repeated-card-layout: 4+ card-like slides in a row near {slide.get('id', '?')}")
            break

    return failures, warnings


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: audit_style_discipline.py <artifact.html|deck-plan.json> [...]", file=sys.stderr)
        return 2

    all_failures: list[str] = []
    all_warnings: list[str] = []
    for raw in sys.argv[1:]:
        path = Path(raw)
        if not path.exists():
            all_failures.append(f"{path}: file does not exist")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".json":
            failures, warnings = scan_deck_plan(path, text)
        else:
            failures, warnings = scan_text(path, text, html_mode=True)
        all_failures.extend(failures)
        all_warnings.extend(warnings)

    for warning in all_warnings:
        print(f"[WARN] {warning}")
    for failure in all_failures:
        print(f"[FAIL] {failure}")
    if all_failures:
        return 1
    print(f"[OK] style discipline audit passed for {len(sys.argv) - 1} file(s); warnings={len(all_warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
