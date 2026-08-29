import { http } from '@kit.NetworkKit';

export class ApiError extends Error {
  readonly statusCode: number;
  readonly detail: string;

  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
    this.detail = message;
  }
}

/**
 * 全局 HTTP 客户端：复用同一个 HttpRequest 以保留服务端下发的会话 Cookie，
 * 这样设备配对 claim 之后即可保持网页账号登录态。
 */
export class ApiClient {
  private static sharedClient: ApiClient | null = null;

  private readonly client: http.HttpRequest;
  private serverAddress: string;

  private constructor(serverAddress: string) {
    this.serverAddress = serverAddress;
    this.client = http.createHttp();
  }

  static shared(): ApiClient {
    if (ApiClient.sharedClient === null) {
      ApiClient.sharedClient = new ApiClient('http://172.20.10.10:8010');
    }
    return ApiClient.sharedClient;
  }

  static reset(): void {
    if (ApiClient.sharedClient !== null) {
      ApiClient.sharedClient.client.destroy();
      ApiClient.sharedClient = null;
    }
  }

  get server(): string {
    return this.serverAddress;
  }

  setServer(address: string): void {
    const trimmed = address.trim();
    if (trimmed.length === 0) {
      return;
    }
    this.serverAddress = trimmed.endsWith('/')
      ? trimmed.substring(0, trimmed.length - 1)
      : trimmed;
  }

  async postJson(path: string, body: Record<string, Object>): Promise<Record<string, Object>> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: {
        'Content-Type': 'application/json'
      },
      extraData: JSON.stringify(body),
      connectTimeout: 15000,
      readTimeout: 60000
    };
    return await this.request(this.serverAddress + path, options);
  }

  async postForm(path: string, form: string): Promise<Record<string, Object>> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      extraData: form,
      connectTimeout: 15000,
      readTimeout: 120000
    };
    return await this.request(this.serverAddress + path, options);
  }

  /** 上传到配对二维码中的绝对地址（可能不在当前服务器上）。 */
  async postAbsoluteJson(url: string, body: Record<string, Object>): Promise<Record<string, Object>> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: {
        'Content-Type': 'application/json'
      },
      extraData: JSON.stringify(body),
      connectTimeout: 15000,
      readTimeout: 60000
    };
    return await this.request(url, options);
  }

  private async request(url: string, options: http.HttpRequestOptions): Promise<Record<string, Object>> {
    const response = await this.client.request(url, options);
    if (response.responseCode >= 200 && response.responseCode < 300) {
      return ApiClient.toRecord(response.result);
    }
    throw new ApiError(response.responseCode, ApiClient.errorDetail(response.result));
  }

  static toRecord(result: Object | string | ArrayBuffer): Record<string, Object> {
    if (typeof result === 'string') {
      try {
        const parsed = JSON.parse(result) as Record<string, Object>;
        if (parsed !== null) {
          return parsed;
        }
      } catch (err) {
        // 非 JSON 响应，按空对象处理
      }
    }
    return {};
  }

  static errorDetail(result: Object | string | ArrayBuffer): string {
    if (typeof result === 'string') {
      try {
        const parsed = JSON.parse(result) as Record<string, Object>;
        const detail = parsed['detail'];
        if (typeof detail === 'string' && detail.length > 0) {
          return detail;
        }
      } catch (err) {
        return result.length > 200 ? result.substring(0, 200) : result;
      }
    }
    return '请求失败，请检查服务器地址或网络';
  }

  static errorMessage(err: Error): string {
    if (err instanceof ApiError) {
      return err.detail;
    }
    if (err instanceof Error) {
      return err.message;
    }
    return '请求失败，请检查服务器地址或网络';
  }
}
