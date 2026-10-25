# README 配图记录

## 2026-10-25 按 Skill 用途选择画风

- README 视频文字跟踪打码配图：[video-text-redactor-cinematic.png](video-text-redactor-cinematic.png)。采用电影感剪辑室与影视技术视觉，重点表现遮挡随文字位置和大小变化、原声音轨及成片复查。
- README 项目开发 LLM Wiki 配图：[project-llm-wiki-engineering.png](project-llm-wiki-engineering.png)。采用现代工程资料室的写实编辑画面，表现来源归档、查阅、验证与知识维护；替换上一版童话知识工坊。
- 故事词汇保留绘本式阅读场景，项目导读保留探索地图式画面；合集仍作统一目录插画，详情配图按具体用途区分。
- 生成方式：内置 `image_gen`，分别生成，工具未披露实际模型名称。完整提示词：[subject-matched-20261025-prompts.md](subject-matched-20261025-prompts.md)。图片均为能力概念图，非实际运行截图。

- `video-text-redactor-cinematic.png` SHA-256：`2b46e1e91e36069f09c9b929575a267bf7c435776be534993e26c7c51337c90f`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-7f673295-da44-45e0-b7f4-3cf65a846049.png`。
- `project-llm-wiki-engineering.png` SHA-256：`ebc79cb1bc36bf6fec58b310ad546e0efa9d9155173b65e4e88657b9a2b76507`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-d0a043b2-1117-4669-902c-713263dbeb84.png`。

## 2026-10-25 场景插画替换方框流程图

- 当时生成：[project-llm-wiki-illustrated.png](project-llm-wiki-illustrated.png)、[story-vocabulary-studio-illustrated.png](story-vocabulary-studio-illustrated.png)、[project-flow-guide-illustrated.png](project-flow-guide-illustrated.png)。LLM Wiki 随后按用途调整为上方工程资料室版本，旧图保留为历史记录。
- 生成方式：内置 `image_gen`，三张分别生成；工具未披露实际模型名称，不额外标注具体 GPT Image 版本。沿用合集的纸感、水彩线稿、人物与助手画风，画面分别为知识工坊、故事阅读教室、项目探索景观。
- 完整提示词：[scene-illustrations-20261025-prompts.md](scene-illustrations-20261025-prompts.md)。
- 原方框箭头图不符合用户确认的展示风格，六张 PNG、六份 Mermaid 源文件及临时渲染说明／脚本全部撤下；视频与电商沿用现有生动插画，移除重复的汇总流程图。
- 图像性质：能力概念插画，非实际运行截图；不作为运行、教学效果或项目理解正确性的验证证据。正文承担功能、依赖与边界说明，配图以场景和动作辅助理解。

- `project-llm-wiki-illustrated.png` SHA-256：`1789084936c0a09bcd1f998929f9092274cc170496005a13079174aefb458d9d`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-b3cf6549-2919-4f3f-a01b-9ee266c0b7f0.png`。
- `story-vocabulary-studio-illustrated.png` SHA-256：`98c7cd449bdc48e1ceece5a47a131dab8b955dbe7d0092d4ed1816cda17a8c25`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-b090b89d-1806-4a52-a749-4cd21c036120.png`。
- `project-flow-guide-illustrated.png` SHA-256：`68e02b6895c859481da98722a97680d67d57806a63e4793b0923497caa4d3b65`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-ec70b572-7a71-4354-9a60-4e31069b89a1.png`。
- LLM Wiki 原始候选图出现额外手臂，使用同一内置工具定点修复后采用上述成品；原候选未纳入仓库。

## 2026-10-25 插画总览与流程图兼容修复

- README 当前总览：[skills-overview-20261025.png](skills-overview-20261025.png)，覆盖 10 个 Skill 和 1 个独立工作流，包含“项目开发 LLM Wiki”。
- 生成方式：内置 `image_gen`，以历史 `skills-overview.png` 为编辑目标和风格参考，沿用纸感底色、人物与物件插画；工具未披露实际模型名称，不额外标注具体 GPT Image 版本。
- 完整提示词：[overview-20261025-prompt.txt](overview-20261025-prompt.txt)。原始输出位于 `/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-8ef6163a-bdae-4731-a5fc-0bb83879bbe4.png`，已复制到仓库。
- 历史尝试：曾将五个 Mermaid 代码块及新增 LLM Wiki 流程预渲染为 PNG，解决显示问题；用户随后指出方框箭头样式不符合预期，该批图与临时渲染文件已移除，当前使用上方场景插画。
- 图像性质：能力与流程示意，非实际运行截图；插画不作为产品结构、运行结果或学习效果的验证依据。
- 当前插画 SHA-256：`fdf1a72b0a41815aad9ef2c8ab6f0f9dc739900c535e830f7c6a9802c333f8f5`。

## 2026-10-25 工具箱目录总览

- 文件：[toolbox-overview.svg](toolbox-overview.svg)。
- 历史用途：曾用于 README 能力总览，覆盖 10 个 Skill 与 1 个独立工作流；现已按用户要求恢复 AI 生成插画，该 SVG 留作历史记录。
- 制作方式：依据 README 与 catalog.json，用原生 SVG 编排分类、名称和用途；无外部图片、字体文件或 AI 生图服务。采用系统字体回退，文本可直接维护。
- 性质：能力与分类示意，非实际运行截图。此前 README 中的 Mermaid 及其预渲染图均已撤下。
- 旧 `skills-overview.png` 保留为历史 AI 生成插画，其来源和哈希仍见下方历史记录；不再作为当前完整目录总览。

## 文字／录音转动态图解视频更新

- 日期：2026-10-12。
- 文件：`skills-overview.png`（更新视频面板）、`text-or-voice-to-video.png`（两种输入的流程示意）。
- 生成方式：内置 `image_gen`；工具未披露实际模型名称。
- 性质：能力示意；README 的实际成片仍使用已有录音实例。
- 提示词：见 `video-update-20261012-prompts.txt`。下方总览提示词保留为历史生成记录。

## 北京中考志愿填报顾问卡通图

- 文件：`beijing-zhongkao-advisor-cartoon.png`
- 日期：2026-10-11
- 用途：替换 README 中来源项目说明和学校信息采集表截图，直接向家长介绍 Skill 能力。
- 生成方式：内置 `image_gen` 工具，独立生成一张卡通图。
- 用户指定模型：`gpt-image-2.5`；内置工具无模型选择参数，返回结果未披露模型名称，无法核实实际模型。
- 性质：能力示意，无具体政策结论或录取承诺。

### 中考顾问图生成提示词

```text
Use case: infographic-diagram. Generate ONE charming cartoon explainer illustration, wide landscape 1536x1024, for a Chinese README introducing the skill 北京中考志愿填报顾问. Warm ivory background, bold legible Chinese typography, friendly hand drawn robots and family, cobalt blue, green and orange palette, polished educational comic with spacious 5 numbered scenes joined by clear arrows, 1→2→3 top then curved arrow to 4→5 bottom.
Title exact "北京中考志愿填报顾问". Subtitle exact "从零散信息出发，陪家长一步步理清选择".
1 "先聊孩子情况", friendly advisor robot talking with a parent and teenager, speech bubble "一次问一个问题", profile cards labeled "中考年份" "户籍学籍" "报考区".
2 "核验报考资格", robot detective with magnifying glass examining official policy documents, a gate with different paths, cards "对应届别" "官方依据". Convey check eligibility before school recommendations.
3 "分析成绩与偏好", family and robot arranging a ranking chart and map pin and school dorm icons; labels "成绩定位" "通勤住宿" "家庭偏好", no invented scores or numerical thresholds.
4 "比较升学选择", robot and family looking at three cute school buildings on branching paths, neutral labels "学校信息" "升学路径" "条件匹配", no actual school names, rankings, guaranteed offers or exact probabilities.
5 "整理建议与清单", robot handing family a clipboard with checklist, labels "信息齐全再给建议" "家长最终复核", parent carefully checking.
Make characters expressive, story easy to understand, child and parent visibly engaged, subtle Beijing city architectural silhouettes in background. Big readable Chinese labels, generous whitespace. Footer exact "能力示意 · 政策按届别核验 · 不承诺录取". No my-volunteer project name, no source-project discussion, no historical 2026 templates, no tables/screenshots or real documents, no phone or laptop mockups, no promotional guaranteed admission claims, no watermarks.
```

## 飞书电商工作流卡通图

- 文件：`feishu-ecommerce-workflow-cartoon.png`
- 日期：2026-10-10
- 用途：替换 README 中手机与笔记本测试任务配图，以卡通流程介绍读取任务、AI 生图、归档打包、状态回写和机器人通知。
- 生成方式：内置 `image_gen` 工具，独立生成一张流程图。
- 用户指定模型：`gpt-image-2.5`；内置工具不提供模型选择参数，返回结果未披露模型名称，无法核实实际模型。
- 性质：流程示意，非实际运行截图。

### 卡通图生成提示词

```text
Use case: infographic-diagram
Create one lively cartoon infographic for a Chinese GitHub README explaining 飞书电商生图工作流. Wide landscape 3:2 composition, polished charming hand-drawn editorial cartoon, warm ivory paper, ink outlines, cobalt blue, mint green and apricot orange, highly legible simplified Chinese. Title exactly "飞书电商生图工作流". Subtitle exactly "从表格任务到图片交付，一路自动衔接".
Depict a whimsical miniature image-making factory with friendly tiny robot workers, papers and conveyor belts. Five clearly numbered stations connected by large directional arrows, arranged 1→2→3 across top and 4→5 across bottom with an unambiguous connecting curved arrow:
1 "读取任务": robot collecting product reference photo cards and a prompt card from a floating spreadsheet, colored status tabs. Small text "待处理 / 失败待重试".
2 "AI 生图": friendly robot artist with a magic paintbrush producing attractive product image cards of a tote bag and a ceramic cup. Small text "按任务要求生成图片".
3 "归档打包": robot sorting image cards into a folder and ZIP parcel. Small text "图片归档 · ZIP 打包".
4 "状态回写": robot stamping a green checkmark onto the original spreadsheet. Small text "更新任务状态".
5 "机器人通知": cheerful messenger robot delivering a notification bubble and completed parcel to a happy ecommerce teammate. Small text "通知负责人领取结果".
Use expressive characters, visually clear actions, lots of breathing room, generous readable type, subtle playful motion lines. Avoid phones, smartphones, laptops, desktop computers, hardware mockups, screenshots, fake UI screenshots, irrelevant logos, watermarks and performance claims. Footer exact text "流程示意 · 非实际运行截图". The illustration must explain the workflow, not show phone or computer products.
```

## Skill 能力总览

- 文件：`skills-overview.png`
- 日期：2026-10-10
- 用途：六个 Skill 的能力概念总览；不是实际运行截图。
- 生成方式：内置 `image_gen` 工具。
- 用户指定模型：`gpt-image-2.5`。当前工具不提供模型选择参数，返回结果未披露模型名称，因此无法核实实际使用该模型。
- README 规格书示例已改用 coding-blog 归档的 KHJE6075 同款原稿与成品；原 Skill 的 examples 文件保持不变。来源见 `../examples/sources.json`。

## 生成提示词

```text
Use case: infographic-diagram
Asset type: Chinese GitHub README illustrated overview, wide landscape high resolution.
Create a beautifully art-directed editorial infographic for a personal AI skills toolbox. Off-white paper background, dark navy typography, restrained cobalt and orange accents, fine ink diagrams with tactile miniature illustrations. Six equally sized panels in a 3 columns by 2 rows grid, generous whitespace and clear readable simplified Chinese. Title exactly "Chris 的 Skill 工具箱", subtitle exactly "把具体问题，变成可执行的工作流". Each panel has one evocative detailed illustration, bold title and short description:
1 title "人际冲突与边界" description "梳理事实 · 建立边界 · 组织回复"; illustration two people conversing with a boundary line and organized speech cards.
2 title "产品保真" description "原图证据 · 结构核对 · 材质质检"; illustration leather handbag under magnifying glass showing stitches and buckle detail, reference cards.
3 title "飞书电商工作流" description "任务读取 · 生图归档 · 状态回写"; illustration connected spreadsheet, image stack, archive box and notification.
4 title "服装规格书中文批注" description "识别翻译 · 保留原稿 · 中文批注"; illustration jacket technical drawing with small blue annotation callouts, do not invent real customer documents.
5 title "北京中考志愿顾问" description "信息补问 · 政策核验 · 志愿建议"; illustration family looking at a branching school roadmap and official document.
6 title "录音驱动动态图解" description "本人录音 · 字幕对齐 · 视频制作"; illustration microphone, waveform and video editing timeline with illustrated frames.
Small footer exactly "能力示意 · 非实际运行截图". Cohesive professional visual storytelling, legible lettering, no unrelated logos or watermark. This is a conceptual overview, no numerical performance claims.
```

## 2026-10-13 独立工作流收录配图

- 日期：2026-10-13。
- 生成方式：内置 `image_gen`；工具未披露实际模型名称。
- 总览：编辑既有 `skills-overview.png`，保留六个 Skill，增加独立工作流区域；标题改为“Chris 的 AI 工具箱”，数量为“6 个 Skill · 1 个工作流”。
- 流程图：新增 `ecommerce-template-image-workflow.png`，展示模板入库、自动选模、产品锁定、几何预检、明确渠道单张生成、逐实例质检及失败重做当前图。
- 性质：能力与流程示意，不是实际运行截图，不作为结构或生成效果的验证依据。
- 完整提示词：[workflow-update-20261013-prompts.md](workflow-update-20261013-prompts.md)。

- `skills-overview.png` SHA-256：`2dba0738f1064a021bd744ddd831961edb9655bc572bd3af78499af4ce34f785`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-b934c564-49d8-4a00-8278-7a5c40e6f851.png`。
- `ecommerce-template-image-workflow.png` SHA-256：`b0a153bb5cb8dcfe82cb70359fffeb0eb6fcfeeb91681a1f5e223bab96e11678`。
  - 原始输出：`/Users/chris/.codex/generated_images/01a13553-7610-7d92-8e5a-58c1a3a1a0d7/exec-81bff2cb-99e6-4158-bace-31651b4b520c.png`。
