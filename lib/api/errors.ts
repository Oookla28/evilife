export class ApiRequestError extends Error {
  public code: string;
  public requestId?: string;
  public retryable: boolean;
  public details?: Record<string, unknown>;

  constructor(
    message: string,
    code: string = "UNKNOWN_ERROR",
    retryable: boolean = false,
    requestId?: string,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.retryable = retryable;
    this.requestId = requestId;
    this.details = details;
  }
}
