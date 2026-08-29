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
  /** 登录后服务端通过 Set-Cookie 下发的会话 Cookie（http 模块不会自动回传，需手动携带）。 */
  private sessionCookie: string = '';

  private constructor(serverAddress: string) {
    this.serverAddress = serverAddress;
    this.client = http.createHttp();
  }

  static shared(): ApiClient {
    if (ApiClient.sharedClient === null) {
      ApiClient.sharedClient = new ApiClient('http://192.168.43.5:8000');
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

  /** POST JSON 并解析 JSON 数组响应（如 observations/batch 返回记录列表）。 */
  async postJsonArray(path: string, body: Record<string, Object>): Promise<Object[]> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.POST,
      header: {
        'Content-Type': 'application/json'
      },
      extraData: JSON.stringify(body),
      connectTimeout: 15000,
      readTimeout: 60000
    };
    return await this.requestArray(this.serverAddress + path, options);
  }

  private async requestArray(url: string, options: http.HttpRequestOptions): Promise<Object[]> {
    this.attachSessionCookie(options);
    const response = await this.client.request(url, options);
    this.captureSessionCookie(response.header);
    if (response.responseCode >= 200 && response.responseCode < 300) {
      return ApiClient.toArray(response.result);
    }
    throw new ApiError(response.responseCode, ApiClient.errorDetail(response.result));
  }

  static toArray(result: Object | string | ArrayBuffer): Object[] {
    if (typeof result === 'string') {
      try {
        const parsed = JSON.parse(result) as Object[];
        if (Array.isArray(parsed)) {
          return parsed;
        }
      } catch (err) {
        // 非 JSON 响应，按空数组处理
      }
    }
    return [];
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

  /** GET JSON 对象响应（如 /today、/account/summary）。 */
  async getJson(path: string): Promise<Record<string, Object>> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.GET,
      header: {
        'Accept': 'application/json'
      },
      connectTimeout: 15000,
      readTimeout: 30000
    };
    return await this.request(this.serverAddress + path, options);
  }

  /** GET JSON 数组响应（如 /observations、/conversations、/reports）。 */
  async getJsonArray(path: string): Promise<Object[]> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.GET,
      header: {
        'Accept': 'application/json'
      },
      connectTimeout: 15000,
      readTimeout: 30000
    };
    return await this.requestArray(this.serverAddress + path, options);
  }

  /** DELETE 请求（204/JSON 均可）。 */
  async deleteJson(path: string): Promise<Record<string, Object>> {
    const options: http.HttpRequestOptions = {
      method: http.RequestMethod.DELETE,
      header: {
        'Accept': 'application/json'
      },
      connectTimeout: 15000,
      readTimeout: 30000
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
    this.attachSessionCookie(options);
    const response = await this.client.request(url, options);
    this.captureSessionCookie(response.header);
    if (response.responseCode >= 200 && response.responseCode < 300) {
      return ApiClient.toRecord(response.result);
    }
    throw new ApiError(response.responseCode, ApiClient.errorDetail(response.result));
  }

  private attachSessionCookie(options: http.HttpRequestOptions): void {
    if (this.sessionCookie.length === 0) {
      return;
    }
    const header = options.header as Record<string, Object>;
    header['Cookie'] = this.sessionCookie;
  }

  private captureSessionCookie(header: Object): void {
    const map = header as Record<string, Object>;
    const raw = map['set-cookie'] ?? map['Set-Cookie'];
    if (raw === null || raw === undefined) {
      return;
    }
    const values: string[] = [];
    if (typeof raw === 'string') {
      values.push(raw);
    } else if (Array.isArray(raw)) {
      const items = raw as Object[];
      for (let i = 0; i < items.length; i++) {
        const value = items[i];
        if (typeof value === 'string') {
          values.push(value);
        }
      }
    }
    for (let i = 0; i < values.length; i++) {
      const pair = values[i].split(';')[0].trim();
      if (pair.startsWith('evilife_session=')) {
        this.sessionCookie = pair;
        return;
      }
    }
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
        if (detail instanceof Array && detail.length > 0) {
          // FastAPI 422 校验错误：[{loc, msg, type}, ...]，取第一条 msg
          const first = detail[0] as Record<string, Object>;
          const message = first['msg'];
          if (typeof message === 'string' && message.length > 0) {
            return message;
          }
          return '请求参数校验失败，请检查输入';
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
