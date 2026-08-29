import { ApiClient } from './ApiClient';

/** 网页端「今日记录 / 健康档案 / 历史 / 报告」接口的鸿蒙端封装。 */
export class LifestyleService {
  /** GET /api/v1/today?date=YYYY-MM-DD（含 fasts / meals / observations）。 */
  static async today(dateStr: string): Promise<Record<string, Object>> {
    return await ApiClient.shared().getJson('/api/v1/today?date=' + dateStr);
  }

  /** POST /api/v1/fasts/start：开始断食。 */
  static async startFast(goalHours: number): Promise<Record<string, Object>> {
    const body: Record<string, Object> = { 'goal_hours': goalHours };
    return await ApiClient.shared().postJson('/api/v1/fasts/start', body);
  }

  /** POST /api/v1/fasts/{fast_id}/end：结束断食。 */
  static async endFast(fastId: string): Promise<Record<string, Object>> {
    return await ApiClient.shared().postJson('/api/v1/fasts/' + fastId + '/end', {});
  }

  /** GET /api/v1/observations?limit=N：健康观察列表。 */
  static async observations(limit: number): Promise<Object[]> {
    return await ApiClient.shared().getJsonArray('/api/v1/observations?limit=' + limit.toString());
  }

  /** DELETE /api/v1/observations/{id}：删除一条健康观察。 */
  static async deleteObservation(id: string): Promise<void> {
    await ApiClient.shared().deleteJson('/api/v1/observations/' + id);
  }

  /** GET /api/v1/conversations：会话历史列表。 */
  static async conversations(): Promise<Object[]> {
    return await ApiClient.shared().getJsonArray('/api/v1/conversations');
  }

  /** GET /api/v1/reports?limit=N：医学报告分析列表。 */
  static async reports(limit: number): Promise<Object[]> {
    return await ApiClient.shared().getJsonArray('/api/v1/reports?limit=' + limit.toString());
  }

  /** GET /api/v1/account/summary：账号摘要。 */
  static async accountSummary(): Promise<Record<string, Object>> {
    return await ApiClient.shared().getJson('/api/v1/account/summary');
  }
}
