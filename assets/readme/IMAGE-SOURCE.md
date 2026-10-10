# README 配图记录

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
