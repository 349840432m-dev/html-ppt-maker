# HTML 动态演示

## 目标

生成一个可浏览器预览、键盘翻页、带克制动态效果的 HTML 演示稿。HTML 是动态和预览主载体，必须稳定、可读、可离线交付。

动效设计必须同时读取 `10-动效词汇与质感审计.md`：先用标准词汇命名，再确认目的、频率、参数和 PPT 降级方式。
审美设计必须同时读取 `13-审美设计与Taste纪律.md`：先写 Design Read 和三个旋钮，再进入模板改造。

## 推荐结构

- `index.html`：单文件优先，便于交付。
- `assets/`：图片、字体、导出资源；路径使用相对路径。
- `deck-plan.json`：保存逐页结构和元数据。

## 渲染轨道选择

先服从 Phase 0 已确认风格，再选择管线：

- **NotebookLM 引擎轨道（标准页）**：bars、funnel、gantt、checklist、waterfall、stack、decision-tree、causal-chain、matrix、journey、before-after、blueprint。填 `render_track: "engine"` 和 `data` 槽位，然后运行 `python3 scripts/render_deck.py deck-plan.json index.html --preset notebooklm`。**不要手写引擎轨道页。**
- **手写轨道（锚点页）**：hero、quote、end、section、视觉隐喻页标 `render_track: "hand"`。引擎输出带 `HAND-TRACK` 注释的起点存根，在存根上手工完成设计——这是发挥创造力的地方，但交付前必须对全部页面执行 `scripts/layout_probe.js` 运行时审计（溢出/裁切/重叠清零），并删除 `HAND-TRACK` 注释。
- **编辑部纸感 hand 轨道**：当前引擎没有编辑部版式 CSS。选择编辑部风时直接以 `index.html` 为起点手工实现页面；引擎支持语义若走 hand，写明 `hand_reason`。不要使用 `render_deck.py --template index.html` 组装引擎页。

编辑部风或引擎不支持的版式使用手工模板流程：

**必须复制 `assets/html-deck-template/` 下的一个模板作为起点**，不要从空白 HTML 重新发明：

- `index.html`：编辑部纸感风（默认）。衬线标题、米白纸底、深绿强调，10 类版式。
- `notebooklm.html`：NotebookLM 信息图风。纯白底、上下黑色压边条、超粗黑体标题、黑/藏蓝/朱红三色、2px 黑边线框，每页一个大图表（层级堆叠、条形图、瀑布图、甘特表、勾选清单），并含全部六个高级公开课组件（decision-tree、funnel、causal-chain、matrix、journey、before-after）。用户要"NotebookLM 风""信息图风""图表型"时用它。它的核心气质是"每页都是一张信息图"：标题给判断，图表给证据，红色只用于最关键的一个信息。

复制模板后必须做减法：删除叙事用不到的 `<section>` 及其专属 CSS 块，避免成品带着无关版式和死代码交付。完成后的样子参考金标准示例 `examples/reference-deck-notebooklm/`。

两个模板共用固定舞台和 data-reveal / data-step 揭示机制，但版式 CSS 不可互换。

动效 token 必须保持一致：

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
```

### 美感来源：密度、标注、真实数据

模板只是骨架，"设计感"主要来自生成 deck 时的填充质量。三条硬规则：

- **密度**：图表页的图表要占画布主体（约 60% 以上），标题区收紧、紧贴内容。大面积留白只允许出现在封面、原则页和结论页；图表页的空白是空虚不是高级。
- **标注层**：每个图表页至少加一层注释——指向箭头、手写式标注（如"核心增长引擎"）、图例、来源行、红色强调点。没有标注层的图表看起来像默认组件库。
- **真实数据**：条形长度、瀑布增量、甘特周期必须来自真实内容，让数据本身制造戏剧性（如 2020 对 58 的悬殊对比）。均匀的假数据和"要素一"式占位词会让任何版式显得廉价；交付前必须把所有占位词替换干净。

## 固定 16:9 舞台

- 页面按固定设计尺寸排版（默认 1280x720），用 `transform: scale()` 等比适配窗口，不要用 100vw/100vh 自适应布局。
- 好处：字号、留白、构图是确定性的，任何窗口下渲染一致，截图和转 PPT 的画布对得上。
- 字号直接用 px，不再需要 clamp 响应式字号。

## 版式库用法

每类版式的详细设计规范（结构、尺寸、标注层、常见错误）见 `09-版式设计指南.md`；整体视觉基因（色彩、字体、红色纪律、禁用项）见 `08-整体视觉与细节.md`。本节只列清单和技术复用规则。

模板内置 10 类版式，与 `06-高级审美与版式.md` 的版式谱系对应：

- `layout-hero`：封面。大衬线标题分层入场，禁止塞要点卡片。
- `layout-section`（深色）：章节页。巨型描边章节编号 + 颗粒质感 + 柔光晕。
- `layout-framework`：方法论页。HTML 节点分步出现，连线用 `.draw` 描边动画绘制。
- `layout-contrast`：对照页。误区面板与改造面板分步揭示。
- `layout-data`：数据页。大数字 `data-count-to` 滚动到最终值，必须带来源行。
- `layout-quote`：原则页。一个强句子居中，关键词强调色。
- `layout-content`：常规卡片内容页。连续使用不得超过 3 页。
- `layout-case`：案例拆解页。全景画布 + 编号标记与右侧看点笔记同步分步揭示；全景用真实素材或占位框，禁止伪造截图。
- `layout-process`：流程页。阶段节点分步推进，连线随路径绘制，支持回流闭环。
- `layout-end`（深色）：结尾页。收束句 + 行动号召。

复用规则：

- 新版式基于 token（CSS 变量）扩展，不要写死色值。
- 两种揭示机制：`data-reveal` + `--i` 表示进入页面自动错峰入场；`data-step="n"` 表示按前进键分步揭示，相同 n 属于同一步。封面、章节页用 `data-reveal`，需要演讲节奏控制的内容用 `data-step`。
- 深色页直接加 `dark` class 复用质感层。
- 生图资产用模板内置的 `.gen-asset` 类嵌入（absolute 定位 + multiply 融合 + 提白滤镜），提示词配方和嵌入规则见 `07-视觉概念与生图执行.md` 的"混合渲染"一节。
- **图形页文字必须用 HTML 元素，禁止用 SVG `<text>`**：在 `transform: scale` 缩放的舞台内，Chromium 会把 SVG 文字渲染到错误位置。SVG 只负责连线、路径和形状，节点框和标签用绝对定位的 HTML 叠加在 SVG 上（见模板 framework 版式）。
- **装饰层优先用 `::before`/`::after` 伪元素，不要用真实 DOM 元素**：伪元素永远不会变成网格项。如果必须用真实元素（如纹理、光环 div），警惕形如 `.slide > *:not(...)` 的通配规则——它的优先级会盖过装饰元素自己的 `position: absolute`，把装饰层变回 in-flow 网格项，撑出整行空白并把正文挤到页面下半部。写通配规则时必须把所有装饰类加进 `:not()` 排除链。

## 交互要求

- 左右方向键、空格、PageUp/PageDown 翻页。
- Home 跳到第一页，End 跳到最后一页。
- `B` 键切换静态最终态，供截图、低性能设备和 PPT 转换前检查。
- 当前页码可见但不喧宾夺主。
- 移动端至少能点击或触摸切换。
- 不依赖网络资源；如使用 CDN，必须说明风险和离线替代。
- 如果页面内有分步 reveal，前进键先推进 reveal，全部 reveal 完成后再进入下一页；后退键先回退 reveal，再返回上一页。

## 页面内动效

**动效必须有动机**：加任何动效前先回答"这个动画传达什么"，合法答案只有四种——层级（把视线引到对的地方）、叙事（按论证顺序揭示）、反馈（响应按键）、状态变化。一句话说不清动机的动效直接删掉。反过来也成立：**动效声明 = 动效兑现**——拨盘定了高动效强度，页面就必须真的动起来（封面分层入场、图表生长、路径绘制至少占一样）；做不到就把拨盘降下来交付干净的静态版，不要交付半残动效（卡一半的揭示、跳帧的入场）。

性能与可及性硬规则：

- 只动 `transform` 和 `opacity`，不动 `top/left/width/height`（图表生长类版式例外，但必须限制在单页少量元素）。
- 必须支持 `prefers-reduced-motion`：命中时所有 reveal 直接呈现最终态（模板 `B` 键的静态模式即降级实现）。

动效用于建立阅读顺序，不用于炫技：

- 封面：标题、背景、署名依次入场。
- 目录：章节项轻微错峰出现。
- 章节页：大标题推进或淡入。
- 内容页：要点分步出现。
- 数据页：数字强调、图表淡入。
- 案例页：图片先入场，文字随后出现。
- 总结页：结论和行动项清晰收束。

常用动效映射（模板中均有参考实现，不要只用淡入）：

- Fade：文本、图片、卡片出现。模板 `[data-reveal]`。
- Slide：列表、模块进入。模板 `[data-reveal]` 自带 14px 上移。
- Scale：重点数字、图标强调。
- Stagger：多项列表依次出现。模板 `transition-delay: calc(var(--i) * 30-80ms)`。
- Count-up：数据强调。模板 `data-count-to` + `data-decimals`，PPT 中使用最终数字。
- Highlight：关键词或区域强调。
- Path/Draw：流程线和箭头。模板 `.draw` + `--len`（路径长度）描边动画，PPT 中使用最终状态。

默认参数：

- 时长：300-700ms。
- easing：`--ease-out`、`--ease-in-out` 或明确的 cubic-bezier；禁止 UI 入场使用 `ease-in`。
- 位移：8-32px。
- 缩放：0.96-1.04 之间。
- 控件反馈：100-200ms，按钮按下用 `scale(.97)` 即可。
- 禁止：`transition: all`、`scale(0)`、快速闪烁、大幅旋转、持续晃动、遮挡正文。
- 性能：优先动画 `transform` 和 `opacity`；条形图增长优先用 `scaleX`，少用 width；hover 动效放进 `@media (hover: hover) and (pointer: fine)`。

## 可访问性与稳定性

- 支持 `prefers-reduced-motion`，用户减少动画时关闭大部分动效。
- 文本不能依赖图片承载。
- 背景图上文字必须有遮罩或足够对比。
- 动态元素进入后保持静止，便于截图和转 PPT。

## 导出边界

- HTML 动效不等于 PPT 动画。
- 转 PPT 时优先导出每页最终状态。
- 如需 PPT 动画，必须单独检查工具是否支持。
- 不支持时，把动效降级为页面间转场和静态版式。
- 复杂交互、WebGL、canvas、Lottie、滚动动画和多元素联动动画不得承诺 1:1 转换。

## 验收点

- HTML 能打开并显示第一页。
- 键盘翻页可用。
- 页面没有文字重叠或溢出。
- 动效不会遮挡内容。
- 关闭动画后仍能理解内容。
- 每个最终 slide 有 `data-slide-id`；第一视觉锚点、主结构、辅助解释和节奏元素分别使用 `data-primary-anchor`、`data-role="main-structure"`、`data-role="support"`、`data-role="rhythm"` 标记，并通过 `audit_layout_contract.mjs`。
