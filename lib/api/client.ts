import { ApiRequestError } from "./errors";

const getBaseUrl = () => {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
};

export const apiClient = async <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const url = `${getBaseUrl()}${endpoint}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: options.credentials ?? "include",
    });
    
    if (!response.ok) {
      let errorData: unknown;
      try {
        errorData = await response.json();
      } catch {
        throw new ApiRequestError(
          "Network or server error",
          "NETWORK_ERROR",
          true
        );
      }
      
      if (
        typeof errorData === "object" &&
        errorData !== null &&
        "error" in errorData &&
        typeof errorData.error === "object" &&
        errorData.error !== null
      ) {
        const apiError = errorData.error as Record<string, unknown>;
        throw new ApiRequestError(
          typeof apiError.message === "string" ? apiError.message : "请求失败",
          typeof apiError.code === "string" ? apiError.code : `HTTP_${response.status}`,
          apiError.retryable !== false,
          typeof apiError.request_id === "string" ? apiError.request_id : undefined,
          typeof apiError.details === "object" && apiError.details !== null
            ? (apiError.details as Record<string, unknown>)
            : undefined
        );
      }
      if (typeof errorData === "object" && errorData !== null && "detail" in errorData) {
        const detail = errorData.detail;
        throw new ApiRequestError(
          typeof detail === "string" ? detail : "提交内容未通过服务器校验",
          `HTTP_${response.status}`,
          response.status >= 500
        );
      }
      
      throw new ApiRequestError(`API Error: ${response.statusText}`, `HTTP_${response.status}`, true);
    }
    
    if (response.status === 204) return undefined as T;
    return await response.json();
  } catch (error) {
    if (error instanceof ApiRequestError) {
      throw error;
    }
    throw new ApiRequestError(
      error instanceof Error ? error.message : "Unknown fetch error",
      "FETCH_FAILED",
      true
    );
  }
};
