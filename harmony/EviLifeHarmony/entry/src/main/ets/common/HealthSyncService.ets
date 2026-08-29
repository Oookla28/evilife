import { ApiClient } from './ApiClient';

/** 单个健康观测：与后端 ConnectorObservation/ ObservationCreate 契约对齐。 */
export class HealthObservation {
  externalId: string;
  kind: string;
  value: number;
  note: string;
  observedAt: string;

  constructor(externalId: string, kind: string, value: number, note: string, observedAt: string) {
    this.externalId = externalId;
    this.kind = kind;
    this.value = value;
    this.note = note;
    this.observedAt = observedAt;
  }

  toPayload(): Record<string, Object> {
    const observation: Record<string, Object> = {
      'kind': this.kind,
      'value': this.value,
      'source': 'device',
      'connector_id': HealthSyncService.CONNECTOR_ID
    };
    if (this.note.length > 0) {
      observation['note'] = this.note;
    }
    if (this.observedAt.length > 0) {
      observation['observed_at'] = this.observedAt;
    }
    return {
      'external_id': this.externalId,
      'observation': observation
    };
  }
}

export class SyncReport {
  accepted: number;
  skipped: number;
  message: string;

  constructor(accepted: number, skipped: number, message: string) {
    this.accepted = accepted;
    this.skipped = skipped;
    this.message = message;
  }
}

/** 健康数据同步：设备配对（6 位码 claim）与网页健康配对（pairing_url 上传）协议。 */
export class HealthSyncService {
  static readonly CONNECTOR_ID: string = 'huawei_health_kit';

  /** 设备配对：6 位配对码 → claim，服务端签发该网页账号的会话 Cookie。返回账号邮箱。 */
  static async claimDevicePairing(code: string): Promise<string> {
    const body: Record<string, Object> = {
      'code': code,
      'mode': 'login'
    };
    const raw = await ApiClient.shared().postJson('/api/v1/device-pairing/claim', body);
    const user = raw['user'];
    if (user instanceof Object && !(user instanceof Array)) {
      const email = (user as Record<string, Object>)['email'];
      if (typeof email === 'string' && email.length > 0) {
        return email;
      }
    }
    const mode = raw['mode'];
    return typeof mode === 'string' ? mode : '已绑定';
  }

  /** 团队协议：扫码得到 pairing_url + token，把健康观测直接上传完成配对。 */
  static async completePairing(pairingURL: string, token: string, observations: HealthObservation[]): Promise<SyncReport> {
    if (observations.length === 0) {
      return new SyncReport(0, 0, '没有可上传的健康数据，请先完成 Health Kit 配置后重试');
    }
    const payloads: Record<string, Object>[] = [];
    for (let i = 0; i < observations.length; i++) {
      payloads.push(observations[i].toPayload());
    }
    const body: Record<string, Object> = {
      'token': token,
      'consent_receipt': 'huawei-healthkit-' + Date.now().toString(),
      'observations': payloads
    };
    const raw = await ApiClient.shared().postAbsoluteJson(pairingURL, body);
    return HealthSyncService.parseReport(raw);
  }

  private static parseReport(raw: Record<string, Object>): SyncReport {
    const accepted = raw['accepted'];
    const skipped = raw['skipped'];
    const acceptedCount = typeof accepted === 'number' ? accepted : 0;
    const skippedCount = typeof skipped === 'number' ? skipped : 0;
    return new SyncReport(
      acceptedCount,
      skippedCount,
      '同步完成：接受 ' + acceptedCount.toString() + ' 条，跳过 ' + skippedCount.toString() + ' 条'
    );
  }

  /**
   * 华为 Health Kit（运动健康服务）接入说明 —— 当前为占位实现，避免未安装 SDK 时编译失败。
   * 完整接入步骤与可用代码示例见 harmony/EviLifeHarmony/README.md「华为 Health Kit 接入」。
   */
  static healthKitStatus(): string {
    return 'Health Kit 待配置：需在 AppGallery Connect 开通服务、安装 @hms.health.healthService 依赖并完成签名，详见 harmony/EviLifeHarmony/README.md';
  }
}
