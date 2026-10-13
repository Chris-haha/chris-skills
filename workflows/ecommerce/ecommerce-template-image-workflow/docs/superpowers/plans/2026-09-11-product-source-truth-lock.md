# Product Source Truth Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make original product references and surface graphics mandatory, generation-blocking product facts.

**Architecture:** Extend the existing immutable `ProductIdentity` schema and Markdown persistence, then propagate the fields through validation, prompt construction, web handoff QA, and CLI input. Preserve current module boundaries and add no new service layer.

**Tech Stack:** Python 3.13, dataclasses, argparse, pytest, Markdown files.

---

### Task 1: Persist and validate source truth

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_projects.py`

- [ ] Add failing round-trip tests for `truth_sources` and `surface_graphics`.
- [ ] Add failing validation tests for each missing field.
- [ ] Run `/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py -q` and confirm the new assertions fail because the fields do not exist.
- [ ] Add both tuple fields, Markdown sections, loader parsing, and non-empty validation.
- [ ] Re-run the focused tests and confirm they pass.

### Task 2: Enforce facts in prompts and handoff QA

**Files:**
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_prompt_builder.py`

- [ ] Add failing prompt assertions for original-reference authority, surface-pattern fidelity, and rejection of historical generated images as product facts.
- [ ] Add failing handoff assertions for source and surface-graphic QA checks.
- [ ] Run `/opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py -q` and confirm expected failures.
- [ ] Add the smallest prompt and handoff text required to satisfy the assertions.
- [ ] Re-run focused tests and confirm they pass.

### Task 3: Expose required CLI inputs

**Files:**
- Modify: `workflow/runner.py`
- Test: `tests/test_prompt_builder.py`

- [ ] Extend the CLI test with repeated `--truth-source` and `--surface-graphic` arguments and assert persisted values.
- [ ] Add a failing test showing either missing argument blocks identity creation.
- [ ] Run the focused test and confirm the failure is caused by absent parser/model support.
- [ ] Add both argparse options and map them through `_clean_required_items`.
- [ ] Re-run focused tests and confirm they pass.

### Task 4: Verify the workflow

**Files:**
- Modify: `README.md`

- [ ] Update the CLI example and explain that original references are the only product-fact authority.
- [ ] Run `/opt/miniconda3/bin/python3 -m pytest tests -q` and confirm all tests pass.
- [ ] Review the diff for unrelated changes and commit the scoped workflow upgrade.

