import { HealthObservation } from './HealthSyncService';

/**
 * Health Kit 桥接层：本文件不依赖任何 HMS SDK 包，保证 SDK 未安装时工程可编译。
 * 接入 Health Kit 后，由 HealthKitService（启用 SDK 依赖后放入本目录）调用
 * registerHealthKitReader() 完成注册，HealthSyncService 即可切换到真实数据。
 */
export interface HealthKitReader {
  /** 读取今日健康数据并映射为 EviLife 观察；失败返回 null。 */
  fetchTodayObservations(): Promise<HealthObservation[] | null>;
}

let reader: HealthKitReader | null = null;

export function registerHealthKitReader(r: HealthKitReader): void {
  reader = r;
}

export function healthKitReady(): boolean {
  return reader !== null;
}

export async function fetchHealthKitObservations(): Promise<HealthObservation[] | null> {
  if (reader === null) {
    return null;
  }
  try {
    return await reader.fetchTodayObservations();
  } catch (err) {
    return null;
  }
}
