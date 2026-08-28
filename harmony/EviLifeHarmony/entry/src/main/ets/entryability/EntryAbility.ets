import { UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';

export default class EntryAbility extends UIAbility {
  onCreate(): void {}
  onWindowStageCreate(windowStage: window.WindowStage): void { windowStage.loadContent('pages/Index', (err) => { if (err) hilog.error(0x0000, 'EviLife', 'load failed'); }); }
  onWindowStageDestroy(): void {}
  onForeground(): void {}
  onBackground(): void {}
}
