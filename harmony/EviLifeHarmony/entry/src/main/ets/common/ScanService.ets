import { scanBarcode, scanCore } from '@kit.ScanKit';
import { common } from '@kit.AbilityKit';

/** 封装 HarmonyOS 扫码服务（Scan Kit 系统扫码页）。 */
export class ScanService {
  static scan(context: common.UIAbilityContext): Promise<scanBarcode.ScanResult> {
    const options: scanBarcode.ScanOptions = {
      scanTypes: [scanCore.ScanType.QR_CODE, scanCore.ScanType.ONE_D_CODE],
      enableMultiMode: false,
      enableAlbum: true
    };
    // 华为扫码服务偶发无回调/立即退出：45 秒未返回则降级提示手动输入配对码。
    return Promise.race([
      scanBarcode.startScanForResult(context, options),
      new Promise<scanBarcode.ScanResult>((resolve, reject) => {
        setTimeout(() => {
          reject(new Error('扫码超时：华为扫码服务未响应，请手动输入配对码'));
        }, 45000);
      })
    ]);
  }
}
