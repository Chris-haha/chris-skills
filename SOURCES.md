# 来源与归集记录

归集日期：2026-10-10。原始项目保持不变；本仓库保存独立副本。

| Skill | 原始目录 | 归集目录 |
| --- | --- | --- |
| preserving-product-fidelity | `/Volumes/Samsung_T5/code/test-image/.codex/skills/preserving-product-fidelity` | `skills/ecommerce/preserving-product-fidelity` |
| feishu-ecommerce-workflow | `/Volumes/Samsung_T5/code/my-workflow/E-commerce/codex_ecommerce_workflow_analysis_20260720/mvp-workflow/skills/feishu-ecommerce-workflow` | `skills/ecommerce/feishu-ecommerce-workflow` |
| garment-spec-cn-annotation | `/Volumes/Samsung_T5/macmini/code/coding-blog/project-sources/skills/garment-spec-cn-annotation` | `skills/ecommerce/garment-spec-cn-annotation` |
| beijing-zhongkao-admissions-advisor | `/Volumes/Samsung_T5/code/my-volunteer/skills/beijing-zhongkao-admissions-advisor` | `skills/education/beijing-zhongkao-admissions-advisor` |
| text-or-voice-to-video | `/Users/chris/.codex/skills/text-or-voice-to-video` | `skills/video/text-or-voice-to-video` |
| story-vocabulary-studio | `/Volumes/Samsung_T5/code/my-workflow/education/story-vocabulary-research/skills/story-vocabulary-studio` | `skills/education/story-vocabulary-studio` |
| project-flow-guide（原名 project-xray） | `/Users/chris/.codex/skills/project-xray` | `skills/development/project-flow-guide` |
| ecommerce-video-breakdown | `/Volumes/Samsung_T5/code/my-workflow/ecommerce/video-breakdown/skills/ecommerce-video-breakdown` | `skills/ecommerce/ecommerce-video-breakdown` |
| media-urls-batch-archive | `/Users/chris/.codex/skills/media-urls-batch-archive` | `skills/video/media-urls-batch-archive` |
| ecommerce-reference-product-swap | `/Users/chris/.codex/skills/ecommerce-reference-product-swap` | `skills/ecommerce/ecommerce-reference-product-swap` |
| bilibili-toolkit | `/Users/chris/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_8ji05hs5w3gc22_3eea/temp/RWTemp/2026-11/b2c0f4fb9b7a2ce09b59bc31f7946a8c/bilibili-toolkit.zip`（用户提供 ZIP） | `skills/video/bilibili-toolkit` |

| 工作流 | 原始目录 | 归集目录 |
| --- | --- | --- |
| ecommerce-template-image-workflow | `/Volumes/Samsung_T5/code/my-workflow/E-commerce/ecommerce-template-image-workflow` | `workflows/ecommerce/ecommerce-template-image-workflow` |

## 补充与缺失

- 飞书 Skill 来源没有 `workflow/`，按其 wrapper 要求从所属 mvp-workflow 补入源码、测试、文档、依赖清单与 `.env.example`。未复制本地 `.env`、运行数据、依赖目录和构建产物。
- `entrepreneurship-system` 原始目录缺失，待从旧电脑或备份恢复；不创建空壳 Skill。
- 人际冲突 Skill 最初保留在根目录 `deal-with-jerks(sb)`；2026-10-11 已统一迁入 `skills/communication/deal-with-jerks/`。
- 逐文件 SHA-256 与来源映射保存在 `catalog.json`。不额外归集博客案例录音、客户资料与运行输出；Skill 包自带示例保持原样。

## 2026-10-10 收录范围调整

按用户要求，移除非原创的电商视觉创作 Skill（ecom-details-image）及其归集目录和目录记录；原项目与博客作品保留。当前本轮归集 5 个 Skill。

## 2026-10-10 北京中考顾问本地改造

- 当前仓库副本已改造，原始来源目录未修改；不再标记为逐文件与来源完全一致。
- 前置采集届别、应往届身份、本人户籍、学籍、报考区及报名/报考范围；成绩区分正式中考与模拟考试，并记录计分和排名口径。
- 新增资格协议、分层输出规则和独立行为验收场景；更新 Agent 入口、来源规范和输出模板。
- catalog.json 中该 Skill 的 files 哈希对应当前本地版本；有原始归集记录的文件另存 sourceSha256，新增文件标为本地补充。未同步安装目录、未提交或推送。

## 2026-10-10 README 示例材料补充

按用户要求，从 coding-blog 的来源索引、已展示资产及 `my-volunteer` 来源项目归集 README 示例。材料保存于 `assets/examples/`，逐文件来源与 SHA-256 见 [sources.json](assets/examples/sources.json)。本次包含产品保真三张候选/草稿、飞书两张任务图片、KHJE6075 原始 PDF 与原稿/中文批注图、视频成片及原录音/稿件/字幕、学校信息采集表截图。仅补充展示材料，未修改 Skill 实现或重新执行外部服务。原有“不额外归集运行输出”的范围按本次用户授权扩展到上述明确选取的示例，不进行全量素材归档。

### 产品保真输入素材补充

从 `test-image/原图/` 补入黄色包商品原图及三张模特/场景参考图，逐文件 SHA-256 与黄色包历史任务 manifest 的来源哈希一致。README 按参考图、共用商品图、三张输出顺序缩小展示。具体路径与哈希见 `assets/examples/sources.json`。

## 2026-10-11 许可配置

新增自定义个人非商业学习许可、商业及其他授权申请说明、第三方权利说明，并向六个 Skill 同步独立副本。仅改变本人有权授权内容的新版本许可表达，不将第三方内容改归本人所有，不追溯撤销既有有效许可；分类 Skill 的新增文件哈希同步到 catalog.json。

## 2026-10-11 面向使用者的 README 整理

规格书案例改为仅展示原始截图与中文批注图片；移除仓库展示用 PDF 及其 assets/examples/sources.json 记录，原始来源文件未修改。README 简化内部状态字段、归集过程和维护操作说明，移除不符合当前判断规则的历史冲突案例入口，保留许可、依赖与影响使用的能力边界，并补充持续更新说明。

## 2026-10-11 沟通类 Skill 目录统一

新增 communication（沟通与边界）分类，将根目录 deal-with-jerks(sb) 完整迁移为 skills/communication/deal-with-jerks，Skill 名称仍为 deal-with-jerks。迁移时全部文件逐字节哈希一致；随后仅更新第三方声明中的仓库路径。README、catalog.json 与各 Skill 的第三方说明同步更新。

## 2026-10-11 闲置展示图片清理

删除已被 README 卡通配图替换的学校信息采集表截图，以及飞书手机、笔记本两张旧任务示例图，移除空目录并同步 assets/examples/sources.json。历史归集记录保留用于追溯；原始来源项目未修改。保留 README 当前展示图、产品保真对照图的七张原始素材、Skill 包内示例及独立交付的朋友圈宣传素材。

## 2026-10-12 视频 Skill 同步与改名

将本机 voice-driven-video 改名为 text-or-voice-to-video（文字／录音转动态图解视频），同步最新版文字稿整理、豆包配音、缓存、音轨与字幕时间线检查及测试到仓库同名分类目录。保留仓库许可，并同步到本机独立 Skill；排除缓存、凭据和已安装依赖。旧录音示例目录随新调用名迁移，博客历史来源路径与页面 slug 不改。更新 README、素材来源索引及 catalog 文件哈希；未调用真实豆包服务。

## 2026-10-13 独立电商工作流收录

- 经目录与 catalog 检索确认此前未收录。源工程没有 `SKILL.md`，入口是 `python -m workflow.runner`，因此新增与 `skills/` 平级的 `workflows/`，按 `ecommerce` 分类保存完整工程。
- 从上表来源复制 65 个文件，包含源码、九个测试文件、README、设计文档、依赖清单、公开配置样例和一套八模块模板库。复制文件逐字节保留，SHA-256 与来源一致；未修改原项目、未转换或安装为 Skill。
- 排除约 130MB 历史 `projects/` 任务、`template-inbox/` 收件箱、`.DS_Store`、Python/pytest 缓存、依赖目录和本地 `image-env.yaml`。仅新建空 `projects/.gitkeep`，运行任务继续由工程 `.gitignore` 排除。
- 工程额外补入仓库 LICENSE、COMMERCIAL-LICENSE.md 与专属 THIRD_PARTY_NOTICES.md；源目录未附许可声明，内置八张模板参考图的权利需另行核实，仓库许可仅覆盖本人有权授权的内容。
- 新增 `workflows/README.md` 说明分类、安装和本仓库运行路径；同步根 README、维护约定、第三方说明及 catalog.json 的工作流来源、日期和文件哈希。源工程 README 的原目录命令保持原样，工作流索引给出本仓库替换路径。
- 使用内置 image_gen 更新能力总览为“6 个 Skill · 1 个工作流”，新增模板库电商生图流程配图。提示词、输出来源及哈希见 `assets/readme/IMAGE-SOURCE.md` 和对应提示词文件。配图仅用于能力说明。
- 验证：归集副本的 181 项自带测试通过，CLI 帮助可正常运行；65 个来源文件哈希一致，69 个交付文件全部登记；42 个本地文档链接有效，生成配置、任务输出和缓存的忽略规则生效。未执行工作流的真实生图接口，未提交或推送 Git。

## 2026-10-17 项目开发 LLM Wiki

来源为用户提供的 `/Users/chris/Downloads/llm-wiki.zip`，SHA-256：`4ffac068245c9f187f6d1a320abe6574bb396f6e36ce70dc75f1e791fd89a293`。原包名 `llm-wiki`，改名为 `project-llm-wiki`，归入 `skills/development/`，并安装至 `/Users/chris/.codex/skills/project-llm-wiki`。保留包内模板与脚本，同步修改调用名称；追加仓库许可说明，第三方权利仍按其原授权处理。

## 2026-10-22 视频文字跟踪打码

从 `/Users/chris/.codex/skills/video-text-redactor` 收录到 `skills/video/video-text-redactor`，保留脚本、测试与规则说明，排除运行环境和缓存；原本机目录不修改。追加仓库许可文件，第三方权利按其原授权处理。

## 2026-10-25 故事词汇工作室

- 从用户指定的上表目录归集 `story-vocabulary-studio` 到 `skills/education/`。12 个源文件逐字节保留，包含 SKILL.md、Agent 元数据、三份 Python 脚本、阅读器 HTML/CSS/JavaScript 及四份参考资料；原项目与本机已安装版本不修改。
- 源包未附独立许可文件；补入仓库 LICENSE、COMMERCIAL-LICENSE.md、专属 THIRD_PARTY_NOTICES.md 和使用 README，共 16 个文件。逐文件 SHA-256、来源和本地补充标记见 catalog.json。
- 收录范围仅为指定 Skill，不额外归集原项目的考试词表、研究原始资料、历史故事样包、运行输出、配音、凭证或测试工程。
- README 补充教育类目录条目、如何选择、能力介绍、调用示例、依赖及使用边界。修正此前遗留的总计为 9 个 Skill、1 个独立工作流；新增可维护的 SVG 能力总览，保留历史 AI 配图及其来源记录；新 Skill 的流程用 Mermaid 说明。
- 检查脚本入口、Python 与 JavaScript 语法、输入模板的未完成状态、离线配音 dry-run、草稿渲染和未审校内容的打包阻断；仅使用临时结构草稿，不盖语义审批章，不调用真实豆包服务，不将检查用网页作为学习成品。

## 2026-10-25 项目主线导读（改名收录）

- 从用户指定的 `/Users/chris/.codex/skills/project-xray` 完整复制 4 个源文件，归入 `skills/development/project-flow-guide/`，中文名称为“项目主线导读”。本次用户明确要求改名，作为维护约定中通常保留原名规则的例外；原本机目录与安装名称不修改。
- SKILL.md 的 frontmatter 名称与标题、agents/openai.yaml 的显示标题及默认 `$project-flow-guide` 调用名同步替换；其余方法内容不变，两份参考文档逐字节保留。catalog.json 分别保存原始 sourceSha256、当前 sha256 与改名说明。
- 源包未附独立许可文件，按仓库约定补入 LICENSE、COMMERCIAL-LICENSE.md 与专属 THIRD_PARTY_NOTICES.md；共收录 7 个文件，许可仅覆盖本人有权授权的部分。
- 同步 README 的用途表、选择指引、详细介绍、示例与流程图，更新 catalog 和第三方来源说明；SVG 能力总览更新为 10 个 Skill、1 个独立工作流。
- 此前检查发现的“公司”“集成”等通用表述按用户要求保留；不修改既有 Skill 内容，不自动安装、提交或推送。

## 2026-10-25 README 插画与流程显示修复

- 按用户反馈，将 README 顶部 SVG 文字卡片改回内置 image_gen 生成的插画合集，保留全部 10 个 Skill 和 1 个独立工作流，沿用历史纸感插画风格。输出、提示词及配图来源见 assets/readme/IMAGE-SOURCE.md。
- 预览器未能显示的五个 Mermaid 流程代码块改为预渲染 PNG；保留对应 `.mmd` 源文件和可选渲染脚本，补一张项目开发 LLM Wiki 的查询、执行、验证、回流流程图。Mermaid 解析与浏览器渲染均已运行，README 直接显示 PNG。
- 核对 `skills/development/project-llm-wiki/` 与 `/Users/chris/.codex/skills/project-llm-wiki/`，22 个文件逐字节一致，无缺失或差异；收录来源与 Skill 内容保持原记录，不因展示调整覆盖源码。README 补充选择指引、交付与流程，说明其与项目主线导读的区别。

## 2026-10-25 README 场景插画调整

- 按用户进一步反馈，撤下上一阶段的方框箭头图及临时 Mermaid 渲染文件。此前解决的是显示问题，用户要求的视觉表达改为有角色、具体场景与动作的生图插画。
- 使用内置 image_gen 分别生成项目开发 LLM Wiki 的知识工坊、故事词汇工作室的阅读场景、项目主线导读的项目探索景观；替换对应三张配图。视频与电商保留已有生动插画，移除重复的方框流程汇总。提示词、来源与哈希见 assets/readme/IMAGE-SOURCE.md。
- 将 README 配图偏好写入 MAINTENANCE.md：使用场景插画辅助理解，不用 Mermaid、方框箭头或 SVG 文字卡片充当能力配图。此轮仅调整展示及维护说明，Skill 内容与已归集文件哈希保持不变。

## 2026-10-25 视频打码配图与按用途区分画风

- 为 `video-text-redactor` 补充电影感剪辑室概念图，展示视频文字跟踪、移动与缩放中的遮挡、原声及成片复查；仅为能力展示，不是实际软件界面或匿名化结果证明。
- 将项目开发 LLM Wiki 的详情配图改为现代工程资料工作台的写实画面；故事词汇保留绘本风、项目导读保留探索地图风，避免所有 Skill 共用同一画风和角色。合集继续承担统一目录展示。
- 使用内置 image_gen 生成，提示词与图像来源记入 assets/readme/IMAGE-SOURCE.md；维护约定补充按 Skill 用途选画风的规则。此轮不修改 Skill 源码、依赖或内容哈希。

## 2026-10-26 电商视频爆款拆解

- 从用户指定的 my-workflow 项目内完整收录 `ecommerce/video-breakdown/skills/ecommerce-video-breakdown` 到 `skills/ecommerce/`，沿用原名称。初次收录时30个源文件逐字节保留，包含技能入口、Agent元数据、脚本、参考资料和公开运行配置示例；当前媒体取材部分已按下方2026-10-27记录替换。
- 排除 Python 缓存；不归集原项目 workspace、真实视频/图片/字幕、博主数据、业务 Excel、运行配置、凭据、Cookie、已安装依赖、模型和验收产物，不修改来源项目或本机已安装技能。
- 源包未附独立许可文件，补入仓库 LICENSE、COMMERCIAL-LICENSE.md 和专属 THIRD_PARTY_NOTICES.md，初次交付共33个文件。当前文件及修改相对于来源版本的SHA-256、本地补充标记见catalog.json。
- 更新 README 的目录、选择指引、用途、交付、运行依赖与边界；使用内置 image_gen 为新增 Skill 补充视频研究室概念图，并更新 11 个 Skill、1 个独立工作流的总览。图像提示词、输出来源与哈希另记 assets/readme/IMAGE-SOURCE.md。
- 验证：隔离复制环境下 26 项独立运行、迁移、打包、Excel 与交付测试通过；14 个 Python 文件语法、Node 脚本语法和 Skill 元数据检查通过；30 个来源文件哈希一致，33 个交付文件全部登记，83 个本地文档链接有效；两张生成配图已查看并核对标题、数量与场景。
- 本轮只归集、整理与本地验证，不自动安装、不提交或推送，不调用视频平台、下载媒体或模型。

## 2026-10-27 视频归档与按参考换商品套图

- 从本机已安装目录收录 `media-urls-batch-archive` 到 `skills/video/`、`ecommerce-reference-product-swap` 到 `skills/ecommerce/`，调用名称保持不变。核对可用的博客 PROJECT_SOURCES.md，未发现这两个准确名称的来源记录，使用用户本次指定的本机 Skill 作为来源。
- 视频归档完整保留 12 个来源文件并补入两份仓库许可文件，共 14 个文件。来源版本已包含本技能的解析流程、批处理、环境初始化、依赖清单、配置示例、迁移说明与 24 项离线测试；开发范围及通用工具依赖声明逐字节保留。
- 按参考换商品完整保留九个来源文件：SKILL.md、Agent 元数据、六份参考说明与独立导出脚本；补入三份许可与权利说明，共 12 个文件。未收录商品图、模特图、用户参考、品牌素材、历史案例或默认模板库。
- 两个来源目录保持不变，来源文件与仓库副本逐字节校验；逐文件 SHA-256、sourceSha256 和补充文件来源记入 catalog.json。未复制环境、模型、缓存、凭据或真实任务输出，未修改已有 Skill。
- README 目录、选择指引与两项详细介绍同步更新，能力总览调整为 13 个 Skill、1 个独立工作流；配图按维护约定使用内置 image_gen，完整提示词与哈希见 assets/readme/IMAGE-SOURCE.md。
- 验证：视频归档副本的 24 项离线测试通过；换商品导出器完成主图、SKU、详情与长图像素一致、已有图集保护和无效输入拒绝共八项检查。21 个来源文件保持不变，catalog 中 381 个文件哈希有效，90 个本地文档链接可解析；两个 Skill 入口格式校验与 git diff --check 通过。未执行真实客户商品生图或视频网站任务。
- 本次仅收录与文档整理，不重复安装，不自动提交或推送；此前电商视频爆款拆解的待提交收录改动保持保留。

## 2026-10-27 电商视频取材模块更新

- 以随包的 scripts/public_media.py 和 scripts/subtitle_formats.py 替换旧取材实现，删除被替换的源码目录及函数快照清单；将解析参考文档改为 references/media-acquisition.md，说明当前取材顺序、身份约束和缓存规则。当前文件清单仅登记随包交付的实现。
- 保持链接输入、匿名分享页、完整字幕、本地模型、关键帧、身份检查和工作区归档协议，后续创作、报告及七表Excel流程沿用原契约。字幕格式读取代码随包提供，不引入其它Skill依赖。
- 更新README、运行说明、包内及仓库权利说明与catalog；分发ZIP补齐三份许可及权利文件。本地faster-whisper/PyAV按验证过的兼容范围约束；平台协议与实际工具依赖如实保留。
- 来源项目、本机安装目录和其它Skill不随本次修改；原有工作区不要求重建。当前文件哈希与原来源哈希分别登记，不再声称当前版本仍为30个源文件逐字节复制。
- 验证：旧版108项离线测试先建立对照；替换后91项原流程、6项稳定适配接口及19项随包取材/取消测试通过。使用已有本地模型和本地生成视频，实测转录、6帧、4.48秒真实时长、缓存及本地HTTP下载通过；任务取消与工具超时不残留下载子进程。三平台响应以固定fixture验证，未声称真实平台或Windows/Linux实机全部通过。
- 全库复查：相关项目名称及旧解析文件标识未命中，原有24个完全相同的函数实现已替换；当前389个交付文件哈希、文档相对链接及独立ZIP（含许可）校验通过。未提交或推送。

## 2026-11-03 B站视频解析工具箱收录

- 来源为用户提供的 `bilibili-toolkit.zip`，ZIP SHA-256：`fb9ab32ec379a0b75cfca2c2ec90a097d04fba6a5850ac3fbe1486c668c7793a`；完整路径见上表及 catalog.json。可用博客 PROJECT_SOURCES.md 未检索到该准确名称，以本次附件为准。
- 六个源文件逐字节保留：SKILL.md、四份 Python 脚本和 UP 主全部视频参考手册；归入 skills/video/bilibili-toolkit，不改原名，不执行附件内的任务指令。
- 原包未附独立许可或作者信息，补入两份仓库许可与专属 THIRD_PARTY_NOTICES.md，共九个文件；许可只覆盖有权授权的部分。来源与当前文件 SHA-256 分别记入 catalog.json。
- README 补充用途、选择指引、交付、Windows 示例与其它平台路径说明，注明额外浏览器技能、未交付的 WBI 函数及平台可用性未实测。未修改原 Skill 的经验性表述，不将其作为当前验证结论。
- 更新16个Skill、1个独立工作流的总览及视频研究桌配图；使用内置 image_gen，提示词、原始输出与哈希记入 assets/readme/IMAGE-SOURCE.md 和对应提示词文件。
- 仅收录与静态验证，不安装依赖或Skill，不下载媒体或模型，不执行浏览器、登录、转写或真实B站接口，不修改原ZIP，不提交或推送Git。仓库已有未提交修改保留。

### 2026-11-03 单独提交说明

本提交仅增加B站工具箱，远端目录为14个Skill、1个独立工作流；生成时本地16项总览包含另外两项尚未提交的Skill，因此仅保存该图与提示词作为制作记录，不替换远端README顶部的历史13项总览。工作区中其余Skill及后续收录保持未提交状态。用户已明确授权本次提交与推送，前述“未提交或推送”描述的是初次收录时的状态。
