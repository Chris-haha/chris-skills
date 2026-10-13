# 生图前几何可行性预检

先检查原始产品图，再检查完整构图是否同时满足全部几何条件。每个可见部件实例都需要五项证据；实例集合必须与 `product-identity.md` 完全一致。原始图无法确认的结构记录 `unknown`，存在矛盾记录 `fail` 并写明冲突；不能根据历史生成图补足事实。

| 维度 | 必须核对的事实与当前构图 |
| --- | --- |
| `rigidity` | 原始部件是刚性还是柔性、固有形状是什么，构图是否要求形变 |
| `joints` | 原始连接件是否允许转动/弯曲，构图是否额外要求关节 |
| `endpoints` | 各端点或关键锚点的位置、归属与同一装配状态是否相容 |
| `direction` | 整条路径和遮挡前后的方向；是否会迫使刚性部件转弯或穿过实体 |
| `support` | 原始真实接触面、承重来源与当前放置方向能否同时成立 |

五项必须联合检查。例如，直杆的端点约束要求“跨越平面后向下转弯”，不能分别将“直杆”“两个端点”“向下路径”标成 pass；应把需要的弯折、额外关节以及端点/方向冲突写入相应 `required` 和 `conflicts`，并判 fail。原图确认无关节时，用明确的 `no-joint` 事实标识；非运动场景也要描述静态朝向和支撑，不留空或使用未检查的“不适用”。

审查数据采用 schema 1，所有对象只接受示例中列出的字段。下面示例表示一个落地支架实例，具体事实需要根据当前原图替换，不能当作所有商品的默认通过记录：

```json
{
  "version": 1,
  "checks": [
    {
      "instance_id": "hero-frame",
      "dimensions": {
        "rigidity": {
          "allowed": ["rigid-straight-leg"],
          "required": ["rigid-straight-leg"],
          "verdict": "pass",
          "sources": ["original-front.png"],
          "evidence": "原图中的腿管从脚端到上方铰链保持直线；当前展开姿态不要求腿管形变。",
          "conflicts": []
        },
        "joints": {
          "allowed": ["upper-hinge-only"],
          "required": ["upper-hinge-only"],
          "verdict": "pass",
          "sources": ["original-front.png"],
          "evidence": "原图上方铰链连接两根腿管；当前展开姿态只使用该关节。",
          "conflicts": []
        },
        "endpoints": {
          "allowed": ["foot-on-floor-to-upper-hinge"],
          "required": ["foot-on-floor-to-upper-hinge"],
          "verdict": "pass",
          "sources": ["original-front.png"],
          "evidence": "原图脚端接地，上端连入铰链；当前姿态保持同一组端点归属和位置关系。",
          "conflicts": []
        },
        "direction": {
          "allowed": ["straight-upward-to-hinge"],
          "required": ["straight-upward-to-hinge"],
          "verdict": "pass",
          "sources": ["original-front.png"],
          "evidence": "从脚端到铰链的直线路径没有转折；当前机位和展开状态保留整条路径的净空。",
          "conflicts": []
        },
        "support": {
          "allowed": ["feet-contact-floor"],
          "required": ["feet-contact-floor"],
          "verdict": "pass",
          "sources": ["original-front.png"],
          "evidence": "原图全部支撑脚与地面接触；当前构图使用相同的展开支撑状态。",
          "conflicts": []
        }
      }
    }
  ]
}
```

`allowed` 与 `required` 是审查者定义的精确事实标识列表，均非空、无重复，程序按字符串精确比较：`required` 必须为 `allowed` 的子集。标识应具体到形状、关节、端点、方向或接触条件，不能用泛化的 `ok` 掩盖尚未检查的几何。即使 `verdict` 写了 `pass`，不相容的标识或非空 `conflicts` 仍会阻断。

每项 `sources` 必须非空，且逐字引用 `ProductIdentity.truth_sources` 中的原始图名称；模板和生成图不能作为来源。`evidence` 必须填写单行具体观察及可行性理由。`verdict` 只接受 `pass`、`fail`、`unknown`；`conflicts` 是必填列表，无冲突时为空。重复 JSON 字段会被拒绝，以免一个 pass 覆盖另一个 fail。

保存并构建提示词：

```bash
python -m workflow.runner record-geometry-preflight \
  --project demo-product --image 1 \
  --objective "展示支架展开状态" \
  --checks-file /path/to/geometry-checks.json

python -m workflow.runner write-web-handoff \
  --project demo-product --image 1 \
  --objective "展示支架展开状态"
```

保存文件 `geometry-preflight.json` 会增加 `identity_sha256`、`objective` 和推导的 `status`。完整的 fail/unknown/冲突记录可正常保存，状态为 `blocked`；记录命令的退出码 0 仅表示保存成功。所有维度通过才是 `passed`。格式或来源无效的记录返回退出码 1，并将最新尝试保存为 `rejected`，在 `attempted_input` 与 `error` 中保留输入和原因，旧通过记录立即失效；无法读取的输入只能保留错误原因。重新提交完整有效的检查才能恢复。

读报告时重新计算状态，手工把 blocked 改成 passed 无法放行。缺少报告或字段、无效来源、产品清单变化、目标不同均阻断生成。几何报告或缓存提示词检查失败后，`brief.md` 保留待生成状态；修正预检并重新运行 `write-web-handoff` 后，可以直接重试 `generate-codex`。

Python 调用可以使用 `workflow.geometry.create_geometry_preflight(data, identity, objective)` 构建报告，或 `write_geometry_preflight(task_directory, data, identity, objective)` 写入；通过 `load_geometry_preflight(path)` 读取后，将报告作为 `geometry_preflight=` 传给 `build_direct_image_prompt` 和 `write_web_handoff`。两者都会重新验证。交接包只接受当前数据构建出的直接提示词；`generate-codex` 在读取网关配置和发出请求前也会重新验证报告与缓存提示词。

旧任务的产品清单仍可读取，新增的生成请求必须补齐预检。预检报告不能批准候选图；后续仍要提供独立的细节/上下文裁图，分别检查 `topology`、`support`、`clearance`、`assembly`、`framing`。schema-v3 之前的视觉质检报告不能批准新候选图。

这是结构化的人工/代理审查门禁。它不识别图片内容，不判断任意自然语言是否矛盾，也不计算坐标、关节运动学或受力。事实标识、来源真实性和跨维度物理判断仍由审查者负责；记录通过不能作为几何正确的数值证明。
