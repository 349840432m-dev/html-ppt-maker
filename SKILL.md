---
name: html-ppt-maker
description: 中文 HTML-first PPT 生成工作流：先模板预览式风格确认，再生成可浏览器预览的 HTML 动态演示稿，并可导出 HTML-matched PPTX。只要用户提到 PPT、幻灯片、演示文稿、演示稿、slides、slide deck、presentation、路演、发布会、汇报、公开课、课件，或想把主题、文章、报告、会议纪要转成演示材料——即使没有明确要求 HTML——都应使用本 skill。Covers template-preview style confirmation, deck-plan validation, visual/taste audits, infographic layouts, motion planning, HTML-matched PPTX export, and storyboard-style export.
---

# HTML 动态 PPT 生成器

## Overview

使用这个技能把中文主题、资料、文章、报告、会议纪要或零散想法，转成一个可预览的 HTML 动态演示稿，并在需要时生成或规划可下载的 `.pptx`。HTML 是动态效果和预览的主载体；PPT 是交付层，必须明确哪些动画能保留、哪些会降级为静态最终状态或页面切换。

## 工作流

开工第一步：读 `references/00-硬规则速查卡.md`，它是全部深度文档的浓缩入口。随后只读取当前阶段明确点名的 reference，不要一次加载全部文档。

### Phase 0：风格确认门

在制作任何 PPT、生成 deck-plan、写 HTML 或导出 PPTX 之前，必须先完成风格确认。这个阶段只允许读取资料、做风格判断和提出方案；不要生成成品、不要启动渲染、不要导出 PPT。

先读取 `references/14-模板学习与风格选择.md` 和 `assets/style-library/manifest.json`，再实际打开 `assets/style-library/index.html` 检查候选模板。风格确认必须从真实模板预览出发：从七套参考模板中选择 3 个候选，明确 1 个主模板；不要只给“高端、科技、杂志”等抽象形容词。如果当前客户端能展示本地图片，附上 `assets/style-library/style-gallery.png`；不能展示时仍要给出模板 ID 和对应页面骨架。

自动给出 3-5 个适合该主题和受众的风格方向，并明确推荐 1 个。必须覆盖：

- **文本展示方式**：阅读件/演示件；大标题判断型、短句金句型、长文摘要型、图表注释型、代码/终端型等。
- **首页设计方向**：默认模板首页、主题专属封面、杂志封面、瑞士网格、IDE/终端隐喻、数据图首页等。
- **视觉风格**：NotebookLM 信息图、黑白瑞士风、编辑部杂志风、技术白皮书风、终端/IDE 风、产品策略简报风等。
- **信息密度与版式节奏**：页数预估、文字密度、图表占比、视觉锚点间隔、是否需要章节页。
- **动效与 PPT 策略**：HTML 动效强度、PPT 是否 HTML-matched、是否另做可编辑降级版。
- **模板证据**：候选模板 ID、采用哪几个真实页面骨架、必须兑现的构图签名，以及不适合当前主题的原因。

输出这张确认卡，然后停止，等待用户确认：

```markdown
# PPT 风格确认

## 推荐方向
[template-id] / [风格名]：为什么适合这个主题、受众和场景。

- 主模板：...
- 辅模板：...（没有则为 null）
- 采用骨架：cover / section / statement / data / process / close
- 构图签名：...

## 文本展示
- 输出模式：阅读件/演示件
- 标题风格：判断型/金句型/问题型/技术说明型
- 正文策略：每页多少文字、如何处理来源和备注

## 视觉设计
- 首页：...
- 全局风格：...
- 图表语言：...
- 色彩/字体/留白：...

## 备选风格
| 方向 | 适合什么 | 取舍 |
|---|---|---|
| ... | ... | ... |

## 生成策略
- HTML：...
- PPT：...
- 验收：...

请回复“确认执行”，或指出要换成哪个模板。
```

只有当用户回复“确认执行”、明确选择某个风格，或明确说“跳过风格确认/你直接定”时，才进入下一步。若用户已经在同一条请求里明确指定风格（例如“做成黑白瑞士风 + IDE 细节”），可把它作为已确认风格，但仍需在开工更新中简短复述该选择。

1. 先做主题内容设计。读取 `references/01-主题内容设计.md`，确认受众、目标、场景、页数、故事线、章节和逐页规划，并继承 Phase 0 已确认的风格约束。
2. 再做视觉设计与生图规划。读取 `references/02-视觉设计与生图.md`，定义视觉系统、页面类型、图片策略和生图提示词。视觉系统必须落实 `references/13-审美设计与Taste纪律.md` 的六项基础设计契约：清晰层级、主动留白、克制色彩、图文对齐、数据聚焦、统一节奏；不能只填写风格形容词。
3. 做高级审美和版式规划。读取 `references/06-高级审美与版式.md` 和 `references/13-审美设计与Taste纪律.md`，先写 Design Read，设置 `DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY` 三个旋钮，再定义版式谱系、关键视觉页、节奏变化和质量门槛。生成 HTML 前，每页必须先完成逐页版式审计字段：`layout_intent`、`first_visual_anchor`、`visual_translation`、`element_budget`、`aesthetic_risk`、`pass_criteria`，并运行 `scripts/audit_layout_aesthetics.py <deck-plan.json>`。资料少时也不能直接降级成文字卡片；必须把抽象内容翻译成一个可画的视觉对象。
4. 如果用户要求“高端”“大气”“有审美”“发布会感”“商业大片感”，必须读取 `references/07-视觉概念与生图执行.md`，先提出 3 个视觉概念方向，选定或自定 1 个方向，再生成主视觉/章节视觉/关键概念图任务。
5. 再生成 HTML 动态演示稿。读取 `references/15-渲染轨道与技术执行.md`，按已确认风格选择渲染轨道：NotebookLM 信息图风的结构化版式走确定性引擎（`render_deck.py --preset notebooklm`），编辑部纸感风、其余六套模板和 hero/quote/end 等锚点页走 hand 轨道。数字字体建制、关系线分层、图片用途声明等硬性技术约束，以及按需查阅的深度文档路由，均以该文件为准。生成前对照 `examples/reference-deck-notebooklm/` 金标准成品校准质量。
6. 做渲染、动效与整套视觉自检。先运行 `scripts/audit_style_discipline.py index.html deck-plan.json` 拦截 `pseudo-connector`，再运行 `scripts/audit_layout_contract.mjs index.html deck-plan.json`，确认 plan 声明的 slide id、版式、第一视觉锚点、主结构、辅助元素和节奏元素已真实落入 DOM；然后执行 `scripts/layout_probe.js` 清零溢出、裁切、文字重叠、`line-text-overlap` 和 `inspect-image-cropped` violations，并处理 `numeric-font-mismatch`、`aggressive-image-crop` warnings；最后运行 `scripts/audit_visual_contact_sheet.mjs`。人工查看 contact sheet，并逐条检查所有大数字页、关系图页和需要检查细节的图片页；不合格必须回到版式或视觉系统迭代。
7. 最后处理 PPT 下载或转换。默认运行 `node scripts/export_html_matched_pptx.mjs index.html deck-html-matched-with-transitions.pptx --plan deck-plan.json`，由 HTML 最终态截图生成全页图片 PPTX 并自动注入转场。关键 reveal 页先生成 `storyboard-plan.json`，再追加 `--storyboard-plan storyboard-plan.json`。只有用户明确要求可编辑元素时，才运行 `generate_pptx_from_plan.py` 生成 `*-editable.pptx` 降级版。
8. 完成前读取 `references/05-验收清单.md`，记录真实验证命令、结果、未验证项和残留风险。

## 输入收敛

如果用户没有给全信息，优先做保守假设并显式标注。风格确认门是强制前置环节，不算普通澄清；除非用户已明确指定或要求跳过，否则必须先给风格确认卡并等待确认。只有以下信息缺失且会导致方向明显错误时才额外提问：

- 使用场景会决定结构，例如融资、发布会、课程、汇报。
- 受众会决定语气、深度和视觉风格。
- 核心行动：讲完后希望观众做什么（批预算、定方案、报名）。
- 输出模式：阅读件（无演讲者也能读懂，文字完整）还是演示件（现场辅助，每页一句金句）。无法判断时默认阅读件并标注假设。
- 是否必须生成真实 `.pptx` 文件。
- 是否允许联网、生图、使用外部素材或付费服务。
- 是否有品牌规范、模板、字体、Logo 或保密要求。

## 输出结构

每次交付至少包含：

- `deck-plan.json` 或等价结构化逐页规划。
- `visual-system.json` 或等价视觉系统说明，包含版式谱系和关键视觉页。
- `deck-plan.json` 顶层包含 `style_confirmation`：确认状态、选定风格、输出模式和 PPT 策略。
- `style_confirmation.selected_template` 必须填写模板库 ID；`visual_system.template_signatures` 记录至少 3 个构图签名，`secondary_template` 没有时写 `null`。
- Design Read 和三个审美旋钮：`DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY`。
- 正式/高审美交付包含 `visual-concepts.json` 或等价视觉概念说明，记录 3 个方向、选定方向、资产清单和生图任务；普通快速稿若未启用视觉概念，须在验收记录中说明。
- `index.html`，作为主预览稿。
- `assets/`，存放生成图、占位图、字体或导出的静态资源；若无资源也要说明。
- `.pptx` 文件，或清晰的生成/下载降级说明。
- 验收记录，列出运行命令、通过项、失败项、未验证项。

## HTML 与 PPT 的边界

不要承诺 HTML 页面内动画能 1:1 转成 PPT 动画。默认规则：

- HTML 保留页面内动态效果、分步出现、轻量交互和键盘翻页。
- PPT 必须与 HTML 的页面内容、视觉层级、图表结构和最终静态状态保持一致；不能只导出标题、takeaway 和 bullet 的简化版。
- 默认优先使用“HTML 渲染图版 PPT”：用浏览器把每个 HTML slide 的最终揭示状态渲染为 16:9 全页图片，再生成 `.pptx` 并注入页面转场。这样观看结果与 HTML 一致。
- 如果用户明确要求 PPT 内部元素可编辑，才生成“可编辑 PPT”。此时必须在验收记录中标明它是可编辑降级版，并说明哪些 HTML 图表、CSS 细节或微动效没有完全保留。
- 若同时交付两种 PPT，文件命名必须清楚区分：`*-html-matched-with-transitions.pptx` 作为推荐观看版，`*-editable.pptx` 或基础文件作为可编辑降级版。
- 如果生成工具支持 PPT 动画，可谨慎添加；否则不要伪装已经保留。
- 转场必须服务叙事，不要每页随机使用不同效果。

## 可用资源

- 开工入口：`references/00-硬规则速查卡.md`，深度文档按其末尾索引按需读取。
- 全部 assets、templates、references 和 scripts 的职责说明见 `references/16-资源与脚本索引.md`；需要某类资源或不确定该调哪个脚本时先查它，不要凭猜测调用。
- 金标准示例成品：`examples/reference-deck-notebooklm/`，生成时用作质量对照。

## 迭代修订

生成后用户提出修改时，默认做局部修订而不是整套重生成：

- 用户指定某页改法（"这页改两栏""右侧换图表"）：只改该页的 HTML 和 deck-plan 条目，不动其他页。
- 修订后重跑该页的渲染自检（截图确认），不需要全套重截。
- 涉及视觉系统级的修改（换色、换字体、换风格预设）才允许全局改动，且改完必须全套快速过一遍防止漏页。
- 每轮修订同步更新 deck-plan，保持规划与 HTML 一致。

优化已有旧稿（非本 skill 生成的 deck）时，先审计再动手：

1. 先判定模式——"保留原风格做现代化"还是"推翻重做"；有分歧只问一个问题。
2. 审计现状：提取既有 token（色/字/圆角）、逐页版式清单、anti-slop 违规项、可保留的亮点。
3. 按性价比顺序修：字体与字阶 → 间距与对齐 → 色彩收敛（去杂色、锁定单强调色）→ 动效层 → 关键页重排 → 整页替换（最后手段）。修到满足要求就停。
4. 保留模式下不默改：故事线和页序、用户写的文案语气、品牌色和 Logo。

## 失败策略

- 资料不足：先输出结构和缺口清单，不编造事实。
- 引用不足：把页面标记为“需来源”，不要伪造链接。
- 生图不可用：输出可执行提示词和占位策略。
- HTML 无法预览：检查文件路径、资源路径、浏览器控制台和本地服务。
- PPT 生成失败：保留 HTML、deck plan 和错误日志，说明可重试命令。
- PPT 转场无法写入：交付无转场 PPT，并在验收记录中标记降级。
- 视觉质量不足：不要只换颜色；回到版式谱系，增加关键视觉页、概念图、案例对照页和节奏变化。若 contact sheet 中缩略图看不清主标题、连续 4 页以上轮廓相近、首页像通用模板、页面大片空白像未完成线稿，视为未达交付标准，必须重排后重跑审计。
- 视觉资产不足：不要只靠抽象线条和卡片；补主视觉、章节视觉和关键概念图，或明确为什么不用图。资料少不等于元素少；若事实材料不足，仍要通过 `visual_translation` 把概念转成流程、矩阵、诊断门、对照图、坐标系、隐喻图等可画对象。
- 页面同质化：如果连续 4 页以上使用同一种版式，必须重排或合并。
- 动效质感不足：不要堆更多动画；先删掉无目的动效，再修正词汇、stagger、easing、duration、reduced motion 和 PPT 降级说明。
- PPT 动态感不足：不要承诺 HTML 动画进 PPT；为关键页补 `storyboard_states`，用 `expand_storyboard_plan.py` 拆成静态状态页。
- 模板感过重：不要继续加装饰；回到 Design Read、三个旋钮、CRAP 对比/重复/对齐/亲密性和 anti-slop 禁令，重排结构。

## 验证要求

完整验收项、命令清单、适用条件和环境依赖前置以 `references/05-验收清单.md` 为唯一事实源；完成前按它逐项执行。任何交付的底线：

- `validate_deck_plan.py`、`audit_layout_aesthetics.py`、`audit_layout_contract.mjs`、`audit_style_discipline.py`、`audit_motion_quality.py` 的 FAIL 必须清零。
- 全部页面执行过 `layout_probe.js` 且 violations 为零；生成 contact sheet 并完成人工审稿，验收记录写明路径和结论。
- 交付 `.pptx` 时运行 `apply_ppt_transitions.py --check`；同时存在 HTML 匹配版和可编辑降级版时，最终答复必须把 HTML 匹配版标为推荐文件，避免用户误用简化版。

跑不了的验证必须说明原因，不要编造结果。
