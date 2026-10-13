# Generic Visible-Instance Continuity Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require every repeated visual component instance to have independently verified continuity evidence before an image can be approved or unlock the next image.

**Architecture:** Add a generic instance contract to `ProductIdentity`, then isolate visual-QA report parsing and validation in `workflow/visual_qa.py`. CLI commands record evidence and approve only passing reports; project sequencing revalidates the report instead of trusting an `approved` string in `brief.md`.

**Tech Stack:** Python 3.13 dataclasses and argparse, Markdown artifacts, pytest, built-in image generation, macOS `sips` for task-local inspection crops.

---

### Task 1: Add generic visible component instances

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Modify: `workflow/runner.py`
- Modify: `workflow/prompt_builder.py`
- Test: `tests/test_projects.py`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests**

Add this required fixture field:

```python
visible_component_instances=(
    "hero-primary-part: 主部件；端点A → 连续结构 → 连接件 → 端点B；无遮挡；桌面支撑；禁止断裂",
),
```

Test missing and empty sections, illegal IDs, duplicate IDs, empty descriptions, CLI persistence, and direct-prompt instance-level hard failures.

- [ ] **Step 2: Verify red**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py -q
```

Expected: FAIL because the model and loader lack `visible_component_instances`.

- [ ] **Step 3: Implement the contract**

Add `visible_component_instances: tuple[str, ...]` and a parser:

```python
_INSTANCE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")

def parse_visible_component_instances(items: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        instance_id, separator, description = item.partition(":")
        instance_id = instance_id.strip()
        description = description.strip()
        if not separator or not _INSTANCE_ID.fullmatch(instance_id) or not description:
            raise ProjectError("可见部件实例格式无效")
        if instance_id in parsed:
            raise ProjectError(f"可见部件实例 ID 重复：{instance_id}")
        parsed[instance_id] = description
    if not parsed:
        raise ProjectError("产品一致性清单的可见部件实例不能为空")
    return parsed
```

Round-trip the “可见部件实例” Markdown section, add repeatable CLI argument `--visible-component-instance`, and inject the generic rule that every instance is independently checked for breakage, residual ends, misalignment, premature termination, penetration, wrong ownership, and fake contact.

- [ ] **Step 4: Verify green and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py -q
git add workflow/models.py workflow/projects.py workflow/runner.py workflow/prompt_builder.py tests/test_projects.py tests/test_prompt_builder.py
git commit -m "feat: require visible component instances"
```

Expected: focused tests PASS.

### Task 2: Create the visual-QA report

**Files:**
- Create: `workflow/visual_qa.py`
- Modify: `workflow/runner.py`
- Create: `tests/test_visual_qa.py`

- [ ] **Step 1: Write failing report tests**

Test this public API:

```python
checks = parse_visual_qa_checks([
    "hero-primary-part|qa/hero-primary-part.png|pass|端点A至端点B连续可见",
])
path = write_visual_qa(task_dir, "generated-image-v1.png", checks, required_instances)
report = load_visual_qa(path)
validate_visual_qa(
    task_dir, report, required_instances, "generated-image-v1.png", require_pass=True
)
```

Also reject a missing required instance, duplicate check ID, invalid result, missing or empty crop, empty trace, path escape, and candidate mismatch.

- [ ] **Step 2: Verify red**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_visual_qa.py -q
```

Expected: collection error because `workflow.visual_qa` does not exist.

- [ ] **Step 3: Implement report parsing and validation**

Create immutable `VisualQACheck` and `VisualQAReport` dataclasses. Parse `ID|crop-path|pass-or-fail|trace` with `split("|", 3)`. Resolve evidence paths under the task directory, require exact instance IDs and nonempty candidate/crop files, compute report status from checks, and write/load deterministic `visual-qa.md`.

- [ ] **Step 4: Add the record command**

Add:

```text
record-visual-qa --project PROJECT --image N --candidate FILE --instance-check "ID|CROP|RESULT|TRACE"
```

The command loads the approved identity, validates the required instance set, writes `visual-qa.md`, and leaves `brief.md` pending user review.

- [ ] **Step 5: Verify and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_visual_qa.py tests/test_prompt_builder.py -q
git add workflow/visual_qa.py workflow/runner.py tests/test_visual_qa.py tests/test_prompt_builder.py
git commit -m "feat: record per-instance visual qa"
```

Expected: focused tests PASS.

### Task 3: Gate approval and next-image sequencing

**Files:**
- Modify: `workflow/runner.py`
- Modify: `workflow/projects.py`
- Modify: `tests/test_projects.py`
- Modify: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing gate tests**

Test that `approve-image` rejects missing QA, failed QA, candidate mismatch, and missing crops. Test a passing report changes only the brief status to `approved`. Update sequencing tests so a manual `approved` status without valid QA is rejected, while a passing report unlocks the next image.

- [ ] **Step 2: Verify red**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py -q
```

Expected: FAIL because approval and sequencing do not validate QA.

- [ ] **Step 3: Implement the gates**

Add:

```text
approve-image --project PROJECT --image N --candidate FILE
```

It loads `product-identity.md` and `visual-qa.md`, requires exact candidate and instance matches with every result passing, then sets the brief status to `approved`. In `prepare_image_task`, revalidate the previous task’s report and raise `ProjectError("上一张图片缺少通过的逐实例视觉质检")` on any failure.

- [ ] **Step 4: Verify and commit**

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py tests/test_visual_qa.py -q
/opt/miniconda3/bin/python3 -m pytest tests -q
git add workflow/runner.py workflow/projects.py tests/test_projects.py tests/test_prompt_builder.py
git commit -m "feat: gate image approval on visual qa"
```

Expected: all tests PASS.

### Task 4: Document the generic workflow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the contract and commands**

Document the `instance-id: description` format, examples from at least three unrelated product categories, `record-visual-qa`, `approve-image`, and the rule that manual brief status edits cannot bypass the gate.

- [ ] **Step 2: Verify and commit**

```bash
rg -n "可见部件实例|record-visual-qa|approve-image|手工" README.md
/opt/miniconda3/bin/python3 -m pytest tests -q
git add README.md
git commit -m "docs: explain generic instance qa gate"
```

Expected: terms are present and all tests PASS.

### Task 5: Regenerate and verify image 05

**Files:**
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/product-identity.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generation-v5-prompt.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v5-original.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v5.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/qa/center-spoon.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/qa/notch-spoon.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/qa/detail-spoon.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/visual-qa.md`
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/brief.md`

- [ ] **Step 1: Register three task-specific instances**

```markdown
## 可见部件实例

- center-spoon: 中央完整长勺；银色勺头 → 连续扁平银色杆 → 银色连接套 → 棕色球柄；无遮挡；木桌支撑；禁止断裂、残端或接触冒充连接
- notch-spoon: 右上合盖缺口中的勺；杯内方向金属杆 → 开放 U 形缺口 → 杯外连续金属杆 → 银色连接套 → 棕色球柄；仅勺头可在杯内遮挡；杯盖支撑球柄；禁止两截错位或套环残端
- detail-spoon: 右下完整长勺；银色勺头 → 连续扁平银色杆 → 银色连接套 → 棕色球柄；无遮挡；木桌支撑；禁止断裂、重复或独立球体
```

- [ ] **Step 2: Generate from original sources only**

Regenerate the handoff, copy it to `generation-v5-prompt.md`, and use the built-in image tool with the template plus at most four original product references. Never use a generated image as a factual reference or edit target. Save the selected original and resize it to 970×600.

- [ ] **Step 3: Create and inspect evidence crops**

Use `sips` to crop all three instances under `qa/`. Inspect at original detail and reject any candidate with a broken path or hidden critical connector.

- [ ] **Step 4: Record QA and verify**

```bash
/opt/miniconda3/bin/python3 -m workflow.runner record-visual-qa --project puppy-mug-set-20260910 --image 5 --candidate generated-image-v5.png --instance-check "center-spoon|qa/center-spoon.png|pass|银色勺头至球柄连续可追踪" --instance-check "notch-spoon|qa/notch-spoon.png|pass|杯内方向金属杆经缺口连续连接套环与球柄" --instance-check "detail-spoon|qa/detail-spoon.png|pass|右下完整长勺全链路连续"
/opt/miniconda3/bin/python3 -m pytest tests -q
sips -g pixelWidth -g pixelHeight projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v5.png
```

Expected: report status is `passed`, all tests PASS, and output is 970×600. Leave the brief pending user review; do not call `approve-image` before user confirmation.
