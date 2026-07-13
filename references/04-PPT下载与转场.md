# PPT 下载与转场

## 目标

从 HTML 演示稿和逐页规划生成或规划 `.pptx` 交付物，并按页面类型添加合适页面转场。PPT 是交付层，优先保证可打开、页数正确、内容完整。

## 生成策略

优先顺序：

1. 默认生成 HTML-matched 观看版：

```bash
node scripts/export_html_matched_pptx.mjs index.html deck-html-matched-with-transitions.pptx \
  --plan deck-plan.json
```

该脚本使用 Playwright 截取 HTML 最终状态，用 PptxGenJS 生成全页图片 PPTX，再调用 `apply_ppt_transitions.py` 注入转场，并输出 `*-export.json`。

2. 需要分镜节奏时追加：

```bash
node scripts/export_html_matched_pptx.mjs index.html deck-html-matched-with-transitions.pptx \
  --plan deck-plan.json --storyboard-plan storyboard-plan.json
```

3. 只有用户明确要求 PPT 内文本可编辑时，才运行：

```bash
python3 scripts/generate_pptx_from_plan.py deck-plan.json deck-editable.pptx
```

这是简化降级版，不能标为 HTML-matched，也不能使用 storyboard-plan。

4. 缺少 Node 依赖时，优先加载 Codex Desktop bundled workspace dependencies；其他环境安装 `playwright sharp pptxgenjs`。仍不可用时保留 HTML 和错误日志，不要悄悄退回简化 PPT。

不要在未说明的情况下安装系统级依赖。

## 转场选择矩阵

- cover -> agenda：fade。
- agenda -> section：push。
- section -> content：fade。
- content -> content：fade。
- content -> data：fade。
- data -> data：fade。
- case -> case：wipe。
- process -> process：push。
- comparison -> summary：fade。
- summary -> closing：fade。

原则：

- 同一章节内转场保持一致。
- 章节切换可以更明显，但不要频繁变化。
- 数据和严肃汇报页优先淡入。
- 发布会或产品愿景页可以使用推进感。

## 转场写入

如果已有 `.pptx` 文件，可使用：

```bash
python3 scripts/apply_ppt_transitions.py deck.pptx --plan deck-plan.json --output deck-with-transitions.pptx
```

检查转场：

```bash
python3 scripts/apply_ppt_transitions.py --check deck-with-transitions.pptx
```

脚本只处理基础转场 XML，不负责生成页面内容。若 PowerPoint 或 Keynote 对某种转场兼容性不同，以实际打开检查为准。

## 分镜式导出

关键 HTML reveal 页不要只导出最终态。先按 `12-分镜式PPT导出.md` 在 `deck-plan.json` 中补 `storyboard_states`，再运行：

```bash
python3 scripts/expand_storyboard_plan.py deck-plan.json storyboard-plan.json
```

生成 PPT 时把 `storyboard-plan.json` 交给 `export_html_matched_pptx.mjs`。脚本按 `visible_steps` 控制 HTML 后逐状态截图；不能把展开 plan 交给可编辑简化脚手架。

## HTML 到 PPT 的降级说明

- 页面内分步动画：默认降级为静态最终状态。
- 列表逐条出现：优先拆页；也可转为基础 appear/fade。
- 图表逐步高亮：拆为多页，每页突出一个重点。
- 对比前后变化：拆为前后两页或使用 Morph 的替代转场。
- 背景和图片：保留为静态图片或形状。
- 图表动画：降级为完整图表。
- 页面切换：按矩阵写入基础转场。
- 音视频和复杂交互：默认不进入 PPT，除非用户明确要求。

## 验收点

- `.pptx` 文件存在且非空。
- 非分镜模式页数和 HTML 一致；分镜模式页数和 `storyboard-plan.json` 一致。
- 每页有标题或视觉主元素。
- 转场检查能发现基础 transition 标签。
- 降级项已经写进验收记录。
- `*-export.json` 中截图数、导出页数和 transition 状态正确。
