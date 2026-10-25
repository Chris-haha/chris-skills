---
name: project-flow-guide
description: Quickly orient in an unfamiliar project, long docs, or noisy AI-written explanations by extracting the main flow, key roles, and a bounded drill-down path.
---
# Project Flow Guide

## Overview
Use this skill to turn a noisy project, repo, or document set into a compact mental model. Prefer structure over completeness. Answer with the main flow first, then only the details needed to support it.

## When To Use
Use this skill when the user:
- needs to understand a new or unfamiliar codebase
- is buried in long, repetitive, or hard-to-scan documentation
- wants the main flow, core logic, or key moving parts first
- asks to translate confusing names into responsibilities
- wants follow-up detail without re-expanding the whole project

Do not use it to produce a long encyclopedic overview. Do not keep adding parallel explanations when one main path is enough.

## Core Method
1. Scan the surface area first: README files, entrypoints, configs, tests, and top-level directories.
2. Identify the main flow or the smallest set of important flows, usually one and at most three.
3. Translate names into roles: class names, variables, config keys, and endpoints should become responsibilities.
4. Produce a one-page overview with the project's structure, the main flow, the key actors, and what to ignore for now.
5. On follow-up, expand only the requested branch. Do not redraw the whole project unless the new question changes the map.

## Output Shape
Default to this order:
- one-sentence summary
- main flow
- key modules or actors
- glossary of names to roles
- what not to worry about yet
- next drill-down target

## Writing Rules
- Default to Chinese when the user writes Chinese.
- Put the conclusion first.
- Keep each section short.
- Prefer tables for symbol-to-role mapping.
- Remove repetition aggressively.
- If something is uncertain, say so briefly and name the next file or area to inspect.
- When the user asks for more detail, only add the missing branch, not a second full explanation.

## Reading Passes
Use the three passes in `references/reading-passes.md` to keep the reading bounded.
Use the output contract in `references/output-contract.md` to keep follow-up answers small and maintainable.

## Common Failure Modes
- repeating the same idea in different words
- explaining every variable before the main flow is clear
- turning a focused follow-up into a full re-summary
- confusing symbol names with actual responsibilities

## Maintenance Rule
Attach new details to the existing flow. If a new detail does not change the main structure, do not let it spawn a new parallel explanation.
