# 报告契约与证据填写

以 `prepare` 生成的文件为唯一模板来源，不另建一份会漂移的 JSON Schema。保留所有14个视频模块和6个博主模块；没有材料的模块写明“缺少什么／因此不能判断什么”，不要删除模块或填造数据。命令用法以 `scripts/video_breakdown.py --help` 和各子命令帮助为准。

## 文件与状态

- `analysis/tasks.json`：全部视频任务、分组和完整来源路径。不得把摘录当全文。
- `analyses/<video-key>.json`：逐条分析。保留 `schema_version: 1`、`video_key` 和 `source_hash`；完成阅读、填写和自查后，才把 `status` 从 `pending` 改为 `complete`。
- `analyses/creators/<creator-key>.json`：博主综合。保留 `creator_key`、`source_hashes` 和全部 `covered_video_keys`。来源变化后应重新阅读受影响的视频，不手工改哈希以绕过过期检查。
- `validate`：检查来源、引用、模块和覆盖；它不能证明分析合理、画面真的被看过或因果成立，Codex仍须审阅内容。
- `render`：根据当前工作区生成 Markdown、JSON、HTML，保留未完成和缺证状态；渲染成功不等于分析完成。
- 完成新版交付需 `creation` 创作包，契约与审阅见 [creation-transfer.md](creation-transfer.md)。结构校验不评价创意效果；缺少机制、购买说服、商品核验、逐镜头脚本和实验的旧报告保留为待升级资料。
- `analysis_mode`：`speech`／`visual`／`mixed`，必须匹配归档。口播质量、标题、正文和来源时间都纳入指纹；审查或正文变化后旧结论需复核。

`source_hash` 是原始证据包指纹，包含正文、来源描述、指标、评论、时间轴与关键帧实际内容；不只是全文哈希。`transcript_hash` 单独记录正文版本。已有分析不会因重新准备而被覆盖，证据变化后应重新阅读并更新分析，旧结论会被标记待复核。

## 单条报告14模块

每个模块为 `{summary, findings}`。`summary` 简要说明该维度的结论和限制；实质性判断写入 `findings` 并引用证据，不能在摘要里藏入无出处的新结论。

| 模块键 | 内容与必要限制 |
|---|---|
| `source_quality` | 平台、博主身份、视频来源、发布时间、时长、提取方式、完整性、原稿与清理稿差异、缺失项 |
| `performance` | 真实可得指标、数据来源与观察时间、用户爆款标签、可比样本资格；没有数据则待核验 |
| `product_audience` | 品类、商品、价格、人群、场景、购买任务和决策阶段；推断明确标记 |
| `title_cover` | 标题／封面承诺、利益点、好奇缺口、焦点和正文兑现；未查看封面不判断画面 |
| `hook` | 开场原话、实际画面、触发对象、钩子类型、价值承诺与兑现位置 |
| `structure` | 实际段落与顺序、各段功能、商品融入、演示证明和行动引导，不强套结构 |
| `pacing` | 信息推进、悬念、转折、重复、冗余；只有原始时间轴才能分析秒级节点与占比 |
| `selling_points` | 特征、利益、场景、证据的对应，主次与表达方式，讲述／展示／证明的差异 |
| `pain_pleasure` | 痛点、爽点、购买顾虑、触发位置；区分博主提出、用户反馈和分析推断 |
| `trust_proof` | 实测、对照、细节、经验、社会证明、限制；区分口述、演示现象和已核验性能 |
| `audiovisual` | 亲自检查过的人物、场景、镜头、字幕、声音配合；静态帧不能证明连续剪辑节奏 |
| `conversion` | 优惠、价格锚点、顾虑处理、风险降低、适用范围、下一步行动与入口 |
| `comments` | 已提供评论的高频疑问、质疑、意向和落差，注明采样范围；缺失则明确未提供 |
| `hypotheses_reuse` | 观察事实、机制假设、表现关联、反例、替代解释、迁移条件与实验建议 |

`findings` 的每项包含：

- `text`：一个可评估的判断，不把事实、心理推断和效果预测混成一句。
- `kind`：`observation` 或 `hypothesis`。
- `confidence`：`high`、`medium` 或 `low`，指证据把握程度。
- `evidence_ids`：引用本条视频 `evidence` 中存在的ID。假设也要有依据，但证据存在不代表它已证明假设。

## 证据

证据ID在单条分析中唯一。原文按原始换行生成 `p0001` 等段落ID；不要改段落编号或伪造时间。

| `type` | 定位字段 | 要求 |
|---|---|---|
| `transcript` | `paragraph_id`、`quote` | 引文必须真实出现在该段原文；保留数值、否定词、条件和说话者含义 |
| `title` | `quote` | 必须出自真实标题，不当作视频开场原话 |
| `caption` | `quote` | 出自 `note_caption`，归档含 `caption_source` 和 `caption_observed_at`；发布者正文不是口播或评论 |
| `frame` | `frame_id`、`inspection_note` | 先亲自查看图片，记录真正可见的内容；时间戳继承归档记录，不能猜 |
| `clip` | `start,end,inspection_note,channels:["visual"]` | 已关联本地原视频内实际检查过的区间；范围在实际时长内，记录静音视觉检查，不含音轨判断 |
| `metric` | `metric_key` | 指向元数据里实际存在、带来源与观察时间的指标，不引用外推数字 |
| `comment` | `comment_id`、`quote` | 指向真实导入评论，短引文应来自该评论；注明反馈并非完整用户总体 |

以下是**合成填写片段**，用于展示引用关系，不是可直接提交的完整报告：

`transcript` 仅在 `narration_evidence_allowed=true` 时有效。画面报告至少引用一张实际查看的 `frame`，可以没有口播证据。标题和正文不能代替看图；不能仅修改分析方式或完成标记绕过检查。见 [质量分流](quality-routing.md)。

```json
{
  "evidence": [
    {"id": "e1", "type": "transcript", "paragraph_id": "p0001", "quote": "包包能装下电脑"}
  ],
  "modules": {
    "selling_points": {
      "summary": "视频以容量利益介绍商品，尚无可检查的装载演示。",
      "findings": [
        {"text": "博主声称能装电脑；这属于口述卖点，不能作为已验证容量。", "kind": "observation", "confidence": "high", "evidence_ids": ["e1"]}
      ]
    }
  }
}
```

用户提供的指标与评论可以随 `metadata.json` 导入，形状如下；实际字段缺失时省略，不填零：

```json
{
  "metrics": {
    "views": {"value": 123, "source": "用户导出的数据文件名", "observed_at": "2026-10-18T10:00:00+08:00"}
  },
  "comments": [
    {"id": "c1", "text": "雨天用会打湿吗？", "source": "用户导出的评论文件名", "observed_at": "2026-10-18T10:00:00+08:00"}
  ]
}
```

## 博主综合6模块

`covered_video_keys` 必须覆盖该博主所有 `ready` 视频。其他状态在总体覆盖清单中交代；不把待确认归属的视频强行纳入这个博主。

| 模块键 | 内容 |
|---|---|
| `profile` | 人设、目标人群、品类、内容类型、表达风格和转化路径 |
| `structure_map` | 钩子、段落功能、卖点呈现、证明和行动引导的组合及覆盖情况 |
| `pain_pleasure_map` | 按人群、场景、品类归类，区分来源并列分母 |
| `performance_comparison` | 同口径样本的表现对照；没有对照就标明不能验证原因 |
| `boundaries` | 反例、样本选择限制、投放未知、商品差异、时间因素和不可迁移部分 |
| `experiments` | 复用优先级、需改变的变量、制作条件、观察指标和补证清单 |

每个综合 `finding` 除逐条字段外还需 `video_keys`，以区分它讨论了哪些实际样本。模式卡 `patterns` 每项包含：

- `name`、`mechanism`：模式及其可能作用，假设不能写成已证实因果。
- `support_video_keys`、`counterexample_video_keys`：去重后的支持与反例视频。
- `evidence_refs`：跨视频引用 `{video_key, evidence_id}`，指向已通过校验的逐条证据。
- `frequency`〔使用频次时〕：`support_count` 为去重后的支持视频数，`denominator` 固定为该博主全部有效分析视频数。若在正文补充分组频次，明确列出分组及其有效分母，不能用分组分母填写这里的整体频次字段。
- `boundaries`、`experiment`：迁移条件、反例解释与下一步验证。

## 可复用元素卡

视频 `elements` 每项包含 `id`、`name`、`problem`、`template`、`variables`、`evidence_ids`、`applies_to`、`excludes`、`materials`、`experiment`。综合报告用 `evidence_refs` 追溯跨视频来源。

报告中的完整元素卡还应说明原始案例、证据位置、覆盖频次、表现关联和反例；从已归档证据与模式中引用这些信息，不重新编造一组频次。模板使用“人群／场景／问题／利益／证明”等变量，提炼结构而不是整段复刻口播。没有适用条件和验证方法的口号不算完成的元素卡。
