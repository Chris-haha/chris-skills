---
name: story-vocabulary-studio
description: 为指定英语词表创作连续原创故事，生成中英阅读、词义回忆、拼写练习、答案、豆包音频与离线网页；用于新建故事学习包、续章、改稿和独立打包。
---

# 故事词汇工作室

先沿用用户已经确认的受众、词表、故事设定和配音范围。Codex负责写作和逐义项审校，脚本负责结构、覆盖、音频缓存与打包；脚本不能替代英语语义判断。

## 新建与续写

读 [内容契约](references/content-contract.md)，用 [输入模板](references/book-template.json) 建立 `book.json`。CSV按 `word_id` 合并词条，注明真实词表出处、版本；自选示例不能包装成完整考试词表。

若要求完整考试词库，先按[词表准入复核](references/exam-wordlist-review.md)核对原件、版本与逐项验收状态；未通过的候选、部分提取或预览文件不得用作正式考试词库，也不得靠补凑总数过关。

先安排每章新词、旧词复现、情节及理解题，再逐段写 `mixed` 与自然英语 `english`。中文只在明确位置用 `[[word_id|sense_zh]]` 嵌词；同一词ID代表一个词性和义项。英语可用词条 `forms` 中的合理词形。六种材料由同一内容源生成，避免分别改稿产生答案冲突。

续写时保留既有ID，为新章新增ID；复现词必须已在更早章节引入。章节数、每章词数由学习目标决定，三章样包只是示例。不要把情节复述等同于逐句翻译，英语须自然且保留主要线索。

## 校验与改稿

以下命令中的 `SKILL_DIR` 指当前 Skill 所在目录，工作文件放到用户的项目目录；不要依赖本机其他项目路径。

```sh
python3 "$SKILL_DIR/scripts/workflow.py" validate book.json --output-dir output
python3 "$SKILL_DIR/scripts/workflow.py" audio book.json --output-dir output --dry-run
python3 "$SKILL_DIR/scripts/workflow.py" render book.json --output-dir output
```

改一章先调整源数据和题目，再读受影响的中英正文，核对词性、义项、搭配、剧情、答案。覆盖缺词须修复；合理的非计划词自然出现不应算计划复现。读完并解决问题后，按内容契约绑定当前哈希的审校记录；不得为通过门禁直接自动盖章。

文本或声线变化会使音频失效。重新配音按文本与声线复用校验缓存；未变化的片段不重复请求。不要删除缓存来代替定位问题。

## 配音与交付

需要配音时读 [音频说明](references/audio.md)。真实合成需要有效 `DOUBAO_TTS_API_KEY` 与音色权限；不把凭证写进JSON或交付包，不用系统朗读、静音或测试波形冒充正式音频。

```sh
python3 "$SKILL_DIR/scripts/workflow.py" audio book.json --output-dir output
python3 "$SKILL_DIR/scripts/workflow.py" render book.json --output-dir output
python3 "$SKILL_DIR/scripts/workflow.py" package book.json --output-dir output --output delivery.zip
```

正式音频须逐个核听并检查段落定位；成功合成仅证明获得可解码音频。用户明确延后配音时，用 `package ... --allow-draft` 生成标注配音待做的包，说明24词/章节声音尚未交付。缺凭证时报告实际状态，继续完成独立可做的内容。

打开实际 `output/index.html` 操作章节、六种模式、词卡、练习及音频状态，检查桌面和手机并保存查看截图。解压ZIP到新目录重复检查，确认相对路径独立可用。交付链接、报告及未完成项，不把草稿宣布为含真实音频的成品。

## 已确认的三步学习路径

需要直接引导学习时设置book.learning_path为mixed→meaning→answers，保留六模式自由切换。reader按本次判分集中展示待巩固词（含未答）；结束标记不当作记住。可增加完整覆盖词表、逐词绑定同一sense_id的新语境review_prompts；按内容契约逐句审校，不复制延迟测验句子或把回顾算新增词。作答只保留在当前页面会话，刷新清空，不以此声称有长期学习档案或自动间隔复习。

看解释后可只重练上次错词和未答词，保持原题型/语境；重练初始留空，与整章草稿分别保留。本轮分数按重练题数显示，不覆盖整章首次作答，不表示长期掌握；刷新清空。旧输入不启用该流程。

用户取消章节朗读时，设置book.chapter_narration=false，保留英文故事阅读和单词点读。阅读器不显示章节播放器或段落播放入口；音频计划/验收/打包仅计算单词，不把取消的章节音频列为待做。省略该字段保留旧输入行为。
