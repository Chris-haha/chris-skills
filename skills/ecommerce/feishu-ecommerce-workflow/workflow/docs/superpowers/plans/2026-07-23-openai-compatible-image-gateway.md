# OpenAI Compatible Image Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support OpenAI-compatible image gateways by allowing a custom image API base URL and API key without changing the existing workflow shape.

**Architecture:** Keep `IMAGE_PROVIDER=openai` as the single real image provider mode. Extend config to accept an optional `OPENAI_BASE_URL`, pass that into the runner, and let `OpenAiImageProvider` build the SDK client with `apiKey` plus optional `baseURL`.

**Tech Stack:** TypeScript, Vitest, OpenAI Node SDK, Zod

---

### Task 1: Add failing tests for gateway configuration

**Files:**
- Modify: `tests/config.test.ts`
- Modify: `tests/runner.test.ts`

- [ ] Add a config test that proves `OPENAI_BASE_URL` is loaded when present.
- [ ] Add a runner/provider test that proves the provider can be constructed with a custom base URL.
- [ ] Run the focused tests and confirm they fail before implementation.

### Task 2: Implement minimal gateway support

**Files:**
- Modify: `src/config.ts`
- Modify: `src/runner.ts`
- Modify: `src/providers/openai-image-provider.ts`

- [ ] Extend config schema and `AppConfig` with optional `openaiBaseUrl`.
- [ ] Pass `openaiBaseUrl` from `createRunner()` into `OpenAiImageProvider`.
- [ ] Update the provider constructor to accept an optional base URL and forward it to `new OpenAI({ apiKey, baseURL })`.
- [ ] Re-run the focused tests and confirm they pass.

### Task 3: Document the new env contract

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] Add `OPENAI_BASE_URL` example and explain when to leave it empty versus when to point it at a third-party OpenAI-compatible gateway.
- [ ] Re-run the full test suite and TypeScript build to verify nothing regressed.
