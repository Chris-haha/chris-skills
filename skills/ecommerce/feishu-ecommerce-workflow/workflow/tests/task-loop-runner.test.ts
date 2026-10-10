import { describe, expect, it, vi } from "vitest";
import { TaskLoopRunner } from "../src/services/task-loop-runner";

describe("TaskLoopRunner", () => {
  it("runs one poll immediately and skips overlapping polls", async () => {
    let release!: () => void;
    const firstRun = new Promise<void>((resolve) => {
      release = resolve;
    });
    const runBatch = vi
      .fn()
      .mockReturnValueOnce(firstRun)
      .mockResolvedValueOnce(undefined);

    const sleeper = vi.fn().mockResolvedValue(undefined);
    const loop = new TaskLoopRunner(runBatch, 1, sleeper);

    const firstTick = loop.tick();
    const secondTick = loop.tick();

    expect(runBatch).toHaveBeenCalledTimes(1);

    release();
    await firstTick;
    await secondTick;
    expect(runBatch).toHaveBeenCalledTimes(1);
  });

  it("starts polling immediately and uses the configured interval", async () => {
    const runBatch = vi.fn().mockResolvedValue(undefined);
    const sleep = vi.fn().mockRejectedValue(new Error("stop-loop"));
    const loop = new TaskLoopRunner(runBatch, 3, sleep);

    await expect(loop.runForever()).rejects.toThrow("stop-loop");

    expect(runBatch).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledWith(3 * 60 * 1000);
  });

  it("keeps polling after a batch error", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const runBatch = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(undefined);
    const sleep = vi
      .fn()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("stop-loop"));
    const loop = new TaskLoopRunner(runBatch, 1, sleep);

    await expect(loop.runForever()).rejects.toThrow("stop-loop");
    await Promise.resolve();

    expect(runBatch).toHaveBeenCalledTimes(2);
    expect(errorSpy).toHaveBeenCalled();

    errorSpy.mockRestore();
  });
});
