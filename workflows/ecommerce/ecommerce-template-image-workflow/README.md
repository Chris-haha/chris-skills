# 模板库电商生图工作流

这是一个轻量的电商详情图工作流：把参考图登记为模板，后续给产品图和需求时自动选最合适的模板。它默认一次只准备、生成和确认一张图；只有你明确说“全部生成”时，才允许连续准备多张图。

支持 Amazon、淘宝、TikTok Shop 和 Shopify。模板用途统一使用“主图”“卖点副图”“详情页横幅图”这类业务名称，不使用 A+ 模块术语。

## 添加模板

### 对话上传（推荐）

你不需要手动创建 `set-*` 文件夹，也不需要自己给图片写标签。直接在 Codex 对话中上传模板参考图即可：

- 同一条消息中的任意数量图片，默认视为一套模板，按上传顺序保存为一个 `set`；图片数量没有特殊阈值。
- 如果一条消息包含多套，请明确说明“这是 N 套”，并按顺序说明每套包含哪些图片。系统会分别建立 `set-001`、`set-002` 等目录，套组之间始终完全隔离。
- 系统先把附件复制到 `template-inbox/<batch>/<set>/`，生成 `manifest.md`、`contact-sheet.webp` 和 `analysis-draft.md`。每张图片先独立成为候选模块。
- 你可以说“整套确认入库”“第 3 张排除”“第 2、4 张合并”或修改体系/模块名称。合并建议只在同一套组内提出，必须得到你的确认后才会归档。
- 未确认前不会写入正式模板库；确认后会保留原始收件箱副本、正式参考图、结构化 `annotations.json` 和可回滚版本。

代理在收到对话附件后使用下面的命令保存一个套组（不要求用户执行）：

```bash
python -m workflow.runner import-template-set \
  --batch batch-001 --set set-001 --platform generic \
  --source /path/to/upload-1.png --source /path/to/upload-2.png
```

分析草稿由代理写入并等待审核：

```bash
python -m workflow.runner write-template-draft \
  --batch batch-001 --set set-001 --draft-file /path/to/analysis-draft.json
python -m workflow.runner approve-template-set --batch batch-001 --set set-001
```

撤回或修订只针对指定模板体系，不会影响其他 `set`：

```bash
python -m workflow.runner rollback-template-set \
  --platform amazon --template-set warm-editorial-01 --revision 1
```

一张图可作为独立模板；一组同色彩、字体感、卡片语言一致、但分属不同用途的参考图，应登记为一个**模板体系**和多个模块。模板体系 ID 只描述可复用的视觉语言，不能用参考图中的具体商品名。

例如这组暖棕天然材质视觉可命名为 `warm-organic-brown-editorial-01`，内部有 `feature-hero`、`care-steps`、`ingredient-grid` 等模块。面包袋仅是适用示例或场景标签，不属于 ID。

```text
template-library/<platform>/<template-set-id>/
  template-set.md
  modules/
    <module-id>/
      reference-01.png
      template.md
```

先把原始参考图放进模块目录，再登记模块；命令只写 `template.md`，不会改动参考图。

```bash
cd E-commerce/ecommerce-template-image-workflow
python -m workflow.runner register-template \
  --platform amazon \
  --template-set warm-organic-brown-editorial-01 \
  --module-id feature-hero \
  --role "详情页横幅图" \
  --ratio 97:60 \
  --size 970x600 \
  --layout "左侧场景图，右侧标题，底部图标卖点" \
  --safe-zone "右侧标题区；底部图标区" \
  --style "暖棕天然材质编辑风" \
  --scene "明亮家庭厨房" \
  --suitable-for "厨房、家居收纳和环保可重复使用产品" \
  --reference reference-01.png
```

`template-set` 和 `module-id` 必须同时使用：前者描述整套视觉体系，后者描述具体图形结构。旧式单张模板仍可用 `--template-id` 登记在平铺目录中。模板 ID、体系 ID 和模块 ID 都必须使用产品无关的名称；具体商品、品类和场景只能写在适用条件或场景字段中。

## 准备一张图

把产品参考图放在 `projects/<project>/product-references/` 中。然后准备当前图片任务：

```bash
python -m workflow.runner prepare-image \
  --project demo-product \
  --platform amazon \
  --role "卖点副图" \
  --ratio 1:1 \
  --product-reference product-front.png \
  --request "突出材质与细节" \
  --layout-keyword right \
  --safe-zone-keyword left
```

工作流按平台、图片用途、比例、版式关键词、文案安全区、产品位置和场景标签选择最高分模板；同分时优先显式目标平台，再使用模板 ID 的字母序。`generic` 模板可作为通用候选，但不同显式平台不会互相代用。没有匹配目标平台（或通用库）与用途的模板时会停止。项目里会生成 `request.md`、`selected-template.md` 和当前 `brief.md`，可查看选择原因。

当工作流已经根据产品需求判断出某个模块时，会内部带上 `--template-set` 与 `--module-id`，以避免“左侧 / 右侧”这类泛化版式词错误命中其他模块。直接运行命令时也可显式提供这两个参数；它们不是让用户挑候选，而是记录已完成的语义选择。

## 锁定产品一致性（生图前必做）

必须先检查全部产品视角和细节图。原始产品图是产品事实的唯一依据；模板图只决定版式与视觉语言，历史生成图不能补充或覆盖产品事实。逐项记录原始事实源、表面图案/印刷、物理与支撑关系、人物与动作可行性、部件数量、固定连接/从属关系、功能结构、正确使用状态及严禁出现的虚构部件。图案与印刷必须锁定元素、可见文字、数量、顺序、位置、朝向、比例和线条；无图案产品也要显式记录“无表面图案或印刷”。物理关系必须说明重力方向、支撑点、接触关系和稳定静置姿态；无特殊摆放要求也要显式记录“所有可见物体遵循重力并由真实接触面稳定支撑”。人物动作必须明确操作者数量、左右手职责、手臂进场方向、握持点、腕部与关节姿态以及动作先后顺序；单手能完成的动作优先只展示一只手，无人物画面也必须显式记录“无人物或手部”。功能结构包括孔、槽、缺口、卡扣、铰链、通道等，必须说明位置、用途和与其他部件的交互；即使没有特殊结构，也要明确记录“已检查，无特殊功能结构”。参考图存在遮挡或无法判断的结构时，把问题写入 `--unknown` 并向用户确认；不得猜测，也不得使用 `--approved`。只要 `product-identity.md` 缺失、未批准、缺少事实源/图案/物理/人物动作/功能/状态记录或仍有待确认项，工作流就会拒绝创建提示词、交接包和发起生图。

固定连接还必须单独记录“可见连接证据”：端点、连接头或套环、连续段、遮挡入口/出口和所属主体。语义上声明“已连接”不够，最终画面必须能沿证据链追踪。遮挡可以隐藏中段，但不能吞掉全部连接证据，也不能让端点看似独立摆件；无法证明时必须换角度或加入同一产品的局部特写。

每个功能交互还必须单独记录“装配状态证据”：当前状态、承载主体、功能结构、交互部件的空间路径、支撑来源和禁止混用的互斥状态。同一功能交互中的主体与参与部件必须处于同一个真实装配状态；已拆卸部件不能同时演示只有安装后才成立的功能，开放槽口也不能被画成封闭孔洞、隧道或桥状假结构。

画面里每次出现的同一物理部件还必须登记为独立的“可见部件实例”，格式为 `instance-id: description`。ID 只能使用小写字母、数字和连字符，并且在当前图片内唯一；description 要写清起点、连续结构、连接件、终点、允许的遮挡、所属主体、支撑来源和禁止错误。这个规则不依赖商品品类，例如：

- 背包：`hero-left-strap: 上端缝线 → 连续织带 → 调节扣 → 下端缝线；允许肩部遮挡中段；归属背包；禁止断带或假接触`
- 台灯：`detail-power-cable: 灯座出线口 → 连续电线 → 插头护套 → 插脚；桌面支撑；禁止断线、穿透或凭空终止`
- 折叠椅：`hero-right-hinge: 前腿管 → 铰链轴 → 后腿管；连接件完整可见；地面支撑；禁止错位、悬空或相切冒充连接`

同一部件在中央、角落、局部特写等位置重复出现时，要分别登记不同 ID；任何一个实例失败，整张图都失败，其他正确实例不能抵消。

```bash
python -m workflow.runner set-product-identity \
  --project demo-product \
  --image 1 \
  --truth-source "product-front.png" \
  --truth-source "product-detail.png" \
  --surface-graphic "杯身图案、文字、数量和排布逐项保持原图" \
  --physical-constraint "所有物体遵循重力并由真实接触面稳定支撑" \
  --physical-constraint "勺柄末端由杯盖表面承托，不得水平悬空" \
  --human-interaction-constraint "单人操作；左右手身份、腕部姿态和动作时序必须真实可执行" \
  --human-interaction-constraint "单手可以完成时只展示一只手" \
  --component "1 个杯子" \
  --component "1 把完整长勺" \
  --relationship "球形末端固定连接在勺杆上，属于同一把勺子" \
  --visible-connection-evidence "球端到勺杆必须显示银色连接套环和至少一段连续金属杆" \
  --functional-feature "杯盖边缘有供勺杆穿过的专用缺口" \
  --use-state "合盖时勺杆穿过缺口，勺头在杯内，手柄末端在杯外" \
  --assembly-state-evidence "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸；不得用平放桌面的独立杯盖演示该交互" \
  --visible-component-instance "hero-main-part: 可见端点 → 连续主体 → 固定连接件 → 所属主体；真实支撑；禁止断裂、残端或相切冒充连接" \
  --forbid "独立球形摆件" \
  --forbid "第二把勺子" \
  --approved
```

确认产品清单后，还必须为当前构图记录**生图前几何可行性预检**。逐个可见实例联合检查刚性/柔性、允许关节、端点位置、路径方向和真实支撑；例如刚性直杆的两个端点和方向要求迫使它中途弯折时，必须先改构图，不能直接交给图片模型。

```bash
python -m workflow.runner record-geometry-preflight \
  --project demo-product --image 1 \
  --objective "突出材质与细节" \
  --checks-file /path/to/geometry-checks.json
```

JSON 格式与完整示例见 [几何预检说明](docs/geometry-preflight.md)。每个实例的 `rigidity`、`joints`、`endpoints`、`direction`、`support` 都必须记录原始产品图来源、具体证据、事实允许范围 `allowed`、当前构图要求 `required`、`verdict` 和 `conflicts`。要求超出允许范围、显式冲突、`fail` 或 `unknown` 都会保留为 blocked；缺项、重复字段或无效来源会返回错误并保存 rejected 尝试，旧的通过记录立即失效。记录命令成功只表示报告已保存，不能把它当成预检通过。

`geometry-preflight.json` 绑定当前产品清单和 `--objective` 原文；清单或目标变化后必须重新检查。缺少、过期或未通过的报告会阻断直接提示词、网页交接包和 `generate-codex`。实际生图还会核对缓存提示词是否由当前清单、模板、文案和预检产生；手工修改或旧提示词必须通过 `write-web-handoff` 重新构建。几何预检阻断会保留待生成状态，补齐检查并重建提示词后可以正常重试。程序验证结构化审查的一致性，不识别照片、不理解自然语言矛盾、不计算数值物理；审查者必须真实核对原图并如实记录未知和冲突。历史生成候选图不能成为事实来源。

确认后的清单和通过的预检会作为硬约束写入当前图片的提示词。生成结果仍须先对照原始事实源逐项复核表面图案与印刷，再复核重力、支撑点、接触关系、稳定静置姿态、操作者数量、左右手身份、手掌与腕部方向、进场路径、握持点、动作时序、部件数量、连接关系、功能结构的位置和正确使用状态；任何近似、增删、替换、重排、风格化改写、无支撑悬空、实体穿透、不稳定摆放、镜像手、重复手、反关节、不可能抓握或多人才能完成的伪单人动作都判定失败，只重做当前图片，不能继续批量生成下一张。生图前预检不能替代下述 schema-v3 视觉质检。

质检还必须按“端点 → 连接件 → 连续段 → 遮挡入口/出口 → 所属主体”逐段追踪关键连接。相邻、相切或叠放不能冒充固定连接；连接链中断、端点消失、连接件缺失、遮挡边界方向矛盾或部件归属不明均直接判定失败。

涉及功能交互时，还必须按“场景状态 → 承载主体 → 功能结构 → 交互部件路径 → 支撑来源 → 遮挡一致性”逐段复原为完整产品状态。混合互斥装配状态、功能主体未安装、交互部件从错误表面进入、路径被实体截断、原始开放结构被封闭，或局部看似成立但无法还原为完整可执行状态，均直接判定失败。

生成候选图后，必须为每个可见部件实例制作任务目录内的独立裁图，并记录逐实例视觉质检：

```bash
python -m workflow.runner record-visual-qa \
  --project demo-product \
  --image 1 \
  --candidate generated-image.png \
  --instance-check "hero-main-part|qa/hero-main-part-detail.png|qa/hero-main-part-context.png|topology=pass:TRACE|support=pass:TRACE|clearance=pass:TRACE|assembly=pass:TRACE|framing=pass:TRACE"
```

`record-visual-qa` 的实例检查严格使用八字段 schema-v3：
`ID|DETAIL_CROP|CONTEXT_CROP|topology=pass:TRACE|support=pass:TRACE|clearance=pass:TRACE|assembly=pass:TRACE|framing=pass:TRACE`。
示例中的 `TRACE` 只是占位符，提交前必须替换为从对应证据图观察到的、与该维度直接相关的具体追踪证据；不能原样复制占位符。例如，发现路径穿过外壳实体时应记录 `clearance=fail:路径穿过外壳实体`，而不是留下 `clearance=pass:TRACE`。
实例集合必须与产品一致性清单完全相等。每个已登记实例必须提供两张任务目录内、非空且互不相同的证据图：`DETAIL_CROP` 是用于核对局部连续性和连接件的细节裁图，`CONTEXT_CROP` 是用于复原完整路径、所属主体、支撑关系和周围实体的上下文图；同一张图不能同时充当两者。

五个质检维度彼此独立且全部必填：`topology`（拓扑连续与归属）、`support`（真实支撑）、`clearance`（路径净空）、`assembly`（真实装配）和 `framing`（画框填充与安全裁切）。`framing` 必须核对媒体框内没有意外占位底色、上下/左右空白带或图片拉伸，同时确认关键主体、部件和图案没有被裁断；比例冲突时必须调整画框或版式。其他维度通过不能补偿 `framing` 失败；任一维度失败，该实例和整张候选图都失败。

缺少、为空、重复或格式无效的实例字段、证据图或维度证据会在报告创建前被拒绝，必须先补正，不能用 `fail` 代替；只有证据完整且确实观察到视觉缺陷时，才在对应维度记录 `fail`。

报告 Markdown 必须明确写入 `- 版本: 3`；旧版报告不能用于批准或解锁后续图片。

用户确认当前候选图后，使用审批命令：

```bash
python -m workflow.runner approve-image \
  --project demo-product \
  --image 1 \
  --candidate generated-image.png
```

审批会重新读取候选图、产品一致性清单、全部裁图和 `visual-qa.md`，仅在每个实例都为 `pass` 时把 `brief.md` 改为 `approved`。手工修改 `brief.md` 状态不能绕过闸门；准备下一张时会再次验证上一张的逐实例证据。

## 设置详情图展示文案

模板的文案安全区只规定文字位置；每张需要展示标题或卖点的图片还必须有自己的 `copy-brief.md`。它只描述包装外的展示文案，不允许复制或重绘产品包装上的 Logo、标签、营养成分表、条码或法规信息。

默认展示语言为英文；用户主动要求中文时，把 `--language` 改为 `Chinese`。所有标题、短标签与事实依据都应可由产品资料核实，不能填写疗效、认证或比较宣称。

```bash
python -m workflow.runner set-display-copy \
  --project demo-product \
  --image 1 \
  --language English \
  --headline "VITAMINS + MINERALS" \
  --subheadline "2 GUMMIES PER SERVING" \
  --label "VITAMIN D" \
  --label "B VITAMINS" \
  --evidence "Supplement Facts panel"
```

随后生成网页交接包或 Codex 提示词。工作流会要求模型把这些文字逐字排版在安全区；生成结果必须检查文字是否完整、清晰、无错字。文字失败时只重做当前图，不能直接进入下一张。

默认只能准备第 1 张；生成、逐实例视觉质检和用户确认后，必须通过 `approve-image` 才能准备下一张。对整套图片确实需要不逐张等待时，准备命令追加 `--all-images`，这就是“全部生成”的显式开关。

模板库的匹配不会使用向量数据库：先做平台/用途/比例硬过滤，再按结构化注解和产品适配关键词评分。用户确认、退回和修改原因只作为轻量排序反馈。

## 选择渠道

每张图在生成前请明确选择一个渠道：`网页 ChatGPT` 或 `Codex`。不要同时发起两个渠道的同一张请求。

### 网页 ChatGPT

生成交接包：

```bash
python -m workflow.runner write-web-handoff \
  --project demo-product \
  --image 1 \
  --objective "突出材质与细节"
```

当前图片目录会出现 `direct-image-prompt.md` 和 `web-chatgpt-prompt.md`。把交接包中的最终指令连同“必须上传的产品图”和“必须上传的模板图”一起传到网页 ChatGPT；每次只让它生成当前一张。提示词保持中文；展示文案默认英文，用户主动声明后可改为中文。交接包会列出展示文案检查项，但不应让模型生成包装文字。

### Codex

复制本地配置样例并填写你自己的中转站信息：

```bash
cp image-env.example.yaml image-env.yaml
```

`image-env.yaml` 只包含三项：`base_url`、`api_key`、`model`。它已经被 Git 忽略，绝不提交、粘贴进项目文档或提示词。`model` 必须写你的中转站实际提供的图片模型名，工作流不会假定或替换成 `gpt-image-2`。

先生成上节的直接生图提示词，再明确选择 Codex 并发起当前这一张：

```bash
python -m workflow.runner generate-codex \
  --project demo-product \
  --image 1 \
  --route codex
```

它只向 `image-env.yaml` 配置的接口提交一次当前图片请求。缺少配置、字段无效、接口失败、模型不支持参考图或返回不合格数据时，任务停止，`brief.md` 变为 `gateway_failed`，并留下不含密钥的 `gateway-error.md`。工作流绝不自动替换 URL、API Key、模型，也不会偷偷切换到网页 ChatGPT。

## 包装与品牌风险

产品图含 Logo、包装文案、营养成分、法规标签、条码或受监管宣称时，不要要求图片模型重绘这些细节。文字或标记必须准确时，使用原始授权产品图并做非破坏性合成。模板匹配和图片生成不保证平台、品牌、法规或类目合规，发布前仍需自行核对规则。
