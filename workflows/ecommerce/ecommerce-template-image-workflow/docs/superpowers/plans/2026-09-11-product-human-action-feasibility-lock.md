# Product Human Action Feasibility Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make anatomically and operationally feasible human interaction a mandatory generation and QA constraint.

**Architecture:** Extend `ProductIdentity` with a required human-interaction tuple, persist it in the Markdown lock, expose it through the CLI, then inject both task-specific and generic feasibility rules into prompts and handoff QA. Preserve all existing source-truth and physical-plausibility gates.

**Tech Stack:** Python 3.13, dataclasses, argparse, pytest, Markdown artifacts.

---

### Task 1: Add regression tests for the human-action lock

**Files:**
- Modify: `tests/test_prompt_builder.py`
- Modify: `tests/test_projects.py`

- [ ] **Step 1: Extend test identities with `human_interaction_constraints`**

```python
human_interaction_constraints=("单人操作；左右手方向、腕部姿态和动作时序必须可执行",)
```

- [ ] **Step 2: Assert prompt and handoff rules**

```python
assert "人物与动作可行性" in prompt
assert "同一人可独立完成" in prompt
assert "逐项核对人物与动作可行性" in text
```

- [ ] **Step 3: Add missing/empty field and CLI cases**

```python
(_identity(human_interaction_constraints=()), "人物与动作可行性不能为空")
("--human-interaction-constraint", "human-interaction-constraint must contain")
```

- [ ] **Step 4: Run focused tests and verify RED**

Run: `/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py tests/test_projects.py -q`

Expected: FAIL because `ProductIdentity` does not yet accept the new field.

### Task 2: Implement storage, validation, prompting, and CLI support

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/runner.py`

- [ ] **Step 1: Add the required dataclass field**

```python
human_interaction_constraints: tuple[str, ...]
```

- [ ] **Step 2: Persist and validate the Markdown section**

```python
"人物与动作可行性": identity.human_interaction_constraints
```

Reject missing or empty values with `产品一致性清单的人物与动作可行性不能为空`.

- [ ] **Step 3: Add direct-prompt hard rules**

Include the task-specific list and the generic rule covering actor count, handedness, palm/thumb orientation, wrist rotation, arm entry direction, grip point, joint feasibility, and action sequence. Prefer one visible hand when one hand is sufficient.

- [ ] **Step 4: Add handoff QA**

Include a checklist line for actor count, left/right hand roles, entry direction, grip point, joint posture, and action sequence. Treat impossible or mismatched hands as hard failure.

- [ ] **Step 5: Add CLI argument and constructor mapping**

```python
product_identity.add_argument("--human-interaction-constraint", action="append", default=[])
```

Pass it through `_clean_required_items`.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py tests/test_projects.py -q`

Expected: all focused tests pass.

### Task 3: Document and verify the upgraded workflow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the new required review dimension and CLI option**

Explain that a generation cannot start until actor count, hand roles, reach, joint posture, grip, and action order are explicit.

- [ ] **Step 2: Run the full suite**

Run: `/opt/miniconda3/bin/python3 -m pytest tests -q`

Expected: all tests pass.

- [ ] **Step 3: Review the diff and commit**

Run: `git diff --check && git status --short`

Commit: `feat: enforce human action feasibility`
