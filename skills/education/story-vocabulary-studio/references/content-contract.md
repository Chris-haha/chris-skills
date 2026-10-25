# 内容契约 v1

Python 3.10+，仅标准库。学习网页无需安装依赖或启动服务，解压后直接打开。脚本从自身位置找到assets，不依赖跨项目导入。

`book.json`顶层：`schema_version:1`、`book`、`vocabulary`、`chapters`、可选`editorial_review`。可从book-template.json复制结构再填完整内容；模板本身不通过成品校验。

- `book`：book_id、title、subtitle、audience、vocabulary_source、characters、chapter_min_chars、chapter_max_chars。长度以移除词条标记后的中文字符计；示例600–1000，可调整。`new_words_per_chapter`默认8，`review_words_per_chapter`默认4（第一章为0）；不同数量需显式设置这两个值。`level_label`是可选简短学习范围标签。
- `vocabulary[]`：稳定word_id（小写字母、数字、连字符）、lemma、pos、ipa、sense_zh、forms、explanation、source、source_version。forms必须列出原形和本书实际使用的合理变化；不把不同词性或派生词偷算进同一义项。可选meaning_answers用于中文判分同义答案。
- `chapters[]`：稳定chapter_id、title、summary、new_word_ids、review_word_ids、paragraphs、questions。新词不能跨章重复引入；复现词必须先前出现。
- `paragraphs[]`：paragraph_id、mixed、english。mixed中用`[[word_id|sense_zh]]`明确标注；标注义须与词表一致。english用自然英语，覆盖本章计划词及允许的词形。
- `questions[]`：question_id、prompt、options（数组）、answer_index（从0开始）、explanation、evidence_paragraph_id。题目要能在本章来源段落找到答案。

网页自动从同一mixed生成中文嵌词阅读、词义回忆和拼写练习，从词条与来源句生成词表和讲解。英文段落单独保存，不做机器逐句替换。出现位置用chapter_id/paragraph_id和显式标记追踪；练习答案来自词条sense_zh/lemma，理解题答案来自answer_index。

CSV列：`word_id,lemma,pos,ipa,sense_zh,forms,explanation,source,source_version`，forms用`|`连接。CSV为选词输入及表格交换格式，Codex将其合并进JSON；CLI直接接收JSON，不会自动写故事。

## 语义审校门禁

先validate取得`content_hash`。人工或Codex逐句读本版本，记录词性/义项/搭配、剧情连续性、答案一致性与明确来源。只有确实审完并处理问题后才添加：

```json
"editorial_review": {
  "status": "approved",
  "reviewer": "审校者和方式",
  "reviewed_content_sha256": "validate打印的content_hash",
  "findings": []
}
```

哈希覆盖除editorial_review外的全部内容，改稿后旧审批自动失效。`findings`非空时不能发布。结构valid不等于语义approved；脚本不能判断单词搭配是否自然。

## 产物与状态

render输出：index.html（全部内容/CSS/JS内嵌）、book.json、vocabulary.csv、quality-report.json、audio-manifest.json。

audio输出：24词示例对应的word文件、各段缓存和章节WAV，以及真实采样数算出的时长/cues。数量跟随实际输入，不写死24或3。缺音频/内容改动时页面不提供播放入口。

package默认要求内容通过及音频ready；用户允许音频待做时显式--allow-draft。ZIP含reader/、sample/、skill/story-vocabulary-studio/、PACKAGE-STATUS.json及README.txt，不含原始竞品素材、缓存、凭证。不要直接递归压缩项目根目录。

## 可选三步路径与新语境回顾

`book.learning_path`省略时沿用旧阅读器；启用时固定为`["mixed","meaning","answers"]`，显示可点击三步、核对后看待巩固词（含未答）和结束本章。六种模式仍可自由进入，不要求全部刷完。启用书籍的词义、拼写与理解题作答以及结束标记仅保留在当前页面内存，刷新清空；不写localStorage或自动评定长期掌握。

可选顶层`review_prompts[]`必须逐个覆盖全部vocabulary，不缺、不重复。每条含`word_id`、与该词`provenance.sense_id`一致的`sense_id`、包含允许词形的英文`sentence`、人工审校的`explanation_zh`。sentence须为新语境，不能直接复制已有故事整句。检查结构不代表语义批准；仍须逐句核对词性、义项、词形、搭配并绑定更新后的内容哈希。

启用后词义回忆可切换“故事语境/新语境回顾”，两套作答分别保留。回顾词不增加独立目标词或剧情复现数。新句不可与延迟测验复用同一句，否则测验不再是独立的新语境题。新语境回顾不是自动安排的隔天/一周复习；真实学习时长和记忆结果须实际采集。

## 可选章节朗读范围

book.chapter_narration是可选布尔值，省略为true；false取消章节英文朗读，保留英文故事和单词点读。计划、生成、完整性检查与打包仅要求词级音频，取消的章节不进入缺失清单；页面无章节播放器、进度、倍速或段落播放按钮。字段参与内容哈希，变更须明确审查并绑定当前哈希。
