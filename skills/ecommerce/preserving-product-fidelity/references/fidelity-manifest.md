# Fidelity manifest：证据合同与验证器

商业精确产品合成必须保存一份 UTF-8 JSON manifest，并在首张候选前及每次交付前运行[验证器](../scripts/validate_fidelity_manifest.py)。本页描述当前实际接口；判断规则见[产品事实与验收协议](product-truth-protocol.md)。

验证器检查工作流证据及字段之间的约束，不检查视觉相似度。它不会读取来源图像或重新计算文件 SHA-256，也不会执行合成、检查真实遮罩像素或证明裁图可读性。它能从验证通过的记录确定性导出结构化提示词合同。退出码 `0` 说明所填记录通过当前规则，不证明所填记录真实。执行者必须核验文件、原图、提示词语义和实际输出，不能伪造证据以通过验证。

## 顶层合同与状态

以下 11 个顶层字段必须存在；集合用数组，复合记录用对象。没有单独的 `schema_version` 要求。ID 使用非空字符串，事实与拓扑共享唯一 ID 空间；来源、atlas 和所选引用也必须无歧义。布尔值用 JSON `true` / `false`，不能写字符串。任何层级的重复 JSON 键均返回 `DUPLICATE_JSON_KEY`，不会按最后一项覆盖；超过解析器嵌套限制则返回 `JSON_NESTING_TOO_DEEP`。两者都阻断验证与合同导出。

| 字段 | 内容 |
|---|---|
| `mode` | `commercial_exact_product` 或 `concept_draft`；后者不能申请商业验证状态 |
| `sources` | 所有原始来源的 ID、角色、路径、哈希、视图、必要性 |
| `facts` | 每个产品事实及状态、重要性、证据 |
| `topology` | 独立组件、连接路径与证据；与事实共同支持提示词 |
| `prompt_claims` | 每条进入提示词的产品断言及支持 ID |
| `reference_plan` | 工具上限、真正选入的来源/atlas ID、atlas provenance |
| `scene_plan` | 目标场景、展示范围、最终方向、表面、身份区域、场景调整 |
| `method` | 编辑方式、真实能力、保护区域、允许遮罩、像素保留约定 |
| `approval` | 明确的事实/拓扑批准范围 |
| `qa` | 实际比较记录；预检时可尚未完成，交付时必须齐全 |
| `delivery_status` | 当前申请的交付状态，不能只凭主观评价设置 |

可选顶层 `forbidden_mutations` 为数组，每条同 `prompt_claims` 使用 `{id, claim, supporting_ids}`；禁止变更也必须有已解决的事实/拓扑证据支持，不能直接写任意字符串。

| 状态 | 意义与使用限制 |
|---|---|
| `blocked` | 缺少证据、可用方法或完整计划，停止相关商业执行 |
| `unverified_draft` | 仅草稿，或预检通过但实际 QA 尚未完成；不能作商业保真承诺 |
| `verified_composite` | 商业模式、允许方法、完整证据及 QA 均通过后的候选状态；再次验证成功才生效 |
| `verified_reference_match` | `evidence_constrained_generation` 的证据约束自然重建已通过结构 landmark 与材质对照；不代表产品像素相同，不得作 pixel-exact 声明 |
| `rejected` | 已发现身份错误或保护像素漂移，保留失败版本用于诊断，不交付为商品图 |

`valid` 与状态不是一回事：一个正确登记为 `blocked` 的 manifest 也可能返回 `valid: true`。交付须同时为退出码 `0`、`valid: true`，且有效状态符合方法。只有 `effective_delivery_status: verified_composite` 才能称为 exact、faithful、commercial-ready 或等价的像素精确保真结果；`verified_reference_match` 不证明像素复用，只能准确称为“已通过参考对照的证据约束重建”。

有错误时，CLI 通常返回 `blocked`；检查到身份 landmark 失败或受保护像素漂移则为 `rejected`；唯一错误仅为全量重绘或概念模式申请过高状态时，上限为 `unverified_draft`。更早的格式错误可能使后续检查尚未执行，因此应修正错误并重新验证，不能把未报出的错误当作不存在。

## 来源、哈希与证据区域

`sources[]` 字段：`id`、`role`、`path`、`sha256`、`view`、`required`。工作流必须保留可找到原文件的路径，优先绝对路径；相对路径需在任务记录中写明基准。CLI 不解析或打开这些图像路径。

| JSON `role` | 提示词角色 | 证据权限 |
|---|---|---|
| `product_truth` | `PRODUCT_TRUTH` | 该 SKU 的原始商品外观与结构 |
| `detail_truth` | `DETAIL_TRUTH` | 该 SKU 的指定局部近照或其他真实角度 |
| `target_scene` | `TARGET_SCENE` | 人物、背景与场景；不能支持产品事实、拓扑、表面或产品 QA |

JSON 角色仅接受上述小写值。质量流程中的 `COMPOSITE_INPUT` / `GEOMETRY_PROXY` 单独记录为操作资产，不能伪装成产品真值来源。每份来源与 atlas 的 `sha256` 为实际文件的 64 位十六进制摘要；修改文件后重算并保留版本。CLI 检查格式和引用，真实文件内容与哈希的一致性由执行者核验。所有必要来源设 `required: true`，不得通过取消必要标记降低证据要求。

`evidence[]` 中每条记录使用 `source_id` 和 `normalized_region: [x, y, width, height]`，坐标相对于该原始来源图：左上角为 `(0, 0)`，右下角为 `(1, 1)`。所有数值有限，`x, y >= 0`、`width, height > 0`，各值不超过 `1`，且 `x + width <= 1`、`y + height <= 1`。布尔值、零面积、越界和非有限数都不合法。不要把候选图或 atlas 坐标填成原图坐标。

例如原图上 `(200, 100)` 开始、宽 `400` 高 `300` 的裁图，在 `1000 × 1000` 原图中为 `[0.2, 0.1, 0.4, 0.3]`。同一规则用于 atlas 源/目标区域、受保护产品区域与 QA 原图裁图。

## 事实、拓扑、提示词与批准

`facts[]` 登记 `id`、`component`、`assertion`、`status`、`commercial_importance`、`evidence`。重要性必须为 `high`、`medium` 或 `low`，不得为了跳过检查降低身份事实的重要性。

`topology[]` 登记 `id`、`component`、`component_count`（已知才填数值）、`endpoints`、`path`、`connection_type`、`purpose`、`status`、`evidence`。端点和用途只写来源支持的内容，不从组件类别推导。无法确认的关系留为未知；不要复制其他 SKU 的组件数或连接方式。

两种记录的 `status` 均只能为：

- `observed`：原始产品像素直接可见，至少一个合法产品证据区域。
- `user_confirmed`：用户明确解释原图中的某项歧义，仍有产品证据区域，而且该 ID 在 `approval.confirmed_fact_ids` 中。
- `unknown`：遮挡、像素不足或视角缺失；不能进入产品结构断言。
- `conflict`：证据或解释相互矛盾；解决前不能用于产品结构断言。

`approval.confirmed_fact_ids` 可包含事实或拓扑 ID。任务记录还应保存明确确认的原话和对应来源区域；`preview_approval` 与包装许可只能作为旁注。泛泛的“确认”、喜欢预览、允许保留泡棉都不能把未知结构升级。批准只解释已有证据，不创造未展示的产品事实。

`prompt_claims[]` 为 `{id, claim, supporting_ids}`；支持列表非空，每个 ID 都必须在事实/拓扑记录中存在、已解决且有产品证据。数量、功能、连接方式以及“只有一个”“没有第二个”等否定句都要登记。使用导出的 `prompt_contract`，写入提示词时保留支持 ID，并把场景风格与产品事实分开。CLI 检查引用是否有资格支持，不理解断言之间的蕴含关系；不能给“只有一个手柄”引用一个仅证明颜色的 ID。

商业规则要求可见或必须重绘的身份关键事实和拓扑均已解决。CLI 对可见/重绘的未知、冲突或证据/批准不足的拓扑返回 `UNRESOLVED_HIGH_RISK_TOPOLOGY`，即使没有任何提示词引用它。每个可见/重绘身份部件都必须完整登记，不得靠遗漏声明规避检查。

## 参考计划与确定性 atlas

`reference_plan.tool_reference_limit` 是实际工具的正整数参考上限。`selected_source_ids` 是真正提供给工具的唯一 ID 列表，可引用原始来源或 atlas；包含模特来源时也占槽。数量不能超过上限。`deterministic_atlases` 没有使用时为 `[]`。

每个必要来源必须直接选入，或属于一个已选 atlas 的父来源。仅创建 atlas 但没有选入不构成覆盖；参考上限永远不能授权丢弃证据，保全不了则停止。

每个 atlas 记录：

- `id`、`path`、`sha256`（atlas 文件自身摘要）、`deterministic: true`。
- `parent_source_ids`：唯一的产品/细节来源 ID；父文件哈希从这些 ID 对应的 `sources[].sha256` 追溯，不能使用模特场景作为产品父证据。
- `crop_mappings[]`：每个父来源至少一个映射，含 `parent_source_id`、`source_normalized_region`、`atlas_normalized_region`。不同父图的输出区域不得重叠；映射不得重复。
- 每个映射实际核验 `identity_landmarks_readable: true`；CLI 允许省略此字段，但工作流必须检查并记录，`false` 或错误类型会被拒绝。

工作流另存生成 atlas 的确定性命令、原图/atlas 像素尺寸与实际缩放因子（可作为附加 `scale` 元数据，当前 CLI 不检验）。禁止生成式重画、镜像、隐藏关键部件或把细节缩小到不可辨认。裁图覆盖必须包含所需证据区域，而不只是父 ID；当前 CLI 不进行像素或语义覆盖分析，必须人工核验。原始事实证据继续引用原图 ID，atlas 不提供新事实。

## scene_plan 与来源支持的 presentation_envelope

`target_scene_source_id` 标记实际目标模特图；`required_product_view` 记录需要的产品方向。二者属于工作流记录，当前 CLI 不替执行者判断选择是否真实。

`presentation_envelope` 必须由产品原图推导，字段如下：

| 字段 | 规则 |
|---|---|
| `supported_orientations` | 非空；每个方向都须有 `product_truth` / `detail_truth` 的同名 `view` 支持 |
| `visible_surfaces` | 有证据且允许展示的 canonical 表面，非空 |
| `surface_evidence` | 每个可见表面映射到非空原始产品来源 ID 列表；来源 `view` 必须支持该表面 |
| `visible_attachment_points` | 必填、唯一的非空字符串数组；没有可见连接点时为 `[]`。每项必须匹配至少一条已观察或已明确确认且有合法产品证据的拓扑 `endpoints`，否则 `UNSUPPORTED_VISIBLE_ATTACHMENT_POINT` |
| `must_remain_hidden` | 所有未获支持的 canonical 表面，非空，保持隐藏且不重绘 |

每条为 `visible_attachment_points` 提供证据的拓扑记录，其 ID 都必须同时列入 `scene_plan.visible_identity_critical_regions` 或 `scene_plan.redrawn_identity_critical_regions`。连接点的支持拓扑因而成为身份验收对象，申请 `verified_composite` 前必须完成对应的原始分辨率 landmark 裁图 QA；不能只声明一个有证据的端点，却遗漏证明该端点的拓扑身份记录。

canonical 表面固定为 `front`、`left_side`、`right_side`、`back`、`top`、`bottom`、`opening`、`interior`。`visible_surfaces` 和 `must_remain_hidden` 必须互斥且合计覆盖全部八项，不能漏掉未知表面。

当前允许的 `sources[].view`、`supported_orientations` 和 `final_orientation` 使用以下闭集；方向名称不是放宽角度或重建隐藏几何的授权：

| 方向 | 可支持表面 |
|---|---|
| `front` | `front` |
| `front_left_three_quarter` | `front`, `left_side` |
| `front_right_three_quarter` | `front`, `right_side` |
| `left_side` / `right_side` | 对应同名表面 |
| `back` | `back` |
| `back_left_three_quarter` | `back`, `left_side` |
| `back_right_three_quarter` | `back`, `right_side` |
| `top` / `bottom` | 对应同名表面 |

当前映射没有能证明 `opening` 或 `interior` 可见的方向标签，因此本 CLI 的商业模式要求它们保持隐藏。即使补了开口照片，也不能伪填 `top` 来放行；需要该展示能力时停止并报告合同范围不足。

`scene_plan` 其余执行字段：

- `final_orientation` 必须在支持方向内；`final_visible_surfaces` 非空且是 envelope 可见表面的子集，同时与最终方向兼容。
- `mirrored_product_view` 必须为 `false`。商业模式拒绝任何镜像产品，即使另一侧有独立照片，也应直接用那张照片而不是镜像。
- `forbidden_invented_regions` 非空，仅 canonical 表面，须全部位于 `must_remain_hidden`；最终可见表面不得与二者相交。
- 商业模式中 `visible_identity_critical_regions` 与 `redrawn_identity_critical_regions` 两个列表都必须存在，缺少任意一个会返回 `MISSING_IDENTITY_REGION_LIST`。`redrawn_identity_critical_regions` 在没有重绘时写为 `[]`。申请 `verified_composite` 时，两个列表的并集必须包含至少一个事实/拓扑身份 landmark ID，否则返回 `MISSING_IDENTITY_LANDMARK_DECLARATION`。两个列表均列事实/拓扑 ID，不能填表面名或漏掉关键部件。每个 ID 必须在共享事实/拓扑命名空间中恰好解析到一条记录；拼错或未知 ID 会在不确定性、QA 和导出处理之前返回 `UNKNOWN_IDENTITY_REGION_ID`，预检和概念模式也不能绕过。商品身份区域不得因生成式编辑而改画；重绘列表用于如实揭示计划或失败中的重绘范围。
- `permitted_scene_adjustments` 非空，只接受 `model_pose`、`hand_placement`、`crop`、`product_position`。`applied_scene_adjustments` 可为空，实际修改必须是允许集合的子集。相机取景通过 `crop` 表达，不添加自创枚举；商品变形或新增角度不属于场景调整。

产品视图不完整时，调整模特姿势、手的位置、裁切和商品位置，仅展示来源支持的角度与表面，未知区域保持隐藏。正面来源不能支持侧开口；三分之四图只支持实拍那一侧。保持人物身份和总体视觉方向，无法自然安排时请求缺失视图或停止；不得镜像或按类别推断。

## 方法能力与交付上限

| `method.type` | 所需合同 | 上限 |
|---|---|---|
| `deterministic_composite` | 复用产品像素；非空 `protected_regions`；`product_pixels_preserved: true`；记录实际确定性变换 | QA 全过后可申请 `verified_composite` |
| `masked_generative_contact` | 上述保护，且 `tool_capabilities.supports_mask: true` 与 `supports_layer_lock: true`，以及非空 `allowed_edit_mask.regions` | QA 全过后可申请 `verified_composite` |
| `evidence_constrained_generation` | `product_pixels_preserved: false`；`protected_regions: []`；非空 `view_anchor_source_ids` 覆盖所选且支持最终角度的产品证据；所有可见身份 ID 同时列入 redrawn；`material_fidelity_required: true` 和非空 `material_identity_fact_ids` | landmark 与材质 QA 全过后可申请 `verified_reference_match` |
| `full_generative_redraw` | 整产品生成，不能保证来源像素 | 最高 `unverified_draft`，不得升为 `verified_composite` |

`protected_regions[]` 是 `{id, source_id, normalized_region}`，来源必须为产品证据，ID 唯一。遮罩角色只接受 `contact`、`occlusion`、`shadow`、`hand_contact`、`hand_occlusion`、`contact_shadow`。这些角色标签不是实际遮罩文件，执行者还须保存可复查的真实遮罩/图层锁设置，并确认编辑范围未侵入受保护产品区域。确定性工具可记录 `supports_deterministic_transform`；CLI 当前不把该元数据作为能力证明。

平面合成默认确定性产品像素复用；遮罩编辑只修手部遮挡、边缘接触与阴影。模特手持或穿戴需要自然透视与真实接触时，可用 `evidence_constrained_generation`，但必须先从产品视角证据选择角度，再适配模特姿势，不得反过来为复刻姿势而显露无证据表面。全量无约束重绘、没有真实保护能力或需要猜产品变形时停止商业执行。模型名称、订阅等级、预览批准不能提升上限；只有工具披露的实际模型元数据才可对外报告。

## 原始分辨率 QA

必须进行原始分辨率对比，填写 `landmark_records` 与 `protected_pixels`，不能只看缩略图、上一张生成图或提示词是否执行。

`qa.original_resolution_comparison` 必须为 `true`；`qa.overall_verdict` 必须为 `pass`。`qa.landmark_records[]` 每条为 `{landmark_id, source_id, normalized_region, verdict}`，每个可见/重绘身份 ID 必须至少有一条且不得重复。逐项检查所有高重要性事实和拓扑；裁图来自产品原图，候选侧裁图与对齐过程另存任务证据。`verdict` 仅接受 `pass`、`fail`、`mismatch`；后两者拒绝结果。

`qa.protected_pixels` 为 `{verdict, compared_region_ids}`，比较列表必须覆盖每个 `method.protected_regions[].id`；`verdict` 只接受 `pass` 或 `drift`。实际比较应按记录的确定性变换对齐来源，核对保护区域，不得以“看起来没变”替代像素验证。任何身份漂移直接拒绝。

`evidence_constrained_generation` 不使用保护像素来伪装成原图复制，而是强制独立材质身份 QA。`method.material_identity_fact_ids` 中每个 ID 必须解析到有产品原图证据、商业重要性为 high、component 明确属于 material 的事实，并同时属于 redrawn 身份区域。`qa.material_comparison` 为 `{original_resolution, fact_ids, verdict}`：必须在原始分辨率对照纹理/grain 尺度与方向、颜色、光泽、软硬挺括、缝线和五金反射；事实列表须完整覆盖，`verdict` 必须为 `pass`。缺失或失败均阻止 `verified_reference_match`。

这些是工作流 QA 记录，CLI 不读取候选、比对哈希或计算图像差分。任何质量修复都会使旧 QA 失效：保存新版本、重做产品/人物/场景及保护像素检查、更新 manifest，再验证交付。

## 验证命令与两个闸门

CLI 默认验证模式接受一个 manifest JSON 文件路径参数；另外支持 `--emit-prompt-contract MANIFEST.json` 导出模式，没有 `--preflight` 或 `--delivery` 开关。以下命令均从 Skill 目录运行，`MANIFEST.json` 代表本任务实际保存的清单路径：

```bash
python3 scripts/validate_fidelity_manifest.py MANIFEST.json
python3 scripts/validate_fidelity_manifest.py --emit-prompt-contract MANIFEST.json
```

1. 首张商业候选前：登记所有证据、完整引用、展示范围与实际方法；`delivery_status` 设为 `unverified_draft`，`qa` 可为 `{}`，尚未执行的 QA 不能预填 `pass`。运行验证命令，再用导出模式获得提示词合同，保存输出和退出码，任何错误都停止。返回 `valid: true` 只允许按照该计划制作候选；全量重绘即使记录合法也不能用作商业方法。
2. 交付前：实际候选完成原始分辨率 QA 后更新 `qa`；像素复用方法申请 `delivery_status: verified_composite`，证据约束自然重建申请 `delivery_status: verified_reference_match`，再次运行同一命令。任何错误、非对应验证状态、结构失败或材质失败均禁止交付。候选、来源、提示词、方法、构图或质量处理改变后要重新验证相应阶段。

退出码：`0` 表示当前清单无验证错误，`1` 表示读取/编码/JSON/合同错误，`2` 表示参数数量错误。输出只有一个 JSON 对象：

```json
{"valid": true, "effective_delivery_status": "verified_composite", "errors": []}
```

每个 `errors[]` 包含稳定 `code` 和说明 `message`。可运行随包回归数据检查安装：

```bash
python3 scripts/validate_fidelity_manifest.py tests/fixtures/valid-deterministic-composite.json
python3 scripts/validate_fidelity_manifest.py --emit-prompt-contract tests/fixtures/valid-deterministic-composite.json
python3 scripts/validate_fidelity_manifest.py tests/fixtures/reject-full-generative-commercial.json
```

前两条退出 `0`；第三条退出 `1`，包含 `UNSAFE_COMMERCIAL_METHOD`，有效上限 `unverified_draft`。这些 [valid fixture](../tests/fixtures/valid-deterministic-composite.json) 与 [atlas fixture](../tests/fixtures/accept-provenance-atlas.json) 是结构回归数据，图像路径与哈希不构成真实生产证据；不得把其中商品事实或 QA 通过记录复制到新 SKU。

### 导出合同的结构与边界

导出模式保留同样的 `valid`、`effective_delivery_status`、`errors` 字段；仅完整验证通过后追加 `prompt_contract` 对象。验证失败时不输出 `prompt_contract`，退出码非零。对同一输入，输出 JSON 完全确定。默认模式不返回合同。

`prompt_contract` 含 `mode`、`delivery_status`、`source_roles`（来源 ID 与角色）、已解决的 `facts` / `topology`（保留 ID、结构字段及证据区域）、验证过的 `prompt_claims` / `forbidden_mutations`，以及 `presentation_envelope`、最终方向/表面、镜像标志、允许/实际场景调整、禁止显露区域、`method` 的类型/像素保护/保护区域/允许遮罩角色。证据约束重建还导出 `view_anchor_source_ids`、`material_identity_fact_ids` 与 `material_fidelity_required`，使角度和材质纹理要求不能在自由提示词中被替换。未知或冲突的隐藏记录被省略，不转化为肯定或否定断言。可见未知记录会阻断整个导出。

只投影这些声明字段，额外的自由提示词、任意元数据和嵌套指令不会被拼进合同。导出还检查结构文本、端点、数量和遮罩角色的类型；概念模式导出也要通过来源展示范围检查，不能借模式名称输出无证据视角。结构文本的真实性仍须人工对照原图核验。不得在导出合同之外添加产品结构断言。

合法的局部导出形状（省略了其他已验证字段，仅用于说明）：

```json
{
  "source_roles": [{"id": "product-front", "role": "product_truth"}],
  "prompt_claims": [{"id": "P-color", "claim": "Preserve the observed burgundy front panel.", "supporting_ids": ["F-color"]}],
  "forbidden_mutations": [],
  "final_orientation": "front",
  "final_visible_surfaces": ["front"],
  "method": {"type": "deterministic_composite", "product_pixels_preserved": true, "allowed_edit_mask": {"regions": ["hand_occlusion", "contact_shadow"]}}
}
```

## 有效与拒绝片段

以下是已有完整清单中的局部记录，不是可单独提交 CLI 的完整 manifest。

有效支持链示例：前提是 `product-front` 已登记为真实产品来源、引用计划覆盖它，且原图确实证明该颜色。

```json
{
  "facts": [{"id": "F-color", "component": "front_panel", "assertion": "Visible front panel is burgundy.", "status": "observed", "commercial_importance": "high", "evidence": [{"source_id": "product-front", "normalized_region": [0.2, 0.1, 0.4, 0.3]}]}],
  "prompt_claims": [{"id": "P-color", "claim": "Preserve the observed burgundy front panel.", "supporting_ids": ["F-color"]}],
  "approval": {"confirmed_fact_ids": []}
}
```

拒绝的结构断言：泡棉遮挡让数量未知，通用批准不会提供事实级支持；若该事实将可见/重绘还会触发 `UNRESOLVED_HIGH_RISK_FACT`。

```json
{
  "facts": [{"id": "F-handles", "component": "handles", "assertion": "Handle count is obscured by foam.", "status": "unknown", "commercial_importance": "high", "evidence": []}],
  "prompt_claims": [{"id": "P-one", "claim": "Exactly one handle, no second handle.", "supporting_ids": ["F-handles"]}],
  "approval": {"confirmed_fact_ids": [], "preview_approval": "确认，包装可保留"}
}
```

该片段的支持引用会产生 `UNSUPPORTED_PROMPT_CLAIM`。换用其他 SKU 的“一个手柄”结论或一个只证明颜色的已观察 ID 仍违反事实合同。

| 修改一个原本有效的完整清单 | 预期拒绝 |
|---|---|
| 正面 envelope 的 `final_visible_surfaces` 改为 `["front", "right_side", "opening"]` | `UNSUPPORTED_VISIBLE_SURFACE` 等视角错误 |
| 移除一个必要来源且没有选入覆盖它的 atlas | `UNCOVERED_REQUIRED_SOURCE` |
| `method.type` 改为 `full_generative_redraw`，保留验证交付状态 | `UNSAFE_COMMERCIAL_METHOD` |
| 遮罩编辑缺少 mask 或 layer lock 实际能力 | `MISSING_PROTECTIVE_TOOL_CAPABILITY` |
| 少一个可见身份 ID 的 QA 裁图 | `MISSING_LANDMARK_QA` |
| `qa.protected_pixels.verdict` 改为 `drift` | `PROTECTED_PRODUCT_PIXEL_DRIFT`，有效状态 `rejected` |
