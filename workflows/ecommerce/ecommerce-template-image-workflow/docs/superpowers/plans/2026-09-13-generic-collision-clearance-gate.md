# Generic Collision-Clearance Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require local and contextual evidence for topology, support, clearance, and assembly before any generated product image can be approved.

**Architecture:** Upgrade `workflow.visual_qa` to a schema-version-2 report whose result is derived from four mandatory dimensions for every registered visible instance. Keep orchestration in `workflow.runner` and sequencing in `workflow.projects`; both reuse the same validator so neither CLI approval nor manual status edits can bypass the gate.

**Tech Stack:** Python 3.13 dataclasses and argparse, Markdown artifacts, pytest, built-in image generation, macOS `sips` evidence crops.

---

### Task 1: Upgrade visual QA to structured schema version 2

**Files:**
- Modify: `workflow/visual_qa.py`
- Modify: `tests/test_visual_qa.py`

- [ ] **Step 1: Replace coarse fixtures with a version-2 fixture**

```python
def _passing_check() -> str:
    return (
        "hero-primary-part|qa/hero-detail.png|qa/hero-context.png|"
        "topology=pass:端点A经连续主体和连接件到端点B|"
        "support=pass:主体由桌面形成连续承重接触|"
        "clearance=pass:整条路径与周围实体保持可见净空|"
        "assembly=pass:局部可还原为完整且互不冲突的装配状态"
    )
```

Create nonempty candidate, detail crop, and context crop files. Assert the loaded report has `version == 2`, four named dimensions, an instance result of `pass`, and report status `passed`.

- [ ] **Step 2: Add failing validation tests**

Test missing, duplicate, and unknown dimensions; invalid results; empty traces; identical detail/context paths; missing or escaped evidence files; and a legacy report without `- 版本: 2`. Add a case where only `clearance=fail:路径穿过固定主体` forces both the instance and report to fail.

- [ ] **Step 3: Run tests to verify red**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_visual_qa.py -q
```

Expected: failures because the parser still accepts the four-field legacy contract and the report has no version or structured dimensions.

- [ ] **Step 4: Implement immutable schema-version-2 types**

```python
QA_DIMENSIONS = ("topology", "support", "clearance", "assembly")

@dataclass(frozen=True)
class VisualQADimension:
    name: str
    result: str
    trace: str

@dataclass(frozen=True)
class VisualQACheck:
    instance_id: str
    detail_crop_path: str
    context_crop_path: str
    dimensions: tuple[VisualQADimension, ...]

@dataclass(frozen=True)
class VisualQAReport:
    version: int
    candidate: str
    status: str
    checks: tuple[VisualQACheck, ...]
```

Parse each CLI value with `split("|", 6)`. Parse each dimension with `partition("=")`, then result/trace with `partition(":")`. Require the exact `QA_DIMENSIONS` set once each, `pass|fail`, and nonempty dimension-specific traces.

- [ ] **Step 5: Implement versioned Markdown and derived results**

Write `- 版本: 2`, two crop fields, four dimension lines in fixed order, and `- 实例结果: pass|fail`. Derive each instance result from all four dimensions and the report status from all instances. `load_visual_qa` must reject missing/non-2 versions and verify stored derived statuses instead of trusting them.

- [ ] **Step 6: Validate distinct task-local evidence**

Reuse `_file_under` for both paths and require:

```python
if check.detail_crop_path == check.context_crop_path:
    raise VisualQAError("细节裁图和上下文图必须是不同文件")
```

- [ ] **Step 7: Run focused tests and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_visual_qa.py -q
git add workflow/visual_qa.py tests/test_visual_qa.py
git commit -m "feat: require collision clearance evidence"
```

Expected: all visual-QA tests pass.

### Task 2: Add occupied-volume rules to prompts and handoffs

**Files:**
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/projects.py`
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing prompt tests**

```python
assert "占用空间" in prompt
assert "允许接触面" in prompt
assert "禁止相交实体" in prompt
assert "路径净空" in prompt
assert "无法区分正常遮挡与实体穿透时直接判定失败" in prompt
assert "装饰性构图不能覆盖物理可行性" in prompt
```

Apply equivalent assertions to the web handoff.

- [ ] **Step 2: Run tests to verify red**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py -q
```

Expected: failures because the occupied-volume wording is absent.

- [ ] **Step 3: Add the generic path-clearance instruction**

After the visible-instance section, add this rule to the direct prompt and mirror it in the handoff checklist:

```text
对每个实例建立完整路径与占用空间：先追踪端点、连续段和连接件，再标记允许接触面与沿途禁止相交实体。整条路径必须保持可见净空，不得与其他固体重叠、裁切、穿透或用相切伪装连接。遮挡只有在入口、出口、方向和前后层级一致时才成立；无法区分正常遮挡与实体穿透时直接判定失败。必须调整机位或路径来证明净空，装饰性构图不能覆盖物理可行性。
```

- [ ] **Step 4: Run focused tests and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py -q
git add workflow/prompt_builder.py workflow/projects.py tests/test_prompt_builder.py
git commit -m "feat: enforce occupied volume checks in prompts"
```

Expected: prompt tests pass.

### Task 3: Enforce version 2 at approval and sequencing boundaries

**Files:**
- Modify: `tests/test_visual_qa.py`
- Modify: `tests/test_projects.py`
- Modify: `tests/test_prompt_builder.py`
- Verify: `workflow/runner.py`
- Verify: `workflow/projects.py`

- [ ] **Step 1: Convert CLI and sequencing fixtures**

Change every `record-visual-qa` test invocation to the seven-field value and create both crop files. Change `_write_passing_previous_image_qa` to create a version-2 report.

- [ ] **Step 2: Add boundary regression tests**

Create four explicit tests named `test_approve_image_rejects_legacy_report`, `test_approve_image_rejects_clearance_failure`, `test_prepare_image_rejects_approved_status_with_legacy_report`, and `test_prepare_image_accepts_complete_version_2_report`. Each test must construct its own task directory, brief, approved identity, candidate, and evidence files; rejected cases must leave `brief.md` unchanged.

Rejected cases must leave `brief.md` unchanged.

- [ ] **Step 3: Run boundary tests**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py tests/test_visual_qa.py -q
```

Expected: legacy fixtures fail until converted; explicit legacy-report regression tests pass only when the version-2 loader is active.

- [ ] **Step 4: Verify shared-validator enforcement**

Confirm both `workflow.runner._approve_image` and `workflow.projects.prepare_image_task` call `load_visual_qa` followed by `validate_visual_qa` with `require_pass=True`. Do not duplicate the dimension logic in either caller.

- [ ] **Step 5: Run the full suite and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests -q
git add tests/test_projects.py tests/test_prompt_builder.py tests/test_visual_qa.py
git commit -m "test: enforce version two qa boundaries"
```

Expected: full suite passes.

### Task 4: Document the collision-clearance contract

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the CLI example**

Replace the legacy four-field example with the seven-field version-2 example. Explain the four mandatory dimensions and two distinct evidence images.

- [ ] **Step 2: Add cross-category examples**

Document a cable clipping through a housing, a backpack strap passing through a buckle body instead of its channel, and a chair brace intersecting a leg instead of joining at its hinge. State that continuity cannot compensate for a clearance failure.

- [ ] **Step 3: Verify and commit**

```bash
rg -n "版本: 2|topology|support|clearance|assembly|上下文图|路径净空" README.md
/opt/miniconda3/bin/python3 -m pytest tests -q
git add README.md
git commit -m "docs: explain collision clearance qa"
```

Expected: all required terms are documented and tests pass.

### Task 5: Re-record the rejection and regenerate image 05

**Files:**
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/product-identity.md`
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/brief.md`
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/visual-qa.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generation-v6-prompt.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v6-original.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v6.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/qa/*-v6-detail.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/qa/*-v6-context.png`

- [ ] **Step 1: Record the current candidate as version-2 failed evidence**

Create a wider `notch-spoon` context crop and record `clearance=fail:金属杆与固定小狗盖钮的身体或底座占用空间重叠，无法证明无碰撞路径`. Keep the report and brief failed.

- [ ] **Step 2: Strengthen task-local instance data**

Require `notch-spoon` to maintain a continuous visible lane from the U-notch to the connector, with a positive gap from the puppy knob/body across its whole route. Keep this product-specific rule in task data, not core code.

- [ ] **Step 3: Regenerate from original sources only**

Use built-in image generation with the task's GPT Image 2.5 requirement. Provide the layout template plus at most four original product photos. Do not supply any generated candidate as a factual reference or edit target. Require the top-right shaft to run through a visibly open lane beside the knob, never across its silhouette or occupied base.

- [ ] **Step 4: Reject failures before delivery**

Inspect `center-spoon`, `notch-spoon`, and `detail-spoon` in both detail and context views. Do not create the deliverable filename or mark the report passed until all twelve dimension results pass.

- [ ] **Step 5: Save and create evidence**

Save the selected original as `generated-image-v6-original.png`, resize to 970×600 as `generated-image-v6.png`, and create distinct detail/context crops for all three instances with `sips`.

- [ ] **Step 6: Record version-2 QA without approving**

Run `record-visual-qa` with three seven-field checks. Confirm report version 2, exact instance coverage, every dimension passing, and candidate `generated-image-v6.png`. Leave `brief.md` pending user review; do not call `approve-image` before explicit confirmation.

- [ ] **Step 7: Final verification**

```bash
/opt/miniconda3/bin/python3 -m pytest tests -q
sips -g pixelWidth -g pixelHeight projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v6.png
```

Then load the identity and report, derive required instances with `parse_visible_component_instances(identity.visible_component_instances)`, and call `validate_visual_qa(task_path, report, required_instances, "generated-image-v6.png", require_pass=True)`. Expected: tests pass, dimensions are 970×600, report status is `passed`, and the brief remains pending user approval.
