# Feishu Task Sequence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sequential task creation for Feishu test records so new tasks get an increasing `task_seq`, table display stays ordered, and the workflow can create a new `iPhone Pro` test task safely.

**Architecture:** Keep task creation and task processing inside the existing Feishu adapter and task runner. Add a numeric `task_seq` field to the task model, compute the next sequence number from existing records before creating a new task, and sort records by that sequence before processing. The workflow will continue to use `owner_open_id` for mentions and `owner_display_name` for readable table output.

**Tech Stack:** TypeScript, Vitest, Feishu Bitable REST API, existing image generation and archive services.

---

### Task 1: Add `task_seq` to task data and sequence-aware reading

**Files:**
- Modify: `src/types.ts`
- Modify: `src/adapters/feishu.ts`
- Test: `tests/feishu-adapter.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it("sorts tasks by task_seq before processing", async () => {
  // mock records out of order and expect ascending task_seq order
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test tests/feishu-adapter.test.ts`
Expected: failure because `task_seq` is missing and no ordering guarantee exists.

- [ ] **Step 3: Write minimal implementation**

```ts
export type ImageTask = {
  taskSeq: number;
  // existing fields...
};
```

```ts
const taskSeq = Number(item.fields.task_seq ?? 0);
return { taskSeq, ... };
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test tests/feishu-adapter.test.ts`
Expected: pass.

### Task 2: Add sequential record creation for new test tasks

**Files:**
- Modify: `src/adapters/feishu.ts`
- Modify: `src/runner.ts`
- Test: `tests/feishu-adapter.test.ts`
- Test: `tests/e2e-smoke.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it("creates the next task with task_seq incremented by 1", async () => {
  // mock existing records with task_seq 5 and expect the created record to use 6
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test tests/feishu-adapter.test.ts`
Expected: failure because no create-task method exists yet.

- [ ] **Step 3: Write minimal implementation**

```ts
async createTask(fields: { taskId: string; productName: string; ownerOpenId: string; ownerDisplayName: string; promptTemplate: string; imageCount: number; retryCount: number; taskStatus: string; statusNote: string; taskSeq: number; }): Promise<void> {
  // read max task_seq and create the next record
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test tests/feishu-adapter.test.ts tests/e2e-smoke.test.ts`
Expected: pass.

### Task 3: Add a lightweight task-seed entrypoint for the iPhone Pro test

**Files:**
- Modify: `src/runner.ts`
- Create: `src/seed-task.ts`
- Test: `tests/e2e-smoke.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it("can seed a new iPhone Pro test task with the next task_seq", async () => {
  // invoke seed flow and assert create payload
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test tests/e2e-smoke.test.ts`
Expected: failure because seeding entrypoint does not exist.

- [ ] **Step 3: Write minimal implementation**

```ts
await adapter.createTask({
  taskId: "iphone-pro-test",
  productName: "iPhone Pro",
  // ...
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test tests/e2e-smoke.test.ts`
Expected: pass.

