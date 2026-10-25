# 故事词汇工作室

`story-vocabulary-studio` 将指定英语词表编入连续原创故事，生成可离线打开的阅读与练习网页，以及内容、词表、质检报告和可选真实音频。完整执行规则见 [SKILL.md](SKILL.md)。

## 适用场景与交付

- 根据词表新建故事学习包，或沿用已有角色、剧情与词条 ID 续章、改稿。
- 六种模式：故事阅读、本章词表、词义回忆、拼写练习、英文故事、答案讲解。
- 可选“读故事 → 词义回忆 → 看解释”三步路径、新语境回顾和错词／未答词重练；当前作答保留在页面会话中，刷新清空。
- 豆包单词点读与可选章节英文朗读；取消章节朗读时保留英文阅读和单词点读。
- 交付 `index.html`、`book.json`、`vocabulary.csv`、`quality-report.json`、`audio-manifest.json`；按实际状态交付 WAV 音频与包含阅读器、源内容及 Skill 的 ZIP。

## 安装与调用

将本目录完整复制到目标 Agent 的 skills 目录，保留脚本、参考文件、阅读器模板及许可文件。分类目录 `education/` 只用于本仓库管理，宿主是否递归发现 Skill 以其规则为准。

> 使用 story-vocabulary-studio，按我提供的词表和学习水平创作连续原创故事，保留中英阅读、词义回忆、拼写和答案讲解。先完成内容与逐义项审校，暂缓配音，交付明确标注音频待做的离线学习包。

> 使用 story-vocabulary-studio，继续现有故事的下一章，保留角色、已学词 ID 和义项，安排旧词复现，更新练习与答案；豆包音频只重新生成变化的片段。

## 运行依赖与命令

脚本需要 Python 3.10+，仅使用标准库。学习网页无需安装依赖或启动服务。真实合成需要有效的 `DOUBAO_TTS_API_KEY` 和音色权限；具体说明见 [audio.md](references/audio.md)，不要把凭证写入内容或交付包。

从仓库根目录将输入模板复制到**自己的工作目录**，参考 [content-contract.md](references/content-contract.md) 完整填写内容。模板仅展示结构，本身不通过成品校验；脚本不会自动写故事，CSV 也需由 Agent 或人工合并为 JSON。

以下命令从仓库根目录执行，`/path/to/book.json` 与输出路径请换为自己的工作目录：

```bash
python3 skills/education/story-vocabulary-studio/scripts/workflow.py --help
python3 skills/education/story-vocabulary-studio/scripts/workflow.py validate /path/to/book.json --output-dir /path/to/output
python3 skills/education/story-vocabulary-studio/scripts/workflow.py audio /path/to/book.json --output-dir /path/to/output --dry-run
python3 skills/education/story-vocabulary-studio/scripts/workflow.py render /path/to/book.json --output-dir /path/to/output
```

`audio --dry-run` 仅检查计划与缓存，不访问配音服务。实际合成时移除 `--dry-run`；内容、词义及音频均完成审查后执行：

```bash
python3 skills/education/story-vocabulary-studio/scripts/workflow.py package /path/to/book.json --output-dir /path/to/output --output /path/to/delivery.zip
```

明确允许音频待做时追加 `--allow-draft`。草稿打包仍要求内容通过结构校验，并具有与当前内容哈希绑定的真实审校记录。校验命令成功不能替代逐句审校；可解码音频不能替代核听。

## 使用边界

原创故事与英语语义审校由 Agent 或人工完成，脚本负责结构、词汇覆盖、缓存、渲染与打包。词表应注明真实来源和版本；完整考试词库需按 [exam-wordlist-review.md](references/exam-wordlist-review.md) 验收，自选示例不得充当官方完整词表。

本目录不包含完整考试词库、正式学习样包或已合成音频。页面会话记录不代表长期学习档案、自动间隔复习或已证实的记忆效果。交付前需在浏览器检查桌面与手机布局、实际交互和音频，再解压 ZIP 复查独立运行。

## 来源与许可

2026-10-25 从用户指定的 `my-workflow/education/story-vocabulary-research/skills/story-vocabulary-studio` 归集，12 个源文件保持原样。此 README、许可与第三方说明为仓库补充；来源与 SHA-256 见根目录 [SOURCES.md](../../../SOURCES.md) 和 [catalog.json](../../../catalog.json)。

许可见 [LICENSE](LICENSE)、[COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
