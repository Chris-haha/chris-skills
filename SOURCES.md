# 来源与归集记录

归集日期：2026-10-10。原始项目保持不变；本仓库保存独立副本。

| Skill | 原始目录 | 归集目录 |
| --- | --- | --- |
| preserving-product-fidelity | `/Volumes/Samsung_T5/code/test-image/.codex/skills/preserving-product-fidelity` | `skills/ecommerce/preserving-product-fidelity` |
| feishu-ecommerce-workflow | `/Volumes/Samsung_T5/code/my-workflow/E-commerce/codex_ecommerce_workflow_analysis_20260720/mvp-workflow/skills/feishu-ecommerce-workflow` | `skills/ecommerce/feishu-ecommerce-workflow` |
| garment-spec-cn-annotation | `/Volumes/Samsung_T5/macmini/code/coding-blog/project-sources/skills/garment-spec-cn-annotation` | `skills/ecommerce/garment-spec-cn-annotation` |
| beijing-zhongkao-admissions-advisor | `/Volumes/Samsung_T5/code/my-volunteer/skills/beijing-zhongkao-admissions-advisor` | `skills/education/beijing-zhongkao-admissions-advisor` |
| text-or-voice-to-video | `/Users/chris/.codex/skills/text-or-voice-to-video` | `skills/video/text-or-voice-to-video` |

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
