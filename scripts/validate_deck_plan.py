#!/usr/bin/env python3
"""Validate a JSON deck plan for the html-ppt-maker skill.

Besides generic per-slide fields, this enforces per-layout slot contracts
(the "card contract" layer of the dual-track pipeline):

- Engine-track slides (render_track == "engine", the default for supported
  standard layouts) must carry a `data` object matching their layout contract,
  so `render_deck.py` can assemble them deterministically.
- Hand-track slides (render_track == "hand": hero, quote, end, metaphor pages)
  skip slot checks; they must pass the runtime layout probe instead.
"""

import json
import sys
from pathlib import Path

REQUIRED_TOP_LEVEL = [
    "title", "audience", "scenario", "goal", "style_confirmation",
    "design_read", "visual_system", "slides",
]
REQUIRED_SLIDE_FIELDS = [
    "id",
    "type",
    "title",
    "takeaway",
    "body",
    "visual",
    "animation",
    "transition",
    "speaker_notes",
]

# 结构固定、由 render_deck.py 组装的标准版式
ENGINE_LAYOUTS = {
    "stack", "bars", "blueprint", "decision-tree", "funnel", "causal-chain",
    "matrix", "journey", "before-after", "waterfall", "gantt", "checklist",
    "cycle", "radial", "pyramid", "hierarchy", "diagnostic-axis",
    "system-map", "spectrum",
}
LAYOUT_ALIASES = {
    "journey-blueprint": "journey",
    "section-impact": "section",
    "quote-principle": "quote",
    "process-map": "process",
    "case-walkthrough": "case",
}
# 允许模型手写、必须过运行时探针的锚点版式
HAND_LAYOUTS = {"hero", "quote", "end", "section", "metaphor"}

ERRORS: list[str] = []
WARNINGS: list[str] = []
STYLE_MANIFEST = Path(__file__).resolve().parent.parent / "assets" / "style-library" / "manifest.json"


def fail(message: str) -> None:
    ERRORS.append(message)


def warn(message: str) -> None:
    WARNINGS.append(message)


def load_style_catalog() -> dict[str, set[str]]:
    try:
        manifest = json.loads(STYLE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read style manifest {STYLE_MANIFEST}: {exc}")
        return {}
    styles = manifest.get("styles")
    if not isinstance(styles, list) or not styles:
        fail(f"style manifest has no styles: {STYLE_MANIFEST}")
        return {}
    catalog: dict[str, set[str]] = {}
    for item in styles:
        if not isinstance(item, dict) or not str(item.get("id", "")).strip():
            fail("style manifest contains a style without an id")
            continue
        style_id = str(item["id"]).strip()
        catalog[style_id] = {str(value).strip() for value in item.get("signatures", []) if str(value).strip()}
    return catalog


def require_text(slide_id: str, field: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        fail(f"{slide_id}: field '{field}' must be a non-empty string")


def require_list(sid: str, data: dict, key: str, lo: int, hi: int, what: str):
    items = data.get(key)
    if not isinstance(items, list) or not (lo <= len(items) <= hi):
        fail(f"{sid}: data.{key} must be a list of {lo}-{hi} {what} (got {len(items) if isinstance(items, list) else type(items).__name__})")
        return None
    return items


def check_bars(sid: str, data: dict) -> None:
    items = require_list(sid, data, "items", 3, 6, "bar rows")
    if items is None:
        return
    for i, item in enumerate(items):
        for key in ("label", "value"):
            if not str(item.get(key, "")).strip():
                fail(f"{sid}: data.items[{i}].{key} is required (bars 每条必须有标签和数值)")
        width = item.get("width_pct")
        if not isinstance(width, (int, float)) or not 1 <= width <= 100:
            fail(f"{sid}: data.items[{i}].width_pct must be 1-100 (宽度必须对应相对量级)")
    hot = [item for item in items if item.get("emphasis") == "hot"]
    if len(hot) > 1:
        fail(f"{sid}: bars 红色纪律——emphasis='hot' 只能有一条（当前 {len(hot)} 条）")


def check_funnel(sid: str, data: dict) -> None:
    layers = require_list(sid, data, "layers", 3, 5, "funnel layers")
    if layers is None:
        return
    widths = []
    for i, layer in enumerate(layers):
        for key in ("label", "value"):
            if not str(layer.get(key, "")).strip():
                fail(f"{sid}: data.layers[{i}].{key} is required")
        width = layer.get("width_px")
        if not isinstance(width, (int, float)) or not 120 <= width <= 900:
            fail(f"{sid}: data.layers[{i}].width_px must be 120-900")
        else:
            widths.append(width)
    if widths != sorted(widths, reverse=True):
        fail(f"{sid}: funnel 层宽必须单调递减（漏斗不允许中途变宽）")
    note = data.get("note", {})
    if not str(note.get("headline", "")).strip():
        fail(f"{sid}: data.note.headline is required（漏斗必须标注最大流失点的具体原因）")


def check_decision_tree(sid: str, data: dict) -> None:
    if not str(data.get("start", "")).strip():
        fail(f"{sid}: data.start is required（决策树起点问题）")
    branches = require_list(sid, data, "branches", 2, 4, "condition nodes")
    if branches is not None:
        for i, branch in enumerate(branches):
            if not str(branch.get("text", "")).strip():
                fail(f"{sid}: data.branches[{i}].text is required")
    if not str(data.get("result", "")).strip():
        fail(f"{sid}: data.result is required（决策树必须收束到结论动作）")


def check_causal_chain(sid: str, data: dict) -> None:
    cards = require_list(sid, data, "cards", 3, 4, "chain cards")
    if cards is None:
        return
    for i, card in enumerate(cards):
        for key in ("kicker", "title", "detail"):
            if not str(card.get(key, "")).strip():
                fail(f"{sid}: data.cards[{i}].{key} is required")


def check_matrix(sid: str, data: dict) -> None:
    for key in ("x_axis", "y_axis", "target_label"):
        if not str(data.get(key, "")).strip():
            fail(f"{sid}: data.{key} is required（坐标轴必须有业务含义）")
    points = require_list(sid, data, "points", 2, 6, "matrix points")
    if points is None:
        return
    for i, point in enumerate(points):
        if not str(point.get("label", "")).strip():
            fail(f"{sid}: data.points[{i}].label is required")
        for axis in ("x_pct", "y_pct"):
            value = point.get(axis)
            if not isinstance(value, (int, float)) or not 5 <= value <= 95:
                fail(f"{sid}: data.points[{i}].{axis} must be 5-95（避免点位贴边溢出）")
    hot = [p for p in points if p.get("hot")]
    if len(hot) > 1:
        fail(f"{sid}: matrix 红色纪律——hot 点只能有一个")


def check_journey(sid: str, data: dict) -> None:
    stages = require_list(sid, data, "stages", 4, 6, "stages")
    actions = data.get("actions")
    mechanisms = data.get("mechanisms")
    if stages is None:
        return
    for key, row in (("actions", actions), ("mechanisms", mechanisms)):
        if not isinstance(row, list) or len(row) != len(stages):
            fail(f"{sid}: data.{key} must align with stages 1:1（机制与动作逐格对应，需 {len(stages)} 格）")
            continue
        for i, cell in enumerate(row):
            text = cell.get("text") if isinstance(cell, dict) else cell
            if not str(text or "").strip():
                fail(f"{sid}: data.{key}[{i}] is empty（不允许空格子）")


def check_before_after(sid: str, data: dict) -> None:
    before = data.get("before", {})
    after = data.get("after", {})
    b_items = before.get("items") if isinstance(before, dict) else None
    a_items = after.get("items") if isinstance(after, dict) else None
    if not isinstance(b_items, list) or not isinstance(a_items, list):
        fail(f"{sid}: data.before.items / data.after.items are required lists")
        return
    if not 2 <= len(b_items) <= 4:
        fail(f"{sid}: before-after 条目须 2-4 条")
    if len(b_items) != len(a_items):
        fail(f"{sid}: before/after 条目必须一一对应（{len(b_items)} vs {len(a_items)}）")
    if not str(data.get("principle", "")).strip():
        fail(f"{sid}: data.principle is required（after 必须指出改造原则）")


def check_checklist(sid: str, data: dict) -> None:
    items = require_list(sid, data, "items", 3, 5, "action rows")
    if items is None:
        return
    for i, item in enumerate(items):
        if not str(item.get("strong", "")).strip() or not str(item.get("text", "")).strip():
            fail(f"{sid}: data.items[{i}] needs 'strong'（动作）and 'text'（怎么做）")


def check_gantt(sid: str, data: dict) -> None:
    columns = require_list(sid, data, "columns", 4, 8, "time columns")
    rows = require_list(sid, data, "rows", 2, 4, "work lanes")
    if columns is None or rows is None:
        return
    for i, row in enumerate(rows):
        if not str(row.get("label", "")).strip():
            fail(f"{sid}: data.rows[{i}].label is required")
        bars = row.get("bars", [])
        if not isinstance(bars, list) or not (0 <= len(bars) <= 2):
            fail(f"{sid}: data.rows[{i}].bars must be a list of 0-2 bars")
            continue
        for j, bar in enumerate(bars):
            for key in ("x_pct", "w_pct"):
                value = bar.get(key)
                if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                    fail(f"{sid}: data.rows[{i}].bars[{j}].{key} must be 0-100")
            if isinstance(bar.get("x_pct"), (int, float)) and isinstance(bar.get("w_pct"), (int, float)):
                if bar["x_pct"] + bar["w_pct"] > 100 and not bar.get("arrow"):
                    fail(f"{sid}: data.rows[{i}].bars[{j}] 超出泳道（x+w>100 且非 arrow 延伸条）")
            if not str(bar.get("text", "")).strip():
                fail(f"{sid}: data.rows[{i}].bars[{j}].text is required")


def check_waterfall(sid: str, data: dict) -> None:
    cols = require_list(sid, data, "cols", 4, 6, "waterfall columns")
    labels = data.get("labels")
    if cols is None:
        return
    if not isinstance(labels, list) or len(labels) != len(cols):
        fail(f"{sid}: data.labels must align with cols 1:1")
    totals = [col for col in cols if col.get("kind") == "total"]
    if len(totals) != 1 or cols[-1].get("kind") != "total":
        fail(f"{sid}: waterfall 必须以唯一的 total 柱收尾")
    for i, col in enumerate(cols):
        for key in ("base_pct", "h_pct"):
            value = col.get(key)
            if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                fail(f"{sid}: data.cols[{i}].{key} must be 0-100")
        if isinstance(col.get("base_pct"), (int, float)) and isinstance(col.get("h_pct"), (int, float)):
            if col["base_pct"] + col["h_pct"] > 100.5:
                fail(f"{sid}: data.cols[{i}] 柱顶超出画布（base+h>100）")
        if not str(col.get("value", "")).strip():
            fail(f"{sid}: data.cols[{i}].value is required")


def check_stack(sid: str, data: dict) -> None:
    for key in ("upper", "lower", "redline"):
        if not str(data.get(key, "")).strip():
            fail(f"{sid}: data.{key} is required")
    cells = require_list(sid, data, "cells", 3, 3, "progression cells")
    if cells is None:
        return
    for i, cell in enumerate(cells):
        if not str(cell.get("title", "")).strip() or not str(cell.get("detail", "")).strip():
            fail(f"{sid}: data.cells[{i}] needs 'title' and 'detail'")


def check_blueprint(sid: str, data: dict) -> None:
    cards = require_list(sid, data, "cards", 3, 3, "blueprint cards")
    if cards is None:
        return
    for i, card in enumerate(cards):
        for key in ("title", "subtitle", "detail"):
            if not str(card.get(key, "")).strip():
                fail(f"{sid}: data.cards[{i}].{key} is required")
    priority = [card for card in cards if card.get("priority")]
    if len(priority) > 1:
        fail(f"{sid}: blueprint 红色纪律——priority 卡只能有一张")


def check_cycle(sid: str, data: dict) -> None:
    if not str(data.get("center", "")).strip():
        fail(f"{sid}: data.center is required（循环必须说明围绕什么目标闭环）")
    items = require_list(sid, data, "items", 3, 6, "cycle nodes")
    if items is None:
        return
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"{sid}: data.items[{i}] must be an object")
            continue
        for key in ("title", "detail"):
            if not str(item.get(key, "")).strip():
                fail(f"{sid}: data.items[{i}].{key} is required")


def check_radial(sid: str, data: dict) -> None:
    if not str(data.get("center", "")).strip():
        fail(f"{sid}: data.center is required（放射图必须有中心命题）")
    spokes = require_list(sid, data, "spokes", 3, 6, "radial spokes")
    if spokes is None:
        return
    for i, item in enumerate(spokes):
        if not isinstance(item, dict):
            fail(f"{sid}: data.spokes[{i}] must be an object")
            continue
        for key in ("title", "detail"):
            if not str(item.get(key, "")).strip():
                fail(f"{sid}: data.spokes[{i}].{key} is required")
        if "hot" in item and not isinstance(item["hot"], bool):
            fail(f"{sid}: data.spokes[{i}].hot must be boolean")
    if sum(bool(item.get("hot")) for item in spokes if isinstance(item, dict)) > 1:
        fail(f"{sid}: radial 红色纪律——hot 分支只能有一个")


def check_pyramid(sid: str, data: dict) -> None:
    layers = require_list(sid, data, "layers", 3, 5, "pyramid layers")
    if layers is None:
        return
    for i, item in enumerate(layers):
        if not isinstance(item, dict):
            fail(f"{sid}: data.layers[{i}] must be an object")
            continue
        for key in ("title", "detail"):
            if not str(item.get(key, "")).strip():
                fail(f"{sid}: data.layers[{i}].{key} is required")
        if "hot" in item and not isinstance(item["hot"], bool):
            fail(f"{sid}: data.layers[{i}].hot must be boolean")
    if sum(bool(item.get("hot")) for item in layers if isinstance(item, dict)) > 1:
        fail(f"{sid}: pyramid 红色纪律——hot 层只能有一层")


def check_hierarchy(sid: str, data: dict) -> None:
    if not str(data.get("root", "")).strip():
        fail(f"{sid}: data.root is required（层级图必须有根节点）")
    groups = require_list(sid, data, "groups", 2, 4, "hierarchy groups")
    if groups is None:
        return
    for i, group in enumerate(groups):
        if not isinstance(group, dict):
            fail(f"{sid}: data.groups[{i}] must be an object")
            continue
        if not str(group.get("title", "")).strip():
            fail(f"{sid}: data.groups[{i}].title is required")
        children = group.get("children")
        if not isinstance(children, list) or not 1 <= len(children) <= 3:
            fail(f"{sid}: data.groups[{i}].children must be a list of 1-3 labels")
        elif any(not str(child).strip() for child in children):
            fail(f"{sid}: data.groups[{i}].children cannot contain empty labels")


def check_diagnostic_axis(sid: str, data: dict) -> None:
    axes = {}
    for key in ("x_axis", "y_axis"):
        axis = data.get(key)
        if not isinstance(axis, dict):
            fail(f"{sid}: data.{key} must be an object with label/min/max")
            continue
        if not str(axis.get("label", "")).strip():
            fail(f"{sid}: data.{key}.label is required")
        if not isinstance(axis.get("min"), (int, float)) or not isinstance(axis.get("max"), (int, float)):
            fail(f"{sid}: data.{key}.min/max must be numbers")
        elif axis["min"] >= axis["max"]:
            fail(f"{sid}: data.{key}.min must be smaller than max")
        else:
            axes[key] = axis
    points = require_list(sid, data, "points", 3, 8, "diagnostic points")
    if points is not None and len(axes) == 2:
        for i, point in enumerate(points):
            if not isinstance(point, dict) or not str(point.get("label", "")).strip():
                fail(f"{sid}: data.points[{i}].label is required")
                continue
            for value_key, axis_key in (("x", "x_axis"), ("y", "y_axis")):
                value = point.get(value_key)
                axis = axes[axis_key]
                safe_min = axis["min"] + (axis["max"] - axis["min"]) * .05
                safe_max = axis["max"] - (axis["max"] - axis["min"]) * .05
                if not isinstance(value, (int, float)) or not safe_min <= value <= safe_max:
                    fail(f"{sid}: data.points[{i}].{value_key} must stay inside the inner 90% of {axis_key}（避免标签贴边）")
        if sum(bool(point.get("hot")) for point in points if isinstance(point, dict)) > 1:
            fail(f"{sid}: diagnostic-axis 红色纪律——hot 点只能有一个")
    target = data.get("target")
    if not isinstance(target, dict) or not str(target.get("label", "")).strip():
        fail(f"{sid}: data.target with a label is required")
    elif len(axes) == 2:
        for lo_key, hi_key, axis_key in (
            ("x_min", "x_max", "x_axis"),
            ("y_min", "y_max", "y_axis"),
        ):
            lo, hi = target.get(lo_key), target.get(hi_key)
            axis = axes[axis_key]
            if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
                fail(f"{sid}: data.target.{lo_key}/{hi_key} must be numbers")
            elif not axis["min"] <= lo < hi <= axis["max"]:
                fail(f"{sid}: data.target.{lo_key}/{hi_key} must form a range inside {axis_key}")


def check_system_map(sid: str, data: dict) -> None:
    if not str(data.get("boundary", "")).strip():
        fail(f"{sid}: data.boundary is required（系统图必须说明边界）")
    for key in ("inputs", "outputs"):
        values = require_list(sid, data, key, 1, 3, key)
        if values is not None and any(not str(value).strip() for value in values):
            fail(f"{sid}: data.{key} cannot contain empty labels")
    modules = require_list(sid, data, "modules", 2, 4, "system modules")
    if modules is None:
        return
    for i, module in enumerate(modules):
        if not isinstance(module, dict):
            fail(f"{sid}: data.modules[{i}] must be an object")
            continue
        for key in ("title", "detail"):
            if not str(module.get(key, "")).strip():
                fail(f"{sid}: data.modules[{i}].{key} is required")
        if "hot" in module and not isinstance(module["hot"], bool):
            fail(f"{sid}: data.modules[{i}].hot must be boolean")
    if sum(bool(module.get("hot")) for module in modules if isinstance(module, dict)) > 1:
        fail(f"{sid}: system-map 红色纪律——hot 模块只能有一个")


def check_spectrum(sid: str, data: dict) -> None:
    for key in ("left_label", "right_label"):
        if not str(data.get(key, "")).strip():
            fail(f"{sid}: data.{key} is required（光谱两端必须有明确含义）")
    stops = require_list(sid, data, "stops", 3, 6, "spectrum stops")
    if stops is not None and any(not str(value).strip() for value in stops):
        fail(f"{sid}: data.stops cannot contain empty labels")
    marker = data.get("marker")
    if not isinstance(marker, dict):
        fail(f"{sid}: data.marker is required")
    else:
        if not str(marker.get("label", "")).strip() or not str(marker.get("detail", "")).strip():
            fail(f"{sid}: data.marker.label/detail are required")
        position = marker.get("position_pct")
        if not isinstance(position, (int, float)) or not 5 <= position <= 95:
            fail(f"{sid}: data.marker.position_pct must be 5-95（避免标记文字贴边）")
    target = data.get("target")
    if target is not None:
        if not isinstance(target, dict) or not str(target.get("label", "")).strip():
            fail(f"{sid}: data.target must be an object with label")
        else:
            start, end = target.get("start_pct"), target.get("end_pct")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                fail(f"{sid}: data.target.start_pct/end_pct must be numbers")
            elif not 0 <= start < end <= 100:
                fail(f"{sid}: data.target must form a range inside 0-100")


LAYOUT_CONTRACTS = {
    "bars": check_bars,
    "funnel": check_funnel,
    "decision-tree": check_decision_tree,
    "causal-chain": check_causal_chain,
    "matrix": check_matrix,
    "journey": check_journey,
    "before-after": check_before_after,
    "checklist": check_checklist,
    "gantt": check_gantt,
    "waterfall": check_waterfall,
    "stack": check_stack,
    "blueprint": check_blueprint,
    "cycle": check_cycle,
    "radial": check_radial,
    "pyramid": check_pyramid,
    "hierarchy": check_hierarchy,
    "diagnostic-axis": check_diagnostic_axis,
    "system-map": check_system_map,
    "spectrum": check_spectrum,
}


def normalize_layout(slide: dict) -> str:
    layout = str(slide.get("layout_family", slide.get("type", ""))).strip()
    return LAYOUT_ALIASES.get(layout, layout)


def check_slide_contract(slide: dict, index: int) -> None:
    sid = str(slide.get("id", f"slide #{index}"))
    layout = normalize_layout(slide)
    track = slide.get("render_track")
    if track is None:
        track = "engine" if layout in ENGINE_LAYOUTS else "hand"
    if track not in ("engine", "hand"):
        fail(f"{sid}: render_track must be 'engine' or 'hand'")
        return
    if track == "hand":
        # 逃生门围栏：引擎支持的版式走 hand 轨道会绕过全部槽位契约，必须给出理由
        if layout in ENGINE_LAYOUTS and not str(slide.get("hand_reason", "")).strip():
            warn(f"{sid}: engine-supported layout '{layout}' marked render_track='hand' without 'hand_reason'; "
                 f"prefer the engine, or state why this page needs hand-crafted HTML")
        return
    if layout not in LAYOUT_CONTRACTS:
        fail(f"{sid}: layout '{layout}' has no engine contract; set render_track='hand' or use a supported layout")
        return
    data = slide.get("data")
    if not isinstance(data, dict):
        fail(f"{sid}: engine-track slide requires a 'data' object for layout '{layout}'")
        return
    LAYOUT_CONTRACTS[layout](sid, data)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: validate_deck_plan.py <deck-plan.json>", file=sys.stderr)
        raise SystemExit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[FAIL] file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] invalid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)

    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            fail(f"missing top-level field: {field}")

    for field in ("title", "audience", "scenario", "goal", "design_read"):
        if field in data and (not isinstance(data[field], str) or not data[field].strip()):
            fail(f"top-level field '{field}' must be a non-empty string")

    style_catalog = load_style_catalog()
    selected_template = None
    secondary = None
    confirmation = data.get("style_confirmation")
    if isinstance(confirmation, dict):
        for field in ("status", "selected_style", "output_mode", "ppt_strategy"):
            if not isinstance(confirmation.get(field), str) or not confirmation[field].strip():
                fail(f"style_confirmation.{field} must be a non-empty string")
        selected_template = confirmation.get("selected_template")
        if not isinstance(selected_template, str) or not selected_template.strip():
            fail("style_confirmation.selected_template must be a non-empty style-library template id")
            selected_template = None
        else:
            selected_template = selected_template.strip()
        if selected_template and selected_template not in style_catalog:
            fail(
                f"style_confirmation.selected_template '{selected_template}' is not in style-library manifest; "
                f"expected one of {sorted(style_catalog)}"
            )
        secondary = confirmation.get("secondary_template")
        if secondary is not None:
            if isinstance(secondary, str):
                secondary = secondary.strip()
            if not isinstance(secondary, str) or secondary not in style_catalog:
                fail("style_confirmation.secondary_template must be null or a style-library template id")
            elif secondary == selected_template:
                fail("style_confirmation.secondary_template must differ from selected_template")
        if confirmation.get("status") not in {"confirmed", "user-specified", "skipped", "inherited"}:
            fail("style_confirmation.status must be confirmed, user-specified, skipped, or inherited")
    elif "style_confirmation" in data:
        fail("style_confirmation must be an object")

    visual_system = data.get("visual_system")
    if isinstance(visual_system, dict):
        for dial in ("DESIGN_VARIANCE", "MOTION_INTENSITY", "VISUAL_DENSITY"):
            value = visual_system.get(dial)
            if not isinstance(value, (int, float)) or not 1 <= value <= 10:
                fail(f"visual_system.{dial} must be a number from 1 to 10")
        preset = visual_system.get("preset")
        if preset is not None and preset not in {"notebooklm", "editorial"}:
            fail("visual_system.preset must be 'notebooklm' or 'editorial' when provided")
        signatures = visual_system.get("template_signatures")
        if not isinstance(signatures, list) or len([value for value in signatures if isinstance(value, str) and value.strip()]) < 3:
            fail("visual_system.template_signatures must contain at least 3 non-empty signatures")
        elif selected_template in style_catalog:
            signature_values = {str(value).strip() for value in signatures if str(value).strip()}
            primary_signatures = signature_values & style_catalog[selected_template]
            if len(primary_signatures) < 3:
                fail(
                    f"visual_system.template_signatures must include at least 3 signatures from "
                    f"manifest style '{selected_template}'"
                )
            allowed_signatures = set(style_catalog[selected_template])
            if isinstance(secondary, str) and secondary in style_catalog:
                allowed_signatures |= style_catalog[secondary]
            unknown = sorted(signature_values - allowed_signatures)
            if unknown:
                fail(
                    f"visual_system.template_signatures must come from manifest style '{selected_template}'; "
                    f"unknown values: {unknown}"
                )
    elif "visual_system" in data:
        fail("visual_system must be an object")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        fail("'slides' must be a non-empty list")
        slides = []

    seen_ids = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            fail(f"slide #{index} must be an object")
            continue
        for field in REQUIRED_SLIDE_FIELDS:
            if field not in slide:
                fail(f"slide #{index} missing field: {field}")

        slide_id = slide.get("id")
        require_text(f"slide #{index}", "id", slide_id)
        if slide_id in seen_ids:
            fail(f"duplicate slide id: {slide_id}")
        seen_ids.add(slide_id)

        for field in ["type", "title", "takeaway", "visual", "animation", "transition", "speaker_notes"]:
            if field in slide:
                require_text(str(slide_id), field, slide[field])

        body = slide.get("body")
        if not isinstance(body, list) or not body:
            fail(f"{slide_id}: field 'body' must be a non-empty list")
        elif any(not isinstance(item, str) or not item.strip() for item in body):
            fail(f"{slide_id}: all body items must be non-empty strings")

        check_slide_contract(slide, index)

    for warning in WARNINGS:
        print(f"[WARN] {warning}")
    if ERRORS:
        for error in ERRORS:
            print(f"[FAIL] {error}", file=sys.stderr)
        raise SystemExit(1)

    engine_count = sum(
        1 for slide in slides
        if isinstance(slide, dict)
        and (slide.get("render_track") or ("engine" if normalize_layout(slide) in ENGINE_LAYOUTS else "hand")) == "engine"
    )
    print(f"[OK] {path}: {len(slides)} slides validated ({engine_count} engine-track, {len(slides) - engine_count} hand-track)")


if __name__ == "__main__":
    main()
