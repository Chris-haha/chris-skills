type Sleep = (ms: number) => Promise<void>;

const defaultSleep: Sleep = (ms) =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

export class TaskLoopRunner {
  private running = false;

  constructor(
    private readonly runBatch: () => Promise<void>,
    private readonly intervalMinutes: number,
    private readonly sleep: Sleep = defaultSleep,
  ) {}

  async tick(): Promise<void> {
    if (this.running) {
      return;
    }

    this.running = true;

    try {
      await this.runBatch();
    } finally {
      this.running = false;
    }
  }

  async runForever(): Promise<void> {
    void this.runSafely();

    while (true) {
      await this.sleep(this.intervalMinutes * 60 * 1000);
      void this.runSafely();
    }
  }

  private async runSafely(): Promise<void> {
    try {
      await this.tick();
    } catch (error) {
      console.error("[TaskLoopRunner] Poll failed", error);
    }
  }
}
