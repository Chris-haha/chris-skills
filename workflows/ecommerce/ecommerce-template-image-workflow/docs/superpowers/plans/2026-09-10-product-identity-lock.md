# Product Identity Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent ecommerce image generation until an approved product component inventory and relationship map exists, and inject that identity lock into prompts and review packets.

**Architecture:** Add a `ProductIdentity` value object and fixed-format Markdown persistence in `workflow.projects`. Gate both handoff creation and gateway generation on an approved identity with no unresolved questions. Pass the identity into the prompt builder so counts, relationships, and forbidden inventions become explicit hard constraints shared by every generation route.

**Tech Stack:** Python 3, dataclasses, argparse, pathlib, pytest, Markdown project artifacts.

---

### Task 1: Product identity model and Markdown persistence

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_projects.py`

- [ ] **Step 1: Write failing round-trip and validation tests**

Add imports for `ProductIdentity`, `load_product_identity`, and `write_product_identity`, then add:

```python
def test_product_identity_round_trips_component_relationship_and_forbidden_rules(tmp_path: Path) -> None:
    identity = ProductIdentity(
        components=("1 个杯子", "1 个杯盖", "1 把完整长勺"),
        relationships=("棕色球形末端固定连接在金属勺杆上",),
        forbidden_inventions=("独立的棕色球形摆件",),
        unknowns=(),
        approved=True,
    )

    path = write_product_identity(tmp_path, identity)

    assert path.name == "product-identity.md"
    assert load_product_identity(path) == identity


def test_product_identity_rejects_empty_required_sections(tmp_path: Path) -> None:
    path = tmp_path / "product-identity.md"
    path.write_text(
        "# 产品一致性清单\n\n- 状态: approved\n\n"
        "## 部件与数量\n\n- 无\n\n"
        "## 部件关系\n\n- 无\n\n"
        "## 禁止出现\n\n- 无\n\n"
        "## 待用户确认\n\n- 无\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectError, match="部件与数量"):
        load_product_identity(path)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/test_projects.py -k product_identity
```

Expected: collection/import failure because `ProductIdentity` and the persistence functions do not exist.

- [ ] **Step 3: Add the immutable data model**

Append to `workflow/models.py`:

```python
@dataclass(frozen=True)
class ProductIdentity:
    """User-approved product inventory and component relationship lock."""

    components: tuple[str, ...]
    relationships: tuple[str, ...]
    forbidden_inventions: tuple[str, ...]
    unknowns: tuple[str, ...] = ()
    approved: bool = False
```

- [ ] **Step 4: Add fixed-format Markdown write/load functions**

Add to `workflow.projects`:

```python
def write_product_identity(task_directory: Path, identity: ProductIdentity) -> Path:
    task_directory.mkdir(parents=True, exist_ok=True)
    sections = {
        "部件与数量": identity.components,
        "部件关系": identity.relationships,
        "禁止出现": identity.forbidden_inventions,
        "待用户确认": identity.unknowns,
    }
    blocks = []
    for heading, values in sections.items():
        items = "\n".join(f"- {value}" for value in values) or "- 无"
        blocks.append(f"## {heading}\n\n{items}")
    status = "approved" if identity.approved else "pending_user_confirmation"
    path = task_directory / "product-identity.md"
    path.write_text(
        f"# 产品一致性清单\n\n- 状态: {status}\n\n" + "\n\n".join(blocks) + "\n",
        encoding="utf-8",
    )
    return path


def _identity_section(lines: list[str], heading: str) -> tuple[str, ...]:
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError as error:
        raise ProjectError(f"产品一致性清单缺少区块：{heading}") from error
    values = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- ") and line[2:] != "无":
            values.append(line[2:].strip())
    return tuple(value for value in values if value)


def load_product_identity(path: Path) -> ProductIdentity:
    lines = path.read_text(encoding="utf-8").splitlines()
    status = next(
        (line.removeprefix("- 状态: ") for line in lines if line.startswith("- 状态: ")),
        None,
    )
    if status not in {"approved", "pending_user_confirmation"}:
        raise ProjectError("产品一致性清单状态无效")
    components = _identity_section(lines, "部件与数量")
    relationships = _identity_section(lines, "部件关系")
    forbidden = _identity_section(lines, "禁止出现")
    if not components:
        raise ProjectError("产品一致性清单的部件与数量不能为空")
    if not relationships:
        raise ProjectError("产品一致性清单的部件关系不能为空")
    if not forbidden:
        raise ProjectError("产品一致性清单的禁止出现不能为空")
    return ProductIdentity(
        components=components,
        relationships=relationships,
        forbidden_inventions=forbidden,
        unknowns=_identity_section(lines, "待用户确认"),
        approved=status == "approved",
    )
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run `pytest -q tests/test_projects.py -k product_identity`.

Expected: `2 passed`.

### Task 2: Generation gate and identity-aware prompts

**Files:**
- Modify: `workflow/projects.py`
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/runner.py`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing gate and prompt tests**

Add tests covering missing, pending, unresolved, and approved identities:

```python
def _identity(*, approved: bool = True, unknowns: tuple[str, ...] = ()) -> ProductIdentity:
    return ProductIdentity(
        components=("1 个杯子", "1 个杯盖", "1 把完整长勺",),
        relationships=("棕色球形末端固定连接在金属勺杆上，属于同一把勺子",),
        forbidden_inventions=("独立的棕色球形摆件", "第二把勺子",),
        unknowns=unknowns,
        approved=approved,
    )


def test_build_direct_image_prompt_includes_product_identity_hard_constraints() -> None:
    prompt = build_direct_image_prompt(
        _template(), ["product-front.png"], "展示杯具", product_identity=_identity()
    )

    assert "产品一致性硬约束" in prompt
    assert "1 把完整长勺" in prompt
    assert "棕色球形末端固定连接" in prompt
    assert "独立的棕色球形摆件" in prompt
    assert "不得拆分、复制、合并或新增" in prompt


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        (_identity(approved=False), "尚未获得用户确认"),
        (_identity(unknowns=("球形部件属于哪里？",)), "球形部件属于哪里"),
    ],
)
def test_validate_product_identity_blocks_unapproved_or_unknown(identity, message: str) -> None:
    with pytest.raises(ProjectError, match=message):
        validate_product_identity(identity)


def test_write_web_handoff_command_requires_product_identity(tmp_path: Path, monkeypatch) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main([
        "prepare-image", "--project", "demo", "--platform", "amazon",
        "--role", "selling-point image", "--ratio", "1:1",
        "--product-reference", "product.png", "--request", "show detail",
    ])

    result = runner.main([
        "write-web-handoff", "--project", "demo", "--image", "1",
        "--objective", "展示材质细节",
    ])

    assert result == 1
    assert not (tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "direct-image-prompt.md").exists()
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_prompt_builder.py`.

Expected: failures because identity validation and prompt support are absent.

- [ ] **Step 3: Add identity validation and prompt sections**

Add to `workflow.projects`:

```python
def validate_product_identity(identity: ProductIdentity) -> None:
    if not identity.approved:
        raise ProjectError("产品一致性清单尚未获得用户确认，禁止生图")
    if identity.unknowns:
        questions = "；".join(identity.unknowns)
        raise ProjectError(f"产品仍有待用户确认的问题，禁止生图：{questions}")
```

Change `build_direct_image_prompt` to require `product_identity: ProductIdentity`, validate it, and insert:

```python
identity_section = f"""## 产品一致性硬约束

部件与精确数量：
{_list_items(product_identity.components)}

连接与从属关系：
{_list_items(product_identity.relationships)}

明确不存在、严禁生成：
{_list_items(product_identity.forbidden_inventions)}

严格按以上清单生成；不得拆分、复制、合并或新增任何产品部件。参考图角度或遮挡造成歧义时，以本清单为准，不得猜测。
"""
```

- [ ] **Step 4: Gate both generation routes**

In `_write_web_handoff`, require `task_path / "product-identity.md"`, load and validate it, then pass it to `build_direct_image_prompt` and `write_web_handoff`. In `_generate_codex`, repeat the same load and validation before reading gateway configuration. This defense-in-depth prevents a stale direct prompt from bypassing the gate.

- [ ] **Step 5: Add identity audit to the handoff packet**

Extend `write_web_handoff` with:

```python
identity_review = f"""
## 产品一致性检查

- 逐项核对部件数量：{'；'.join(product_identity.components)}
- 逐项核对连接关系：{'；'.join(product_identity.relationships)}
- 确认未出现：{'；'.join(product_identity.forbidden_inventions)}
- 任一项不符时保留失败图并只重做当前图片，不得批准或继续下一张。
"""
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run `pytest -q tests/test_prompt_builder.py`.

Expected: all prompt-builder tests pass after existing calls are updated with approved identities.

### Task 3: CLI command and documentation

**Files:**
- Modify: `workflow/runner.py`
- Modify: `README.md`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing CLI test**

```python
def test_set_product_identity_command_writes_reviewable_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    task = tmp_path / "projects" / "demo" / "images" / "01-main-image"
    task.mkdir(parents=True)

    result = runner.main([
        "set-product-identity", "--project", "demo", "--image", "1",
        "--component", "1 个杯子", "--component", "1 把完整长勺",
        "--relationship", "球形末端连接在勺杆上",
        "--forbid", "独立球形摆件", "--approved",
    ])

    text = (task / "product-identity.md").read_text(encoding="utf-8")
    assert result == 0
    assert "状态: approved" in text
    assert "球形末端连接在勺杆上" in text
```

- [ ] **Step 2: Run the test and verify RED**

Run `pytest -q tests/test_prompt_builder.py::test_set_product_identity_command_writes_reviewable_file`.

Expected: argparse rejects the unknown command.

- [ ] **Step 3: Implement `set-product-identity`**

Add a parser with repeatable `--component`, `--relationship`, `--forbid`, and `--unknown` flags plus `--approved`. `_set_product_identity` resolves the current task, creates `ProductIdentity`, writes the file, and prints its path.

- [ ] **Step 4: Update README workflow order**

Document that agents must inspect all reference views, record counts and relationships, ask only about unresolved facts, run `set-product-identity`, and cannot create a handoff or generate while the file is missing, pending, or contains unknowns.

- [ ] **Step 5: Run focused and full tests**

Run:

```bash
pytest -q tests/test_prompt_builder.py tests/test_projects.py
pytest -q
```

Expected: all tests pass.

### Task 4: Record the corrected mug identity and regenerate image 01

**Files:**
- Create: `projects/puppy-mug-set-20260910/product-references/spoon-rounded-end-detail.png`
- Create: `projects/puppy-mug-set-20260910/images/01-detail-banner/product-identity.md`
- Create: `projects/puppy-mug-set-20260910/images/01-detail-banner/generated-image-v2-original.png`
- Create: `projects/puppy-mug-set-20260910/images/01-detail-banner/generated-image-v2.png`
- Modify: `projects/puppy-mug-set-20260910/images/01-detail-banner/direct-image-prompt.md`
- Modify: `projects/puppy-mug-set-20260910/images/01-detail-banner/brief.md`

- [ ] **Step 1: Preserve the new close-up reference**

Copy the supplied spoon-end close-up into the project reference directory with the stable name `spoon-rounded-end-detail.png`.

- [ ] **Step 2: Write the approved identity through the CLI**

Run the exact `set-product-identity` command from the design specification, including all component counts, the spoon relationship, and four forbidden-invention rules.

- [ ] **Step 3: Rebuild the direct prompt**

Generate an identity-aware prompt using the selected `feature-hero` template, the three original views, and the spoon close-up. The prompt must say there is exactly one complete spoon; its brown sphere remains attached to the metal shaft; the lid has only the puppy knob; no second sphere or second spoon may appear.

- [ ] **Step 4: Generate non-destructively with the built-in image tool**

Use the ChatGPT built-in image generation route requested by the user. Preserve the old image and save the new output as `generated-image-v2-original.png`; derive the 970×600 delivery as `generated-image-v2.png`.

- [ ] **Step 5: Perform the product-identity audit**

Inspect the output at original resolution and fail it unless all conditions hold: one mug, one lid, one puppy lid knob, one complete spoon, brown sphere attached to the spoon, no sphere on the lid, no duplicated spoon, unchanged mug artwork/color/shape, approved copy only, and no unsupported claims.

- [ ] **Step 6: Verify delivery files and status**

Run file existence checks, `sips` dimension inspection, SHA-256 hashes, the full pytest suite, and `git diff --check`. Update `brief.md` to `generated_v2_pending_user_approval` only after every check passes.
