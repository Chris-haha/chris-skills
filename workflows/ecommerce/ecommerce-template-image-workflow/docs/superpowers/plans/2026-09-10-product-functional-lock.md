# Product Functional Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make functional product geometry and correct assembly/use state mandatory before any ecommerce image prompt or generation handoff can be created.

**Architecture:** Extend the existing immutable `ProductIdentity` record and Markdown serializer with two required collections. Validate them at the same generation gates already used for counts and relationships, then expose them through the CLI, prompt, handoff audit, and documentation.

**Tech Stack:** Python 3, dataclasses, argparse, pytest, Markdown project records.

---

### Task 1: Persist functional features and required use states

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_projects.py`

- [ ] Add failing round-trip tests requiring `functional_features` and `required_use_states`.
- [ ] Add failing loader tests for identity files missing either new section.
- [ ] Run `python -m pytest -q tests/test_projects.py -k product_identity` and confirm failure because the fields/sections do not exist.
- [ ] Add both fields to `ProductIdentity`, write/load `功能结构` and `必须呈现的使用状态`, and reject empty values.
- [ ] Re-run the focused tests and commit.

### Task 2: Put functional semantics into every prompt and audit

**Files:**
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_prompt_builder.py`

- [ ] Extend the test identity fixture with a lid notch and spoon-installed state.
- [ ] Add failing assertions that direct prompts and handoff audits include both categories and prohibit changing their geometry/state.
- [ ] Run `python -m pytest -q tests/test_prompt_builder.py` and confirm the new assertions fail.
- [ ] Render the two categories as prompt hard constraints and handoff audit checks.
- [ ] Re-run the focused tests and commit.

### Task 3: Require the new fields in the batch CLI and docs

**Files:**
- Modify: `workflow/runner.py`
- Modify: `README.md`
- Test: `tests/test_prompt_builder.py`

- [ ] Update the CLI test to pass `--functional-feature` and `--use-state`; assert they round-trip.
- [ ] Run the CLI test and confirm failure because the arguments do not exist.
- [ ] Add repeatable CLI arguments and required-value validation.
- [ ] Document the mandatory functional-feature/use-state inspection step.
- [ ] Run the focused and full test suites and commit.

### Task 4: Correct the mug identity and regenerate image 01

**Files:**
- Modify: `projects/puppy-mug-set-20260910/images/01-detail-banner/product-identity.md`
- Modify: `projects/puppy-mug-set-20260910/images/01-detail-banner/direct-image-prompt.md`
- Create: `projects/puppy-mug-set-20260910/images/01-detail-banner/generated-image-v3-original.png`
- Create: `projects/puppy-mug-set-20260910/images/01-detail-banner/generated-image-v3.png`

- [ ] Record the lid notch and the exact closed-lid spoon state as approved facts.
- [ ] Rebuild the direct prompt through the workflow.
- [ ] Generate one replacement through ChatGPT's built-in image route, preserving earlier versions.
- [ ] Visually verify the notch, spoon path, connected handle end, component counts, and all display copy.
- [ ] Save the original and a 970×600 delivery image.
- [ ] Run `python -m pytest -q`, dimension/hash checks, and `git diff --check` before completion.
