import { StreamEvent } from "./types";
import { StreamEventSchema } from "./schemas";

export type SSECallback = (event: StreamEvent) => void;
export type SSEErrorCallback = (error: Event) => void;
export type SSECompleteCallback = () => void;

export class StreamClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private retryCount = 0;
  private manuallyClosed = false;
  private callbacks: {
    onEvent?: SSECallback;
    onError?: SSEErrorCallback;
    onComplete?: SSECompleteCallback;
  } = {};

  constructor(runId: string) {
    const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
    this.url = `${baseUrl}/api/v1/runs/${runId}/events`;
  }

  public connect(
    onEvent: SSECallback,
    onError?: SSEErrorCallback,
    onComplete?: SSECompleteCallback
  ) {
    this.callbacks = { onEvent, onError, onComplete };
    this.manuallyClosed = false;
    this.open();
  }

  private open() {
    this.eventSource = new EventSource(this.url, { withCredentials: true });

    this.eventSource.onmessage = (e) => {
      try {
        const rawData = JSON.parse(e.data);
        const parsedEvent = StreamEventSchema.parse(rawData);
        
        if (this.callbacks.onEvent) {
          this.callbacks.onEvent(parsedEvent);
        }

        if (parsedEvent.type === "run.completed" || parsedEvent.type === "run.failed") {
          this.disconnect();
          if (this.callbacks.onComplete) {
            this.callbacks.onComplete();
          }
        }
      } catch (err) {
        console.error("Failed to parse SSE event", err);
      }
    };

    this.eventSource.onerror = (e) => {
      this.eventSource?.close();
      this.eventSource = null;
      if (!this.manuallyClosed && this.retryCount < 1) {
        this.retryCount += 1;
        window.setTimeout(() => this.open(), 800);
        return;
      }
      this.callbacks.onError?.(e);
    };
  }

  public disconnect() {
    this.manuallyClosed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
