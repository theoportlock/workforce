export type PositionUpdate = { node_id: string; x: number; y: number };
export type StatusUpdate = { element_type: 'node' | 'edge'; element_id: string; value: string };

type QueueOp =
  | { type: 'position'; key: string; payload: PositionUpdate }
  | { type: 'status'; key: string; payload: StatusUpdate };

type QueueKey = string;

type FlushHandlers = {
  flushPositions: (positions: PositionUpdate[]) => Promise<void>;
  flushStatuses: (updates: StatusUpdate[]) => Promise<void>;
  onFlushError?: (message: string) => void;
};

function isBridgeUnavailableError(error: unknown): boolean {
  return error instanceof Error && error.message.includes('Bridge API is unavailable');
}

export class FrontendOperationQueue {
  private readonly debounceMs: number;

  private timer: ReturnType<typeof setTimeout> | undefined;

  private readonly queuedByKey = new Map<QueueKey, QueueOp>();

  private readonly pendingByKey = new Map<QueueKey, QueueOp>();

  private readonly handlers: FlushHandlers;

  constructor(handlers: FlushHandlers, debounceMs = 100) {
    this.handlers = handlers;
    this.debounceMs = debounceMs;
  }

  enqueuePosition(update: PositionUpdate): void {
    const key = `position:${update.node_id}`;
    this.queuedByKey.set(key, { type: 'position', key, payload: update });
    this.resetTimer();
  }

  enqueueStatus(update: StatusUpdate): void {
    const key = `status:${update.element_type}:${update.element_id}`;
    this.queuedByKey.set(key, { type: 'status', key, payload: update });
    this.resetTimer();
  }

  async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }

    if (this.queuedByKey.size === 0) {
      return;
    }

    const snapshot = Array.from(this.queuedByKey.values());
    this.queuedByKey.clear();

    for (const op of snapshot) {
      this.pendingByKey.set(op.key, op);
    }

    const positionUpdates = snapshot
      .filter((op): op is Extract<QueueOp, { type: 'position' }> => op.type === 'position')
      .map((op) => op.payload);
    const statusUpdates = snapshot
      .filter((op): op is Extract<QueueOp, { type: 'status' }> => op.type === 'status')
      .map((op) => op.payload);

    if (positionUpdates.length > 0) {
      const keys = snapshot.filter((op) => op.type === 'position').map((op) => op.key);
      try {
        await this.handlers.flushPositions(positionUpdates);
      } catch (error) {
        if (!isBridgeUnavailableError(error)) {
          this.handlers.onFlushError?.(
            `Batch move failed: ${error instanceof Error ? error.message : 'unknown error'}`
          );
        }
      } finally {
        keys.forEach((key) => this.pendingByKey.delete(key));
      }
    }

    if (statusUpdates.length > 0) {
      const keys = snapshot.filter((op) => op.type === 'status').map((op) => op.key);
      try {
        await this.handlers.flushStatuses(statusUpdates);
      } catch (error) {
        if (!isBridgeUnavailableError(error)) {
          this.handlers.onFlushError?.(
            `Status batch failed: ${error instanceof Error ? error.message : 'unknown error'}`
          );
        }
      } finally {
        keys.forEach((key) => this.pendingByKey.delete(key));
      }
    }
  }

  clearPendingPosition(nodeId: string): void {
    const key = `position:${nodeId}`;
    this.pendingByKey.delete(key);
    this.queuedByKey.delete(key);
  }

  clearPendingStatus(elementType: 'node' | 'edge', elementId: string): void {
    const key = `status:${elementType}:${elementId}`;
    this.pendingByKey.delete(key);
    this.queuedByKey.delete(key);
  }

  dispose(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
    this.queuedByKey.clear();
    this.pendingByKey.clear();
  }

  private resetTimer(): void {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      void this.flush();
    }, this.debounceMs);
  }
}
