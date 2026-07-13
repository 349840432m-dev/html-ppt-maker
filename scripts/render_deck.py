#!/usr/bin/env python3
"""Assemble a deck's index.html from deck-plan.json (dual-track pipeline).

Engine track: standard layouts (bars, funnel, gantt, checklist, ...) are
generated from `slide.data` using markup fragments identical to the template's
reference implementation, so structural bugs (SVG text, transform conflicts,
grid overflow) can never be reintroduced by hand-written HTML.

Hand track: anchor layouts (hero, quote, end, section, metaphor) are emitted
as clearly marked starting stubs; the model rewrites them by hand and they
must pass the runtime layout probe (layout_probe.js) before delivery.

Usage:
    python3 render_deck.py deck-plan.json output.html [--preset notebooklm|editorial]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "html-deck-template"
NOTEBOOK_TEMPLATE = TEMPLATE_DIR / "notebooklm.html"
EDITORIAL_TEMPLATE = TEMPLATE_DIR / "index.html"

ENGINE_LAYOUTS = {
    "stack", "bars", "blueprint", "decision-tree", "funnel", "causal-chain",
    "matrix", "journey", "before-after", "waterfall", "gantt", "checklist",
}
LAYOUT_ALIASES = {"journey-blueprint": "journey"}
# CSS 分块标记关键词 -> 版式 key（hero/end 永远保留）
CSS_MARKER_KEYS = [
    ("hero", "hero"), ("stack", "stack"), ("bars", "bars"), ("blueprint", "blueprint"),
    ("decision-tree", "decision-tree"), ("funnel", "funnel"), ("causal-chain", "causal-chain"),
    ("matrix", "matrix"), ("journey", "journey"), ("before-after", "before-after"),
    ("waterfall", "waterfall"), ("gantt", "gantt"), ("checklist", "checklist"),
    ("quote", "quote"), ("end", "end"),
]
ALWAYS_KEEP_CSS = {"hero", "end"}


def esc(text) -> str:
    """Escape text; `**x**` becomes red-emphasis <em>x</em>."""
    escaped = html.escape(str(text or ""))
    return re.sub(r"\*\*(.+?)\*\*", r"<em>\1</em>", escaped)


def layout_of(slide: dict) -> str:
    layout = str(slide.get("layout_family", slide.get("type", ""))).strip()
    return LAYOUT_ALIASES.get(layout, layout)


def track_of(slide: dict) -> str:
    track = slide.get("render_track")
    if track in ("engine", "hand"):
        return track
    return "engine" if layout_of(slide) in ENGINE_LAYOUTS else "hand"


def header_html(slide: dict, center=False) -> str:
    style = ' style="text-align:center; max-width:none"' if center else ""
    parts = [f"      <header>\n        <h2 data-primary-anchor data-role=\"rhythm\"{style}>{esc(slide['title'])}</h2>"]
    if str(slide.get("takeaway", "")).strip():
        parts.append(f'        <p class="takeaway">{esc(slide["takeaway"])}</p>')
    parts.append("      </header>")
    return "\n".join(parts)


def footer_html(slide: dict, deck: dict) -> str:
    label = slide.get("data", {}).get("footer") or deck.get("footer") or deck.get("title", "")
    return f'      <footer class="meta" data-role="support"><span>{esc(label)}</span><span class="page"></span></footer>'


def mark_main_structure(body: str) -> str:
    return re.sub(r"(<(?:div|section|table)\b)", r'\1 data-role="main-structure"', body, count=1)


def section(slide: dict, body: str, deck: dict, extra_cls="", center_header=False, with_header=True) -> str:
    layout = layout_of(slide)
    tab = esc(slide.get("data", {}).get("tab") or slide.get("type", layout))
    head = header_html(slide, center_header) + "\n" if with_header else ""
    body = mark_main_structure(body)
    sid = esc(slide.get("id", ""))
    return (f'    <section class="slide layout-{layout}{extra_cls}" data-title="{tab}" data-slide-id="{sid}">\n'
            f"{head}{body}\n{footer_html(slide, deck)}\n    </section>")


# ---------- engine-track generators ----------

def gen_bars(slide: dict, deck: dict) -> str:
    data = slide["data"]
    rows = []
    hot_step = 0
    for i, item in enumerate(data["items"]):
        cls = {"hot": " hot", "minor": " minor"}.get(item.get("emphasis"), "")
        if item.get("emphasis") == "hot":
            hot_step = i
        rows.append(
            f'        <div class="bar-row{cls}" data-step="{i}" style="--w:{item["width_pct"]}%">\n'
            f'          <span class="label">{esc(item["label"])}</span>\n'
            f'          <div class="track"><div class="bar"></div></div>\n'
            f'          <span class="value num">{esc(item["value"])}</span>\n'
            f"        </div>"
        )
    note = ""
    if str(data.get("note", "")).strip():
        note = f'\n        <p class="bar-note" data-step="{hot_step}">{esc(data["note"])}</p>'
    body = '      <div class="chart">\n' + "\n".join(rows) + note + "\n      </div>"
    if str(data.get("status_band", "")).strip():
        body += f'\n      <div class="status-band" data-step="{len(data["items"])}">{esc(data["status_band"])}</div>'
    return section(slide, body, deck)


def gen_funnel(slide: dict, deck: dict) -> str:
    data = slide["data"]
    layers = "\n".join(
        f'          <div class="funnel-layer{" hot" if l.get("hot") else ""}" data-step="{i}" style="--w:{int(l["width_px"])}px">'
        f'<span>{esc(l["label"])}</span><span>{esc(l["value"])}</span></div>'
        for i, l in enumerate(data["layers"])
    )
    note = data["note"]
    body = (
        '      <div class="funnel-wrap">\n'
        '        <div class="funnel">\n' + layers + "\n        </div>\n"
        f'        <div class="funnel-note" data-step="{len(data["layers"])}">\n'
        f"          {esc(note['headline'])}\n"
        + (f"          <small>{esc(note['detail'])}</small>\n" if str(note.get("detail", "")).strip() else "")
        + "        </div>\n      </div>"
    )
    return section(slide, body, deck)


def gen_decision_tree(slide: dict, deck: dict) -> str:
    data = slide["data"]
    branches = data["branches"]
    half = (len(branches) + 1) // 2
    mid = "\n".join(
        f'          <div class="tree-node{" stop" if b.get("stop") else ""}" data-step="{1 if i < half else 2}">{esc(b["text"])}</div>'
        for i, b in enumerate(branches)
    )
    body = (
        '      <div class="tree-wrap">\n'
        f'        <div class="tree-node start" data-step="0">{esc(data["start"])}</div>\n'
        '        <div class="tree-mid">\n' + mid + "\n        </div>\n"
        f'        <div class="tree-node result" data-step="3">{esc(data["result"])}</div>\n'
        "      </div>\n"
        '      <div class="tree-rail" data-step="1" aria-hidden="true"></div>'
    )
    return section(slide, body, deck)


def gen_causal_chain(slide: dict, deck: dict) -> str:
    data = slide["data"]
    cards = []
    for i, card in enumerate(data["cards"]):
        result = " result" if card.get("result") or i == len(data["cards"]) - 1 else ""
        cards.append(
            f'        <div class="chain-card{result}" data-step="{i}">\n'
            f'          <div class="k">{esc(card["kicker"])}</div>\n'
            f'          <div class="t">{esc(card["title"])}</div>\n'
            f'          <div class="m">{esc(card["detail"])}</div>\n'
            f"        </div>"
        )
    body = '      <div class="chain">\n' + "\n".join(cards) + "\n      </div>"
    return section(slide, body, deck)


def gen_matrix(slide: dict, deck: dict) -> str:
    data = slide["data"]
    points = "\n".join(
        f'        <div class="matrix-point{" hot" if p.get("hot") else ""}" data-step="{2 + i // 2}" '
        f'style="--x:{p["x_pct"]}%; --y:{p["y_pct"]}%">{esc(p["label"])}</div>'
        for i, p in enumerate(data["points"])
    )
    body = (
        '      <div class="matrix-wrap" data-step="0">\n'
        '        <div class="matrix-target" data-step="1"></div>\n'
        f'        <div class="matrix-label" data-step="1">{esc(data["target_label"])}</div>\n'
        f'        <div class="matrix-axis y">{esc(data["y_axis"])}</div>\n'
        f'        <div class="matrix-axis x">{esc(data["x_axis"])}</div>\n'
        + points + "\n      </div>"
    )
    return section(slide, body, deck)


def gen_journey(slide: dict, deck: dict) -> str:
    data = slide["data"]
    stages = data["stages"]
    n = len(stages)
    grid = f' style="grid-template-columns:118px repeat({n}, minmax(0,1fr))"' if n != 5 else ""

    def cell(raw, step):
        text = raw.get("text") if isinstance(raw, dict) else raw
        risk = '<span class="risk" data-step="3"></span>' if isinstance(raw, dict) and raw.get("risk") else ""
        return f'        <div class="j-cell" data-step="{step}">{esc(text)}{risk}</div>'

    rows = ['        <div class="j-cell j-head"></div>']
    rows += [f'        <div class="j-cell j-head" data-step="0">{esc(s)}</div>' for s in stages]
    rows.append(f'        <div class="j-cell j-lane">{esc(data.get("action_lane", "用户动作"))}</div>')
    rows += [cell(a, 1) for a in data["actions"]]
    rows.append(f'        <div class="j-cell j-lane">{esc(data.get("mechanism_lane", "产品机制"))}</div>')
    rows += [cell(m, 2) for m in data["mechanisms"]]
    body = f'      <div class="journey-wrap"{grid}>\n' + "\n".join(rows) + "\n      </div>"
    if str(data.get("note", "")).strip():
        body += f'\n      <p class="journey-note" data-step="3">{esc(data["note"])}</p>'
    return section(slide, body, deck)


def gen_before_after(slide: dict, deck: dict) -> str:
    data = slide["data"]

    def panel(side, mark, step):
        p = data[side]
        items = "\n".join(f'          <div class="ba-item">{esc(i)}</div>' for i in p["items"])
        return (
            f'        <div class="ba-panel {side}" data-step="{step}">\n'
            f'          <div class="ba-head"><span class="mark">{mark}</span>{esc(p.get("head", "改造前" if side == "before" else "改造后"))}</div>\n'
            + items + "\n        </div>"
        )

    body = ('      <div class="ba">\n' + panel("before", "✕", 0) + "\n" + panel("after", "✓", 1) + "\n      </div>\n"
            f'      <div class="ba-principle" data-step="2">{esc(data["principle"])}</div>')
    return section(slide, body, deck)


def gen_checklist(slide: dict, deck: dict) -> str:
    data = slide["data"]
    rows = "\n".join(
        f'        <div class="check-row" data-step="{i}">\n'
        f'          <div class="tick">✓</div>\n'
        f'          <div class="txt"><strong>{esc(item["strong"])}</strong>{esc(item["text"])}</div>\n'
        f"        </div>"
        for i, item in enumerate(data["items"])
    )
    body = '      <div class="list">\n' + rows + "\n      </div>"
    return section(slide, body, deck, center_header=True)


def gen_gantt(slide: dict, deck: dict) -> str:
    data = slide["data"]
    cols = data["columns"]
    n = len(cols)
    table_style = f' style="grid-template-columns:170px repeat({n},1fr)"' if n != 6 else ""
    lane_span = f"grid-column:2/{n + 2};" if n != 6 else ""
    lane_grid = (f'background:repeating-linear-gradient(90deg, transparent 0, transparent calc(100%/{n} - 1px), '
                 f'var(--ink) calc(100%/{n} - 1px), var(--ink) calc(100%/{n}));') if n != 6 else ""
    header = ['        <div class="g-cell"></div>']
    for i, col in enumerate(cols):
        fix = ' style="border-right:0"' if n != 6 and i == n - 1 else ""
        header.append(f'        <div class="g-cell"{fix}>{esc(col)}</div>')

    step = 0
    lanes = []
    for row in data["rows"]:
        lanes.append(f'        <div class="g-cell g-row-label" style="min-height:104px">{esc(row["label"])}</div>')
        inner = [f'          <div class="lane-grid"{f" style=\"{lane_grid}\"" if lane_grid else ""}></div>']
        if row.get("drop_x") is not None:
            inner.append(f'          <div class="g-drop" data-step="{step}" style="--x:{row["drop_x"]}%"></div>')
        for bar in row.get("bars", []):
            arrow = " arrow" if bar.get("arrow") else ""
            inner.append(
                f'          <div class="g-bar{arrow}" data-step="{step}" style="--x:{bar["x_pct"]}%; --w:{bar["w_pct"]}%">{esc(bar["text"])}</div>'
            )
            step += 1
        if row.get("diamond_x") is not None:
            inner.append(f'          <div class="g-diamond" data-step="{step}" style="--x:{row["diamond_x"]}%"></div>')
            step += 1
        lane_style = f' style="{lane_span}"' if lane_span else ""
        lanes.append(f'        <div class="g-lane"{lane_style}>\n' + "\n".join(inner) + "\n        </div>")

    body = (f'      <div class="gantt">\n        <div class="g-table"{table_style}>\n'
            + "\n".join(header) + "\n" + "\n".join(lanes) + "\n        </div>\n      </div>")
    return section(slide, body, deck)


def gen_waterfall(slide: dict, deck: dict) -> str:
    data = slide["data"]
    cols = data["cols"]
    n = len(cols)
    grid = f' style="grid-template-columns:repeat({n},1fr)"' if n != 5 else ""
    kinds = {"base": " base", "hot": " hot", "total": " total", "normal": ""}
    col_html = "\n".join(
        f'          <div class="col{kinds.get(c.get("kind", "normal"), "")}" data-step="{i}" style="--b:{c["base_pct"]}%; --h:{c["h_pct"]}%">\n'
        f'            <div class="block"></div><div class="val">{esc(c["value"])}</div>\n'
        f"          </div>"
        for i, c in enumerate(cols)
    )
    note = ""
    if str(data.get("note", "")).strip():
        note = f'\n          <div class="wf-note" data-step="{n}">{esc(data["note"])}</div>'
    labels = "\n".join(f"          <span>{esc(l)}</span>" for l in data["labels"])
    body = (
        '      <div class="wf-wrap">\n'
        f'        <div class="wf"{grid}>\n' + col_html + note + "\n        </div>\n"
        f'        <div class="wf-labels"{grid}>\n' + labels + "\n        </div>\n      </div>"
    )
    return section(slide, body, deck)


def gen_stack(slide: dict, deck: dict) -> str:
    data = slide["data"]
    cells = []
    for i, cell in enumerate(data["cells"]):
        if i:
            cells.append(f'          <div class="tri-arrow" data-step="{i + 1}">▶</div>')
        cells.append(
            f'          <div class="tri-cell" data-step="{i + 1}">\n'
            f'            <div class="t">{esc(cell["title"])}</div>\n'
            f'            <div class="d">{esc(cell["detail"])}</div>\n'
            f"          </div>"
        )
    body = (
        '      <div class="stack-wrap">\n'
        '        <div class="stack" data-step="0">\n'
        f'          <div class="tier upper">{esc(data["upper"])}</div>\n'
        f'          <div class="redline"><span class="tag">{esc(data["redline"])}</span></div>\n'
        f'          <div class="tier lower">{esc(data["lower"])}</div>\n'
        "        </div>\n"
        '        <div class="tri-row">\n' + "\n".join(cells) + "\n        </div>\n      </div>"
    )
    return section(slide, body, deck)


def gen_blueprint(slide: dict, deck: dict) -> str:
    data = slide["data"]
    cards = "\n".join(
        f'        <div class="bp-card{" priority" if c.get("priority") else ""}" data-step="{i}">\n'
        f'          <div class="figure">{esc(c.get("figure_note", "图示区：线稿图标 / 示意图"))}</div>\n'
        f'          <div class="t">{esc(c["title"])}</div>\n'
        f'          <div class="s">{esc(c["subtitle"])}</div>\n'
        f'          <div class="strip"></div>\n'
        f'          <div class="d">{esc(c["detail"])}</div>\n'
        f"        </div>"
        for i, c in enumerate(data["cards"])
    )
    body = '      <div class="cards">\n' + cards + "\n      </div>"
    return section(slide, body, deck)


ENGINE_GENERATORS = {
    "bars": gen_bars,
    "funnel": gen_funnel,
    "decision-tree": gen_decision_tree,
    "causal-chain": gen_causal_chain,
    "matrix": gen_matrix,
    "journey": gen_journey,
    "before-after": gen_before_after,
    "checklist": gen_checklist,
    "gantt": gen_gantt,
    "waterfall": gen_waterfall,
    "stack": gen_stack,
    "blueprint": gen_blueprint,
}

HAND_NOTE = ("    <!-- HAND-TRACK 锚点页：以下是引擎生成的起点存根。"
             "按 09-版式设计指南 / 07-视觉概念 手工完成本页，交付前必须通过 layout_probe.js 运行时审计。 -->")


def gen_hand(slide: dict, deck: dict, first: bool) -> str:
    layout = layout_of(slide)
    data = slide.get("data", {})
    active = " active" if first else ""
    if layout == "hero":
        foot_cells = data.get("foot") or [
            {"k": "核心主张", "v": slide.get("takeaway", "")},
            {"k": "信息一", "v": "补充场景 / 周期 / 团队"},
            {"k": "信息二", "v": "补充日期 / 性质 / 数据说明"},
        ]
        foot = "\n".join(
            f'        <div data-reveal style="--i:{4 + i}"><p class="k">{esc(c["k"])}</p><p class="v">{esc(c["v"])}</p></div>'
            for i, c in enumerate(foot_cells[:3])
        )
        body = (
            f'{HAND_NOTE}\n'
            f'    <section class="slide layout-hero{active}" data-title="封面" data-slide-id="{esc(slide.get("id", ""))}">\n'
            "      <header>\n"
            f'        <h1 data-primary-anchor data-role="rhythm" data-reveal style="--i:0">{esc(slide["title"])}</h1>\n'
            f'        <p class="subtitle" data-reveal style="--i:1">{esc(slide.get("takeaway", ""))}</p>\n'
            "      </header>\n"
            '      <svg class="curve" data-role="main-structure" width="1152" height="260" viewBox="0 0 1152 260" aria-hidden="true">\n'
            '        <path class="draw" data-reveal style="--len:420; --i:2" d="M 20 218 H 430" stroke="var(--navy)" stroke-width="9" stroke-linecap="round"/>\n'
            '        <circle data-reveal style="--i:3" cx="446" cy="218" r="12" fill="var(--red)"/>\n'
            '        <path class="draw" data-reveal style="--len:760; --i:3" d="M 462 218 C 700 214, 900 160, 1080 24" stroke="var(--red)" stroke-width="7" stroke-linecap="round"/>\n'
            "      </svg>\n"
            f'      <div class="hero-foot" data-role="support">\n{foot}\n      </div>\n'
            "    </section>"
        )
        return body
    if layout == "quote":
        return (
            f"{HAND_NOTE}\n"
            f'    <section class="slide layout-quote{active}" data-title="结论页" data-slide-id="{esc(slide.get("id", ""))}">\n'
            '      <div class="box" data-role="main-structure" data-reveal style="--i:0">\n'
            '        <div class="q-mark" aria-hidden="true">\u201c</div>\n'
            f"        <blockquote data-primary-anchor data-role=\"rhythm\">{esc(slide['title'])}</blockquote>\n"
            "      </div>\n"
            f"{footer_html(slide, deck)}\n    </section>"
        )
    if layout == "end":
        return (
            f"{HAND_NOTE}\n"
            f'    <section class="slide layout-end{active}" data-title="结尾页" data-slide-id="{esc(slide.get("id", ""))}">\n'
            '      <div class="end-block" data-role="main-structure">\n'
            f'        <p class="lead" data-reveal style="--i:0">{esc(slide.get("takeaway", ""))}</p>\n'
            '        <div data-reveal style="--i:1">\n'
            f"          <h2 data-primary-anchor data-role=\"rhythm\">{esc(slide['title'])}</h2>\n"
            '          <div class="underline"></div>\n'
            "        </div>\n"
            "      </div>\n"
            f"{footer_html(slide, deck)}\n    </section>"
        )
    # 未知手写版式：给最小骨架
    return (
        f"{HAND_NOTE}\n"
        f'    <section class="slide layout-{layout or "custom"}{active}" data-title="{esc(slide.get("type", "手写页"))}" data-slide-id="{esc(slide.get("id", ""))}">\n'
        f"{header_html(slide)}\n"
        "      <!-- 在此手写本页内容 -->\n"
        f"{footer_html(slide, deck)}\n    </section>"
    )


# ---------- template shell handling ----------

def split_template(template_text: str):
    match = re.search(r'(^.*?<main class="stage"[^>]*>\n)(.*?)(\n  </main>.*$)', template_text, re.S)
    if not match:
        raise SystemExit("[FAIL] template structure not recognized (need <main class=\"stage\"> ... </main>)")
    return match.group(1), match.group(3)


def prune_css(prefix: str, used_layouts: set) -> str:
    marker_re = re.compile(r"    /\* ========== ([^\n]*?) ========== \*/")
    positions = [(m.start(), m.group(1)) for m in marker_re.finditer(prefix)]
    if not positions:
        return prefix
    style_end = prefix.rfind("</style>")
    keep = [prefix[: positions[0][0]]]
    for idx, (start, name) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else style_end
        # 取最长关键词匹配，避免子串误判
        key = None
        best = -1
        for kw, layout_key in CSS_MARKER_KEYS:
            if kw in name and len(kw) > best:
                key, best = layout_key, len(kw)
        if key is None or key in ALWAYS_KEEP_CSS or key in used_layouts:
            keep.append(prefix[start:end])
    keep.append(prefix[style_end:])
    return "".join(keep)


def style_text(deck: dict) -> str:
    visual_system = deck.get("visual_system", {})
    system_style = visual_system.get("style", "") if isinstance(visual_system, dict) else ""
    confirmation = deck.get("style_confirmation", {})
    selected = confirmation.get("selected_style", "") if isinstance(confirmation, dict) else ""
    return " ".join(str(value) for value in (deck.get("visual_style", ""), system_style, selected)).lower()


def resolve_template(deck: dict, preset: str, explicit: str | None) -> tuple[Path, str]:
    if explicit:
        template = Path(explicit)
        inferred = "notebooklm" if template.name == "notebooklm.html" else "editorial"
        return template, inferred
    if preset == "auto":
        text = style_text(deck)
        preset = "notebooklm" if any(key in text for key in ("notebooklm", "信息图", "infographic")) else "editorial"
    return (NOTEBOOK_TEMPLATE, preset) if preset == "notebooklm" else (EDITORIAL_TEMPLATE, preset)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("output")
    parser.add_argument("--preset", choices=("auto", "notebooklm", "editorial"), default="auto")
    parser.add_argument("--template")
    args = parser.parse_args()

    deck = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    template_path, preset = resolve_template(deck, args.preset, args.template)
    template_text = template_path.read_text(encoding="utf-8")
    prefix, suffix = split_template(template_text)

    slides = deck.get("slides", [])
    if not slides:
        print("[FAIL] plan has no slides", file=sys.stderr)
        return 1
    engine_slides = [slide for slide in slides if track_of(slide) == "engine"]
    if preset != "notebooklm" and engine_slides:
        ids = ", ".join(str(slide.get("id", "?")) for slide in engine_slides[:8])
        print(
            "[FAIL] the deterministic engine currently supports only the NotebookLM template; "
            f"editorial engine slides found: {ids}. Use --preset notebooklm, or mark editorial pages hand with hand_reason.",
            file=sys.stderr,
        )
        return 1

    sections = []
    hand_count = 0
    used_layouts = set()
    for i, slide in enumerate(slides):
        layout = layout_of(slide)
        used_layouts.add(layout)
        if track_of(slide) == "engine":
            generator = ENGINE_GENERATORS.get(layout)
            if generator is None:
                print(f"[FAIL] {slide.get('id')}: no engine generator for layout '{layout}'; set render_track='hand'", file=sys.stderr)
                return 1
            html_block = generator(slide, deck)
            if i == 0:
                html_block = html_block.replace('class="slide ', 'class="slide active ', 1)
            sections.append(html_block)
        else:
            hand_count += 1
            sections.append(gen_hand(slide, deck, first=(i == 0)))

    if preset == "notebooklm":
        prefix = prune_css(prefix, used_layouts)
    title = deck.get("title", "HTML 动态演示稿")
    prefix = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", prefix, count=1, flags=re.S)

    output = prefix + "\n\n".join(sections) + suffix
    Path(args.output).write_text(output, encoding="utf-8")
    engine_count = len(slides) - hand_count
    print(f"[OK] wrote {args.output}: {len(slides)} slides ({engine_count} engine, {hand_count} hand-track stubs), preset={preset}")
    if hand_count:
        print(f"[NEXT] 手工完成 {hand_count} 个 HAND-TRACK 锚点页，然后用 layout_probe.js 对全部页面跑运行时审计。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
