# Product Physical Plausibility Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make gravity, support, contact, and stable resting poses mandatory product-generation facts.

**Architecture:** Extend the existing immutable `ProductIdentity` and Markdown schema with one required physical-constraints field. Propagate it through validation, prompt construction, web QA, CLI input, and documentation while preserving current module boundaries.

**Tech Stack:** Python 3.13, dataclasses, argparse, pytest, Markdown.

---

### Task 1: Persist and validate physical constraints

**Files:**
- Modify: `workflow/models.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_projects.py`
- Test: `tests/test_prompt_builder.py`

- [ ] Add `physical_constraints` to test identities and round-trip assertions.
- [ ] Add failing tests for a missing Markdown section and an empty tuple.
- [ ] Run `/opt/miniconda3/bin/python3 -m pytest tests/test_projects.py tests/test_prompt_builder.py -q` and confirm failure because the field does not exist.
- [ ] Add the dataclass field, Markdown section, loader parsing, and non-empty validation.
- [ ] Re-run the focused tests and confirm they pass.

### Task 2: Add prompt and delivery gates

**Files:**
- Modify: `workflow/prompt_builder.py`
- Modify: `workflow/projects.py`
- Test: `tests/test_prompt_builder.py`

- [ ] Add failing assertions for physical constraints, gravity, support contacts, and unsupported suspension rejection.
- [ ] Add failing handoff assertions for physical-plausibility QA.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Add the minimal prompt and handoff text needed to satisfy the assertions.
- [ ] Re-run the focused tests and confirm they pass.

### Task 3: Require physical constraints in CLI

**Files:**
- Modify: `workflow/runner.py`
- Modify: `README.md`
- Test: `tests/test_prompt_builder.py`

- [ ] Extend the successful CLI test with `--physical-constraint` and assert persistence.
- [ ] Add a failing CLI test for the missing option.
- [ ] Add the argparse option and map it through `_clean_required_items`.
- [ ] Document the new required field and a stable-support example.
- [ ] Run `/opt/miniconda3/bin/python3 -m pytest tests -q` and confirm all tests pass.

### Task 4: Integrate

**Files:**
- Modify: no additional files

- [ ] Run `git diff --check` and inspect the scoped diff.
- [ ] Commit the workflow change.
- [ ] Fast-forward the local `master` branch and rerun the full test suite there.

