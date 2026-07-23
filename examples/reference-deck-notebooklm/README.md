# 金标准示例 deck（NotebookLM 信息图风）

一套完整的 10 页成品，主题为「付费问卷激励设计公开课」，用作生成新 deck 时的质量对照物。

- `index.html`：可直接在浏览器打开的成品（本地起 `python3 -m http.server` 预览）。
- `deck-plan.json`：配套逐页规划，含 style confirmation、design read、三旋钮、逐页审美契约和双轨字段。`render_deck.py --preset notebooklm` 可重建 8 个 engine 页并生成 2 个 hand 起点存根；不要用重建结果覆盖已完成的金标准 HTML。

## 它示范了什么

- 语义到版式：数据对比用 bars、判断用 decision-tree、诊断用 funnel、机制用 causal-chain、优先级用 matrix、流程用 journey、改造用 before-after、行动用 checklist。
- 红色纪律：每页只有一个红色关键信息。
- 数据纪律：全部数字标注"教学示例数据"，页脚与状态条可追溯口径。
- 模板瘦身：从 `notebooklm.html` 起步后，删除了叙事用不到的版式（stack、blueprint、waterfall、gantt、quote）及其 CSS。
- 标题即判断："同样的预算，完成率差出一倍"而不是"数据对比"。
- 收束回应核心行动：结尾页是行动指令，不是"谢谢观看"。

## 验证方式

```bash
RUN=../../scripts/run_tool.sh
"$RUN" ../../scripts/validate_deck_plan.py deck-plan.json
"$RUN" ../../scripts/audit_deck_quality.py deck-plan.json
"$RUN" ../../scripts/audit_layout_aesthetics.py deck-plan.json
"$RUN" ../../scripts/audit_layout_contract.mjs index.html deck-plan.json
"$RUN" ../../scripts/audit_style_discipline.py index.html deck-plan.json
"$RUN" ../../scripts/audit_motion_quality.py index.html
"$RUN" ../../scripts/audit_visual_contact_sheet.mjs --out /tmp/reference-audit index.html
```

结构、DOM、风格和动效脚本必须 0 FAIL；contact sheet 的 warnings 必须人工复核并在交付前处理。
