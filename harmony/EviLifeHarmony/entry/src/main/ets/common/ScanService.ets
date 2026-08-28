import { scanBarcode, scanCore } from '@kit.ScanKit';
import { common } from '@kit.AbilityKit';

/** 封装 HarmonyOS 扫码服务（Scan Kit，系统相机扫码）。 */
export class ScanService {
  static scan(context: common.UIAbilityContext): Promise<scanBarcode.ScanResult> {
    const options: scanBarcode.ScanOptions = {
      scanTypes: [scanCore.ScanType.QR_CODE, scanCore.ScanType.BARCODE],
      enableMultiMode: false,
      enableAlbum: true,
      enableTorch: true,
      scanFrameColor: scanCore.Color.GREEN,
      enableVibrate: true,
      enableTip: '将 EviLife 配对二维码放入框内即可自动扫描'
    };
    return scanBarcode.startScanForResult(context, options);
  }
}