---
name: preserving-product-fidelity
description: Use when replacing a real product in ecommerce model or lifestyle photos and exact product identity must be preserved, including outputs that are blurry, waxy, noisy, materially flat, oversmoothed, or unstable; not for approximate, inspired, or imaginary product design.
---

# Preserving Product Fidelity

把任务作为受证据约束的商业产品合成。优先级固定为：**产品事实 > 模特与场景不变量 > 接触与遮挡 > 纹理质量 > 风格**。漂亮或同类相似不能抵消产品结构错误。

## 必读路由

- 每个任务开始前必须阅读 [产品事实与验收协议](references/product-truth-protocol.md)。
- 执行商业精确替换时，必须阅读 [manifest 合同与 CLI](references/fidelity-manifest.md)，保存结构化 JSON manifest，不能用口头清单替代。
- 涉及模糊、材质、皮肤、头发、织物、放大/超分、线稿、泥模/白模或摄影质感时，再阅读 [质量修复协议](references/quality-restoration-protocol.md)。
- 仅分析该历史 SKU 的失败时，可选阅读 [黑包案例复盘](references/black-bag-case-study.md)；不得作为包袋任务的默认参考，也不得迁移其部件数量或连接事实。

## 执行闸门

1. **建立产品证据。** 在原始分辨率检查原图，登记来源角色、SHA-256、事实与拓扑 ID、证据区域及 `observed` / `user_confirmed` / `unknown` / `conflict`。产品原图提供产品事实；模特图只提供场景。生成图、类别常识、其他 SKU 和模型记忆都不能补证据。
2. **限定批准范围。** 仅明确指向事实 ID 的用户解释能消除原图歧义；泛泛的“确认”、预览批准、允许保留包装不能确认未知结构。将关键未知保持隐藏且不重绘，或停止并请求缺失证据。
3. **保存全部必要参考。** 工具参考图上限不能授权丢弃证据；用有来源哈希、裁切映射且关键细节可读的确定性 atlas，无法保全则停止。
4. **以产品证据决定展示方式。** 先建立来源支持的 `presentation_envelope`。视图不完整时，调整模特姿势、手的位置、裁切和商品位置，仅展示来源支持的角度与表面，未知区域保持隐藏；禁止镜像补侧面、类别推断和凭空变形。无法自然摆放则停止并索要视图。
5. **选择可保真的方法。** 平面陈列、简单贴合且不会产生明显照片拼贴感时，优先 `deterministic_composite` 复用产品像素。模特手持或穿戴商品、需要新的真实透视、手部接触和现场光照时，使用 `evidence_constrained_generation`：产品证据先确定角度，再调整模特姿势与手位；自然重建整件可见商品，但只能重建证据已经证明的角度、表面与身份事实，不能把商品原图原封不动贴到人物上，也不能自由设计未知区域。`masked_generative_contact` 必须具有显式遮罩和图层锁、受保护产品区域、最小接触编辑范围及像素保留证据。`full_generative_redraw` 最高为 `unverified_draft`，不得升级为 `verified_composite`，无论模型名称或观感如何。
6. **生成前验证。** 首张商业候选制作之前，必须运行 `python3 scripts/validate_fidelity_manifest.py MANIFEST.json`（在 Skill 目录下）；验证失败必须停止。预检用 `unverified_draft`，QA 如实记为未完成；预检通过仅允许按已验证计划制作候选。再用 `python3 scripts/validate_fidelity_manifest.py --emit-prompt-contract MANIFEST.json` 导出合同；只使用成功返回的 `prompt_contract`，每条结构断言追溯到已解决的事实/拓扑 ID，禁止额外自由补写产品事实。
7. **逐张 QA。** 候选与原图并排，在原始分辨率逐项检查可见高重要性事实、拓扑与 landmark 裁图。像素复用方法验证 `protected_pixels`；`evidence_constrained_generation` 还必须登记 `material_identity_fact_ids` 并通过 `qa.material_comparison`，逐项核对纹理/粒面尺度与方向、颜色、光泽、软硬挺括度、走线及五金反射。材质不能只凭“高级感”或整体观感通过。任何身份或材质漂移直接 `rejected`；证据不足为 `blocked`。一次一张，同一错误连续两次停止当前方法；首张通过后才扩展整组并复核跨图一致性。
8. **质量修复与交付。** 产品、材质、模特、场景和接触 QA 通过后才单独修质量；修复后更新 manifest 并重做完整 QA。交付前必须再次运行 `python3 scripts/validate_fidelity_manifest.py MANIFEST.json`，要求返回 `valid: true`，且有效状态与实际方法相符：像素复用为 `verified_composite`，证据约束自然重建为 `verified_reference_match`。`verified_reference_match` 不代表像素完全相同，不得宣称 pixel-exact、原像素复用或“完全一致”；它只表示可见的结构与材质均通过逐项原图对照。只有通过验证的 `verified_composite` 才可称为 exact、faithful、commercial-ready 或“精确一致”的像素保真合成。其余状态必须准确标注，不能因用户喜欢或时间紧而放行。

验证器检查工作流证据，不能代替原图视觉核验。交付应报告方法、状态和未解决项；只在工具实际披露时报告模型名称，订阅等级和请求参数不能证明所用模型。
