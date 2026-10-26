# 从拆解到商品视频创作

交付目标：编导能据此执行条件化拍摄，不停在风格标签或一句模板；也不把创意假设当作已验证销量公式。

## 从具体信息推进寻找机制

先问观众开始知道什么、画面提供什么新信息、形成哪个问题、何时回应、商品承担什么作用。把“有反差”展开成“熟悉商品出现在陌生位置→观众辨认用途→成品回应→尚缺操作与适配证明”。每一步保留出处，心理和效果写假设。

分开吸引注意、帮助考虑、推动行动。美学展示让人喜欢，不自动解释为什么买这一款。指出原片未覆盖的购买问题，再提出我方该补拍什么、补什么条件；不能虚构原片有演示、有CTA或有成交。

迁移结构变量，不照搬原句和外观。说明保留什么、替换什么、适合哪个商品条件、至少验证什么、条件不成立如何替代。例如戒指不适合编发时，迁移“同一饰物多种真实搭配”，不能硬造发饰用途。

## 原片与新设计分开

有本地原视频时检查全片视觉推进，必要时借助密集序列；实际没听音就不写听音结论。少量抽帧只能描述抽样点，不能虚构连续动作、剪辑切点、平均镜头长度。

`source_beats` 描述原片信息推进，定位到原文、图片或实际检查区间，记录动作、观众问题、新信息及引用；区间不是自动确定的镜头边界。拟拍脚本独立使用 `timeline_basis: proposed`，秒段都是新创作建议，不能冒充原片结构或高留存证据。

## 我方商品未知也继续创作

没有我方SKU时：`product_status: not_provided`、`readiness: conditional_brief`、`script.shoot_status: conditional`。照样给目标品类、可执行镜头／文案、明确占位字段、补证方法和失败时的替代路线，不用缺信息代替创作。

属性、尺寸、价格、使用时长、性能和购买入口来自我方资料。原博主说蜜蜡、有香味、戴半年，不能移成我方卖点或经历。未核实参数用 `[实测尺寸]` 等占位，或改写成不含该承诺的文案。只有用户提供SKU、必要字段已核实并有出处，才能标记 `sku_ready`／`ready`。

## creation 数据契约

以 `scripts/creation.py::template()` 和 `prepare` 新建分析为准。旧分析保留，但缺创作包不算完成新版交付。工具检查关系和完整性，不用字数或机械条数衡量深度。

| 字段 | 必需内容 |
|---|---|
| `version` | 当前1，独立于归档schema_version |
| `verdict` | `transfer_value,sales_gap,evidence_ids`：学什么、距购买缺什么 |
| `source_beats` | 每项 `locator,action,viewer_question,new_information,evidence_ids` |
| `mechanisms` | 每项 `id,name,observation,evidence_ids,viewer_task,interpretation,commercial_role,transfer_rule,conditions,counterfactual,test`。commercial_role为attention／consideration／conversion；反事实假设不能冒充已观察反例 |
| `purchase_bridge` | 每项 `objection,evidence_ids,recommended_shot,conditional_copy,release_condition`。问题可为推断，不能冒充真实评论 |
| `product_requirements` | 每项 `field,status,needed_for,verification`；status为unknown／verified，verified须有 `evidence` 指向我方资料 |
| `script` | `title,objective,format,duration_seconds,timeline_basis,shoot_status,beats,cta,materials,claim_checks` |
| `script.beats` | 每项 `start,end,stage,shot,spoken_text,on_screen_text,viewer_job,selling_point,proof_needed,mechanism_ids`。秒段连续覆盖时长，口播可空但不能没有口播和字幕设计；机制回链有效 |
| `experiments` | 每项 `variable,control,treatment,constants,metric,denominator,decision_rule`。一个主要变量，明确停留／收藏／点击／询问／成交口径、分母及复测条件 |

每条脚本要有自己的商品任务。配色展示帮助搭配决策、新用途需要真实操作、态度风格要与商品轮廓和日常场景对应、长期关系依赖真实经历与具体物件；依据案例判断，不把这四种说法套给其它品类。

## 人工创作审阅

报告正文采用普通拍摄语言，不照搬上表的内部字段名。先描述画面，再解释可能的观看理由，再给具体做法；完整记录留在JSON里，不用九行抽象字段压住一个简单结论。以下是用词示例，不是机械替换词表：

- “争取注意”写成“先让人愿意停下来看”；它不是已证明的购买效果，不放在“购买作用”下。
- “迁移条件”改成具体条件：“如果这枚戒指放进辫子后会滑落，就不要拍这个用法，改拍两套手部搭配。”
- “对比必须服务真实颜色”改成具体动作：“用干净背景衬出发饰，拍出来的粉色和绿色要接近实物。”
- “反事实比较”可作为可展开的“换一种拍法会怎样”，标清这是设想，不冒充真实对照结果。

条件必须落实到完整脚本。不要只写“失败时换个方案”，却让后面镜头继续沿用失败的用法。未知商品优先给一份前后连贯、能准备拍摄的草稿；尚未试过的特殊用途留作以后选题。真人与模特头等会改变口播真实性的条件，要同时改画面、口播和字幕，不能只在拍摄清单里补一句提醒。

拍摄或选款时必须知道的条件写在建议中，通用注意事项放到最后；不要把“不能证明材质”等与当前拍法无关的提醒塞进每张学习卡。报告的深度来自解释和动作，不来自术语数量或字段数量。

- 观察能追到素材，事实、解释、新设计能分清；机制是否说明观众任务和商业作用？
- 去掉品类和商品名后是否还能套给任何商品？如果能，补具体动作、场景、细节和购买顾虑。
- 镜头能否拍出，字幕／口播能否读懂，素材与证明条件是否明确？
- 原片未证明的性能是否被新脚本偷偷承诺？时长、证言、优惠、稀缺性是否有出处？
- 为什么此处拍这个画面、删掉会失去什么，实验不支持假设时如何调整？

限制集中说明，判断旁只保留影响决策的条件，不让14模块重复免责。缺因果对照仍可提出深入且可检验的创意假设，不能只剩泛泛标签。
