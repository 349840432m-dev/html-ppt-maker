# 分镜式 PPT 导出

## 目标

HTML 可以有页面内 reveal、路径绘制和讲授节奏；PPT 交付时不承诺 1:1 保留 HTML 动画。分镜式导出把关键步骤拆成多张静态状态页，用页面转场模拟动态讲述。

## 何时使用

- 用户要求 `.pptx`，且 HTML 页面包含 2 步以上 reveal。
- 公开课、发布会、路演、培训课需要讲授节奏。
- 关键页需要先错后对、先问题后方案、先数据后结论。

## 数据契约

在 `deck-plan.json` 的 slide 中增加可选字段：

```json
{
  "id": "s12",
  "type": "decision-tree",
  "title": "什么时候应该付费答卷",
  "storyboard_states": [
    {
      "suffix": "a",
      "label": "只显示起点问题",
      "include_steps": [0],
      "speaker_note": "先让观众判断是否所有问卷都值得付费。"
    },
    {
      "suffix": "b",
      "label": "显示主判断路径",
      "include_steps": [0, 1],
      "speaker_note": "把关键条件逐个推出来。"
    },
    {
      "suffix": "c",
      "label": "显示最终建议",
      "include_steps": [0, 1, 2],
      "speaker_note": "落到产品动作。"
    }
  ]
}
```

字段规则：

- `suffix`：追加到原 slide id 后，如 `s12a`。
- `label`：分镜状态说明。
- `include_steps`：该状态需要显示的 `data-step` 序号。
- `speaker_note`：该分镜页的讲稿补充。

没有 `storyboard_states` 的页面，默认原样导出一页。

## 导出原则

- 一页最多拆 5 个状态；超过 5 个说明原页信息过载，应拆成多页。
- 每个状态都必须是可理解的静态画面。
- before-after、决策树、流程、因果链、矩阵页优先拆状态。
- 数据页可以拆成"空图表 -> 高亮主项 -> 结论横幅"三步。
- PPT 页码可以保留原章节页码，分镜页用同一个主编号或隐藏细分编号。

## 推荐转场

- 同一页面拆出的状态：fade 或 morph 替代。
- 章节切换：push。
- before-after：wipe。
- 路径推进：push。
- 数据高亮：fade。

## 验收

- 运行 `python3 scripts/expand_storyboard_plan.py deck-plan.json storyboard-plan.json`。
- 检查输出页数不少于原页数。
- 检查每个分镜 id 唯一。
- 检查 `source_slide_id` 可以追溯回原始页面。
- 运行 `export_html_matched_pptx.mjs` 时同时传入原始 `deck-plan.json` 和 `storyboard-plan.json`。
- 检查 `*-export.json` 中每个状态的 `visible_steps`、截图路径和 `source_slide_id`；同一源页不同状态的截图哈希不得全部相同。
- 不要把 storyboard-plan 交给 `generate_pptx_from_plan.py`；简化可编辑脚手架不能表达 HTML reveal 状态。
