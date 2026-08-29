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
    return scanBarcode.startScanForResult(context, options);
  }
}
