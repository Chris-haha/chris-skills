# Product Visible Connectivity Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Require visible, traceable evidence for every critical product connection so occlusion cannot turn connected parts into detached-looking objects.

**Architecture:** Extend ProductIdentity with a required evidence tuple, persist it in the identity Markdown, expose it in the CLI, and inject it into generation and QA prompts. Keep semantic relationships unchanged; the new field specifies how those relationships must be visually proven.

**Tech Stack:** Python 3.13, dataclasses, argparse, pytest, Markdown artifacts.

---

### Task 1: Add failing regression tests

**Files:**
- Modify: tests/test_prompt_builder.py
- Modify: tests/test_projects.py

- [ ] **Step 1: Extend test identities**

Add visible_connection_evidence with the example “球端到勺杆必须显示银色连接套环和至少一段连续金属杆”.

- [ ] **Step 2: Assert generation and QA behavior**

Assert that the prompt contains “可见连接证据” and “遮挡前后”; assert that the handoff contains “逐项核对可见连接证据” and “端点消失”.

- [ ] **Step 3: Add empty, missing-section, and missing-CLI cases**

Add the empty identity expectation “可见连接证据不能为空”, the missing Markdown heading case, and the missing CLI expectation “visible-connection-evidence must contain”.

- [ ] **Step 4: Verify RED**

Run: /opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py tests/test_projects.py -q

Expected: collection fails because ProductIdentity does not accept visible_connection_evidence.

### Task 2: Implement the visible-connectivity lock

**Files:**
- Modify: workflow/models.py
- Modify: workflow/projects.py
- Modify: workflow/prompt_builder.py
- Modify: workflow/runner.py

- [ ] **Step 1: Add the required model field**

Add visible_connection_evidence as a tuple of strings.

- [ ] **Step 2: Persist and validate the Markdown section**

Write and load “可见连接证据”. Reject missing or empty values with “产品一致性清单的可见连接证据不能为空”.

- [ ] **Step 3: Add prompt hard rules**

Output task-specific evidence and require endpoint-to-owner tracing, visible connectors, consistent occlusion boundaries, and rejection of tangent contact masquerading as fixed connection.

- [ ] **Step 4: Add web QA hard failure rules**

Require tracing through endpoint, connector, continuous segment, occlusion boundary, and owner. Fail on broken chains, vanished endpoints, missing connectors, or ambiguous ownership.

- [ ] **Step 5: Add CLI support**

Add repeatable --visible-connection-evidence and map it through _clean_required_items.

- [ ] **Step 6: Verify GREEN**

Run: /opt/miniconda3/bin/python3 -m pytest tests/test_prompt_builder.py tests/test_projects.py -q

Expected: all focused tests pass.

### Task 3: Document, verify, and integrate

**Files:**
- Modify: README.md

- [ ] **Step 1: Document the required evidence chain**

Explain the difference between semantic relationship and visible proof, including occlusion boundaries and connector visibility.

- [ ] **Step 2: Run complete verification**

Run: /opt/miniconda3/bin/python3 -m pytest tests -q

Expected: all tests pass.

- [ ] **Step 3: Check and commit**

Run: git diff --check && git status --short

Commit: feat: enforce visible product connectivity
