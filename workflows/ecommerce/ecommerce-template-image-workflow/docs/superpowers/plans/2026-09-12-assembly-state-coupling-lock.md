# Product Assembly-State Coupling Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent product images from combining mutually exclusive detached and installed states, then regenerate image 05 with a physically valid assembled spoon-notch close-up.

**Architecture:** Extend `ProductIdentity` with a required `assembly_state_evidence` tuple that round-trips through Markdown and the CLI. Inject task-specific evidence plus generic state-coupling rules into both the direct generation prompt and the web QA handoff, so local connectivity cannot pass when the overall assembly state is impossible.

**Tech Stack:** Python 3.13 dataclasses, argparse, Markdown task files, pytest, built-in image generation, macOS `sips`.

---

### Task 1: Add the required assembly-state evidence field

**Files:**
- Modify: `workflow/models.py:87-103`
- Modify: `workflow/projects.py:207-329`
- Test: `tests/test_projects.py:201-285`

- [ ] **Step 1: Write failing round-trip and missing-section tests**

Add `assembly_state_evidence` to the valid fixture:

```python
assembly_state_evidence=(
    "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
),
```

Add `("装配状态证据", "装配状态证据")` to `test_product_identity_rejects_missing_functional_sections`, add this section to its Markdown fixture, and add an empty-section assertion:

```python
with pytest.raises(ProjectError, match="装配状态证据"):
    load_product_identity(path)
```

- [ ] **Step 2: Run the focused tests and verify red**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py -q
```

Expected: FAIL because `ProductIdentity` does not accept `assembly_state_evidence` and the loader does not require the section.

- [ ] **Step 3: Implement the minimal model and Markdown changes**

Add the field after `required_use_states`:

```python
assembly_state_evidence: tuple[str, ...]
```

Add the section to `write_product_identity`:

```python
"装配状态证据": identity.assembly_state_evidence,
```

Load, validate, and return it in `load_product_identity`:

```python
assembly_state_evidence = _identity_section(lines, "装配状态证据")
if not assembly_state_evidence:
    raise ProjectError("产品一致性清单的装配状态证据不能为空")
```

Add the same nonempty check to `validate_product_identity`.

- [ ] **Step 4: Run focused tests and verify green**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py -q
```

Expected: all `tests/test_projects.py` tests PASS.

- [ ] **Step 5: Commit the schema change**

```bash
git add workflow/models.py workflow/projects.py tests/test_projects.py
git commit -m "feat: require assembly state evidence"
```

### Task 2: Expose the evidence through the CLI

**Files:**
- Modify: `workflow/runner.py:202-232`
- Modify: `workflow/runner.py` in the `set-product-identity` parser definition
- Test: `tests/test_prompt_builder.py:345-396`

- [ ] **Step 1: Write a failing CLI persistence test**

Add this argument to `test_set_product_identity_command_writes_approved_inventory`:

```python
"--assembly-state-evidence",
"合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
```

Assert:

```python
assert identity.assembly_state_evidence == (
    "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
)
```

- [ ] **Step 2: Run the focused test and verify red**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py::test_set_product_identity_command_writes_approved_inventory -q
```

Expected: FAIL because argparse does not recognize `--assembly-state-evidence`.

- [ ] **Step 3: Add the CLI argument and mapping**

Register a repeatable required argument using the existing product identity parser pattern:

```python
parser.add_argument("--assembly-state-evidence", action="append", required=True)
```

Map it in `_product_identity_from_args`:

```python
assembly_state_evidence=_clean_required_items(
    args.assembly_state_evidence, "assembly-state-evidence"
),
```

- [ ] **Step 4: Run the focused test and verify green**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py::test_set_product_identity_command_writes_approved_inventory -q
```

Expected: PASS.

- [ ] **Step 5: Commit the CLI change**

```bash
git add workflow/runner.py tests/test_prompt_builder.py
git commit -m "feat: capture assembly state evidence"
```

### Task 3: Enforce state coupling in prompts and QA

**Files:**
- Modify: `workflow/prompt_builder.py:15-75`
- Modify: `workflow/projects.py:430-463`
- Test: `tests/test_prompt_builder.py:20-110`
- Test: `tests/test_prompt_builder.py:180-205`

- [ ] **Step 1: Write failing prompt and handoff assertions**

Update the shared `_identity` fixture with `assembly_state_evidence`, then assert the direct prompt contains:

```python
assert "装配状态证据" in prompt
assert "同一功能交互中的主体与参与部件必须处于同一个真实装配状态" in prompt
assert "已拆卸部件不能同时演示只有安装后才成立的使用关系" in prompt
assert "不得生成封闭孔洞、桥状假结构或实体穿透" in prompt
```

Assert the web handoff contains:

```python
assert "场景状态、承载主体、功能结构、交互部件路径、支撑来源和遮挡一致性" in text
assert "混合互斥装配状态" in text
```

- [ ] **Step 2: Run the focused tests and verify red**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py -q
```

Expected: FAIL on the new prompt and QA assertions.

- [ ] **Step 3: Add direct-prompt rules**

After the use-state list, render:

```python
装配状态证据：
{_list_items(product_identity.assembly_state_evidence)}

同一功能交互中的主体与参与部件必须处于同一个真实装配状态。已拆卸部件不能同时演示只有安装后才成立的使用关系。功能通道必须保持原始开放边界，不得生成封闭孔洞、桥状假结构或实体穿透。进入容器的部件必须从容器开口或已经确认的功能通道进入，遮挡方向必须与进入路径一致。无法同时证明装配状态和交互路径时，必须调整机位或取消该交互演示。
```

- [ ] **Step 4: Add web-handoff QA and hard failures**

Add a checklist line:

```python
- 逐项追踪装配状态证据，包括场景状态、承载主体、功能结构、交互部件路径、支撑来源和遮挡一致性：{'；'.join(product_identity.assembly_state_evidence)}
```

Extend the hard-failure sentence with `混合互斥装配状态、功能主体未安装、交互路径错误、开放结构被画成封闭孔洞或桥状假结构`.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py -q
/opt/miniconda3/bin/python3 -m pytest tests -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit prompt enforcement**

```bash
git add workflow/prompt_builder.py workflow/projects.py tests/test_prompt_builder.py
git commit -m "feat: enforce coupled assembly states"
```

### Task 4: Document the mandatory workflow gate

**Files:**
- Modify: `README.md:90-130`

- [ ] **Step 1: Update the product identity workflow documentation**

Document that every functional interaction must state the assembly state, host, interacting component, spatial path, support source, and mutually exclusive states. Add `--assembly-state-evidence` to the CLI example.

- [ ] **Step 2: Add the QA rejection rule**

State that an image fails if it mixes installed and detached states, shows a functional interaction without its installed host, routes a part through the wrong surface, or closes an originally open channel.

- [ ] **Step 3: Verify documentation and tests**

Run:

```bash
rg -n "装配状态证据|assembly-state-evidence|互斥装配状态" README.md
/opt/miniconda3/bin/python3 -m pytest tests -q
```

Expected: all three terms are present and all tests PASS.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md
git commit -m "docs: explain assembly state gate"
```

### Task 5: Regenerate image 05 from original truth sources

**Files:**
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/product-identity.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generation-v4-prompt.md`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v4-original.png`
- Create: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v4.png`
- Modify: `projects/puppy-mug-set-20260910/images/05-详情页横幅图/brief.md`

- [ ] **Step 1: Add task-specific assembly-state evidence**

Add an approved “装配状态证据” section containing these facts:

```markdown
- 右上功能特写处于真实合盖使用状态：杯体承托杯盖，杯盖同心安装在杯口，不能平放桌面或脱离杯体
- 扁平银色勺杆从杯内经过向外开放的 U 形缺口延伸到杯外；勺头在杯内自然遮挡，连接套环与棕色球柄在杯外
- 棕色球柄由杯盖上表面稳定支撑；勺杆不得从杯盖底面、桌面缝隙或陶瓷实体中穿过
- 中央开放陈列与右上合盖特写是同一产品的两个独立摄影状态，不得在单个局部画面内混合两种状态
```

- [ ] **Step 2: Regenerate the direct prompt and write v4 prompt**

Run:

```bash
/opt/miniconda3/bin/python3 -m workflow.runner write-web-handoff \
  --project puppy-mug-set-20260910 \
  --image 5 \
  --objective "展示杯身原始小狗花纹、真实合盖状态下的开放式勺杆缺口、小狗杯盖钮和完整长勺"
cp projects/puppy-mug-set-20260910/images/05-详情页横幅图/direct-image-prompt.md \
  projects/puppy-mug-set-20260910/images/05-详情页横幅图/generation-v4-prompt.md
```

Verify that `generation-v4-prompt.md` contains the exact right-top assembled-state requirements and explicitly says only the template and original files under `product-references/` are image inputs; v1-v3 outputs are excluded.

- [ ] **Step 3: Generate one v4 image through the built-in image tool**

Use case: `infographic-diagram`. Reference the ingredient-grid template for layout and these original product truth sources for the product:

```text
product-front-with-accessories.jpg
product-front-pattern-detail.jpg
product-front-with-lid.jpg
lid-spoon-notch-detail.jpg
spoon-rounded-end-detail.png
```

Generate the whole banner from scratch. Do not use any generated-image file as a reference or edit target. Copy the selected built-in output into the task directory as `generated-image-v4-original.png`.

- [ ] **Step 4: Resize and perform visual QA**

Resize non-destructively:

```bash
sips -z 600 970 generated-image-v4-original.png --out generated-image-v4.png
```

Inspect the full image and a crop of the right-top card. Reject unless all of these are visible:

```text
cup wall below lid; lid seated on mug rim; open U-shaped edge notch;
flat metal handle travelling from inside cup through notch to outside;
brown ball handle outside and supported by lid; no tabletop under detached lid;
no tunnel, bridge, solid-ceramic penetration, or mutually exclusive state.
```

- [ ] **Step 5: Record QA and run final verification**

Mark v3 failed in `brief.md` with the detached/installed state conflict and add v4 QA. Run:

```bash
/opt/miniconda3/bin/python3 -m pytest tests -q
/opt/miniconda3/bin/python3 - <<'PY'
from pathlib import Path
from workflow.projects import load_product_identity, validate_product_identity
p = Path('projects/puppy-mug-set-20260910/images/05-详情页横幅图/product-identity.md')
identity = load_product_identity(p)
validate_product_identity(identity)
assert len(identity.assembly_state_evidence) == 4
print('identity_ok', len(identity.assembly_state_evidence))
PY
sips -g pixelWidth -g pixelHeight projects/puppy-mug-set-20260910/images/05-详情页横幅图/generated-image-v4.png
```

Expected: full tests PASS, identity prints `identity_ok 4`, and image dimensions are `970 × 600`.

- [ ] **Step 6: Preserve project artifacts without sweeping unrelated changes**

The entire `projects/puppy-mug-set-20260910/` directory is currently untracked in the enclosing repository. Leave the image task artifacts untracked and report their absolute paths; do not sweep this directory or unrelated workspace changes into a commit.
